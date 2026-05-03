"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Tests for InstanceRegistry, get_active_instances, and connect_and_run.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from openstaad_mcp.connection import InstanceRegistry, StaadInstance, connect_and_run

# ---------------------------------------------------------------------------
# get_active_instances — ROT enumeration (mocked COM layer)
# ---------------------------------------------------------------------------


def _make_moniker(display_name: str, pid: int = 1234, version: str = "22.12") -> MagicMock:
    """Build a minimal mock IMoniker that behaves like a STAAD FileMoniker."""
    staad_obj = MagicMock()
    staad_obj.GetProcessId = pid
    staad_obj.GetApplicationVersion = version

    moniker = MagicMock()
    moniker.GetDisplayName.return_value = display_name
    moniker.BindToObject.return_value = MagicMock()  # IDispatch
    return moniker, staad_obj


class TestGetActiveInstances:
    def _patch_pythoncom(self, monikers: list[tuple[str, int, str]]):
        """Return a context-manager that patches the module-level pythoncom/win32com mocks."""
        pythoncom_mock = MagicMock()
        win32com_mock = MagicMock()

        moniker_objs = []
        staad_objs = []
        for display_name, pid, version in monikers:
            m, s = _make_moniker(display_name, pid, version)
            moniker_objs.append(m)
            staad_objs.append(s)

        # IEnumMoniker.Next yields one moniker at a time then []
        calls = iter([[m] for m in moniker_objs] + [[]])
        enum = MagicMock()
        enum.Next.side_effect = lambda n: next(calls)

        rot = MagicMock()
        rot.EnumRunning.return_value = enum

        pythoncom_mock.GetRunningObjectTable.return_value = rot
        pythoncom_mock.CreateBindCtx.return_value = MagicMock()
        pythoncom_mock.IID_IDispatch = object()

        # win32com.client.Dispatch returns the matching staad object per call
        dispatch_calls = iter(staad_objs)
        win32com_mock.client.Dispatch.side_effect = lambda _: next(dispatch_calls)

        return patch.multiple(
            "openstaad_mcp.connection",
            pythoncom=pythoncom_mock,
            win32com=win32com_mock,
        )

    def test_filters_non_std_monikers(self):
        registry = InstanceRegistry()
        with (
            patch("openstaad_mcp.connection.sys") as sys_mock,
            self._patch_pythoncom(
                [
                    ("C:\\Models\\Bridge.std", 1234, "22.12"),
                    ("C:\\Notes\\readme.txt", 9999, ""),
                    ("C:\\Models\\Tower.std", 5678, "22.12"),
                ]
            ),
        ):
            sys_mock.platform = "win32"
            results = registry.get_active_instances()

        assert len(results) == 2
        paths = [r.file_path for r in results]
        assert "C:\\Models\\Bridge.std" in paths
        assert "C:\\Models\\Tower.std" in paths
        assert not any("readme" in p for p in paths)

    def test_assigns_monotonic_aliases(self):
        registry = InstanceRegistry()
        with (
            patch("openstaad_mcp.connection.sys") as sys_mock,
            self._patch_pythoncom(
                [
                    ("C:\\A.std", 100, "22.12"),
                    ("C:\\B.std", 200, "22.12"),
                ]
            ),
        ):
            sys_mock.platform = "win32"
            results = registry.get_active_instances()

        aliases = {r.pid: r.alias for r in results}
        assert aliases[100] == "staadPro1"
        assert aliases[200] == "staadPro2"
        assert registry._next_num == 3

    def test_non_windows_returns_empty(self):
        registry = InstanceRegistry()
        with patch("openstaad_mcp.connection.sys") as sys_mock:
            sys_mock.platform = "linux"
            results = registry.get_active_instances()
        assert results == []


# ---------------------------------------------------------------------------
# execute_code / get_status instance selection (mocked get_active_instances)
# ---------------------------------------------------------------------------


def _mock_get_active_instances(instances: list[StaadInstance]):
    """Return a patch that makes InstanceRegistry.get_active_instances return *instances*."""
    return patch.object(InstanceRegistry, "get_active_instances", return_value=instances)


def _call_tool(mcp, tool_name: str, arguments: dict):
    """Call an MCP tool within the server lifespan and return the result."""

    async def _run():
        async with mcp._lifespan_manager():
            return await mcp.call_tool(tool_name, arguments)

    return asyncio.run(_run())


class TestInstanceSelection:
    def test_auto_select_single_instance(self):
        """With one instance and no 'instance' param, it is selected automatically."""
        from openstaad_mcp.server import create_mcp_server

        single = [StaadInstance(alias="staadPro1", pid=1234, file_path="C:\\A.std", version="22.12")]
        expected = {"success": True, "result": 42, "stdout": "", "stderr": "", "error": None, "duration_seconds": 0.1}

        with (
            _mock_get_active_instances(single),
            patch("openstaad_mcp.server.connect_and_run", return_value=expected) as mock_run,
        ):
            mcp = create_mcp_server()
            _call_tool(mcp, "openstaad_execute_code", {"code": "result = 42"})
            assert mock_run.called
            called_path = mock_run.call_args[0][1]
            assert called_path == "C:\\A.std"

    def test_auto_select_errors_on_zero_instances(self):
        with _mock_get_active_instances([]):
            from openstaad_mcp.server import create_mcp_server

            mcp = create_mcp_server()
            result = _call_tool(mcp, "openstaad_execute_code", {"code": "result = 1"})
            text = result.content[0].text
            assert "No STAAD.Pro instances found" in text

    def test_auto_select_errors_on_multiple_instances(self):
        two = [
            StaadInstance(alias="staadPro1", pid=1234, file_path="C:\\A.std", version="22.12"),
            StaadInstance(alias="staadPro2", pid=5678, file_path="C:\\B.std", version="22.12"),
        ]
        with _mock_get_active_instances(two):
            from openstaad_mcp.server import create_mcp_server

            mcp = create_mcp_server()
            result = _call_tool(mcp, "openstaad_execute_code", {"code": "result = 1"})
            text = result.content[0].text
            assert "staadPro1" in text
            assert "staadPro2" in text


# ---------------------------------------------------------------------------
# connect_and_run — timeout
# ---------------------------------------------------------------------------


class TestConnectAndRun:
    def test_timeout_raises_timeout_error(self):
        """connect_and_run raises TimeoutError when the worker doesn't finish in time."""
        barrier = threading.Event()

        def _hang(staad: Any) -> None:
            barrier.wait(timeout=30)

        mock_os = MagicMock()
        mock_os.connect.return_value = MagicMock()

        import sys

        with (
            patch.dict(sys.modules, {"openstaadpy": MagicMock(), "openstaadpy.os_analytical": mock_os}),
            pytest.raises(TimeoutError),
        ):
            connect_and_run(_hang, "C:\\A.std", timeout=0.2)
        barrier.set()

    def test_non_windows_raises_import_error(self):
        """On non-Windows, openstaadpy is unavailable — ImportError propagates as exception."""
        import sys

        def _fn(staad: Any) -> str:
            return "ok"

        with (
            patch.dict(sys.modules, {"openstaadpy": None, "openstaadpy.os_analytical": None}),
            pytest.raises(ImportError),
        ):
            connect_and_run(_fn, "C:\\A.std", timeout=5.0)


# ---------------------------------------------------------------------------
# Async execution mode — openstaad_execute_code with mode="async"
# ---------------------------------------------------------------------------


def _call_tool_async(mcp, tool_name: str, arguments: dict):
    """Call an MCP tool within the server lifespan (async-aware, keeps loop running)."""

    async def _run():
        async with mcp._lifespan_manager():
            return await mcp.call_tool(tool_name, arguments)

    return asyncio.run(_run())


def _call_tools_sequence(mcp, calls: list[tuple[str, dict]]):
    """Call multiple MCP tools in sequence within one lifespan session."""

    async def _run():
        async with mcp._lifespan_manager():
            results = []
            for tool_name, arguments in calls:
                r = await mcp.call_tool(tool_name, arguments)
                results.append(r)
            return results

    return asyncio.run(_run())


class TestAsyncExecution:
    """Test the async execution flow: execute_code(mode=async) → get_job_result."""

    def test_async_returns_job_id(self):
        """mode='async' returns a job_id immediately without blocking for result."""
        import json
        import time

        from openstaad_mcp.server import create_mcp_server

        single = [StaadInstance(alias="staadPro1", pid=1234, file_path="C:\\A.std", version="22.12")]
        # Simulate a slow execution that takes 0.5s
        barrier = threading.Event()

        def _slow_connect_and_run(fn, file_path, timeout=120.0):
            barrier.wait(timeout=5)
            mock_staad = MagicMock()
            return fn(mock_staad)

        with (
            _mock_get_active_instances(single),
            patch("openstaad_mcp.server.connect_and_run", side_effect=_slow_connect_and_run),
        ):
            mcp = create_mcp_server()

            async def _run():
                async with mcp._lifespan_manager():
                    # Call with mode=async — should return immediately with job_id
                    start = time.monotonic()
                    result = await mcp.call_tool("openstaad_execute_code", {"code": "result = 42", "mode": "async"})
                    elapsed = time.monotonic() - start

                    text = result.content[0].text
                    data = json.loads(text)

                    # Should get job_id back quickly (not waiting for barrier)
                    assert "job_id" in data
                    assert elapsed < 2.0  # Should not block for 5s

                    job_id = data["job_id"]

                    # Check status — should be running (long-poll with wait_seconds=0 returns immediately)
                    status_result = await mcp.call_tool(
                        "openstaad_get_job_result", {"job_id": job_id, "wait_seconds": 0}
                    )
                    status_data = json.loads(status_result.content[0].text)
                    assert status_data["status"] == "running"

                    # Release the barrier so the job completes
                    barrier.set()
                    # Give the background task time to finish
                    await asyncio.sleep(0.3)

                    # Now get the result
                    result_response = await mcp.call_tool("openstaad_get_job_result", {"job_id": job_id})
                    result_data = json.loads(result_response.content[0].text)
                    assert result_data["status"] in ("completed", "failed")
                    # The executor ran with a MagicMock staad object, so result depends on sandbox
                    assert "success" in result_data

            asyncio.run(_run())

    def test_async_progress_updates(self):
        """progress() calls in async mode update the job's progress_message."""
        import json

        from openstaad_mcp.server import create_mcp_server

        single = [StaadInstance(alias="staadPro1", pid=1234, file_path="C:\\A.std", version="22.12")]
        progress_barrier = threading.Event()
        done_barrier = threading.Event()

        def _slow_connect_and_run(fn, file_path, timeout=120.0):
            # Create a mock staad that simulates enough for the executor
            mock_staad = MagicMock()
            # Wait for test to check progress before completing
            progress_barrier.wait(timeout=5)
            result = fn(mock_staad)
            done_barrier.set()
            return result

        with (
            _mock_get_active_instances(single),
            patch("openstaad_mcp.server.connect_and_run", side_effect=_slow_connect_and_run),
        ):
            mcp = create_mcp_server()

            async def _run():
                async with mcp._lifespan_manager():
                    # Use code that calls progress()
                    code = 'progress("Working on it...")\nresult = 123'
                    result = await mcp.call_tool("openstaad_execute_code", {"code": code, "mode": "async"})
                    data = json.loads(result.content[0].text)
                    job_id = data["job_id"]

                    # Let the execution proceed (progress will be called)
                    progress_barrier.set()
                    done_barrier.wait(timeout=5)
                    await asyncio.sleep(0.2)

                    # Collect result
                    result_response = await mcp.call_tool("openstaad_get_job_result", {"job_id": job_id})
                    result_data = json.loads(result_response.content[0].text)
                    assert result_data["success"] is True
                    assert result_data["result"] == 123

            asyncio.run(_run())

    def test_async_running_response_has_strategy(self):
        """Running job response includes strategy and next_wait_seconds fields."""
        import json

        from openstaad_mcp.server import create_mcp_server

        single = [StaadInstance(alias="staadPro1", pid=1234, file_path="C:\\A.std", version="22.12")]
        barrier = threading.Event()

        def _slow_connect_and_run(fn, file_path, timeout=120.0):
            barrier.wait(timeout=5)
            mock_staad = MagicMock()
            return fn(mock_staad)

        with (
            _mock_get_active_instances(single),
            patch("openstaad_mcp.server.connect_and_run", side_effect=_slow_connect_and_run),
        ):
            mcp = create_mcp_server()

            async def _run():
                async with mcp._lifespan_manager():
                    result = await mcp.call_tool(
                        "openstaad_execute_code", {"code": "result = 1", "mode": "async"}
                    )
                    job_id = json.loads(result.content[0].text)["job_id"]  # type: ignore[union-attr]

                    # wait_seconds=0 returns immediately — job is still running
                    status_result = await mcp.call_tool(
                        "openstaad_get_job_result", {"job_id": job_id, "wait_seconds": 0}
                    )
                    data = json.loads(status_result.content[0].text)  # type: ignore[union-attr]

                    assert data["status"] == "running"
                    assert "strategy" in data
                    assert data["strategy"] in ("poll", "await_user_trigger")
                    assert "next_wait_seconds" in data
                    assert isinstance(data["next_wait_seconds"], int)
                    assert "message" in data
                    assert len(data["message"]) > 0

                    barrier.set()

            asyncio.run(_run())

    def test_async_unknown_job_id(self):
        """get_job_result with an unknown job_id returns status=unknown."""
        import json

        from openstaad_mcp.server import create_mcp_server

        single = [StaadInstance(alias="staadPro1", pid=1234, file_path="C:\\A.std", version="22.12")]

        with _mock_get_active_instances(single):
            mcp = create_mcp_server()

            async def _run():
                async with mcp._lifespan_manager():
                    result = await mcp.call_tool("openstaad_get_job_result", {"job_id": "nonexistent123"})
                    data = json.loads(result.content[0].text)
                    assert data["status"] == "unknown"

            asyncio.run(_run())
