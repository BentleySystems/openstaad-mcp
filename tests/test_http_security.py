"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Tests for ``HostHeaderMiddleware`` — DNS-rebinding defence via Host header validation.

The middleware must reject HTTP requests whose ``Host`` header is not
in the configured allowlist, without ever invoking the downstream app
(which in real deployment would include the bearer-auth middleware).
"""

from __future__ import annotations

from typing import Any

import pytest

from openstaad_mcp.http_security import (
    DEFAULT_ALLOWED_HOSTNAMES,
    HostHeaderMiddleware,
    _extract_hostname,
)


# ---------------------------------------------------------------------------
# ASGI harness
# ---------------------------------------------------------------------------


class _RecordingApp:
    """Minimal ASGI app that records invocation and returns 200 OK."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, scope, receive, send):
        self.calls.append({"scope": scope})
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"inner"})


def _make_scope(host_header: bytes | None, scope_type: str = "http") -> dict[str, Any]:
    headers: list[tuple[bytes, bytes]] = []
    if host_header is not None:
        headers.append((b"host", host_header))
    return {
        "type": scope_type,
        "method": "POST",
        "path": "/mcp",
        "headers": headers,
    }


async def _drive(middleware: HostHeaderMiddleware, scope: dict[str, Any]) -> dict[str, Any]:
    """Invoke the middleware and collect the single response it produced."""
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:  # pragma: no cover - unused
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    await middleware(scope, receive, send)

    start = next((m for m in sent if m["type"] == "http.response.start"), None)
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return {"start": start, "body": body, "messages": sent}


# ---------------------------------------------------------------------------
# _extract_hostname
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("127.0.0.1:18120", "127.0.0.1"),
        ("127.0.0.1", "127.0.0.1"),
        ("localhost:8080", "localhost"),
        ("localhost", "localhost"),
        ("[::1]:18120", "[::1]"),
        ("[::1]", "[::1]"),
        ("example.com", "example.com"),
        ("example.com:443", "example.com"),
        ("", ""),
        # Malformed IPv6 without brackets → reject.
        ("::1:18120", ""),
        # Malformed bracketed form missing closing bracket → reject.
        ("[::1:18120", ""),
    ],
)
def test_extract_hostname(raw: str, expected: str) -> None:
    assert _extract_hostname(raw) == expected


# ---------------------------------------------------------------------------
# Allowlist behaviour
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize(
    "host_header",
    [
        b"127.0.0.1:18120",
        b"127.0.0.1",
        b"localhost:18120",
        b"localhost",
        b"[::1]:18120",
        b"[::1]",
    ],
)
async def test_default_allowlist_accepts_loopback(host_header: bytes) -> None:
    inner = _RecordingApp()
    mw = HostHeaderMiddleware(inner)

    result = await _drive(mw, _make_scope(host_header))

    assert len(inner.calls) == 1, "inner app should have been called for allowlisted host"
    assert result["start"]["status"] == 200
    assert result["body"] == b"inner"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "host_header",
    [
        b"attacker.com",
        b"attacker.com:18120",
        b"staad-mcp.example.com",
        b"",  # empty header
        b"127.0.0.1.nip.io",  # rebinding classic: resolves to 127.0.0.1 but header differs
    ],
)
async def test_default_allowlist_rejects_foreign_host(host_header: bytes) -> None:
    inner = _RecordingApp()
    mw = HostHeaderMiddleware(inner)

    result = await _drive(mw, _make_scope(host_header))

    assert inner.calls == [], "downstream app must not be invoked for rejected host"
    assert result["start"]["status"] == 421
    # The response names the problem but does not echo the attacker-controlled header.
    assert b"Misdirected" in result["body"]


@pytest.mark.anyio
async def test_missing_host_header_rejected() -> None:
    inner = _RecordingApp()
    mw = HostHeaderMiddleware(inner)

    result = await _drive(mw, _make_scope(None))

    assert inner.calls == []
    assert result["start"]["status"] == 421


@pytest.mark.anyio
async def test_custom_allowlist_accepts_extra_hostname() -> None:
    inner = _RecordingApp()
    mw = HostHeaderMiddleware(
        inner, allowed_hostnames=frozenset({"my-tunnel.example.com"})
    )

    result = await _drive(mw, _make_scope(b"my-tunnel.example.com:18120"))

    assert len(inner.calls) == 1
    assert result["start"]["status"] == 200


@pytest.mark.anyio
async def test_custom_allowlist_still_rejects_foreign_host() -> None:
    inner = _RecordingApp()
    mw = HostHeaderMiddleware(
        inner, allowed_hostnames=frozenset({"my-tunnel.example.com"})
    )

    result = await _drive(mw, _make_scope(b"attacker.com"))

    assert inner.calls == []
    assert result["start"]["status"] == 421


@pytest.mark.anyio
async def test_case_insensitive_match() -> None:
    inner = _RecordingApp()
    mw = HostHeaderMiddleware(inner)

    result = await _drive(mw, _make_scope(b"LOCALHOST:18120"))

    assert len(inner.calls) == 1
    assert result["start"]["status"] == 200


@pytest.mark.anyio
async def test_non_http_scope_passes_through() -> None:
    """Lifespan / websocket scopes must bypass the middleware entirely."""
    inner = _RecordingApp()
    mw = HostHeaderMiddleware(inner)

    # Lifespan scope has no ``headers`` and must not be rejected.
    scope = {"type": "lifespan"}

    async def receive() -> dict[str, Any]:
        return {"type": "lifespan.startup"}

    async def send(message: dict[str, Any]) -> None:  # pragma: no cover - inner records via calls
        pass

    await mw(scope, receive, send)

    assert len(inner.calls) == 1
    assert inner.calls[0]["scope"]["type"] == "lifespan"


def test_empty_allowlist_rejected_at_construction() -> None:
    with pytest.raises(ValueError, match="at least one allowed hostname"):
        HostHeaderMiddleware(_RecordingApp(), allowed_hostnames=frozenset())


def test_default_allowlist_contents() -> None:
    """Guard against accidental widening of the default loopback allowlist."""
    assert DEFAULT_ALLOWED_HOSTNAMES == frozenset(
        {"127.0.0.1", "localhost", "::1", "[::1]"}
    )


# ---------------------------------------------------------------------------
# CLI integration: --allowed-host parsing
# ---------------------------------------------------------------------------


def test_cli_allowed_host_defaults_to_empty_list_when_absent() -> None:
    from openstaad_mcp.main import parse_args

    args = parse_args(["--transport", "http"])
    assert args.allowed_host == []


def test_cli_allowed_host_accepts_multiple_values() -> None:
    from openstaad_mcp.main import parse_args

    args = parse_args(
        [
            "--transport",
            "http",
            "--allowed-host",
            "tunnel.example.com",
            "--allowed-host",
            "proxy.internal",
        ]
    )
    assert args.allowed_host == ["tunnel.example.com", "proxy.internal"]


def test_cli_allowed_host_in_stdio_mode_warns() -> None:
    import warnings as _warnings

    from openstaad_mcp.main import parse_args

    with _warnings.catch_warnings(record=True) as caught:
        _warnings.simplefilter("always")
        parse_args(["--allowed-host", "tunnel.example.com"])

    messages = [str(w.message) for w in caught]
    assert any("--allowed-host has no effect in stdio mode" in m for m in messages), messages


# ---------------------------------------------------------------------------
# Anyio config
# ---------------------------------------------------------------------------


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
