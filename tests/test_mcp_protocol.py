"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

MCP protocol conformance tests.

Uses the FastMCP client to verify that the server
correctly lists tools and responds to tool calls.
"""

import asyncio

import pytest
from fastmcp import Client

# These tests require a running server instance on localhost.
# They are designed to be run manually or in a CI step that starts
# the server in the background first.
#
# To run locally:
#   1. python -m openstaad_mcp.main --port 18120
#   2. pytest tests/test_mcp_protocol.py -v

SERVER_URL = "http://127.0.0.1:18120/mcp"


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.mark.skip(reason="Requires a running MCP server instance")
class TestMCPProtocol:
    """MCP protocol-level tests against a live server."""

    @pytest.mark.asyncio
    async def test_list_tools(self):
        async with Client(SERVER_URL) as client:
            tools = await client.list_tools()
            tool_names = {t.name for t in tools}
            assert "openstaad_discover_api" in tool_names
            assert "openstaad_execute_code" in tool_names
            assert "openstaad_get_status" in tool_names

    @pytest.mark.asyncio
    async def test_get_status(self):
        async with Client(SERVER_URL) as client:
            result = await client.call_tool("openstaad_get_status", {})
            # Should return structured content with connection info
            assert result is not None

    @pytest.mark.asyncio
    async def test_describe_api_overview(self):
        async with Client(SERVER_URL) as client:
            result = await client.call_tool("openstaad_discover_api", {})
            assert result is not None

    @pytest.mark.asyncio
    async def test_describe_api_module(self):
        async with Client(SERVER_URL) as client:
            result = await client.call_tool("openstaad_discover_api", {"module": "geometry"})
            assert result is not None

    @pytest.mark.asyncio
    async def test_execute_code_simple(self):
        async with Client(SERVER_URL) as client:
            result = await client.call_tool("openstaad_execute_code", {"code": "result = 1 + 2"})
            assert result is not None

    @pytest.mark.asyncio
    async def test_execute_code_blocked(self):
        async with Client(SERVER_URL) as client:
            result = await client.call_tool("openstaad_execute_code", {"code": "import os"})
            # Should return an error, not crash
            assert result is not None
