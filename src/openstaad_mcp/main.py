"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

CLI entry point for the OpenSTAAD MCP server.
"""

from __future__ import annotations

import argparse
import logging
import os
import secrets
import sys
import warnings

from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from openstaad_mcp.file_io import validate_args_allowed_dirs
from openstaad_mcp.http_middleware import SecFetchMiddleware
from openstaad_mcp.server import create_mcp_server

# Suppress authlib deprecation warning that pollutes stderr on import
warnings.filterwarnings("ignore", message="authlib.jose module is deprecated")

_HTTP_ONLY_DEFAULTS = {"port": 18120, "token": None}

_MCP_TRANSPORT_DEFAULT = "stdio"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="openstaad-mcp",
        description="MCP server for Bentley STAAD.Pro (OpenSTAAD COM bridge)",
    )

    # ── Shared options ────────────────────────────────────────────
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=_MCP_TRANSPORT_DEFAULT,
        help="Transport mode (default: stdio)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )
    parser.add_argument(
        "--allowed-dirs",
        type=str,
        nargs="+",
        default=None,
        help="Directories the openSTAAD server can access (for MCP clients that don't support roots; space separated list)",
    )

    # ── HTTP-only options ─────────────────────────────────────────
    parser.add_argument(
        "--port",
        type=int,
        default=_HTTP_ONLY_DEFAULTS["port"],
        help=f"[http] TCP port to listen on (default: {_HTTP_ONLY_DEFAULTS['port']})",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=os.environ.get("OPENSTAAD_MCP_TOKEN"),
        help="[http] Bearer token (or set OPENSTAAD_MCP_TOKEN env var)",
    )

    args = parser.parse_args(argv)

    # Warn when HTTP-only flags are passed in stdio mode.
    if args.transport == "stdio":
        for opt, default in _HTTP_ONLY_DEFAULTS.items():
            if getattr(args, opt) != default:
                flag = f"--{opt.replace('_', '-')}"
                warnings.warn(
                    f"{flag} has no effect in stdio mode (requires --transport http)",
                    stacklevel=2,
                )
    return args


def setup_logging(log_level: str) -> None:
    """Configure logging with the given log level and file path."""
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stderr),
        ],
        force=True,
    )
    logging.info(f"Logging initialized at {log_level} level")
    _quiet_fastmcp_to_client_logger()


def _quiet_fastmcp_to_client_logger() -> None:
    """Silence FastMCP's internal "Sending <level> to client" trace logger.

    FastMCP already delivers ``ctx.log()`` messages to clients out-of-band via
    ``session.send_log_message`` — the ``to_client`` logger call in
    ``fastmcp.server.context`` is a redundant internal trace, not the actual
    delivery mechanism. Left at its default level, it duplicates every
    progress message onto FastMCP's own Rich console handler, which resolves
    ``sys.stderr`` dynamically on each write (``rich.console.Console(stderr=True)``).
    Because ``execute_code`` temporarily reassigns the process-global
    ``sys.stderr`` while sandboxed user code runs on a worker thread, a
    same-time log call from the event-loop thread (e.g. triggered by
    ``progress()``) can have its output captured into that request's sandboxed
    ``stderr`` buffer instead of the real console — leaking internal SDK
    chatter into the tool result and inflating it for long-running loops.
    Raising this logger's level to WARNING removes the trace entirely.
    """
    logging.getLogger("fastmcp.server.context.to_client").setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    setup_logging(args.log_level)
    allowed_dirs = validate_args_allowed_dirs(args.allowed_dirs)

    if args.transport == "stdio":
        # Run FastMCP server in the main thread, the COM thread will be started by the lifespan.
        mcp = create_mcp_server(allowed_dirs)
        _quiet_fastmcp_to_client_logger()  # re-apply: create_mcp_server may reconfigure fastmcp's logger
        try:
            mcp.run(transport="stdio", show_banner=False)
        except KeyboardInterrupt:
            logging.info("Shutting down MCP server due to keyboard interrupt")

    else:  # http
        token = args.token
        if not token:
            token = secrets.token_urlsafe(32)
            logging.warning(
                "No --token provided; auto-generated token for this session: %s",
                token,
            )
        fastmcp_kwargs = {
            "auth": StaticTokenVerifier(
                tokens={token: {"client_id": "authorized-user", "scopes": ["read:data"]}},
                required_scopes=["read:data"],
            )
        }
        mcp = create_mcp_server(allowed_dirs, fastmcp_kwargs=fastmcp_kwargs)
        _quiet_fastmcp_to_client_logger()  # re-apply: create_mcp_server may reconfigure fastmcp's logger
        try:
            mcp.run(
                transport="http",
                host="127.0.0.1",
                port=args.port,
                stateless_http=True,
                middleware=[
                    Middleware(SecFetchMiddleware),
                    Middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1"]),
                ],
            )
        except KeyboardInterrupt:
            logging.info("Shutting down MCP server due to keyboard interrupt")


if __name__ == "__main__":
    main()
