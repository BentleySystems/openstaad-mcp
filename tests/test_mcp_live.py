"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Live MCP integration tests — exercise the real server over stdio transport.

These tests spawn the actual MCP server as a subprocess using fastmcp's
stdio client, then call tools exactly as an AI agent would.  This catches
issues invisible to unit tests:

    - evaluator.wasm binary freshness (the unit tests always use whatever
      wasm is on disk, but never verify the MCP server loads it correctly)
    - JSON-RPC framing and content-type negotiation
    - Tool argument validation in the MCP layer
    - Consent-gate elicitation flow (blocked by default, no ctx in tests)
    - End-to-end Host.getFunctions() hardening from the LLM's perspective

Requirements:
    - A running STAAD.Pro instance with an open model (for COM tests).
    - The openstaad-mcp package installed in the current venv.

Run:
    pytest tests/test_mcp_live.py -v --timeout=30

Skip:
    All tests are marked ``integration`` — they are skipped by default
    unless you run with ``-m integration`` or ``--run-integration``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastmcp import Client

# ---------------------------------------------------------------------------
# Marker — all tests require a live STAAD.Pro
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Server command — same as mcp.json but explicit
# ---------------------------------------------------------------------------

_VENV_PYTHON = str(
    Path(__file__).resolve().parents[1] / ".venv" / "Scripts" / "python"
)
_SERVER_CMD = [_VENV_PYTHON, "-m", "openstaad_mcp.main"]
_SERVER_CWD = str(Path(__file__).resolve().parents[1])


def _make_client() -> Client:
    """Create a fastmcp stdio Client that spawns the MCP server."""
    from fastmcp.client.transports import StdioTransport

    transport = StdioTransport(
        command=_SERVER_CMD[0],
        args=_SERVER_CMD[1:],
        cwd=_SERVER_CWD,
    )
    return Client(transport=transport)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def mcp():
    """Yield a connected MCP client. Tears down the subprocess on exit."""
    client = _make_client()
    async with client:
        yield client


# ---------------------------------------------------------------------------
# 1. Smoke tests — server starts, lists tools, basic call
# ---------------------------------------------------------------------------


class TestSmoke:
    @pytest.mark.asyncio
    async def test_server_starts_and_lists_tools(self, mcp: Client) -> None:
        tools = await mcp.list_tools()
        names = {t.name for t in tools}
        assert "execute_code" in names
        assert "get_status" in names
        assert "discover_api" in names
        assert "list_instances" in names

    @pytest.mark.asyncio
    async def test_get_status_returns_connection_info(self, mcp: Client) -> None:
        result = await mcp.call_tool("get_status", {})
        # fastmcp returns a list of content blocks
        text = _extract_text(result)
        data = json.loads(text)
        # Should have 'connected' key regardless of STAAD being open
        assert "connected" in data


# ---------------------------------------------------------------------------
# 2. Execute-code tests (require STAAD.Pro)
# ---------------------------------------------------------------------------


class TestExecuteCode:
    @pytest.mark.asyncio
    async def test_simple_expression(self, mcp: Client) -> None:
        result = await mcp.call_tool("execute_code", {"code": "1 + 2"})
        data = _parse_execute_result(result)
        assert data["success"], data.get("error")
        assert data["result"] == 3

    @pytest.mark.asyncio
    async def test_staad_get_base_unit(self, mcp: Client) -> None:
        result = await mcp.call_tool(
            "execute_code", {"code": "staad.GetBaseUnit()"}
        )
        data = _parse_execute_result(result)
        assert data["success"], data.get("error")
        assert isinstance(data["result"], str)

    @pytest.mark.asyncio
    async def test_staad_geometry_node_count(self, mcp: Client) -> None:
        result = await mcp.call_tool(
            "execute_code", {"code": "staad.Geometry.GetNodeCount()"}
        )
        data = _parse_execute_result(result)
        assert data["success"], data.get("error")
        assert isinstance(data["result"], int)
        assert data["result"] >= 0

    @pytest.mark.asyncio
    async def test_console_log_captured(self, mcp: Client) -> None:
        result = await mcp.call_tool(
            "execute_code",
            {"code": "console.log('mcp-live-test'); return 42;"},
        )
        data = _parse_execute_result(result)
        assert data["success"], data.get("error")
        assert data["result"] == 42
        assert "mcp-live-test" in data.get("stdout", "")

    @pytest.mark.asyncio
    async def test_js_error_returns_user_error(self, mcp: Client) -> None:
        result = await mcp.call_tool(
            "execute_code", {"code": "throw new Error('deliberate')"}
        )
        data = _parse_execute_result(result)
        assert not data["success"]
        assert "deliberate" in (data.get("error") or "")


# ---------------------------------------------------------------------------
# 3. Security hardening — verified end-to-end through MCP
# ---------------------------------------------------------------------------


class TestHardeningViaMCP:
    """These tests verify the evaluator.js hardening from the perspective
    of an AI agent calling execute_code through the real MCP protocol.
    This is the definitive test — if it passes here, the deployed server
    is safe."""

    @pytest.mark.asyncio
    async def test_host_get_functions_neutered(self, mcp: Client) -> None:
        """Host.getFunctions() must return empty object — no raw fn refs."""
        result = await mcp.call_tool(
            "execute_code",
            {"code": "return Object.keys(Host.getFunctions())"},
        )
        data = _parse_execute_result(result)
        assert data["success"], data.get("error")
        assert data["result"] == [], f"Leaked keys: {data['result']}"

    @pytest.mark.asyncio
    async def test_host_functions_array_empty(self, mcp: Client) -> None:
        result = await mcp.call_tool(
            "execute_code",
            {
                "code": (
                    "return Array.isArray(Host.__hostFunctions) "
                    "? Host.__hostFunctions.length : 'not array'"
                )
            },
        )
        data = _parse_execute_result(result)
        assert data["success"], data.get("error")
        assert data["result"] == 0

    @pytest.mark.asyncio
    async def test_invoke_func_rejects_negative_offset(self, mcp: Client) -> None:
        """Negative offset must throw JS error, NOT reach CFFI."""
        result = await mcp.call_tool(
            "execute_code",
            {
                "code": (
                    "try { Host.invokeFunc('com_get', -1); return 'REACHED CFFI'; }"
                    " catch(e) { return e.message; }"
                )
            },
        )
        data = _parse_execute_result(result)
        assert data["success"], data.get("error")
        assert data["result"] == "invalid memory offset", f"Got: {data['result']}"

    @pytest.mark.asyncio
    async def test_fetch_neutered(self, mcp: Client) -> None:
        result = await mcp.call_tool(
            "execute_code", {"code": "typeof fetch"}
        )
        data = _parse_execute_result(result)
        assert data["success"], data.get("error")
        assert data["result"] == "undefined"

    @pytest.mark.asyncio
    async def test_no_process_global(self, mcp: Client) -> None:
        result = await mcp.call_tool(
            "execute_code", {"code": "typeof process"}
        )
        data = _parse_execute_result(result)
        assert data["success"], data.get("error")
        assert data["result"] == "undefined"

    @pytest.mark.asyncio
    async def test_no_require(self, mcp: Client) -> None:
        result = await mcp.call_tool(
            "execute_code", {"code": "typeof require"}
        )
        data = _parse_execute_result(result)
        assert data["success"], data.get("error")
        assert data["result"] == "undefined"


# ---------------------------------------------------------------------------
# 4. Allowlist / denylist enforcement via MCP
# ---------------------------------------------------------------------------


class TestAllowlistViaMCP:
    @pytest.mark.asyncio
    async def test_disallowed_sub_object_rejected(self, mcp: Client) -> None:
        result = await mcp.call_tool(
            "execute_code",
            {"code": "staad.NotRealSubObject.Whatever()"},
        )
        data = _parse_execute_result(result)
        assert not data["success"]
        err = (data.get("error") or "").lower()
        assert "not allowed" in err or "not a function" in err

    @pytest.mark.asyncio
    async def test_denied_method_rejected(self, mcp: Client) -> None:
        result = await mcp.call_tool(
            "execute_code", {"code": "staad.Run()"}
        )
        data = _parse_execute_result(result)
        assert not data["success"]
        assert "not allowed" in (data.get("error") or "").lower()

    @pytest.mark.asyncio
    async def test_destructive_method_blocked_without_consent(
        self, mcp: Client
    ) -> None:
        """Without MCP elicitation context, destructive ops are refused."""
        result = await mcp.call_tool(
            "execute_code", {"code": "staad.SaveModel()"}
        )
        data = _parse_execute_result(result)
        assert not data["success"]
        # Either "blocked" (sandbox-level) or "destructive" (pre-flight)
        err = (data.get("error") or "").lower()
        assert "blocked" in err or "destructive" in err or "approve" in err


# ---------------------------------------------------------------------------
# 5. Protocol-level edge cases
# ---------------------------------------------------------------------------


class TestProtocolEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_code_string(self, mcp: Client) -> None:
        """Empty code should return undefined/null, not crash."""
        result = await mcp.call_tool("execute_code", {"code": ""})
        data = _parse_execute_result(result)
        # May succeed with null or fail with a parse error — either is fine.
        # Must NOT crash the server.
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_very_long_code_rejected(self, mcp: Client) -> None:
        """Code exceeding the byte limit must be rejected cleanly."""
        # Default MAX_CODE_BYTES is 256 KiB — send 300 KB.
        code = "// " + "x" * 300_000
        result = await mcp.call_tool("execute_code", {"code": code})
        data = _parse_execute_result(result)
        assert not data["success"]
        assert "exceeds" in (data.get("error") or "").lower()

    @pytest.mark.asyncio
    async def test_unicode_code_works(self, mcp: Client) -> None:
        result = await mcp.call_tool(
            "execute_code", {"code": "return '日本語テスト'"}
        )
        data = _parse_execute_result(result)
        assert data["success"], data.get("error")
        assert data["result"] == "日本語テスト"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_text(result) -> str:
    """Extract text content from fastmcp CallToolResult."""
    # fastmcp 3.x returns CallToolResult with .content list
    if hasattr(result, "content"):
        for item in result.content:
            if hasattr(item, "text"):
                return item.text
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        for item in result:
            if hasattr(item, "text"):
                return item.text
    raise ValueError(f"Cannot extract text from result: {type(result)}")


def _parse_execute_result(result) -> dict:
    """Parse an execute_code tool result into a dict."""
    # Prefer structured_content if available (fastmcp 3.x)
    if hasattr(result, "structured_content") and result.structured_content:
        return result.structured_content
    text = _extract_text(result)
    return json.loads(text)
