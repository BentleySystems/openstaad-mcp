"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

MCP server definition — tools, lifespan, and ASGI app factory.

Exposes MCP tools:
- ``discover_api``  — lists available skills and usage guidance
- ``read_skills``   — returns requested skill content
- ``execute_code``  — runs agent-authored JavaScript inside the WASM sandbox
- ``get_status``    — reports connection health

HTTP transport security:
- Bearer token auth is mandatory in HTTP mode (see ``main.py``); the
  server auto-generates a token and delivers it via a OneTimeSecret
  share URL displayed in the terminal auth banner.
- The listener binds to ``127.0.0.1`` only.
- ``HostHeaderMiddleware`` (see ``http_security.py``) rejects requests
  whose ``Host`` header is not in the allowlist. This defeats DNS
  rebinding: a browser attacking ``http://attacker.com:<port>/mcp``
  still sends ``Host: attacker.com``, which is rejected with HTTP 421
  before the bearer-auth layer ever runs. The allowlist defaults to
  loopback names and can be extended with ``--allowed-host`` (e.g. for
  tunnel or reverse-proxy hostnames).

Sec-Fetch-Site filtering is intentionally *not* implemented. With
loopback-only bind, mandatory bearer auth, and the Host-header
allowlist, an extra fetch-metadata check adds negligible value. The
three controls we do ship already defeat every known rebinding path
for this transport.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.server.context import AcceptedElicitation
from fastmcp.server.lifespan import lifespan

from openstaad_mcp.connection import InstanceRegistry, StaadInstance, connect_and_run
from openstaad_mcp.sandbox import ALL_DESTRUCTIVE_METHOD_NAMES, WasmExecutor
from openstaad_mcp.skills import discover_api_impl, read_skills_impl

logger = logging.getLogger(__name__)


def _safe_error_message(exc: BaseException) -> str:
    """Return an error string safe to expose to the MCP client.

    ValueError messages are ours (instance resolution), so they are safe.
    Everything else (COM errors, connection failures) may contain paths,
    usernames, or DLL names — return only the exception class name.
    """
    if isinstance(exc, ValueError):
        return str(exc)
    return f"Internal error: {type(exc).__name__}"


# ── Tool registrations ────────────────────────────────────────────


def _register_tools(mcp: FastMCP, registry: InstanceRegistry, exc: WasmExecutor) -> None:
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

    @mcp.tool()
    def discover_api() -> str:
        """Discover available API guidance and skills.

        Call this before using other openstaad-mcp tools to understand the API surface
        and see what skills are available. Then use ``read_skills`` with one or more
        specific skill names to load full guidance.
        """
        return discover_api_impl()

    @mcp.tool()
    def read_skills(skills: list[str]) -> str:
        """Read one or more skills by name.

        Use ``discover_api`` first to list available skills.
        Each skill provides domain-specific guidance (e.g. analysis, geometry, loads).

        Pass skill names like ``["staad-analysis"]`` or sub-paths like
        ``["staad-design/assets/STEEL_CODES"]`` to read reference files
        within a skill.
        """
        return read_skills_impl(skills)

    @mcp.tool()
    def list_instances() -> list[dict[str, Any]]:
        """List all running STAAD.Pro instances.

        Returns a list of instances with their alias, process ID, currently
        open file path, and STAAD version.  Call this before ``execute_code``
        when multiple STAAD instances may be running so you can pick the
        right one.  The ``alias`` (e.g. ``staadPro1``) is stable for the
        server session even if the model file changes.
        """

        return [asdict(i) for i in registry.get_active_instances()]

    @mcp.tool()
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
            return {
                "connected": True,
                "staad_version": version,
                "model_path": model_path,
                "alias": target.alias,
                "analyzing": analyzing,
            }

        try:
            return connect_and_run(_read_status, target.file_path, timeout=10.0)
        except TimeoutError:
            return {"connected": False, "error": "Connection timed out"}
        except Exception as e:
            logger.debug("get_status failed", exc_info=True)
            return {"connected": False, "error": _safe_error_message(e)}

    @mcp.tool()
    async def execute_code(
        code: str,
        instance: str | None = None,
        ctx: Context | None = None,
    ) -> dict[str, Any]:
        """Execute JavaScript code against the OpenSTAAD API.

        The sandbox provides a pre-connected ``staad`` object (the
        OpenSTAAD root). Filesystem, network, and module imports are
        physically unreachable — user code runs inside a WebAssembly
        isolate with only ``staad`` and ``console`` exposed. Standard
        JavaScript built-ins (``JSON``, ``Math``, ``Array``, etc.) are
        available as usual.

        The last expression value or an explicit ``return <value>`` is
        returned as the result. Use ``console.log`` / ``console.error``
        for progress output (captured into ``stdout`` / ``stderr``).

        Pass ``instance`` (alias from ``list_instances``, e.g. ``staadPro1``)
        to target a specific STAAD instance. Omit it when only one instance
        is running — it will be selected automatically.

        COM methods that write to the filesystem or modify the STAAD
        session (e.g. ``NewSTAADFile``, ``SaveModel``, ``ExportView``,
        ``Quit``) are blocked by default. When such methods are detected,
        the server asks the user for explicit approval via the host's
        confirmation dialog — this cannot be bypassed by the AI agent.
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

        # ── Pre-flight: detect destructive method names in the code ──
        detected = {m for m in ALL_DESTRUCTIVE_METHOD_NAMES if m in code}
        allow_destructive = False

        if detected:
            methods_str = ", ".join(sorted(detected))
            if ctx is None:
                return {
                    "success": False,
                    "result": None,
                    "stdout": "",
                    "stderr": "",
                    "error": (
                        f"Code references destructive method(s): {methods_str}. "
                        f"Cannot proceed without user confirmation (no context "
                        f"available for elicitation)."
                    ),
                    "duration_seconds": 0.0,
                }
            try:
                elicit_result = await ctx.elicit(
                    f"This code calls method(s) that can modify the filesystem "
                    f"or STAAD session: {methods_str}.\n\n"
                    f"Allow this operation?",
                    response_type=bool,
                    response_title="Allow destructive operation",
                )
                if isinstance(elicit_result, AcceptedElicitation) and elicit_result.data:
                    allow_destructive = True
                else:
                    return {
                        "success": False,
                        "result": None,
                        "stdout": "",
                        "stderr": "",
                        "error": f"User declined destructive operation ({methods_str}).",
                        "duration_seconds": 0.0,
                    }
            except Exception as elicit_exc:
                logger.debug("Elicitation failed", exc_info=True)
                return {
                    "success": False,
                    "result": None,
                    "stdout": "",
                    "stderr": "",
                    "error": (
                        f"Code references destructive method(s): {methods_str}. "
                        f"User approval is required but the MCP host does not "
                        f"support confirmation dialogs ({type(elicit_exc).__name__})."
                    ),
                    "duration_seconds": 0.0,
                }

        def _run(staad: Any) -> dict[str, Any]:
            return exc.execute(
                code, staad, allow_destructive=allow_destructive
            ).to_dict()

        try:
            return connect_and_run(_run, target.file_path)
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
            logger.debug("execute_code failed", exc_info=True)
            return {
                "success": False,
                "result": None,
                "stdout": "",
                "stderr": "",
                "error": _safe_error_message(e),
                "duration_seconds": 0.0,
            }

    # Maximum size (bytes) returned from read_analysis_output.  .ANL files
    # can be large for big models; we cap to avoid flooding the LLM context.
    _MAX_OUTPUT_FILE_BYTES: int = 512 * 1024  # 512 KiB

    @mcp.tool()
    def read_analysis_output(
        file_type: str = "anl",
        instance: str | None = None,
    ) -> dict[str, Any]:
        """Read the analysis output file (.ANL) or solver log (.LOG) for the currently open model.

        The file path is derived automatically from the open STAAD model —
        there is no user-supplied path.  This is the only way to access
        concrete, timber, and aluminum design results, which are not
        available through the COM API.

        ``file_type``: ``"anl"`` (default) for the analysis output file,
        or ``"log"`` for the solver diagnostic log.
        """
        ft = file_type.strip().lower()
        if ft not in ("anl", "log"):
            return {
                "success": False,
                "content": None,
                "error": f"file_type must be 'anl' or 'log', got {file_type!r}",
            }

        try:
            target = _resolve_target(instance)
        except ValueError as e:
            return {"success": False, "content": None, "error": str(e)}

        def _read(staad: Any) -> dict[str, Any]:
            import pathlib

            model_path = staad.GetSTAADFile()
            if not model_path:
                return {
                    "success": False,
                    "content": None,
                    "error": "No model file is currently open in STAAD.Pro",
                }

            output_path = pathlib.Path(model_path).with_suffix(f".{ft.upper()}")

            if not output_path.is_file():
                return {
                    "success": False,
                    "content": None,
                    "error": (
                        f"Output file not found: {output_path.name}. "
                        f"Run analysis first (AnalyzeEx)."
                    ),
                }

            try:
                raw = output_path.read_bytes()
            except OSError as read_exc:
                return {
                    "success": False,
                    "content": None,
                    "error": f"Cannot read {output_path.name}: {type(read_exc).__name__}",
                }

            truncated = len(raw) > _MAX_OUTPUT_FILE_BYTES
            text = raw[:_MAX_OUTPUT_FILE_BYTES].decode("utf-8", errors="replace")

            result: dict[str, Any] = {
                "success": True,
                "file_name": output_path.name,
                "content": text,
            }
            if truncated:
                result["truncated"] = True
                result["total_bytes"] = len(raw)
                result["returned_bytes"] = _MAX_OUTPUT_FILE_BYTES
            return result

        try:
            return connect_and_run(_read, target.file_path, timeout=10.0)
        except TimeoutError:
            return {"success": False, "content": None, "error": "Connection timed out"}
        except Exception as e:
            logger.debug("read_analysis_output failed", exc_info=True)
            return {"success": False, "content": None, "error": _safe_error_message(e)}


def create_mcp_server(fastmcp_kwargs: dict | None = None) -> FastMCP:
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
            "`execute_code` to run code against a live STAAD.Pro model, "
            "`read_analysis_output` to read the .ANL or .LOG file for concrete/"
            "timber/aluminum design results, and `get_status` to check connection."
        ),
        lifespan=mcp_lifespan,
        **fastmcp_kwargs,
    )
    _register_tools(mcp, registry, WasmExecutor())
    return mcp
