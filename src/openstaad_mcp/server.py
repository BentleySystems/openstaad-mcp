"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

MCP server definition — tools, lifespan, and ASGI app factory.

Exposes MCP tools:
- ``discover_api``  — lists available skills and usage guidance
- ``read_skills``   — returns requested skill content
- ``execute_code``  — runs validated Python against the COM bridge
- ``get_status``    — reports connection health
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.context import Context
from fastmcp.server.lifespan import lifespan
from mcp.types import ToolAnnotations

from openstaad_mcp.connection import InstanceRegistry, StaadInstance, connect_and_run
from openstaad_mcp.file_io import get_allowed_dirs, get_input_data, write_output_file
from openstaad_mcp.sandbox.executor import Executor
from openstaad_mcp.file_io.path_validator import FileIOError
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

        Returns connection state, STAAD version, and model path.
        """
        try:
            target = _resolve_target(instance)
        except ValueError as e:
            return {"connected": False, "error": str(e)}

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
            }
            warning = check_version_warning(version)
            if warning:
                result["warning"] = warning
            return result

        try:
            return connect_and_run(_read_status, target.file_path, timeout=10.0)
        except TimeoutError:
            return {"connected": False, "error": "Connection timed out"}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Execute Python code",
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,  # Different result for repeated calls
            openWorldHint=False,  # Only internal data
        )
    )
    async def execute_code(
        code: str,
        ctx: Context,
        instance: str | None = None,
        input_path: str | None = None,
        output_path: str | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Execute Python code in a sandbox against the OpenSTAAD API.

        The sandbox provides a pre-connected ``staad`` variable (the OpenSTAAD root object)  plus ``json``
        and ``math`` modules. Imports and regular filesystem access are blocked for security; all data exchange
        happens through `result`, `__input__`, and the file I/O params below.

        The last expression value or an explicit ``result = ...`` assignment is returned as the result.

        Pass ``instance`` (alias from ``list_instances``, e.g. ``staadPro1``) to target a specific
        STAAD instance.  Omit it when only one instance is running — it will be selected automatically.

        **File I/O** (optional):

        - ``input_path``: path to a ``.csv`` or ``.xlsx`` file. The server reads the file and injects its contents
          as the immutable `__input__` variable inside the sandbox. Use this to feed large datasets
          (e.g. node loads, section properties) into your code without hardcoding them.

        - `output_path`: path where the sandbox return value will be written as a file. Use this whenever
          the result is tabular data destined for a file (node lists, member forces, design results, etc.) —
          it avoids flooding the context window with large arrays. The `result` variable must be formatted as one of:
            - List-of-lists → written as CSV or single-sheet xlsx:
                result = [["Node ID", "X", "Y", "Z"], [1, 0.0, 0.0, 0.0], ...]
            - Dict of sheet dicts → written as multi-sheet xlsx:
                result = {
                    "Nodes": {"columns": ["Node ID", "X", "Y", "Z"],
                            "rows": [[1, 0.0, 0.0, 0.0], ...]},
                    "Members": {"columns": ["Member ID", "Start", "End"],
                                "rows": [[1, 1, 2], ...]}
                }

        - ``overwrite``: allow overwriting an existing output file.

        Paths must be inside MCP roots or `allowed_dirs`configured by the client.
        On Claude Desktop, users can configure allowed directories in the extension settings.
        If no roots are configured, omit both file I/O params and handle the returned
        `result` value in the agent instead (e.g. write the file via a separate tool).
        """
        try:
            target = _resolve_target(instance)
        except ValueError as e:
            return {
                "success": False,
                "result": None,
                "stdout": "",
                "stderr": "",
                "error": str(e),
                "duration_seconds": 0.0,
            }

        # ── Resolve allowed dirs for path validation ──
        allowed_dirs = await get_allowed_dirs(ctx, args_allowed_dirs, input_path, output_path)

        # ── Input file handling (server-side, outside sandbox) ───────
        try:
            input_data, input_summary = await get_input_data(input_path, allowed_dirs)
        except FileIOError as e:
            return {
                "success": False,
                "result": None,
                "stdout": "",
                "stderr": "",
                "error": f"{e.code}: {e.message}",
                "duration_seconds": 0.0,
            }

        # ── Execute code in sandbox ──────────────────────────────────
        def _run(staad: Any) -> dict[str, Any]:
            return exc.execute(code, staad, input_data=input_data).to_dict()

        try:
            result = connect_and_run(_run, target.file_path)
        except TimeoutError:
            return {
                "success": False,
                "result": None,
                "stdout": "",
                "stderr": "",
                "error": "Code execution timed out",
                "duration_seconds": 0.0,
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

        # ── Output file handling (server-side, outside sandbox) ──────
        if output_path is not None and result.get("success"):
            try:
                result["result"] = write_output_file(output_path, result["result"], allowed_dirs, overwrite=overwrite)
            except FileIOError as e:
                return {
                    "success": False,
                    "result": None,
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "error": f"{e.code}: {e.message}",
                    "duration_seconds": result.get("duration_seconds", 0.0),
                }

        # ── Attach summaries ─────────────────────────────────────────
        if input_summary is not None:
            result["input_summary"] = input_summary
        if target.warning:
            result["warning"] = target.warning
        return result


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
            "When a `warning` field appears in any tool response, report it to the user."
        ),
        lifespan=mcp_lifespan,
        **fastmcp_kwargs,
    )
    _register_tools(mcp, registry, Executor(), SkillsManager(), args_allowed_dirs=allowed_dirs)
    return mcp
