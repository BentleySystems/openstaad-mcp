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
from openstaad_mcp.file_io.helpers import (
    detect_input_output_collision,
    get_allowed_dirs,
    get_input_data,
    write_output_file,
)
from openstaad_mcp.file_io.path_validator import FileIOError
from openstaad_mcp.ptc.adapter import build_registry
from openstaad_mcp.ptc.runtime import PTCRuntime
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
    """Register MCP tools on *mcp*, closing over the *InstanceRegistry*."""
    ptc_runtime = PTCRuntime(exc)
    ptc_catalog = build_registry()

    @mcp.tool(annotations=ToolAnnotations(title="Discover PTC query tools", readOnlyHint=True, openWorldHint=False))
    def discover_ptc(namespace: str | None = None) -> list[dict[str, Any]]:
        """List registered tools.* Python calls, parameter schemas and return-field guidance.

        No STAAD connection is needed. Optionally filter by geometry, properties,
        loads, supports, analysis or design. Use execute_ptc to compose these
        synchronous queries; intermediate data stays in the local runtime.
        """
        return ptc_catalog.discover(namespace)

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
        ctx: Context,
        code: str,
        instance: str | None = None,
        input_data_path: str | None = None,
        output_data_path: str | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Execute Python code in a sandbox against the OpenSTAAD API (don't forget to call discover_api and read_skills for API guidance).

        The sandbox provides pre-connected ``staad`` (the OpenSTAAD root object) and ``input_data`` (if input_data_path is provided) variables (plus ``json``
        and ``math`` modules). `import` statements, `dir()`, `getattr()`, ... are **BLOCKED**.

        The last expression value or an explicit ``result = ...`` assignment is returned as the result.
        If ``output_data_path`` is provided, the sandbox will write the result to the specified file.

        Paths must be on the user LOCAL filesystem and inside MCP roots or configured `allowed_dirs`.
        On Claude Desktop, users can configure allowed directories in the extension settings and Claude can use the filesystem ``copy_file_to_claude``
        tool to move files to Claude's filesystem.

        Parameters
        ----------
        code: str
            Python source code to execute.  Use the pre-injected ``staad`` variable to interact with the API.
            (don't forget to call discover_api and read_skills for API guidance)
        instance: str
            Alias (from ``list_instances``, e.g. ``staadPro1``) of the STAAD instance to target. If omitted, last opened instance is selected.
        input_data_path: str, optional
            Path on user LOCAL filesystem to a ``.csv`` or ``.xlsx`` file. Its content is parsed and injected as ``input_data`` inside the sandbox.
            Use this to feed large datasets (e.g. node loads, section properties) into your code without hardcoding them.
            The shape is determined by the extension:
            - CSV -> list of row lists. When a header is detected, it is the first row:
                columns = input_data[0]
                for row in input_data[1:]:
                    print(row)
            - XLSX -> dict mapping every sheet to ``columns`` and ``rows`` lists:
                sheet = input_data["Sheet1"]
                columns = sheet["columns"]
                for row in sheet["rows"]:
                    print(row)
            The containers are mutable for normal Python compatibility, but are fresh for each execution; mutations do not change the source file or persist across executions.
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
        """
        return await _execute_request(ctx, code, instance, input_data_path, output_data_path, overwrite)

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Execute programmatic OpenSTAAD queries",
            readOnlyHint=False,  # Queries are read-only; optional file export writes to disk.
            destructiveHint=True,  # overwrite=True can replace an allowed output file.
            idempotentHint=False,
            openWorldHint=False,
        )
    )
    async def execute_ptc(
        ctx: Context,
        code: str,
        instance: str | None = None,
        input_data_path: str | None = None,
        output_data_path: str | None = None,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """Compose read-only OpenSTAAD queries in one local sandboxed Python program.

        Call discover_ptc for tool schemas. Available globals: tools, input_data,
        math and json. Use tools.geometry.get_members(), tools.analysis.*,
        tools.design.get_utilization(), etc. Native dict/list results stay local
        until an explicit result assignment or the last expression is returned.
        staad, imports, async and raw COM access are not exposed in this mode.

        Limits: 1000 tool calls, 10000 IDs per list, 100000 result rows per batch,
        65536 bytes for an inline result. stdout is also returned: do not print
        intermediate datasets. Use output_data_path to export large final results
        as CSV/XLSX (same table shapes and allowed-directory rules as execute_code).
        Input data is a fresh copy per execution. No cross-call handles or cache.
        Specify an instance alias when multiple STAAD models are open.

        Design utilization is from the last steel design parameter block; it is
        not derived from member forces or restricted to an analysis load case.
        Geometry uses base length units, with Y up by default (pass up_axis='Z'
        for Z-up models). Use analysis.get_units() for output units.
        """
        return await _execute_request(ctx, code, instance, input_data_path, output_data_path, overwrite, ptc=True)

    async def _execute_request(
        ctx: Context,
        code: str,
        instance: str | None,
        input_data_path: str | None,
        output_data_path: str | None,
        overwrite: bool,
        *,
        ptc: bool = False,
    ) -> dict[str, Any]:
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
        allowed_dirs = await get_allowed_dirs(ctx, args_allowed_dirs)

        # ── Input file handling (server-side, outside sandbox) ───────
        try:
            await detect_input_output_collision(input_data_path, output_data_path, allowed_dirs)
            input_data, _ = await get_input_data(input_data_path, allowed_dirs)
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
            if ptc:
                return ptc_runtime.execute(code, staad, input_data=input_data, export=output_data_path is not None)
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
            "For programmatic read-only workflows, use `discover_ptc` to inspect "
            "the tools.* catalog, then `execute_ptc` to query, filter and aggregate "
            "locally in one Python program. Only return the final summary. "
            "When a `warning` field appears in any tool response, report it to the user."
        ),
        lifespan=mcp_lifespan,
        **fastmcp_kwargs,
    )
    _register_tools(mcp, registry, Executor(), SkillsManager(), args_allowed_dirs=allowed_dirs)
    return mcp
