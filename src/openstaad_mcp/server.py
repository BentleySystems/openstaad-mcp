"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

MCP server definition — tools, lifespan, and ASGI app factory.

Exposes MCP tools:
- ``discover_api``      — lists available skills and usage guidance
- ``read_skills``       — returns requested skill content
- ``list_instances``    — lists running STAAD.Pro instances
- ``get_status``        — reports connection health
- ``execute_code``      — runs code with auto-detected timeout/mode (overridable)
- ``get_job_result``    — returns current status of a background job or its result when done
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
    timeout: float = 600.0
    progress_message: str = ""
    last_progress_time: float = 0.0
    task: asyncio.Task[None] | None = None


class _JobStore:
    """Minimal in-memory store for background code executions.

    Jobs are evicted after *ttl_seconds* (default 2 h).
    """

    def __init__(self, ttl_seconds: float = 7200.0) -> None:
        self._jobs: dict[str, _Job] = {}
        self._delivered: set[str] = set()
        self._ttl = ttl_seconds

    def create(self, future: asyncio.Future[dict[str, Any]], timeout: float = 600.0) -> str:
        self._evict()
        job_id = uuid.uuid4().hex[:12]
        now = time.monotonic()
        self._jobs[job_id] = _Job(
            future=future,
            created=now,
            timeout=timeout,
            last_progress_time=now,
        )
        return job_id

    def get(self, job_id: str) -> _Job | None:
        self._evict()
        return self._jobs.get(job_id)

    def pop(self, job_id: str) -> _Job | None:
        self._evict()
        job = self._jobs.pop(job_id, None)
        if job is not None:
            self._delivered.add(job_id)
        return job

    def was_delivered(self, job_id: str) -> bool:
        return job_id in self._delivered

    def _evict(self) -> None:
        now = time.monotonic()
        expired = [k for k, v in self._jobs.items() if now - v.created > self._ttl]
        for k in expired:
            job = self._jobs.pop(k)
            self._delivered.add(k)
            job.future.cancel()


# ── Adaptive wait interval ────────────────────────────────────────


def _poll_hint(job: _Job) -> int:
    """Return how many seconds ``get_job_result`` should sleep before responding.

    Returns 0 for jobs running longer than 20 min (caller returns
    immediately and tells the user to ask again manually).

    Sleep grows linearly with elapsed time, clamped to [10, 55] seconds to
    avoid burning tokens on overly frequent polls while still giving timely
    updates.
    """
    now = time.monotonic()
    elapsed = now - job.created

    if elapsed > 1200:
        return 0  # > 20 min: return immediately, let user decide

    # Linear ramp: 10 s at start → 55 s after 10 min (600 s elapsed)
    interval = int(10 + (elapsed / 600) * 45)
    return max(10, min(55, interval))


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
    def discover_api() -> str:
        """Discover available API guidance and skills.

        Call this before using other openstaad-mcp tools to understand the API surface
        and see what skills are available. Then use ``read_skills`` with one or more
        specific skill names to load full guidance.
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
    def read_skills(skills: list[str]) -> str:
        """Read one or more skills by name.

        Use ``discover_api`` first to list available skills.
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
            idempotentHint=False,
            openWorldHint=False,  # Only internal data
        )
    )
    def list_instances() -> list[dict[str, Any]]:
        """List all running STAAD.Pro instances.

        Returns a list of instances with their alias, process ID, currently
        open file path, and STAAD version.  Call this before ``execute_code``
        when multiple STAAD instances may be running so you can pick the
        right one.  The ``alias`` (e.g. ``staadPro1``) is stable for the
        server session even if the model file changes.

        If a version is below the minimum supported (26.0.1), a ``warning``
        field is included with details about potential data inaccuracies.
        """
        results = []
        for inst in registry.get_active_instances():
            results.append(inst.asdict())
        return results

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get STAAD.Pro instance status",
            readOnlyHint=True,
            idempotentHint=False,
            openWorldHint=False,  # Only internal data
        )
    )
    def get_status(instance: str | None = None) -> dict[str, Any]:
        """Check the connection to a STAAD.Pro instance.

        Pass ``instance`` (alias from ``list_instances``) to target a
        specific instance.  Omit it when only one instance is running.

        Returns connection state, STAAD version, model path, and whether the
        executor is currently busy (``executor_busy``).  Always call this
        before ``execute_code`` if a previous execution may still
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
            destructiveHint=True,  # Can modify the STAAD model
            idempotentHint=False,  # Each run may change state
            openWorldHint=False,  # Only internal data
        ),
        output_schema={
            "type": "object",
            "description": "sync mode: execution result. async mode: job handle ({job_id, message}).",
            "properties": {
                "job_id": {"type": "string", "description": "async mode: pass to get_job_result"},
                "message": {"type": "string", "description": "async mode: polling instructions"},
                "success": {"type": "boolean", "description": "sync mode"},
                "result": {"description": "sync mode: return value of the executed code"},
                "stdout": {"type": "string"},
                "stderr": {"type": "string"},
                "error": {"type": ["string", "null"]},
                "duration_seconds": {"type": "number"},
            },
        },
    )
    async def execute_code(
        code: str,
        instance: str | None = None,
        timeout: float | None = None,
        mode: Literal["sync", "async"] | None = None,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """Execute Python code against the OpenSTAAD API.

        Imports are blocked; sandbox provides ``staad``, ``json``, ``math``,
        ``progress``.

        **IMPORTANT — progress reporting:** call ``progress(f"Processing {i}/{total}")``
        inside any loop iterating more than ~20 elements, and once before any
        long single operation (analysis, design).  Without ``progress()`` calls
        the user sees no feedback during execution.

        Timeout and execution mode are auto-detected from code keywords but
        can be overridden:

        - ``timeout`` — max seconds before the execution is killed (default:
          120 for simple code, 600 for loops, 3600 for analysis/design).
        - ``mode="sync"`` — block and return result directly.
        - ``mode="async"`` — return ``job_id`` immediately; poll with
          ``get_job_result``.

        **Async polling:** call ``get_job_result(job_id)``, write ``message``
        to the user each time. The server paces calls internally — call again
        immediately after each response.
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
                }
            except Exception as e:
                return {
                    "success": False,
                    "result": None,
                    "stdout": "",
                    "stderr": "",
                    "error": str(e),
                    "duration_seconds": 0.0,
                }
            return result

        # ── Async mode: start background job, return job_id ──────────
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        job_id = jobs.create(future, timeout=_timeout)
        job_ref = jobs.get(job_id)

        async def _bg_task() -> None:
            try:
                result = await loop.run_in_executor(
                    None, functools.partial(connect_and_run, _run, target.file_path, _timeout)
                )
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
                        }
                    )

        if job_ref is not None:
            job_ref.task = asyncio.create_task(_bg_task())

        return {
            "job_id": job_id,
            "message": (
                f"Job started (job_id={job_id!r}). "
                "Call get_job_result(job_id) to check progress. "
                "Write the 'message' field to the user each time."
            ),
        }

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Wait for job result — ALWAYS show message to user",
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
                "message": {"type": "string", "description": "ALWAYS write this to user in your text response"},
                "elapsed_seconds": {"type": "number"},
                "success": {"type": "boolean"},
                "result": {"description": "Return value of the executed code"},
                "stdout": {"type": "string"},
                "stderr": {"type": "string"},
                "error": {"type": ["string", "null"]},
                "duration_seconds": {"type": "number"},
            },
        },
    )
    async def get_job_result(job_id: str) -> dict[str, Any]:
        """IMPORTANT: write the ``message`` field to the user in your text response — it is the ONLY way they see progress.

        Waits internally for the job to finish (the server controls pacing).
        When the job is still running after the wait, returns
        ``status="running"`` with a progress message — call again immediately.

        When ``status="completed"`` or ``"failed"``, the full result payload
        is included and the job is removed from the store.
        """
        job = jobs.get(job_id)
        if job is None:
            if jobs.was_delivered(job_id):
                return {
                    "status": "completed",
                    "message": f"Result for {job_id!r} was already delivered. Do not poll again.",
                }
            return {
                "status": "unknown",
                "message": f"Job not found or expired: {job_id!r}. Results are kept for 2 hours.",
            }

        # Sleep to enforce pacing — wake early if job completes
        if not job.future.done():
            wait = _poll_hint(job)
            if wait > 0:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(asyncio.shield(job.future), timeout=wait)

        elapsed = round(time.monotonic() - job.created, 1)

        if not job.future.done():
            progress = job.progress_message
            if _poll_hint(job) == 0:
                msg = (
                    f"⏳ Still running ({elapsed:.0f}s). "
                    "Tell the user the analysis is still in progress "
                    f"(job_id={job_id!r}) and wait for them to ask for an update."
                )
            else:
                msg = f"⏳ Running ({elapsed:.0f}s): {progress}" if progress else f"⏳ Running ({elapsed:.0f}s)..."
            return {
                "status": "running",
                "message": msg,
                "elapsed_seconds": elapsed,
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
            "OpenSTAAD COM API. Use `discover_api` first to list available skills "
            "and guidance, then call `read_skills` with skill names to load detailed "
            "instructions. Use `list_instances` to see running STAAD instances, "
            "`execute_code` to run code against a live STAAD.Pro model, and "
            "`get_status` to check connection. "
            "When a `warning` field appears in any tool response, report it to the user."
        ),
        lifespan=mcp_lifespan,
        **fastmcp_kwargs,
    )
    return mcp
