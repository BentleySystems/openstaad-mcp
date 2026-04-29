"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

HTTP transport security middleware.

DNS-rebinding defence for the ``--transport http`` listener.

A DNS-rebinding attacker works by:

1. Getting a victim's browser to load a page on a hostname the attacker
   controls (``attacker.com``).
2. Flipping the DNS record for that hostname to ``127.0.0.1`` after the
   page has loaded.
3. Having the page make same-origin ``fetch`` requests to
   ``http://attacker.com:<port>/mcp``. The TCP connection lands on our
   local server, but the browser treats it as same-origin and is willing
   to send custom headers (including ``Authorization``).

The hinge of the defence: the browser still sends ``Host: attacker.com``
in the HTTP request, because that is the hostname the URL named. By
validating the ``Host`` header against a small allowlist *before* auth
runs, we reject rebound requests without the attacker ever touching the
bearer-auth layer.

This middleware is deliberately narrow:
- It only runs for ``http`` ASGI scopes; lifespan and websocket events
  pass through untouched.
- It strips the port before comparing; the port is pinned by the bind
  so checking it again adds nothing.
- It rejects with HTTP 421 Misdirected Request, which is the
  semantically-correct "you are not talking to the right server" status.
"""

from __future__ import annotations

import logging
from typing import Final

logger = logging.getLogger(__name__)

#: Default allowlist for HTTP transport. Loopback only.
#:
#: ``--transport http`` binds to ``127.0.0.1`` by design, so any
#: legitimate client URL resolves to one of these names. Requests whose
#: ``Host`` header is something else did not come from a correctly
#: configured MCP client — the only realistic source is a DNS-rebinding
#: attack.
DEFAULT_ALLOWED_HOSTNAMES: Final[frozenset[str]] = frozenset(
    {
        "127.0.0.1",
        "localhost",
        "::1",
        "[::1]",
    }
)


def _extract_hostname(host_header: str) -> str:
    """Return the hostname part of an HTTP ``Host`` header value.

    Handles three forms:
    - ``example.com``
    - ``example.com:8080``
    - ``[::1]:8080`` / ``[::1]``

    An empty or malformed header returns an empty string, which the
    allowlist will then reject.
    """
    if not host_header:
        return ""

    # IPv6 literal: keep the bracketed form as the hostname identity and
    # strip only the trailing ``:port`` after the closing bracket.
    if host_header.startswith("["):
        closing = host_header.find("]")
        if closing == -1:
            return ""  # malformed
        return host_header[: closing + 1]

    # IPv4 / hostname: the port (if any) is after the final colon.
    # A value with multiple colons and no brackets is malformed IPv6.
    if host_header.count(":") > 1:
        return ""

    return host_header.rsplit(":", 1)[0]


class HostHeaderMiddleware:
    """ASGI middleware that rejects requests with an unexpected ``Host`` header.

    Intended to sit *outside* the auth middleware so that rebound requests
    never reach the bearer-token check.

    Parameters
    ----------
    app:
        The downstream ASGI application.
    allowed_hostnames:
        Iterable of hostnames to accept. Matched case-insensitively and
        with the port stripped from the incoming header. Defaults to
        :data:`DEFAULT_ALLOWED_HOSTNAMES` (loopback only).
    """

    def __init__(
        self,
        app,
        allowed_hostnames: frozenset[str] | set[str] | tuple[str, ...] | None = None,
    ) -> None:
        self.app = app
        names = allowed_hostnames if allowed_hostnames is not None else DEFAULT_ALLOWED_HOSTNAMES
        # Normalise: lowercase, strip whitespace, drop empty entries.
        self._allowed: frozenset[str] = frozenset(
            n.strip().lower() for n in names if n and n.strip()
        )
        if not self._allowed:
            raise ValueError(
                "HostHeaderMiddleware requires at least one allowed hostname"
            )

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        host_header = ""
        for name, value in scope.get("headers", ()):
            if name == b"host":
                host_header = value.decode("latin-1")
                break

        hostname = _extract_hostname(host_header).lower()

        if hostname not in self._allowed:
            logger.warning(
                "Rejecting HTTP request with disallowed Host header %r "
                "(allowed: %s). Possible DNS-rebinding attempt.",
                host_header,
                sorted(self._allowed),
            )
            await send(
                {
                    "type": "http.response.start",
                    "status": 421,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8")],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b"Misdirected Request: Host header not in allowlist.\n",
                }
            )
            return

        await self.app(scope, receive, send)
