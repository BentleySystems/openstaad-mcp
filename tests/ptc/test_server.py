import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastmcp import Client

from openstaad_mcp.connection import InstanceRegistry, StaadInstance
from openstaad_mcp.server import create_mcp_server


@pytest.fixture
def instance():
    return StaadInstance(alias="staadPro1", pid=123, file_path="C:/models/test.std", version="26.0.0")


@pytest.fixture
def server(monkeypatch, staad, instance, tmp_path):
    monkeypatch.setattr(InstanceRegistry, "get_active_instances", lambda _: [instance])
    dispatch = Mock(side_effect=lambda fn, path: fn(staad))
    monkeypatch.setattr("openstaad_mcp.server.connect_and_run", dispatch)
    return create_mcp_server(allowed_dirs=[tmp_path]), dispatch


async def call(server, name, arguments):
    async with Client(server) as client:
        reply = await client.call_tool(name, arguments)
        return json.loads(reply.content[0].text)


async def test_mcp_discovery_and_execution(server):
    mcp, dispatch = server
    async with Client(mcp) as client:
        catalog = await client.list_tools()
        assert {tool.name for tool in catalog} == {
            "discover_api",
            "read_skills",
            "list_instances",
            "get_status",
            "execute_code",
            "execute_ptc",
            "discover_ptc",
        }
    tools = await call(mcp, "discover_ptc", {"namespace": "design"})
    assert {tool["name"] for tool in tools} == {"tools.design.get_utilization", "tools.design.get_member_results"}
    dispatch.assert_not_called()
    result = await call(mcp, "execute_ptc", {"code": "tools.geometry.get_node_count()"})
    assert result["success"] and result["result"] == 4
    assert dispatch.call_args.args[1] == "C:/models/test.std"
    old = await call(mcp, "execute_code", {"code": "staad.Geometry.GetNodeCount()"})
    assert old["success"] and old["result"] == 4
    assert "ptc" not in old


async def test_csv_and_xlsx_roundtrip(server, tmp_path):
    mcp, _ = server
    source = tmp_path / "input.csv"
    source.write_text("id,value\n10,12\n", encoding="utf-8")
    for suffix in ("csv", "xlsx"):
        target = tmp_path / f"export.{suffix}"
        reply = await call(
            mcp,
            "execute_ptc",
            {
                "code": "input_data[1][1] = 99\nresult = input_data",
                "input_data_path": str(source),
                "output_data_path": str(target),
            },
        )
        assert reply["success"], reply
        assert target.exists()
        assert "12" in source.read_text()
        assert isinstance(reply["result"], dict)  # Only export summary returns over MCP.
        collision = await call(mcp, "execute_ptc", {"code": "[['x']]", "output_data_path": str(target)})
        assert not collision["success"]
        overwritten = await call(
            mcp, "execute_ptc", {"code": "[['x']]", "output_data_path": str(target), "overwrite": True}
        )
        assert overwritten["success"]


async def test_filesystem_boundaries(server, tmp_path):
    mcp, dispatch = server
    source = tmp_path / "data.csv"
    source.write_text("a\n1\n")
    cases = [
        {"input_data_path": str(source), "output_data_path": str(source)},
        {"input_data_path": str(tmp_path.parent / "outside.csv")},
        {"input_data_path": r"\\server\share\data.csv"},
    ]
    for paths in cases:
        response = await call(mcp, "execute_ptc", {"code": "1", **paths})
        assert not response["success"]
    dispatch.assert_not_called()
    response = await call(
        mcp, "execute_ptc", {"code": "[['x']]", "output_data_path": str(tmp_path.parent / "outside.csv")}
    )
    assert not response["success"]


async def test_instance_selection_and_failures(server, monkeypatch, instance):
    mcp, dispatch = server
    monkeypatch.setattr(InstanceRegistry, "get_active_instances", lambda _: [])
    response = await call(mcp, "execute_ptc", {"code": "1"})
    assert "No STAAD" in response["error"]
    another = StaadInstance("staadPro2", 124, "C:/models/other.std", "26.0.0")
    monkeypatch.setattr(InstanceRegistry, "get_active_instances", lambda _: [instance, another])
    assert "Multiple instances" in (await call(mcp, "execute_ptc", {"code": "1"}))["error"]
    monkeypatch.setattr(InstanceRegistry, "resolve", lambda _, alias: 124 if alias == "staadPro2" else None)
    assert "unknown" in (await call(mcp, "execute_ptc", {"code": "1", "instance": "missing"}))["error"]
    response = await call(mcp, "execute_ptc", {"code": "1", "instance": "staadPro2"})
    assert response["success"]
    assert dispatch.call_args.args[1] == another.file_path
    dispatch.side_effect = TimeoutError()
    assert "timed out" in (await call(mcp, "execute_ptc", {"code": "1", "instance": "staadPro2"}))["error"]


@pytest.mark.integration
async def test_ptc_live_read_only_model():
    """Opt-in only: use an independent saved test model with STAAD.Pro running."""
    import os

    expected = os.environ.get("OPENSTAAD_PTC_TEST_MODEL")
    if not expected:
        pytest.skip("Set OPENSTAAD_PTC_TEST_MODEL to an independent model path")
    instances = InstanceRegistry().get_active_instances()
    matches = [i for i in instances if Path(i.file_path).resolve() == Path(expected).resolve()]
    if len(matches) != 1:
        pytest.fail("The exact independent test model must be open in one STAAD instance")
    from openstaad_mcp.connection import connect_and_run
    from openstaad_mcp.ptc.runtime import PTCRuntime
    from openstaad_mcp.sandbox.executor import Executor

    result = connect_and_run(
        lambda staad: PTCRuntime(Executor()).execute(
            "result = {'count': tools.geometry.get_member_count(), 'members': len(tools.geometry.get_members())}",
            staad,
        ),
        matches[0].file_path,
    )
    assert result["success"], result
    assert result["result"]["count"] == result["result"]["members"]
