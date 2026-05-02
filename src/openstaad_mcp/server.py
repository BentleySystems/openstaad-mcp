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
- ``openstaad_execute_code``  — starts validated Python execution (returns job_id)
- ``openstaad_get_job_status`` — checks job progress
- ``openstaad_get_job_result`` — collects completed job result
"""

from __future__ import annotations

import asyncio
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


class _JobStore:
    """Minimal in-memory store for background code executions.

    Jobs are evicted after *ttl_seconds* (default 10 min).
    """

    def __init__(self, ttl_seconds: float = 600.0) -> None:
        self._jobs: dict[str, _Job] = {}
        self._ttl = ttl_seconds

    def create(self, future: asyncio.Future[dict[str, Any]]) -> str:
        self._evict()
        job_id = uuid.uuid4().hex[:12]
        self._jobs[job_id] = _Job(future=future, created=time.monotonic())
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
        results = []
        for inst in registry.get_active_instances():
            results.append(inst.asdict())
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
            result: dict[str, Any] = {
                "connected": True,
                "staad_version": version,
                "model_path": model_path,
                "alias": target.alias,
                "analyzing": analyzing,
                "executor_busy": exc.is_busy,
            }
            warning = check_version_warning(version)
            if warning:
                result["warning"] = warning
            return result

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
    )
    async def openstaad_execute_code(
        code: str,
        instance: str | None = None,
        timeout: float = 120.0,
        mode: Literal["sync", "async"] = "sync",
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """Execute Python code against the OpenSTAAD API.

        Imports are blocked; sandbox provides ``staad``, ``json``, ``math``,
        ``progress``.  ``mode="sync"`` (default) blocks and returns the result
        directly.  ``mode="async"`` returns a job_id — you MUST then poll
        ``openstaad_get_job_status`` every 5-10 seconds and display each
        ``message`` field to the user immediately so they see live progress.
        Do not silently poll. See staad-core skill for patterns.
        """
        try:
            target = _resolve_target(instance)
        except ValueError as e:
            return {"success": False, "error": str(e)}

        loop = asyncio.get_running_loop()
        start = time.monotonic()

        # In async mode, progress updates the job object.
        # In sync mode, progress is forwarded to the MCP client via log notifications.
        # NOTE: Since _run executes in run_in_executor, the event loop IS free to
        # process the scheduled coroutine — run_in_executor yields the event loop
        # while the thread does blocking work.
        job_ref: _Job | None = None

        def _progress_fn(message: str) -> None:
            if job_ref is not None:
                job_ref.progress_message = message
            elif ctx is not None:
                asyncio.run_coroutine_threadsafe(
                    ctx.log(message, level="info"),
                    loop,
                )

        def _run(staad: Any) -> dict[str, Any]:
            return exc.execute(code, staad, progress_fn=_progress_fn, lock_timeout=timeout).to_dict()

        # ── Sync mode: block and return result directly ──────────────
        if mode == "sync":
            try:
                result = await loop.run_in_executor(
                    None, functools.partial(connect_and_run, _run, target.file_path, timeout)
                )
            except TimeoutError:
                return {
                    "success": False,
                    "result": None,
                    "stdout": "",
                    "stderr": "",
                    "error": "Code execution timed out",
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
            if target.warning:
                result["warning"] = target.warning
            return result

        # ── Async mode: start background job, return job_id ──────────
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        job_id = jobs.create(future)
        job_ref = jobs.get(job_id)

        async def _bg_task() -> None:
            try:
                result = await loop.run_in_executor(
                    None, functools.partial(connect_and_run, _run, target.file_path, timeout)
                )
                if target.warning:
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
                            "error": "Code execution timed out",
                            "duration_seconds": timeout,
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

        asyncio.create_task(_bg_task())  # noqa: RUF006

        return {
            "job_id": job_id,
            "message": f"Job started. Poll openstaad_get_job_status('{job_id}') every 5-10s "
            "and show each 'message' field to the user so they see progress.",
        }

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get job status — SHOW message to user",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        output_schema={
            "type": "object",
            "required": ["status", "message"],
            "properties": {
                "status": {"type": "string", "enum": ["running", "completed", "failed", "unknown"]},
                "progress": {"type": "string", "description": "Last progress message from the sandbox"},
                "elapsed_seconds": {"type": "number"},
                "message": {
                    "type": "string",
                    "description": "IMPORTANT: Always display this message to the user so they can see execution progress",
                },
            },
        },
    )
    def openstaad_get_job_status(job_id: str) -> dict[str, Any]:
        """IMPORTANT: Always display the ``message`` field from the response to the user so they can see execution progress. Poll every 5-10 seconds while status is "running". Do not batch or skip messages — the user is waiting."""
        job = jobs.get(job_id)
        if job is None:
            return {"status": "unknown", "progress": "", "elapsed_seconds": 0.0, "message": "Job not found."}
        elapsed = round(time.monotonic() - job.created, 1)
        if not job.future.done():
            progress = job.progress_message
            msg = f"⏳ Running ({elapsed:.0f}s): {progress}" if progress else f"⏳ Running ({elapsed:.0f}s)..."
            return {"status": "running", "progress": progress, "elapsed_seconds": elapsed, "message": msg}
        result = job.future.result()
        status = "completed" if result.get("success") else "failed"
        msg = f"✅ Completed in {elapsed:.0f}s" if status == "completed" else f"❌ Failed after {elapsed:.0f}s"
        return {"status": status, "progress": job.progress_message, "elapsed_seconds": elapsed, "message": msg}

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get job execution result",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
        output_schema={
            "type": "object",
            "required": ["success", "stdout", "stderr", "duration_seconds"],
            "properties": {
                "success": {"type": "boolean"},
                "result": {"description": "Return value of the executed code"},
                "stdout": {"type": "string"},
                "stderr": {"type": "string"},
                "error": {"type": ["string", "null"]},
                "duration_seconds": {"type": "number"},
                "result_size_bytes": {"type": "integer"},
                "warning": {"type": "string"},
                "status": {"type": "string", "enum": ["running", "completed", "failed", "unknown"]},
                "progress": {"type": "string"},
            },
        },
    )
    def openstaad_get_job_result(job_id: str) -> dict[str, Any]:
        """Collect the result of a completed job.

        If the job is still running, returns ``status: "running"`` with
        the latest progress message — call again when ready.
        Once complete, the job is removed from the store.
        """
        job = jobs.get(job_id)
        if job is None:
            return {
                "success": False,
                "result": None,
                "stdout": "",
                "stderr": "",
                "error": f"Unknown or expired job_id: {job_id!r}",
                "duration_seconds": 0.0,
                "result_size_bytes": 0,
                "status": "unknown",
            }
        if not job.future.done():
            return {
                "success": True,
                "result": None,
                "stdout": "",
                "stderr": "",
                "error": None,
                "duration_seconds": round(time.monotonic() - job.created, 1),
                "result_size_bytes": 0,
                "status": "running",
                "progress": job.progress_message,
            }
        # Done — pop and return
        jobs.pop(job_id)
        result = job.future.result()
        result["status"] = "completed" if result.get("success") else "failed"
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
            "running STAAD instances. Use `openstaad_execute_code` to run Python code "
            "— sync mode (default) returns the result directly; for long operations use "
            "mode='async', which returns a job_id, then monitor with "
            "`openstaad_get_job_status` and collect with `openstaad_get_job_result`. "
            "Use `openstaad_get_status` to check connection health. "
            "When a `warning` field appears in any tool response, report it to the user.\n\n"
            "PROGRESS VISIBILITY: When using async mode, poll `openstaad_get_job_status` "
            "every 5-10 seconds and DISPLAY the `message` field to the user in your text "
            "response (e.g. '⏳ Running (12s): Processing plate 500/111684...'). This is "
            "the only way the user sees execution progress — MCP notifications are not "
            "displayed in the chat UI. Always show the `message` value between polls."
        ),
        lifespan=mcp_lifespan,
        **fastmcp_kwargs,
    )
    return mcp
