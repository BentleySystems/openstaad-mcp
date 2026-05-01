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
- ``openstaad_execute_code``  — runs validated Python against the COM bridge
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan
from mcp.types import ToolAnnotations

from openstaad_mcp.connection import InstanceRegistry, StaadInstance, connect_and_run
from openstaad_mcp.sandbox.executor import Executor
from openstaad_mcp.skills import SkillsManager
from openstaad_mcp.version import check_version_warning

logger = logging.getLogger(__name__)


# ── Tool registrations ────────────────────────────────────────────


def _register_tools(mcp: FastMCP, registry: InstanceRegistry, exc: Executor, skills_mgr: SkillsManager) -> None:
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
                "warning": {"type": "string"},
                "error": {"type": "string"},
            },
        },
    )
    def openstaad_get_status(instance: str | None = None) -> dict[str, Any]:
        """Check the connection to a STAAD.Pro instance.

        Pass ``instance`` (alias from ``openstaad_list_instances``) to target a
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
                "warning": {"type": "string"},
            },
        },
    )
    def openstaad_execute_code(code: str, instance: str | None = None) -> dict[str, Any]:
        """Execute Python code against the OpenSTAAD API.

        Imports and filesystem access are blocked for security.

        The sandbox provides a pre-connected ``staad`` variable (the
        OpenSTAAD root object) plus ``json`` and ``math`` modules.
        The last expression value or an explicit ``result = ...``
        assignment is returned as the result.

        Pass ``instance`` (alias from ``openstaad_list_instances``, e.g. ``staadPro1``)
        to target a specific STAAD instance.  Omit it when only one instance
        is running — it will be selected automatically.
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

        def _run(staad: Any) -> dict[str, Any]:
            return exc.execute(code, staad).to_dict()

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
        if target.warning:
            result["warning"] = target.warning
        return result


def create_mcp_server(fastmcp_kwargs: dict | None = None) -> FastMCP:
    """Create an MCP server instance with tools registered"""
    fastmcp_kwargs = fastmcp_kwargs or {}

    @lifespan
    async def mcp_lifespan(server: Any) -> AsyncIterator[None]:
        registry = InstanceRegistry()
        exc = Executor()
        skills_mgr = SkillsManager()
        _register_tools(server, registry, exc, skills_mgr)
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
            "running STAAD instances, `openstaad_execute_code` to run code against a "
            "live STAAD.Pro model, and `openstaad_get_status` to check connection. "
            "When a `warning` field appears in any tool response, report it to the user."
        ),
        lifespan=mcp_lifespan,
        **fastmcp_kwargs,
    )
    return mcp
