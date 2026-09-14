import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from openstaad_mcp.ptc.adapter import build_registry
from openstaad_mcp.ptc.namespace import ToolCallable, ToolNamespace
from openstaad_mcp.ptc.registry import CallBudget, ToolRegistry
from openstaad_mcp.ptc.runtime import PTCRuntime
from openstaad_mcp.sandbox.executor import Executor


def test_composed_workflow_returns_only_final_data(staad):
    result = PTCRuntime(Executor()).execute(
        "members = tools.geometry.get_members()\n"
        "ids = [m['id'] for m in members if m['is_horizontal']]\n"
        "ratios = tools.design.get_utilization(ids)\n"
        "[r for r in ratios if r['available'] and r['ratio'] > 0.9]",
        staad,
    )
    assert result["success"], result
    assert result["result"] == [{"member_id": 10, "ratio": 1.1, "available": True, "source_code": None}]
    assert result["stdout"] == ""
    assert result["ptc"]["tool_calls"] == 2
    assert "members" not in result
    assert staad.Geometry.GetNodeCoordinates.call_count == 4


@pytest.mark.parametrize(
    "code",
    [
        "import os",
        "getattr(tools, 'geometry')",
        "tools.__class__",
        "tools._members",
        "tools.geometry._members",
        "tools.geometry.get_nodes._invoke",
        "tools.geometry.get_nodes.__globals__",
        "tools.geometry.get_nodes.__call__",
        "tools.geometry.get_nodes._invoke = 1",
        "del tools.geometry.get_nodes._invoke",
        "tools.geometry = 1",
        "del tools.geometry",
        "tools.geometry.get_nodes = 1",
        "del tools.geometry.get_nodes",
        "tools.geometry.delete_node(1)",
        "tools.geometry.get_nodes._staad",
        "staad.Geometry.GetNodeCount()",
        "tools.geometry.get_nodes() if False else tools._members",
        "'{x._members}'.format(x=tools)",
        "await tools.geometry.get_nodes()",
        "json.codecs",
        "open('model.std', 'w')",
        "tools.geometry.get_nodes.__reduce__()",
    ],
)
def test_sandbox_rejects_escape_and_unregistered_operations(staad, code):
    response = PTCRuntime(Executor()).execute(code, staad)
    assert not response["success"], response
    staad.Geometry.GetNodeCoordinates.assert_not_called()


@pytest.mark.parametrize(
    "code",
    [
        "tools.geometry.get_nodes([True])",
        "tools.geometry.get_nodes(['1'])",
        "tools.geometry.get_nodes([0])",
        "tools.geometry.get_nodes([-1])",
        "tools.geometry.get_nodes(node_ids=[], extra=1)",
        "tools.geometry.get_nodes([], [])",
        "tools.geometry.get_nodes(node_ids=[1.0])",
        "tools.geometry.get_nodes([1] * 10001)",
        "tools.geometry.get_members(up_axis='X')",
        "tools.geometry.get_members(tolerance=-1)",
        "tools.geometry.get_members(tolerance=float('nan'))",
        "tools.analysis.get_member_forces([10], [201], ends=[])",
        "tools.analysis.get_member_forces([10], [201], ends=[True])",
        "tools.analysis.get_member_forces([10], [201], coordinate_system='other')",
        "tools.analysis.get_member_forces([10])",
    ],
)
def test_invalid_arguments_fail_before_com(staad, code):
    result = PTCRuntime(Executor()).execute(code, staad)
    assert not result["success"]
    assert "Invalid arguments" in result["error"]
    staad.Output.AreResultsAvailable.assert_not_called()
    staad.Geometry.GetNodeCoordinates.assert_not_called()


def test_input_and_tool_results_do_not_persist(staad):
    runtime = PTCRuntime(Executor())
    data = [["A"], [1]]
    first = runtime.execute(
        "input_data[1][0] = 99\nx = tools.geometry.get_nodes()\nx[0]['x'] = 42\nx", staad, input_data=data
    )
    assert first["success"]
    assert data == [["A"], [1]]
    second = runtime.execute("tools.geometry.get_nodes()[0]['x']", staad)
    assert second["result"] == 0
    assert second["ptc"]["tool_calls"] == 1
    assert not runtime.execute("x", staad)["success"]


def test_result_export_and_inline_limit(staad):
    runtime = PTCRuntime(Executor())
    code = "result = [['x' * 1000] for i in range(70)]"
    assert not runtime.execute(code, staad)["success"]
    exported = runtime.execute(code, staad, export=True)
    assert exported["success"]
    assert len(exported["result"]) == 70
    assert runtime.execute("result = 12\n99", staad)["result"] == 12


def test_registry_contract_and_budget():
    shared = {"rows": [1]}

    def query(number: int = 2) -> dict:
        """Query a record."""
        return {"number": number, "shared": shared}

    registry = ToolRegistry()
    registry.register("sample.query", query)
    for name in ("sample.query", "_private.query", "sample.query.extra"):
        with pytest.raises(ValueError):
            registry.register(name, query)
    schema = registry.discover("sample")[0]
    assert schema["description"] == "Query a record."
    assert schema["input_schema"]["properties"]["number"]["default"] == 2
    with pytest.raises(ValueError, match="Unknown PTC namespace"):
        registry.discover("absent")
    budget = CallBudget(limit=2)
    tools = registry.bind(budget)
    tools.sample.query()["shared"]["rows"].append(2)
    assert shared == {"rows": [1]}
    assert tools.sample.query(4)["number"] == 4
    with pytest.raises(ValueError, match="call limit"):
        tools.sample.query()
    assert budget.calls == 2
    assert budget.counts == {"sample.query": 2}


def test_registry_never_returns_objects():
    def query() -> object:
        return object()

    registry = ToolRegistry()
    registry.register("sample.query", query)
    with pytest.raises(TypeError):
        registry.bind(CallBudget()).sample.query()


def test_catalog_is_connection_free_and_json_serializable():
    catalog = build_registry().discover()
    assert len(catalog) == 31
    assert {x["name"].split(".")[1] for x in catalog} == {
        "geometry",
        "analysis",
        "properties",
        "loads",
        "supports",
        "design",
    }
    json.dumps(catalog)


def test_opaque_reprs_and_private_access():
    callback = ToolCallable(lambda: 1)
    namespace = ToolNamespace({"query": callback})
    assert repr(callback) == "<PTC tool>"
    assert repr(namespace) == "<PTC namespace>"
    with pytest.raises(AttributeError):
        _ = callback._invoke
    with pytest.raises(AttributeError):
        _ = namespace._members


def test_ptc_namespace_type_and_legacy_executor(staad):
    executor = Executor()
    invalid = executor.execute("1", staad, ptc_tools=Mock())
    assert not invalid.success
    assert executor.execute("staad.Geometry.GetNodeCount()", staad).result == 4
    assert not executor.execute("tools.geometry.get_nodes()", staad).success


@pytest.mark.parametrize("filename", ["critical_members.py", "member_forces.py"])
def test_delivered_examples(staad, filename):
    path = Path(__file__).resolve().parents[2] / "examples" / "ptc" / filename
    response = PTCRuntime(Executor()).execute(path.read_text(encoding="utf-8"), staad)
    assert response["success"], response
    assert response["stdout"] == ""
    assert isinstance(response["result"], dict)
