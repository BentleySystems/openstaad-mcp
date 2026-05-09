"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

MCP server definition — tools, lifespan, and ASGI app factory.

Exposes MCP tools:
- ``openstaad_discover_api``  — lists available skills and usage guidance
- ``openstaad_read_skills``   — returns requested skill content
- ``openstaad_list_instances`` — lists running STAAD.Pro instances
- ``openstaad_get_status``    — reports connection health
- ``openstaad_execute_code``      — runs code with auto-detected timeout/mode (overridable)
- ``openstaad_get_job_result``    — long-polls a running job or collects its result when done
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import logging
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal

from fastmcp import Context, FastMCP
from fastmcp.server.lifespan import lifespan
from mcp.types import ToolAnnotations

from openstaad_mcp.connection import InstanceRegistry, StaadInstance, connect_and_run
from openstaad_mcp.sandbox.executor import Executor
from openstaad_mcp.skills import SkillsManager
from openstaad_mcp.version import check_version_warning

logger = logging.getLogger(__name__)


# ── Background job store ──────────────────────────────────────────


@dataclass
class _Job:
    """In-flight or completed background execution."""

    future: asyncio.Future[dict[str, Any]]
    created: float
    progress_message: str = ""
    last_progress_time: float = 0.0
    task: asyncio.Task[None] | None = None


class _JobStore:
    """Minimal in-memory store for background code executions.

    Jobs are evicted after *ttl_seconds* (default 2 h).
    """

    def __init__(self, ttl_seconds: float = 7200.0) -> None:
        self._jobs: dict[str, _Job] = {}
        self._ttl = ttl_seconds

    def create(self, future: asyncio.Future[dict[str, Any]]) -> str:
        self._evict()
        job_id = uuid.uuid4().hex[:12]
        now = time.monotonic()
        self._jobs[job_id] = _Job(future=future, created=now, last_progress_time=now)
        return job_id

    def get(self, job_id: str) -> _Job | None:
        self._evict()
        return self._jobs.get(job_id)

    def pop(self, job_id: str) -> _Job | None:
        self._evict()
        return self._jobs.pop(job_id, None)

    def _evict(self) -> None:
        now = time.monotonic()
        expired = [k for k, v in self._jobs.items() if now - v.created > self._ttl]
        for k in expired:
            job = self._jobs.pop(k)
            job.future.cancel()


# ── Adaptive polling hint ─────────────────────────────────────────


def _poll_hint(job: _Job) -> tuple[str, int]:
    """Return (strategy, next_wait_seconds) for a still-running job.

    strategy="poll"               → call get_job_result again with next_wait_seconds
    strategy="await_user_trigger" → stop autonomous polling; wait for user to ask
    """
    now = time.monotonic()
    elapsed = now - job.created
    if elapsed < 10:  # first few seconds: quick check
        return "poll", 5
    if elapsed < 120:  # < 2 min: match default cadence
        return "poll", 10
    if elapsed < 600:  # 2-10 min: slow down
        return "poll", 20
    if elapsed < 1200:  # 10-20 min: back off
        return "poll", 30
    return "await_user_trigger", 0  # > 20 min: let the user decide when to check


# ── Execution mode classifier ─────────────────────────────────────

_ANALYSIS_KWS: frozenset[str] = frozenset({"analyzemodel", "analyzeex"})
_DESIGN_KWS: frozenset[str] = frozenset(
    {
        "performdesign",
        "performsteeldesign",
        "performconcretedesign",
        "perform_design",
    }
)


def _classify_mode(code: str) -> tuple[float, Literal["sync", "async"]]:
    """Return (default_timeout, mode) based on code keywords.

    Simple heuristic — the LLM can override via explicit timeout/mode params.
    """
    lower = code.lower()
    has_loop = "for " in lower or "while " in lower

    if any(kw in lower for kw in _ANALYSIS_KWS):
        return 3600.0, "async"

    if any(kw in lower for kw in _DESIGN_KWS):
        return 3600.0, "async"

    if has_loop:
        return 600.0, "async"

    return 120.0, "sync"


# ── Tool registrations ────────────────────────────────────────────


def _register_tools(
    mcp: FastMCP, registry: InstanceRegistry, exc: Executor, skills_mgr: SkillsManager, jobs: _JobStore
) -> None:
    """Register MCP tools on *mcp*, closing over the *InstanceRegistry*."""

    def _resolve_target(instance: str | None) -> StaadInstance:
        """Return the target StaadInstance or raise ValueError."""
        instances = registry.get_active_instances()
        if not instances:
            raise ValueError("No STAAD.Pro instances found")
        if instance is None:
            if len(instances) > 1:
                aliases = [i.alias for i in instances]
                raise ValueError(f"Multiple instances running — specify one: {aliases}")
            return instances[0]
        pid = registry.resolve(instance)
        if pid is None:
            alive = [i.alias for i in instances]
            raise ValueError(f"{instance!r} is unknown. Available: {alive}")
        matches = [i for i in instances if i.pid == pid]
        if not matches:
            alive = [i.alias for i in instances]
            raise ValueError(f"{instance!r} is no longer running. Available: {alive}")
        return matches[0]

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Discover API and skills",
            readOnlyHint=True,
            idempotentHint=True,  # Same result for repeated calls
            openWorldHint=False,  # Only internal data
        )
    )
    def openstaad_discover_api() -> str:
        """Discover available API guidance and skills.

        Call this before using other openstaad-mcp tools to understand the API surface
        and see what skills are available. Then use ``openstaad_read_skills`` with one
        or more specific skill names to load full guidance.
        """
        return skills_mgr.discover_api()

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Read OpenSTAAD skills",
            readOnlyHint=True,
            idempotentHint=True,  # Same result for repeated calls
            openWorldHint=False,  # Only internal data
        )
    )
    def openstaad_read_skills(skills: list[str]) -> str:
        """Read one or more skills by name.

        Use ``openstaad_discover_api`` first to list available skills.
        Each skill provides domain-specific guidance (e.g. analysis, geometry, loads).

        Pass skill names like ``["staad-analysis"]`` or sub-paths like
        ``["staad-steel-design/assets/DESIGN_CODES"]`` to read reference files
        within a skill.
        """
        return skills_mgr.read_skills(skills)

    @mcp.tool(
        annotations=ToolAnnotations(
            title="List running STAAD.Pro instances",
            readOnlyHint=True,
            idempotentHint=False,  # Instance list can change between calls
            openWorldHint=False,  # Only internal data
        ),
        output_schema={
            "type": "object",
            "required": ["instances"],
            "properties": {
                "instances": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["alias", "pid", "file_path", "version"],
                        "properties": {
                            "alias": {"type": "string", "description": "Stable session alias, e.g. staadPro1"},
                            "pid": {"type": "integer"},
                            "file_path": {"type": "string"},
                            "version": {"type": "string"},
                            "warning": {
                                "type": "string",
                                "description": "Present only when version is below minimum supported",
                            },
                        },
                    },
                }
            },
        },
    )
    def openstaad_list_instances() -> dict[str, Any]:
        """List all running STAAD.Pro instances.

        Returns ``{"instances": [...]}`` where each entry contains alias, pid,
        file_path, and version.  Call this before ``openstaad_execute_code``
        when multiple STAAD instances may be running so you can pick the
        right one.  The ``alias`` (e.g. ``staadPro1``) is stable for the
        server session even if the model file changes.

        If a version is below the minimum supported (26.0.1), a ``warning``
        field is included with details about potential data inaccuracies.
        """
        results = [inst.asdict() for inst in registry.get_active_instances()]
        return {"instances": results}

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get STAAD.Pro instance status",
            readOnlyHint=True,
            idempotentHint=False,  # Connection state can change between calls
            openWorldHint=False,  # Only internal data
        ),
        output_schema={
            "type": "object",
            "required": ["connected"],
            "properties": {
                "connected": {"type": "boolean"},
                "staad_version": {"type": "string"},
                "model_path": {"type": ["string", "null"]},
                "alias": {"type": "string"},
                "analyzing": {"type": "boolean"},
                "executor_busy": {
                    "type": "boolean",
                    "description": "True if the executor is currently running code (new calls will be rejected)",
                },
                "warning": {"type": "string"},
                "error": {"type": "string"},
            },
        },
    )
    def openstaad_get_status(instance: str | None = None) -> dict[str, Any]:
        """Check the connection to a STAAD.Pro instance.

        Pass ``instance`` (alias from ``openstaad_list_instances``) to target a
        specific instance.  Omit it when only one instance is running.

        Returns connection state, STAAD version, model path, and whether the
        executor is currently busy (``executor_busy``).  Always call this
        before ``openstaad_execute_code`` if a previous execution may still
        be running — new calls are rejected while the executor is busy.
        """
        try:
            target = _resolve_target(instance)
        except ValueError as e:
            return {"connected": False, "executor_busy": exc.is_busy, "error": str(e)}

        def _read_status(staad: Any) -> dict[str, Any]:
            version = staad.GetApplicationVersion()
            try:
                analyzing = staad.IsAnalyzing()
            except Exception:
                analyzing = False
            try:
                model_path = staad.GetSTAADFile()
            except Exception:
                model_path = None
            return {
                "connected": True,
                "staad_version": version,
                "model_path": model_path,
                "alias": target.alias,
                "analyzing": analyzing,
                "executor_busy": exc.is_busy,
                "warning": check_version_warning(version),
            }

        try:
            return connect_and_run(_read_status, target.file_path, timeout=10.0)
        except TimeoutError:
            return {"connected": False, "executor_busy": exc.is_busy, "error": "Connection timed out"}
        except Exception as e:
            return {"connected": False, "executor_busy": exc.is_busy, "error": str(e)}

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Execute Python code",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
        output_schema={
            "type": "object",
            "description": "sync mode: execution result. async mode: job handle ({job_id, message}).",
            "properties": {
                "job_id": {"type": "string", "description": "async mode: pass to openstaad_get_job_result"},
                "message": {"type": "string", "description": "async mode: polling instructions"},
                "success": {"type": "boolean", "description": "sync mode"},
                "result": {"description": "sync mode: return value of the executed code"},
                "stdout": {"type": "string"},
                "stderr": {"type": "string"},
                "error": {"type": ["string", "null"]},
                "duration_seconds": {"type": "number"},
                "result_size_bytes": {"type": "integer"},
                "warning": {"type": "string"},
            },
        },
    )
    async def openstaad_execute_code(
        code: str,
        instance: str | None = None,
        timeout: float | None = None,
        mode: Literal["sync", "async"] | None = None,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """Execute Python code against the OpenSTAAD API.

        Imports are blocked; sandbox provides ``staad``, ``json``, ``math``,
        ``progress``.

        Timeout and execution mode are auto-detected from code keywords but
        can be overridden:

        - ``timeout`` — max seconds before the execution is killed (default:
          120 for simple code, 600 for loops, 3600 for analysis/design).
        - ``mode="sync"`` — block and return result directly.
        - ``mode="async"`` — return ``job_id`` immediately; poll with
          ``openstaad_get_job_result``.

        **Async polling:** call ``openstaad_get_job_result(job_id, wait_seconds=N)``.
        Check ``strategy``: ``"poll"`` → call again; ``"await_user_trigger"`` → stop, tell user.
        """
        try:
            target = _resolve_target(instance)
        except ValueError as e:
            return {"success": False, "error": str(e)}

        loop = asyncio.get_running_loop()
        start = time.monotonic()

        # Auto-detect timeout and mode from code keywords; LLM can override both
        _default_timeout, _auto_mode = _classify_mode(code)
        _timeout = timeout if timeout is not None else _default_timeout
        effective_mode: Literal["sync", "async"] = mode if mode is not None else _auto_mode

        # In async mode, progress updates the job object.
        # In sync mode, progress is forwarded to the MCP client via log notifications.
        # NOTE: Since _run executes in run_in_executor, the event loop IS free to
        # process the scheduled coroutine — run_in_executor yields the event loop
        # while the thread does blocking work.
        job_ref: _Job | None = None

        def _progress_fn(message: str) -> None:
            if job_ref is not None:
                job_ref.progress_message = message
                job_ref.last_progress_time = time.monotonic()
            elif ctx is not None:
                asyncio.run_coroutine_threadsafe(
                    ctx.log(message, level="info"),
                    loop,
                )

        def _run(staad: Any) -> dict[str, Any]:
            return exc.execute(code, staad, progress_fn=_progress_fn, lock_timeout=_timeout).to_dict()

        # ── Sync mode: block and return result directly ──────────────
        if effective_mode == "sync":
            try:
                result = await loop.run_in_executor(
                    None, functools.partial(connect_and_run, _run, target.file_path, _timeout)
                )
            except TimeoutError:
                return {
                    "success": False,
                    "result": None,
                    "stdout": "",
                    "stderr": "",
                    "error": (
                        f"Code execution timed out after {_timeout:.0f}s. "
                        "Retry with mode='async' to run in the background."
                    ),
                    "duration_seconds": round(time.monotonic() - start, 1),
                    "result_size_bytes": 0,
                }
            except Exception as e:
                return {
                    "success": False,
                    "result": None,
                    "stdout": "",
                    "stderr": "",
                    "error": str(e),
                    "duration_seconds": 0.0,
                    "result_size_bytes": 0,
                }
            result["warning"] = target.warning
            return result

        # ── Async mode: start background job, return job_id ──────────
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        job_id = jobs.create(future)
        job_ref = jobs.get(job_id)

        async def _bg_task() -> None:
            try:
                result = await loop.run_in_executor(
                    None, functools.partial(connect_and_run, _run, target.file_path, _timeout)
                )
                result["warning"] = target.warning
                if not future.done():
                    future.set_result(result)
            except TimeoutError:
                if not future.done():
                    future.set_result(
                        {
                            "success": False,
                            "result": None,
                            "stdout": "",
                            "stderr": "",
                            "error": (
                                f"Code execution timed out after {_timeout:.0f}s. "
                                "The operation took longer than expected — consider splitting "
                                "it into smaller chunks."
                            ),
                            "duration_seconds": _timeout,
                            "result_size_bytes": 0,
                        }
                    )
            except Exception as e:
                if not future.done():
                    future.set_result(
                        {
                            "success": False,
                            "result": None,
                            "stdout": "",
                            "stderr": "",
                            "error": str(e),
                            "duration_seconds": 0.0,
                            "result_size_bytes": 0,
                        }
                    )

        if job_ref is not None:
            job_ref.task = asyncio.create_task(_bg_task())

        return {
            "job_id": job_id,
            "message": (
                f"Job started (job_id={job_id!r}). "
                "Call openstaad_get_job_result(job_id, wait_seconds=10) — the server holds "
                "the response until done or 10s elapses. Check the 'strategy' field: "
                "'poll' → call again with wait_seconds=next_wait_seconds; "
                "'await_user_trigger' → stop polling, tell the user the job is still running "
                "(include the job_id), and wait for their request."
            ),
        }

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Poll job — ALWAYS show message to user",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=False,  # Job state can change between calls
            openWorldHint=False,
        ),
        output_schema={
            "type": "object",
            "required": ["status"],
            "properties": {
                "status": {"type": "string", "enum": ["running", "completed", "failed", "unknown"]},
                "message": {"type": "string", "description": "Always display this to the user"},
                "progress": {"type": "string", "description": "Last progress message (running only)"},
                "elapsed_seconds": {"type": "number"},
                "strategy": {
                    "type": "string",
                    "enum": ["poll", "await_user_trigger"],
                    "description": (
                        "poll: call again with wait_seconds=next_wait_seconds; "
                        "await_user_trigger: stop polling, tell user job is still running "
                        "(include job_id), wait for their request"
                    ),
                },
                "next_wait_seconds": {
                    "type": "integer",
                    "description": "Pass as wait_seconds on the next call when strategy is 'poll'",
                },
                "success": {"type": "boolean"},
                "result": {"description": "Return value of the executed code"},
                "stdout": {"type": "string"},
                "stderr": {"type": "string"},
                "error": {"type": ["string", "null"]},
                "duration_seconds": {"type": "number"},
                "result_size_bytes": {"type": "integer"},
                "warning": {"type": "string"},
            },
        },
    )
    async def openstaad_get_job_result(job_id: str, wait_seconds: float = 10.0) -> dict[str, Any]:
        """IMPORTANT: Always display the ``message`` field to the user — it is the only way they see progress.

        Poll a running job or collect its result when done. Pass ``wait_seconds``
        (default 10, max 55) — the server holds the response until the job finishes
        or the timeout elapses, so each call covers a block of time rather than a
        single instant. Pass ``wait_seconds=0`` to return immediately without waiting
        (useful for a non-blocking status check).

        When ``status="running"``, check the ``strategy`` field:

        - ``"poll"`` — display ``message`` to the user, then call again immediately
          with ``wait_seconds=next_wait_seconds``.
        - ``"await_user_trigger"`` — display ``message`` to the user, then stop all
          autonomous polling; wait for the user to ask for an update.

        When ``status="completed"`` or ``"failed"``, the full result payload is included
        and the job is removed from the store.
        """
        job = jobs.get(job_id)
        if job is None:
            return {
                "status": "unknown",
                "message": f"Job not found or expired: {job_id!r}. Results are kept for 2 hours.",
            }
        # Long-poll: hold until done or timeout — returns as soon as the job finishes
        if not job.future.done() and wait_seconds > 0:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(asyncio.shield(job.future), timeout=min(wait_seconds, 55.0))

        elapsed = round(time.monotonic() - job.created, 1)

        if not job.future.done():
            strategy, next_wait = _poll_hint(job)
            progress = job.progress_message
            if strategy == "await_user_trigger":
                msg = (
                    f"⏳ Still running ({elapsed:.0f}s). "
                    "Stop polling — tell the user the analysis is still in progress "
                    f"(job_id={job_id!r}) and wait for them to ask for an update."
                )
            else:
                msg = f"⏳ Running ({elapsed:.0f}s): {progress}" if progress else f"⏳ Running ({elapsed:.0f}s)..."
            return {
                "status": "running",
                "message": msg,
                "progress": progress,
                "elapsed_seconds": elapsed,
                "strategy": strategy,
                "next_wait_seconds": next_wait,
            }

        # Done — pop and return full result
        jobs.pop(job_id)
        result = job.future.result()
        status = "completed" if result.get("success") else "failed"
        result["status"] = status
        result["elapsed_seconds"] = elapsed
        result["message"] = (
            f"✅ Completed in {elapsed:.0f}s" if status == "completed" else f"❌ Failed after {elapsed:.0f}s"
        )
        return result


def create_mcp_server(fastmcp_kwargs: dict | None = None) -> FastMCP:
    """Create an MCP server instance with tools registered"""
    fastmcp_kwargs = fastmcp_kwargs or {}

    @lifespan
    async def mcp_lifespan(server: Any) -> AsyncIterator[None]:
        registry = InstanceRegistry()
        exc = Executor()
        skills_mgr = SkillsManager()
        job_store = _JobStore()
        _register_tools(server, registry, exc, skills_mgr, job_store)
        logger.info("OpenSTAAD MCP server started")
        yield
        logger.info("OpenSTAAD MCP server shut down")

    mcp = FastMCP(
        "OpenSTAAD MCP",
        instructions=(
            "This MCP server bridges AI agents to Bentley STAAD.Pro via the "
            "OpenSTAAD COM API. Use `openstaad_discover_api` first to list available "
            "skills and guidance, then call `openstaad_read_skills` with skill names "
            "to load detailed instructions. Use `openstaad_list_instances` to see "
            "running STAAD instances. Use `openstaad_execute_code` to run Python code. "
            "Use `openstaad_get_status` to check connection health. "
            "When a `warning` field appears in any tool response, report it to the user.\n\n"
            "EXECUTION MODES: Timeout and mode are auto-detected from code keywords "
            "(120s sync for simple code, 600s async for loops, 3600s async for analysis/design). "
            "Override with `timeout=` for precise control when you know the expected duration "
            "(e.g. `timeout=elements*0.005` for large loops at ~3ms per COM call). "
            "Override with `mode='async'` to force background execution. "
            "If the response has a job_id key, the job is running in the background.\n\n"
            "ASYNC POLLING: Call `openstaad_get_job_result(job_id, wait_seconds=N)` — the "
            "server holds the response until the job finishes or N seconds elapse (default 10, "
            "max 55). Always display the `message` field to the user. Check `strategy`: "
            "'poll' → call again immediately with wait_seconds=next_wait_seconds; "
            "'await_user_trigger' → stop all autonomous polling, tell the user the job is "
            "still running (include the job_id), and wait for them to ask for an update."
        ),
        lifespan=mcp_lifespan,
        **fastmcp_kwargs,
    )
    return mcp
