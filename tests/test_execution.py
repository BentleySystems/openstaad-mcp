"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Tests for the code-execution orchestration layer (openstaad_mcp.execution).
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from openstaad_mcp.connection import StaadInstance
from openstaad_mcp.execution import (
    DEFAULT_TIMEOUT_SECONDS,
    ExecutionService,
    JobStore,
    _error_result,
    _Job,
    poll_hint,
)


class _FakeRegistry:
    def __init__(self, instances: list[StaadInstance], resolve_map: dict[str, int] | None = None) -> None:
        self._instances = instances
        self._resolve_map = resolve_map or {}

    def get_active_instances(self) -> list[StaadInstance]:
        return self._instances

    def resolve(self, instance: str) -> int | None:
        return self._resolve_map.get(instance)


def _instance(alias: str = "staadPro1", pid: int = 1, path: str = "C:\\A.std") -> StaadInstance:
    return StaadInstance(alias=alias, pid=pid, file_path=path, version="22.12")


def _fake_ctx(*, is_background_task: bool = False, tasks: Any = None) -> SimpleNamespace:
    return SimpleNamespace(
        is_background_task=is_background_task,
        session=SimpleNamespace(client_params=SimpleNamespace(capabilities=SimpleNamespace(tasks=tasks))),
    )


def _service(instances: list[StaadInstance], resolve_map: dict[str, int] | None = None) -> ExecutionService:
    executor = MagicMock()
    executor.is_busy = False
    return ExecutionService(_FakeRegistry(instances, resolve_map), executor, [])


# ---------------------------------------------------------------------------
# poll_hint
# ---------------------------------------------------------------------------


def _job_with_age(age_seconds: float) -> _Job:
    loop = asyncio.new_event_loop()
    try:
        fut: asyncio.Future[dict[str, Any]] = loop.create_future()
    finally:
        loop.close()
    return _Job(future=fut, created=time.monotonic() - age_seconds)


class TestPollHint:
    def test_fresh_job_returns_floor(self):
        assert poll_hint(_job_with_age(0)) == 10

    def test_old_job_clamped_to_ceiling(self):
        assert poll_hint(_job_with_age(700)) == 55

    def test_very_old_job_returns_zero(self):
        assert poll_hint(_job_with_age(1300)) == 0


# ---------------------------------------------------------------------------
# JobStore
# ---------------------------------------------------------------------------


class TestJobStore:
    def test_create_get_pop_delivered(self):
        loop = asyncio.new_event_loop()
        try:
            store = JobStore()
            fut: asyncio.Future[dict[str, Any]] = loop.create_future()
            job_id = store.create(fut)
            assert len(job_id) == 12
            assert store.get(job_id) is not None
            popped = store.pop(job_id)
            assert popped is not None
            assert store.was_delivered(job_id) is True
            assert store.get(job_id) is None
        finally:
            loop.close()

    def test_pop_missing_returns_none(self):
        store = JobStore()
        assert store.pop("does-not-exist") is None

    def test_eviction_after_ttl(self):
        loop = asyncio.new_event_loop()
        try:
            store = JobStore(ttl_seconds=1.0)
            fut: asyncio.Future[dict[str, Any]] = loop.create_future()
            job_id = store.create(fut)
            store._jobs[job_id].created -= 5.0
            assert store.get(job_id) is None
            assert store.was_delivered(job_id) is True
            assert fut.cancelled() is True
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# _error_result
# ---------------------------------------------------------------------------


def test_error_result_shape():
    result = _error_result("nope", duration=1.5)
    assert result == {
        "success": False,
        "result": None,
        "stdout": "",
        "stderr": "",
        "error": "nope",
        "duration_seconds": 1.5,
    }


# ---------------------------------------------------------------------------
# ExecutionService.resolve_target
# ---------------------------------------------------------------------------


class TestResolveTarget:
    def test_no_instances(self):
        with pytest.raises(ValueError, match=r"No STAAD\.Pro instances found"):
            _service([]).resolve_target(None)

    def test_auto_select_single(self):
        inst = _instance()
        assert _service([inst]).resolve_target(None) is inst

    def test_multiple_requires_explicit(self):
        two = [_instance("staadPro1", 1), _instance("staadPro2", 2)]
        with pytest.raises(ValueError, match="Multiple instances running"):
            _service(two).resolve_target(None)

    def test_unknown_alias(self):
        with pytest.raises(ValueError, match="is unknown"):
            _service([_instance()]).resolve_target("nope")

    def test_alias_no_longer_running(self):
        svc = _service([_instance(pid=1)], resolve_map={"ghost": 999})
        with pytest.raises(ValueError, match="no longer running"):
            svc.resolve_target("ghost")

    def test_alias_resolves_to_match(self):
        inst = _instance(pid=42)
        svc = _service([inst], resolve_map={"staadPro1": 42})
        assert svc.resolve_target("staadPro1") is inst


# ---------------------------------------------------------------------------
# ExecutionService.execute — sync
# ---------------------------------------------------------------------------


class TestExecuteSync:
    async def test_success(self):
        svc = _service([_instance()])
        expected = {"success": True, "result": 42, "stdout": "", "stderr": "", "error": None, "duration_seconds": 0.1}
        with patch("openstaad_mcp.execution.connect_and_run", return_value=expected) as mock_run:
            result = await svc.execute(ctx=None, code="result = 42")
        assert result["result"] == 42
        assert mock_run.call_args[0][1] == "C:\\A.std"
        assert mock_run.call_args[0][2] == DEFAULT_TIMEOUT_SECONDS

    async def test_resolve_error(self):
        result = await _service([]).execute(ctx=None, code="result = 1")
        assert result["success"] is False
        assert "No STAAD.Pro instances found" in result["error"]

    async def test_timeout(self):
        svc = _service([_instance()])
        with patch("openstaad_mcp.execution.connect_and_run", side_effect=TimeoutError):
            result = await svc.execute(ctx=None, code="result = 1", timeout=0.5)
        assert result["success"] is False
        assert "timed out" in result["error"]

    async def test_generic_error(self):
        svc = _service([_instance()])
        with patch("openstaad_mcp.execution.connect_and_run", side_effect=RuntimeError("kaboom")):
            result = await svc.execute(ctx=None, code="result = 1")
        assert result["success"] is False
        assert "kaboom" in result["error"]

    async def test_poll_mode_without_ctx_runs_native(self):
        """Without a ctx (no MCP session), poll mode cannot start a background job
        and falls through to native synchronous execution."""
        svc = _service([_instance()])
        expected = {"success": True, "result": 1, "stdout": "", "stderr": "", "error": None, "duration_seconds": 0.0}
        with patch("openstaad_mcp.execution.connect_and_run", return_value=expected):
            result = await svc.execute(ctx=None, code="result = 1", mode="poll")
        assert "job_id" not in result
        assert result["result"] == 1

    async def test_poll_mode_not_background_task_uses_job(self):
        """poll mode with a real ctx that is not a background task returns a job_id
        so the AI can relay progress via get_job_result."""
        svc = _service([_instance()])
        ctx = _fake_ctx(is_background_task=False, tasks=object())
        expected = {"success": True, "result": 1, "stdout": "", "stderr": "", "error": None, "duration_seconds": 0.0}
        with patch("openstaad_mcp.execution.connect_and_run", return_value=expected):
            result = await svc.execute(ctx=ctx, code="result = 1", mode="poll")
        assert "job_id" in result

    async def test_poll_mode_background_task_runs_native(self):
        """When this call is genuinely running as a native MCP background task
        (a task_id was actually assigned), the outer tasks protocol already
        handles async delivery — starting our own job would just leak in the
        job store since nothing would ever poll it."""
        svc = _service([_instance()])
        ctx = _fake_ctx(is_background_task=True, tasks=object())
        expected = {"success": True, "result": 1, "stdout": "", "stderr": "", "error": None, "duration_seconds": 0.0}
        with patch("openstaad_mcp.execution.connect_and_run", return_value=expected):
            result = await svc.execute(ctx=ctx, code="result = 1", mode="poll")
        assert "job_id" not in result

    async def test_output_written(self):
        svc = _service([_instance()])
        raw = {"success": True, "result": [[1, 2]], "stdout": "", "stderr": "", "error": None, "duration_seconds": 0.0}

        async def _list_roots() -> list[Any]:
            return []

        ctx = SimpleNamespace(list_roots=_list_roots)
        with (
            patch("openstaad_mcp.execution.connect_and_run", return_value=raw),
            patch("openstaad_mcp.execution.get_allowed_dirs", return_value=[]),
            patch("openstaad_mcp.execution.write_output_file", return_value={"path": "out.csv"}) as mock_write,
        ):
            result = await svc.execute(ctx=ctx, code="result = 1", output_data_path="out.csv", mode="native")
        assert mock_write.called
        assert result["result"] == {"path": "out.csv"}


# ---------------------------------------------------------------------------
# ExecutionService.execute — poll fallback + get_job_result
# ---------------------------------------------------------------------------


class TestExecutePollFallback:
    async def test_job_lifecycle(self):
        svc = _service([_instance()])
        ctx = _fake_ctx(is_background_task=False, tasks=None)
        expected = {"success": True, "result": 7, "stdout": "", "stderr": "", "error": None, "duration_seconds": 0.0}
        with patch("openstaad_mcp.execution.connect_and_run", return_value=expected):
            started = await svc.execute(ctx=ctx, code="result = 7", mode="poll")
            job_id = started["job_id"]
            assert "job_id" in started

            for _ in range(50):
                result = await svc.get_job_result(job_id)
                if result.get("status") != "running":
                    break
                await asyncio.sleep(0.01)

        assert result["status"] == "completed"
        assert result["result"] == 7

        # Second lookup: already delivered.
        again = await svc.get_job_result(job_id)
        assert again["status"] == "delivered"
        assert "already delivered" in again["message"]

    async def test_unknown_job(self):
        result = await _service([_instance()]).get_job_result("deadbeefdead")
        assert result["status"] == "unknown"

    async def test_failed_job(self):
        svc = _service([_instance()])
        ctx = _fake_ctx(is_background_task=False, tasks=None)
        failed = {
            "success": False,
            "result": None,
            "stdout": "",
            "stderr": "",
            "error": "boom",
            "duration_seconds": 0.0,
        }
        with patch("openstaad_mcp.execution.connect_and_run", return_value=failed):
            started = await svc.execute(ctx=ctx, code="raise", mode="poll")
            for _ in range(50):
                result = await svc.get_job_result(started["job_id"])
                if result.get("status") != "running":
                    break
                await asyncio.sleep(0.01)
        assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# ExecutionService._sync_progress_fn
# ---------------------------------------------------------------------------


class TestSyncProgressFn:
    async def test_reports_on_both_log_and_progress_channels(self):
        log_calls: list[tuple[str, str]] = []
        progress_calls: list[tuple[float, str | None]] = []

        async def _log(message: str, level: str) -> None:
            log_calls.append((message, level))

        async def _report_progress(progress: float, message: str | None = None) -> None:
            progress_calls.append((progress, message))

        ctx = SimpleNamespace(log=_log, report_progress=_report_progress)
        loop = asyncio.get_running_loop()
        progress_fn = ExecutionService._sync_progress_fn(loop, ctx)

        progress_fn("step 1")
        progress_fn("step 2")
        await asyncio.sleep(0.01)

        assert log_calls == [("step 1", "info"), ("step 2", "info")]
        assert progress_calls == [(1, "step 1"), (2, "step 2")]

    async def test_noop_without_ctx(self):
        loop = asyncio.get_running_loop()
        progress_fn = ExecutionService._sync_progress_fn(loop, None)
        progress_fn("ignored")  # must not raise
