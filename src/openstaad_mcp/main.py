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

from openstaad_mcp.http_middleware import QueryParamTokenMiddleware, SecFetchMiddleware
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
    )
    logging.info(f"Logging initialized at {log_level} level")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    setup_logging(args.log_level)

    if args.transport == "stdio":
        # Run FastMCP server in the main thread, the COM thread will be started by the lifespan.
        mcp = create_mcp_server()
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
        mcp = create_mcp_server(fastmcp_kwargs=fastmcp_kwargs)

        # Wrap http_app so QueryParamTokenMiddleware runs BEFORE FastMCP's auth layer.
        _original_http_app = mcp.http_app

        def _patched_http_app(**kwargs):
            app = _original_http_app(**kwargs)
            return QueryParamTokenMiddleware(app)

        mcp.http_app = _patched_http_app

        try:
            mcp.run(
                transport="http",
                host="127.0.0.1",
                port=args.port,
                stateless_http=False,
                middleware=[
                    Middleware(SecFetchMiddleware),
                    Middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1"]),
                ],
            )
        except KeyboardInterrupt:
            logging.info("Shutting down MCP server due to keyboard interrupt")


if __name__ == "__main__":
    main()
