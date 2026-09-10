import pytest

from openstaad_mcp.ptc.adapter import build_registry
from openstaad_mcp.ptc.registry import CallBudget


@pytest.fixture
def tools(staad):
    return build_registry(staad).bind(CallBudget())


def test_geometry_and_axes(tools, staad):
    assert tools.geometry.get_node_count() == 4
    assert tools.geometry.get_member_count() == 4
    assert tools.geometry.get_nodes([2, 2]) == [{"id": 2, "x": 4, "y": 0, "z": 0}]
    assert tools.geometry.get_nodes([]) == []
    assert tools.geometry.get_members([]) == []
    assert [m["id"] for m in tools.geometry.get_members() if m["is_horizontal"]] == [10, 50]
    assert [m["id"] for m in tools.geometry.get_members(up_axis="Z") if m["is_horizontal"]] == [10, 30]
    assert tools.geometry.get_members([30])[0]["length"] == 3
    assert tools.geometry.get_base_units() == {"system": "Metric", "length": "m", "force": "kN"}
    staad.GetBaseUnit.return_value = "English"
    assert tools.geometry.get_base_units()["length"] == "in"
    staad.GetBaseUnit.return_value = "unknown"
    with pytest.raises(ValueError, match="unknown base unit"):
        tools.geometry.get_base_units()


def test_properties_loads_supports(tools):
    prop = tools.properties.get_member_properties([10])[0]
    assert prop == {
        "id": 10,
        "section": "W12",
        "material": "STEEL",
        "width": 1,
        "depth": 2,
        "AX": 3,
        "AY": 4,
        "AZ": 5,
        "IZ": 6,
        "IY": 7,
        "IX": 8,
    }
    assert tools.loads.get_load_cases() == [
        {"id": 201, "title": "Load 201", "is_combination": False},
        {"id": 203, "title": "Load 203", "is_combination": False},
        {"id": 301, "title": "Load 301", "is_combination": True},
    ]
    assert len(tools.loads.get_load_cases(False)) == 2
    assert tools.supports.get_supports() == [{"node_id": 1, "type": 1, "releases": [0] * 6, "springs": [0.0] * 6}]


def test_force_mapping_and_units(tools, staad):
    assert tools.analysis.are_results_available()
    assert tools.analysis.get_units() == {
        "force": "kN",
        "moment": "kN-m",
        "displacement": "m",
        "stress": "kN/m2",
        "dimension": "m",
        "rotation": "rad",
    }
    rows = tools.analysis.get_member_forces([10, 10], [201, 203], coordinate_system="global")
    assert len(rows) == 4
    assert rows[0] == {
        "member_id": 10,
        "load_case": 201,
        "end": 0,
        "coordinate_system": "global",
        "FX": 10,
        "FY": 0,
        "FZ": 201,
        "MX": 1,
        "MY": 5,
        "MZ": 6,
    }
    assert "ratio" not in rows[0]
    staad.Output.GetMemberEndForces.assert_any_call(10, 1, 203, 1)
    assert tools.analysis.get_member_forces([10], [201], ends=[1])[0]["MX"] == 0
    assert tools.analysis.get_node_displacements([1], [201])[0]["RX"] == 4
    assert tools.analysis.get_support_reactions([1], [201])[0]["FX"] == 6
    assert tools.analysis.get_member_forces([], [201]) == []


def test_design_sentinels_are_not_passing_results(tools):
    rows = tools.design.get_utilization()
    assert rows[0]["ratio"] == 1.1
    assert rows[1]["ratio"] == 0.7
    assert rows[2] == {"member_id": 50, "ratio": None, "available": False, "source_code": -999}
    assert rows[3]["source_code"] == -1
    assert all("load_case" not in row for row in rows)


@pytest.mark.parametrize("ratio", [float("nan"), float("inf"), True, "unknown"])
def test_invalid_design_result(tools, staad, ratio):
    staad.Output.GetMemberSteelDesignRatio.side_effect = None
    staad.Output.GetMemberSteelDesignRatio.return_value = ratio
    with pytest.raises(ValueError, match="invalid steel design ratio"):
        tools.design.get_utilization([10])


def test_no_results_and_com_failure(tools, staad):
    staad.Output.AreResultsAvailable.return_value = False
    with pytest.raises(ValueError, match="unavailable"):
        tools.analysis.get_member_forces([10], [201])
    staad.Output.GetMemberEndForces.assert_not_called()
    staad.Geometry.GetNodeCount.side_effect = RuntimeError("private model path")
    with pytest.raises(ValueError, match=r"Geometry\.GetNodeCount failed") as error:
        tools.geometry.get_node_count()
    assert "private model path" not in str(error.value)


def test_row_budget_prevents_com_fanout(tools, staad):
    with pytest.raises(ValueError, match="row limit"):
        tools.analysis.get_member_forces(list(range(1, 1001)), list(range(1, 101)))
    with pytest.raises(ValueError, match="row limit"):
        tools.analysis.get_node_displacements(list(range(1, 1001)), list(range(1, 102)))
    staad.Output.GetMemberEndForces.assert_not_called()
    staad.Output.GetNodeDisplacements.assert_not_called()


def test_invalid_upstream_shape_does_not_silently_truncate(tools, staad):
    staad.Output.GetMemberEndForces.side_effect = None
    staad.Output.GetMemberEndForces.return_value = [1, 2]
    with pytest.raises(ValueError):
        tools.analysis.get_member_forces([10], [201])
    staad.Geometry.GetBeamList.return_value = [False]
    with pytest.raises(ValueError):
        tools.geometry.get_members()
