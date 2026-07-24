"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

MCP server definition — tools, lifespan, and ASGI app factory.

Exposes MCP tools:
- ``discover_api``   — lists available skills and usage guidance
- ``read_skills``    — returns requested skill content
- ``list_instances`` — lists running STAAD.Pro instances
- ``get_status``     — reports connection health
- ``execute_code``   — runs validated Python against the COM bridge (native MCP task, poll fallback, or auto-detect)
- ``get_job_result`` — returns the status/result of a background execution job
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.context import Context
from fastmcp.server.lifespan import lifespan
from fastmcp.utilities.tasks import TaskConfig
from mcp.types import ToolAnnotations

from openstaad_mcp.connection import InstanceRegistry, connect_and_run
from openstaad_mcp.execution import ExecutionMode, ExecutionService
from openstaad_mcp.sandbox.executor import Executor
from openstaad_mcp.skills import SkillsManager
from openstaad_mcp.version import check_version_warning

logger = logging.getLogger(__name__)


# ── Tool registrations ────────────────────────────────────────────


def _register_tools(
    mcp: FastMCP,
    registry: InstanceRegistry,
    exc: Executor,
    skills_mgr: SkillsManager,
    args_allowed_dirs: list[Path],
) -> None:
    """Register MCP tools on *mcp*, delegating execution to an :class:`ExecutionService`."""

    service = ExecutionService(registry, exc, args_allowed_dirs)

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

        Call this FIRST before using other openstaad-mcp tools.
        Then use ``read_skills`` with one or more specific skill names to load full guidance.
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

        Parameters
        ----------
        skills: list[str]
            List of skill names or sub-paths to read.  Use ``discover_api`` to see available skills.
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

        If a version is below the minimum supported (25.0.1), a ``warning``
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
        executor is currently busy (``executor_busy``).
        """
        try:
            target = service.resolve_target(instance)
        except ValueError as e:
            return {"connected": False, "executor_busy": service.executor_busy, "error": str(e)}

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
                "executor_busy": service.executor_busy,
            }
            warning = check_version_warning(version)
            if warning:
                result["warning"] = warning
            return result

        try:
            return connect_and_run(_read_status, target.file_path, timeout=10.0)
        except TimeoutError:
            return {"connected": False, "executor_busy": service.executor_busy, "error": "Connection timed out"}
        except Exception as e:
            return {"connected": False, "executor_busy": service.executor_busy, "error": str(e)}

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Execute Python code",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,  # Different result for repeated calls
            openWorldHint=False,  # Only internal data
        ),
        task=TaskConfig(mode="optional"),
    )
    async def execute_code(
        ctx: Context,
        code: str,
        instance: str | None = None,
        input_data_path: str | None = None,
        output_data_path: str | None = None,
        overwrite: bool = False,
        mode: ExecutionMode = "auto",
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Execute Python code in a sandbox against the OpenSTAAD API (don't forget to call discover_api and read_skills for API guidance).

        The sandbox provides pre-connected ``staad`` (the OpenSTAAD root object) and ``input_data`` (if input_data_path is provided) variables (plus ``json``
        and ``math`` modules) and a ``progress(message)`` callback. `import` statements, `dir()`, `getattr()`, ... are **BLOCKED**.

        Call ``progress(f"Processing {i}/{total}")`` inside long loops or before a long single operation
        (analysis, design) so the user sees real-time feedback.

        The last expression value or an explicit ``result = ...`` assignment is returned as the result.
        If ``output_data_path`` is provided, the sandbox will write the result to the specified file.

        Paths must be on the user LOCAL filesystem and inside MCP roots or configured `allowed_dirs`.
        On Claude Desktop, users can configure allowed directories in the extension settings and Claude can use the filesystem ``copy_file_to_claude``
        tool to move files to Claude's filesystem.

        Long-running work: by default (``mode="auto"``) the server detects whether the client will
        surface progress natively (via a progress token or native MCP background task) and falls back
        to ``"poll"`` automatically when it cannot.  Pass ``mode="poll"`` explicitly to always use the
        AI-polling path: the server returns a ``job_id`` immediately and you poll ``get_job_result(job_id)``
        (writing its ``message`` to the user each time).  Pass ``mode="native"`` to always trust the
        client's MCP progress notifications.

        IMPORTANT — when a ``job_id`` is returned: your very next tool call MUST be
        ``get_job_result``.  Do NOT write any text to the user before the first poll — every
        second of delay is progress the user cannot see.  Write the ``message`` field to the
        user *after* each ``get_job_result`` response, then call it again immediately.
        Stop after 5 consecutive ``"running"`` responses: tell the user the job is still in
        progress (include the ``job_id``) and wait for them to ask for an update.

        Parameters
        ----------
        code: str
            Python source code to execute.  Use the pre-injected ``staad`` variable to interact with the API.
            (don't forget to call discover_api and read_skills for API guidance)
        instance: str
            Alias (from ``list_instances``, e.g. ``staadPro1``) of the STAAD instance to target. If omitted, last opened instance is selected.
        input_data_path: str, optional
            Path on user LOCAL filesystem to a ``.csv`` or ``.xlsx`` file. Its content is injected as the immutable `input_data` variable inside the sandbox.
            Use this to feed large datasets (e.g. node loads, section properties) into your code without hardcoding them.
        output_data_path: str, optional
            Path on user LOCAL filesystem to a ``.csv`` or ``.xlsx`` file where to write the ``result`` value.
            Use this to avoid flooding the context window with large amount of data. The ``result`` variable must be formatted as one of:
            - List-of-lists → written as CSV or single-sheet xlsx:
                result = [["Node ID", "X", "Y", "Z"], [1, 0.0, 0.0, 0.0], ...]
            - Dict of sheet dicts → written as multi-sheet xlsx:
                result = {
                    "Nodes": {"columns": ["Node ID", "X", "Y", "Z"],
                            "rows": [[1, 0.0, 0.0, 0.0], ...]},
                    "Members": {"columns": ["Member ID", "Start", "End"],
                                "rows": [[1, 1, 2], ...]}
                }
        overwrite: bool, optional
            Allow overwriting an existing output file.
        mode: {"auto", "native", "poll"}, optional
            ``"auto"`` (default) detects whether the client will surface progress natively and
            falls back to ``"poll"`` when it cannot.  ``"native"`` trusts the client's MCP progress
            notifications (``notifications/progress``).  ``"poll"`` always returns a ``job_id``
            immediately so you can poll ``get_job_result`` and relay progress in your text responses.
        timeout: float, optional
            Max seconds to wait for the call to complete (default: 120). The COM operation
            cannot be safely interrupted, so on timeout the call returns an error but the work
            continues running in the background (the executor stays busy, reported via
            ``get_status``'s ``executor_busy``, until it finishes on its own).
        """
        return await service.execute(
            ctx=ctx,
            code=code,
            instance=instance,
            input_data_path=input_data_path,
            output_data_path=output_data_path,
            overwrite=overwrite,
            mode=mode,
            timeout=timeout,
        )

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get background job result — ALWAYS show message to user",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=False,  # Job state can change between calls
            openWorldHint=False,
        )
    )
    async def get_job_result(job_id: str) -> dict[str, Any]:
        """Wait (server-paced) for a background ``execute_code`` job and return its status or result.

        The server sleeps internally before responding — call this again immediately after each
        response regardless of status.  Write the ``message`` field to the user after each call;
        that is the only way they see progress.  Stop when ``status`` is ``"completed"``,
        ``"failed"`` (full result payload included; job is then removed from the store), or
        ``"delivered"`` (the terminal result was already returned on an earlier poll).
        """
        return await service.get_job_result(job_id)


def create_mcp_server(allowed_dirs: list[Path], fastmcp_kwargs: dict | None = None) -> FastMCP:
    """Create an MCP server instance with tools registered"""
    fastmcp_kwargs = fastmcp_kwargs or {}

    registry = InstanceRegistry()

    @lifespan
    async def mcp_lifespan(server: Any) -> AsyncIterator[None]:
        yield

    mcp = FastMCP(
        "OpenSTAAD MCP",
        instructions=(
            "This MCP server bridges AI agents to Bentley STAAD.Pro via the "
            "OpenSTAAD COM API. Use `discover_api` first to list available skills "
            "and guidance, then call `read_skills` with skill names to load detailed "
            "instructions. Use `list_instances` to see running STAAD instances, "
            "`execute_code` to run code against a live STAAD.Pro model, and "
            "`get_status` to check connection. "
            "When `execute_code` returns a `job_id`, follow the `next_action` field exactly: "
            "call `get_job_result` immediately — no text output before the first poll. "
            "When a `warning` field appears in any tool response, report it to the user."
        ),
        lifespan=mcp_lifespan,
        **fastmcp_kwargs,
    )
    _register_tools(mcp, registry, Executor(), SkillsManager(), args_allowed_dirs=allowed_dirs)
    return mcp
