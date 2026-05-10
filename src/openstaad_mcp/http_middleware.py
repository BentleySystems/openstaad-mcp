"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

HTTP security middleware for the OpenSTAAD MCP server.

Provides ``SecFetchMiddleware``, a Starlette middleware that rejects
browser-initiated cross-origin requests based on the ``Sec-Fetch-Site``
header.  This is a defense-in-depth layer on top of the MCP SDK's
built-in ``TransportSecurityMiddleware`` (Host / Origin validation).

The ``Sec-Fetch-Site`` header is set by browsers automatically and
cannot be spoofed by JavaScript.  Filtering on it ensures that even if
DNS-rebinding or other browser tricks bypass Host/Origin checks, the
request is still rejected.

Allowed values:

- **``same-origin``** — request originates from the same origin.
- **``none``** — request is a direct navigation or non-browser client
  (curl, Python, MCP clients).  This is the typical case for MCP.
- **(absent)** — older browsers or non-browser clients may omit the
  header entirely; these are allowed.

Blocked values:

- **``cross-site``** — request from a completely different site.
- **``same-site``** — request from a sibling sub-domain (still
  potentially malicious for localhost services).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# Values that indicate the request was initiated by a browser from a
# different origin — these MUST be rejected for localhost services.
_BLOCKED_SEC_FETCH_SITE_VALUES = frozenset({"cross-site", "same-site"})


class SecFetchMiddleware(BaseHTTPMiddleware):
    """Reject HTTP requests with dangerous ``Sec-Fetch-Site`` values.

    This middleware blocks browser-initiated cross-origin requests as a
    defense-in-depth measure against DNS rebinding and CSRF attacks
    targeting the localhost MCP endpoint.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        sec_fetch_site = request.headers.get("sec-fetch-site", "")

        if sec_fetch_site in _BLOCKED_SEC_FETCH_SITE_VALUES:
            return Response(
                content="Forbidden: cross-origin requests are not allowed.",
                status_code=403,
                media_type="text/plain",
            )

        return await call_next(request)


class QueryParamTokenMiddleware:
    """Promote a ``?token=`` query parameter to an Authorization Bearer header.

    This allows clients that cannot set custom HTTP headers (e.g. the Bentley
    Copilot SDK which only accepts a URL string) to authenticate by appending
    the token as a query parameter.  If an Authorization header is already
    present, the query parameter is ignored.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    def __getattr__(self, name: str):
        """Proxy attribute access to the wrapped app (e.g. app.state)."""
        return getattr(self.app, name)

    async def __call__(self, scope, receive, send):  # type: ignore[no-untyped-def]
        if scope["type"] == "http":
            raw_headers = scope.get("headers", [])
            has_auth = any(k == b"authorization" for k, _ in raw_headers)
            if not has_auth:
                qs = scope.get("query_string", b"").decode()
                for part in qs.split("&"):
                    if part.startswith("token="):
                        token = part[6:]  # len("token=") == 6
                        scope["headers"] = [
                            *raw_headers,
                            (b"authorization", f"Bearer {token}".encode()),
                        ]
                        break
        await self.app(scope, receive, send)
