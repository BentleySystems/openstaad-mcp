"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Tests for the Sec-Fetch-Site security middleware.
"""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from openstaad_mcp.http_middleware import SecFetchMiddleware

# ── Test helpers ──────────────────────────────────────────────────


def _homepage(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


@pytest.fixture
def client() -> TestClient:
    """Starlette test client with SecFetchMiddleware applied."""
    app = Starlette(routes=[Route("/", _homepage)])
    app.add_middleware(SecFetchMiddleware)
    return TestClient(app, raise_server_exceptions=False)


# ── Allowed requests ─────────────────────────────────────────────


class TestAllowedRequests:
    """Requests that should pass through the middleware."""

    def test_no_sec_fetch_header(self, client: TestClient) -> None:
        """Non-browser clients (curl, MCP clients) omit the header."""
        r = client.get("/")
        assert r.status_code == 200
        assert r.text == "ok"

    def test_sec_fetch_site_none(self, client: TestClient) -> None:
        """Direct navigation or non-browser requests send 'none'."""
        r = client.get("/", headers={"sec-fetch-site": "none"})
        assert r.status_code == 200
        assert r.text == "ok"

    def test_sec_fetch_site_same_origin(self, client: TestClient) -> None:
        """Same-origin requests are safe."""
        r = client.get("/", headers={"sec-fetch-site": "same-origin"})
        assert r.status_code == 200
        assert r.text == "ok"

    def test_empty_sec_fetch_header(self, client: TestClient) -> None:
        """Empty header value should be treated as absent (allowed)."""
        r = client.get("/", headers={"sec-fetch-site": ""})
        assert r.status_code == 200
        assert r.text == "ok"


# ── Blocked requests ─────────────────────────────────────────────


class TestBlockedRequests:
    """Requests that must be rejected by the middleware."""

    def test_cross_site_blocked(self, client: TestClient) -> None:
        """Cross-site requests (malicious web page) must be rejected."""
        r = client.get("/", headers={"sec-fetch-site": "cross-site"})
        assert r.status_code == 403
        assert "Forbidden" in r.text

    def test_same_site_blocked(self, client: TestClient) -> None:
        """Same-site (sibling sub-domain) requests must be rejected."""
        r = client.get("/", headers={"sec-fetch-site": "same-site"})
        assert r.status_code == 403
        assert "Forbidden" in r.text

    def test_cross_site_post_blocked(self, client: TestClient) -> None:
        """POST requests with cross-site are also blocked."""
        r = client.post("/", headers={"sec-fetch-site": "cross-site"})
        assert r.status_code == 403

    def test_same_site_post_blocked(self, client: TestClient) -> None:
        """POST requests with same-site are also blocked."""
        r = client.post("/", headers={"sec-fetch-site": "same-site"})
        assert r.status_code == 403


# ── Response details ─────────────────────────────────────────────


class TestResponseDetails:
    """Verify the blocked response content."""

    def test_blocked_response_is_plain_text(self, client: TestClient) -> None:
        r = client.get("/", headers={"sec-fetch-site": "cross-site"})
        assert r.status_code == 403
        assert "text/plain" in r.headers.get("content-type", "")

    def test_blocked_response_contains_reason(self, client: TestClient) -> None:
        r = client.get("/", headers={"sec-fetch-site": "cross-site"})
        assert "cross-origin" in r.text.lower()
