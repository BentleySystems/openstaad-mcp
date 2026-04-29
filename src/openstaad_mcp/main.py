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
import threading
import time
import warnings

from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
from starlette.middleware import Middleware

from openstaad_mcp.http_security import DEFAULT_ALLOWED_HOSTNAMES, HostHeaderMiddleware
from openstaad_mcp.ots_delivery import OTSDeliveryError, deliver_token_via_ots
from openstaad_mcp.server import create_mcp_server

# HTTP-only flags and their defaults. Used both to populate argparse
# defaults and to detect accidental use of HTTP flags in stdio mode.
# ``allowed_hosts`` is a list so argparse can append multiple values.
_HTTP_ONLY_DEFAULTS: dict[str, object] = {
    "port": 18120,
    "ots_base_url": "https://uk.onetimesecret.com",
    "allowed_host": None,
}

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
        "--ots-base-url",
        type=str,
        default=_HTTP_ONLY_DEFAULTS["ots_base_url"],
        help=(
            "[http] OneTimeSecret regional endpoint "
            f"(default: {_HTTP_ONLY_DEFAULTS['ots_base_url']})"
        ),
    )
    parser.add_argument(
        "--allowed-host",
        action="append",
        default=None,  # post-process below so repeat-flag behaviour is predictable
        metavar="HOSTNAME",
        help=(
            "[http] Additional hostname to accept in the Host header. "
            "May be repeated. Loopback names (127.0.0.1, localhost, ::1) "
            "are always accepted; use this flag to add tunnel hostnames, "
            "reverse-proxy names, etc. Defeats DNS rebinding."
        ),
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

    # Normalise: after the "flag used in stdio?" check, collapse the
    # None default for --allowed-host into an empty list so later code
    # can iterate it without a None-guard.
    if args.allowed_host is None:
        args.allowed_host = []

    return args


def setup_logging(log_level: str) -> None:
    """Configure logging with the given log level and file path."""
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
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
            mcp.run(transport="stdio")
        except KeyboardInterrupt:
            logging.info("Shutting down MCP server due to keyboard interrupt")

    else:  # http
        # HTTP transport requires authenticated access.
        # A bearer token is auto-generated and delivered via a
        # one-time link (OneTimeSecret).  The raw token never
        # appears in logs or on the CLI.

        # Generate a strong random bearer token (never on CLI).
        token = secrets.token_urlsafe(32)

        # Push token to OTS as a one-time secret (no email — guest
        # endpoints cannot send mail without an OTS account).  The
        # share URL is displayed prominently after server startup.
        ots_share_url: str | None = None
        try:
            result = deliver_token_via_ots(
                token, ots_base_url=args.ots_base_url
            )
            logging.info("Bearer token stored as one-time secret")
            ots_share_url = result.share_url
        except OTSDeliveryError as exc:
            logging.warning("OTS delivery failed (%s) — raw token fallback", exc)

        fastmcp_kwargs = {
            "auth": StaticTokenVerifier(
                tokens={token: {"client_id": "authorized-user", "scopes": ["read:data"]}},
                required_scopes=["read:data"],
            )
        }
        mcp = create_mcp_server(fastmcp_kwargs=fastmcp_kwargs)

        # DNS-rebinding defence. Reject requests whose Host
        # header is not in the allowlist *before* auth runs. Loopback
        # names are always accepted; --allowed-host adds more (tunnel
        # hostnames, reverse-proxy names, etc).
        allowed_hostnames = frozenset(DEFAULT_ALLOWED_HOSTNAMES) | {
            h.strip().lower() for h in args.allowed_host if h and h.strip()
        }
        http_middleware = [
            Middleware(HostHeaderMiddleware, allowed_hostnames=allowed_hostnames),
        ]
        logging.info(
            "HTTP Host allowlist: %s", sorted(allowed_hostnames)
        )

        # Schedule a prominent auth banner to print AFTER the
        # FastMCP splash / uvicorn startup noise has settled.
        def _deferred_auth_banner() -> None:
            time.sleep(3)

            from rich.console import Console, Group
            from rich.panel import Panel
            from rich.text import Text

            server_url = f"http://127.0.0.1:{args.port}/mcp"

            # Build auth section
            if ots_share_url:
                auth_lines = Text.assemble(
                    ("Open this ONE-TIME link to reveal your bearer token:\n", ""),
                    (ots_share_url, f"bold underline link {ots_share_url}"),
                    ("\n\n(Link expires after first view or 24 hours)", "dim"),
                )
            else:
                auth_lines = Text.assemble(
                    ("Copy this bearer token (will NOT be shown again):\n", ""),
                    (token, "bold"),
                )

            # Build mcp.json snippet
            json_snippet = Text.assemble(
                ('{"type":"http","url":"', "dim"),
                (server_url, "dim"),
                ('",\n "headers":{"Authorization":"Bearer <TOKEN>"}}', "dim"),
            )

            content = Group(
                Text("🔐  AUTHENTICATION", style="bold yellow"),
                Text(""),
                auth_lines,
                Text(""),
                Text.assemble(("Server: ", ""), (server_url, "bold")),
                Text(""),
                Text("mcp.json snippet:", style=""),
                json_snippet,
            )

            panel = Panel(
                content,
                border_style="bright_yellow",
                padding=(1, 2),
                width=74,
            )

            console = Console(stderr=True)
            console.print("\n", panel, "\n")

        threading.Thread(
            target=_deferred_auth_banner, daemon=True, name="auth-banner"
        ).start()

        try:
            mcp.run(
                transport="http",
                host="127.0.0.1",
                port=args.port,
                stateless_http=True,
                middleware=http_middleware,
            )
        except KeyboardInterrupt:
            logging.info("Shutting down MCP server due to keyboard interrupt")


if __name__ == "__main__":
    main()
