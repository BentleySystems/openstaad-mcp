"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Code-execution orchestration layer.

Keeps the MCP tools in :mod:`openstaad_mcp.server` thin: they simply delegate
to :class:`ExecutionService`, which owns instance resolution, file I/O wiring,
sandbox dispatch and the two long-running-work strategies below.  The public
``execute_code`` ``mode`` parameter exposes three values that map onto these two
strategies: ``"native"`` and ``"poll"`` select one explicitly, while ``"auto"``
(the default) picks one per request from the signals described in :meth:`ExecutionService.execute`.

- **MCP tasks (SEP-1686)** — used when FastMCP has actually accepted *this specific*
  call as a native background task (``ctx.is_background_task``).  FastMCP runs the
  ``task="optional"`` tool in a Docket worker and the client polls via ``tasks/get``
  / ``tasks/result``.  Nothing extra is needed here; the service just runs the code
  and returns the result.
- **Server-paced polling fallback** — used whenever ``mode="poll"`` is requested
  (or ``mode="auto"`` resolves to ``"poll"``) and this call is *not* running as a
  native background task.  A client's general ``tasks`` capability declaration does
  not guarantee it task-augmented this particular request, nor that it surfaces the
  resulting notifications to the user — so capability alone must never suppress this
  fallback.  The service starts a background job, returns a ``job_id`` immediately,
  and ``get_job_result`` waits (with adaptive pacing) for completion.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import itertools
import logging
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from openstaad_mcp.connection import InstanceRegistry, StaadInstance, connect_and_run
from openstaad_mcp.file_io.helpers import (
    detect_input_output_collision,
    get_allowed_dirs,
    get_input_data,
    write_output_file,
)
from openstaad_mcp.file_io.path_validator import FileIOError

if TYPE_CHECKING:
    from collections.abc import Callable
    from concurrent.futures import Future

    from fastmcp.server.context import Context

    from openstaad_mcp.sandbox.executor import Executor

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 120.0
ExecutionMode = Literal["native", "poll", "auto"]
# native — progress via MCP protocol notifications (client must render them)
# poll   — AI polls get_job_result and writes progress to the user
# auto   — detects progress token / background-task; falls back to "poll"

# Poll pacing (see poll_hint): sleep grows linearly with elapsed time, clamped to
# [MIN, MAX] seconds; past ABANDON seconds get_job_result returns immediately.
_POLL_ABANDON_SECONDS = 1200.0  # 20 min — stop auto-pacing, let the user decide
_POLL_RAMP_SECONDS = 600.0  # reach the ceiling after 10 min
_POLL_MIN_INTERVAL = 10
_POLL_MAX_INTERVAL = 55


# ── Background job store (non-task-client fallback) ───────────────


@dataclass
class _Job:
    """In-flight or completed background execution."""

    future: asyncio.Future[dict[str, Any]]
    created: float
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    progress_message: str = ""
    task: asyncio.Task[None] | None = None


class JobStore:
    """Minimal in-memory store for background code executions.

    Jobs are evicted after *ttl_seconds* (default 2 h).
    """

    def __init__(self, ttl_seconds: float = 7200.0) -> None:
        self._jobs: dict[str, _Job] = {}
        self._delivered: dict[str, float] = {}
        self._ttl = ttl_seconds

    def create(self, future: asyncio.Future[dict[str, Any]], timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
        self._evict()
        job_id = uuid.uuid4().hex[:12]
        now = time.monotonic()
        self._jobs[job_id] = _Job(future=future, created=now, timeout=timeout)
        return job_id

    def get(self, job_id: str) -> _Job | None:
        self._evict()
        return self._jobs.get(job_id)

    def pop(self, job_id: str) -> _Job | None:
        self._evict()
        job = self._jobs.pop(job_id, None)
        if job is not None:
            self._delivered[job_id] = time.monotonic()
        return job

    def was_delivered(self, job_id: str) -> bool:
        return job_id in self._delivered

    def _evict(self) -> None:
        now = time.monotonic()
        expired = [k for k, v in self._jobs.items() if now - v.created > self._ttl]
        for k in expired:
            job = self._jobs.pop(k)
            self._delivered[k] = now
            job.future.cancel()
        # Bound the delivered-ID history so it doesn't grow forever on a long-lived server.
        stale = [k for k, delivered_at in self._delivered.items() if now - delivered_at > self._ttl]
        for k in stale:
            del self._delivered[k]


def poll_hint(job: _Job) -> int:
    """Return how many seconds ``get_job_result`` should sleep before responding.

    Returns 0 for jobs running longer than ``_POLL_ABANDON_SECONDS`` (caller returns
    immediately and tells the user to ask again manually).  Otherwise the sleep grows
    linearly with elapsed time, clamped to ``[_POLL_MIN_INTERVAL, _POLL_MAX_INTERVAL]``
    seconds to avoid burning tokens on overly frequent polls while still giving timely
    updates.
    """
    elapsed = time.monotonic() - job.created
    if elapsed > _POLL_ABANDON_SECONDS:
        return 0  # return immediately, let the user decide
    span = _POLL_MAX_INTERVAL - _POLL_MIN_INTERVAL
    interval = int(_POLL_MIN_INTERVAL + (elapsed / _POLL_RAMP_SECONDS) * span)
    return max(_POLL_MIN_INTERVAL, min(_POLL_MAX_INTERVAL, interval))


# ── Client capability detection ───────────────────────────────────


def _has_progress_token(ctx: Context | None) -> bool:
    """Return True when the client included a progressToken in this specific request.

    A progress token is a strong signal: the client is actively requesting
    ``notifications/progress`` for this call and is expected to surface them.
    Absence of a token means ``ctx.report_progress()`` is a silent no-op and
    the user will see nothing from native MCP progress notifications.
    """
    if ctx is None:
        return False
    try:
        return getattr(ctx.meta, "progressToken", None) is not None
    except Exception:
        return False


# ── Result helpers ────────────────────────────────────────────────


def _log_notify_failure(fut: Future[Any]) -> None:
    """Consume a fire-and-forget notification future so its exception isn't swallowed silently."""
    with contextlib.suppress(BaseException):
        exc = fut.exception()
        if exc is not None:
            logger.debug("progress notification failed: %s", exc)


def _error_result(message: str, duration: float = 0.0) -> dict[str, Any]:
    return {
        "success": False,
        "result": None,
        "stdout": "",
        "stderr": "",
        "error": message,
        "duration_seconds": duration,
    }


# ── Execution service ─────────────────────────────────────────────


class ExecutionService:
    """Owns instance resolution, file I/O wiring and code-execution dispatch."""

    def __init__(
        self,
        registry: InstanceRegistry,
        executor: Executor,
        args_allowed_dirs: list[Path],
        jobs: JobStore | None = None,
    ) -> None:
        self._registry = registry
        self._executor = executor
        self._args_allowed_dirs = args_allowed_dirs
        self._jobs = jobs if jobs is not None else JobStore()

    @property
    def executor_busy(self) -> bool:
        return self._executor.is_busy

    def resolve_target(self, instance: str | None) -> StaadInstance:
        """Return the target StaadInstance or raise ValueError."""
        instances = self._registry.get_active_instances()
        if not instances:
            raise ValueError("No STAAD.Pro instances found")
        if instance is None:
            if len(instances) > 1:
                aliases = [i.alias for i in instances]
                raise ValueError(f"Multiple instances running — specify one: {aliases}")
            return instances[0]
        pid = self._registry.resolve(instance)
        if pid is None:
            alive = [i.alias for i in instances]
            raise ValueError(f"{instance!r} is unknown. Available: {alive}")
        matches = [i for i in instances if i.pid == pid]
        if not matches:
            alive = [i.alias for i in instances]
            raise ValueError(f"{instance!r} is no longer running. Available: {alive}")
        return matches[0]

    async def execute(
        self,
        *,
        ctx: Context | None,
        code: str,
        instance: str | None = None,
        input_data_path: str | None = None,
        output_data_path: str | None = None,
        overwrite: bool = False,
        mode: ExecutionMode = "auto",
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Resolve target + inputs, then run *code* synchronously or as a background job."""
        try:
            target = self.resolve_target(instance)
        except ValueError as e:
            return _error_result(str(e))

        # ── File I/O resolution (request-context bound; must run before any job) ──
        allowed_dirs = await get_allowed_dirs(ctx, self._args_allowed_dirs, input_data_path, output_data_path)
        try:
            await detect_input_output_collision(input_data_path, output_data_path, allowed_dirs)
            input_data, _ = await get_input_data(input_data_path, allowed_dirs)
        except FileIOError as e:
            return _error_result(f"{e.code}: {e.message}")

        effective_timeout = timeout if timeout is not None else DEFAULT_TIMEOUT_SECONDS

        def make_blocking(progress_fn: Callable[[str], None]) -> Callable[[], dict[str, Any]]:
            return functools.partial(
                self._run_blocking,
                target=target,
                code=code,
                input_data=input_data,
                output_data_path=output_data_path,
                overwrite=overwrite,
                allowed_dirs=allowed_dirs,
                timeout=effective_timeout,
                progress_fn=progress_fn,
            )

        loop = asyncio.get_running_loop()

        # Auto-detect: use "poll" unless there is strong evidence the client will
        # surface progress natively.  Two reliable signals:
        #   1. ctx.is_background_task — FastMCP actually assigned a task_id to *this*
        #      request; the client is expected to poll tasks/get for status.
        #   2. _has_progress_token — the client included a progressToken, explicitly
        #      requesting notifications/progress for this call.
        # A client's general ``tasks`` capability alone is NOT reliable: it may not
        # have task-augmented this specific call (tool is ``task="optional"``), or it
        # may declare the capability but silently swallow the resulting notifications.
        resolved = mode
        if resolved == "auto":
            is_bg = ctx is not None and getattr(ctx, "is_background_task", False)
            resolved = "native" if is_bg or _has_progress_token(ctx) else "poll"

        use_fallback = resolved == "poll" and ctx is not None and not getattr(ctx, "is_background_task", False)

        if not use_fallback:
            return await self._run_sync(loop, ctx, make_blocking, effective_timeout)
        return self._start_job(loop, make_blocking, effective_timeout)

    def _run_blocking(
        self,
        *,
        target: StaadInstance,
        code: str,
        input_data: Any,
        output_data_path: str | None,
        overwrite: bool,
        allowed_dirs: list[Path],
        timeout: float,
        progress_fn: Callable[[str], None],
    ) -> dict[str, Any]:
        """Blocking work: connect on the COM thread, run the sandbox, write output."""

        def _run(staad: Any) -> dict[str, Any]:
            return self._executor.execute(
                code, staad, input_data=input_data, progress_fn=progress_fn, lock_timeout=timeout
            ).to_dict()

        result = connect_and_run(_run, target.file_path, timeout)

        if output_data_path is not None and result.get("success"):
            try:
                result["result"] = write_output_file(
                    output_data_path, result["result"], allowed_dirs, overwrite=overwrite
                )
            except FileIOError as e:
                return {
                    "success": False,
                    "result": None,
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "error": f"{e.code}: {e.message}",
                    "duration_seconds": result.get("duration_seconds", 0.0),
                }

        if target.warning:
            result["warning"] = target.warning
        return result

    async def _run_sync(
        self,
        loop: asyncio.AbstractEventLoop,
        ctx: Context | None,
        make_blocking: Callable[[Callable[[str], None]], Callable[[], dict[str, Any]]],
        timeout: float,
    ) -> dict[str, Any]:
        start = time.monotonic()
        blocking = make_blocking(self._sync_progress_fn(loop, ctx))
        try:
            return await loop.run_in_executor(None, blocking)
        except TimeoutError:
            return _error_result(
                f"Code execution timed out after {timeout:.0f}s. Retry with mode='poll' to run in the background.",
                round(time.monotonic() - start, 1),
            )
        except Exception as e:
            return _error_result(str(e))

    def _start_job(
        self,
        loop: asyncio.AbstractEventLoop,
        make_blocking: Callable[[Callable[[str], None]], Callable[[], dict[str, Any]]],
        timeout: float,
    ) -> dict[str, Any]:
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        job_id = self._jobs.create(future, timeout=timeout)
        job = self._jobs.get(job_id)

        def _progress_fn(message: str) -> None:
            if job is not None:
                job.progress_message = message

        blocking = make_blocking(_progress_fn)

        async def _bg_task() -> None:
            try:
                result = await loop.run_in_executor(None, blocking)
            except TimeoutError:
                result = _error_result(
                    f"Code execution timed out after {timeout:.0f}s. "
                    "The operation took longer than expected — consider splitting it into smaller chunks.",
                    timeout,
                )
            except Exception as e:
                result = _error_result(str(e))
            if not future.done():
                future.set_result(result)

        if job is not None:
            job.task = asyncio.create_task(_bg_task())

        return {
            "job_id": job_id,
            "next_action": (
                f"IMMEDIATELY call get_job_result('{job_id}') — do NOT write any text to the user first. "
                "Write the 'message' field to the user after each get_job_result response, then call it again immediately. "
                "Stop after 5 consecutive 'running' responses: tell the user the job is still in progress "
                f"(job_id='{job_id}') and wait for them to ask for an update before polling again."
            ),
        }

    @staticmethod
    def _sync_progress_fn(loop: asyncio.AbstractEventLoop, ctx: Context | None) -> Callable[[str], None]:
        """Build the ``progress()`` callback injected into the sandbox for synchronous/task execution.

        Reports on two independent MCP channels so a client renders whichever it supports:

        - ``ctx.log()`` — a logging notification (``notifications/message``).
        - ``ctx.report_progress()`` — the dedicated progress-token notification
          (``notifications/progress``) in the foreground, or — critically, when this call is
          running as a native background task (``ctx.is_background_task``) — an update to the
          task's own progress, which becomes visible to the client via ``tasks/get`` and
          ``notifications/tasks/status``. This is the one channel that reaches a client polling
          task status directly, so it must not be limited to the logging notification alone.

        Both are fire-and-forget: neither is awaited, matching the sandbox's threaded execution
        model where ``progress()`` is called synchronously from a worker thread.
        """
        step = itertools.count(1)

        def _progress_fn(message: str) -> None:
            if ctx is None:
                return
            log_fut = asyncio.run_coroutine_threadsafe(ctx.log(message, level="info"), loop)
            progress_fut = asyncio.run_coroutine_threadsafe(ctx.report_progress(next(step), message=message), loop)
            log_fut.add_done_callback(_log_notify_failure)
            progress_fut.add_done_callback(_log_notify_failure)

        return _progress_fn

    async def get_job_result(self, job_id: str) -> dict[str, Any]:
        """Wait (server-paced) for a background job and return its status or result."""
        job = self._jobs.get(job_id)
        if job is None:
            if self._jobs.was_delivered(job_id):
                return {
                    "status": "delivered",
                    "message": f"Result for {job_id!r} was already delivered. Do not poll again.",
                }
            return {
                "status": "unknown",
                "message": f"Job not found or expired: {job_id!r}. Results are kept for 2 hours.",
            }

        # Sleep to enforce pacing — wake early if the job completes.
        if not job.future.done():
            wait = poll_hint(job)
            if wait > 0:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(asyncio.shield(job.future), timeout=wait)

        elapsed = round(time.monotonic() - job.created, 1)

        if not job.future.done():
            progress = job.progress_message
            if poll_hint(job) == 0:
                msg = (
                    f"⏳ Still running ({elapsed:.0f}s). Tell the user the operation is still in progress "
                    f"(job_id={job_id!r}) and wait for them to ask for an update."
                )
            else:
                msg = f"⏳ Running ({elapsed:.0f}s): {progress}" if progress else f"⏳ Running ({elapsed:.0f}s)..."
            return {"status": "running", "message": msg, "elapsed_seconds": elapsed}

        # Done — pop and return the full result.
        self._jobs.pop(job_id)
        result = job.future.result()
        status = "completed" if result.get("success") else "failed"
        result["status"] = status
        result["elapsed_seconds"] = elapsed
        result["message"] = (
            f"✅ Completed in {elapsed:.0f}s" if status == "completed" else f"❌ Failed after {elapsed:.0f}s"
        )
        return result
