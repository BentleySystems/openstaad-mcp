"""Domain contracts for the OpenStaadPython-inspired queries."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from openstaad_mcp.ptc.adapter import build_registry
from openstaad_mcp.ptc.base import values_record
from openstaad_mcp.ptc.registry import CallBudget
from openstaad_mcp.ptc.runtime import PTCRuntime
from openstaad_mcp.sandbox.executor import Executor


@pytest.fixture
def extended(staad):
    additions = {
        "Geometry": {
            "GetPlateList": (),
            "GetSolidList": (),
            "GetPlateIncidence": (1, 2, 3, 0),
            "GetSolidIncidence": (1, 2, 3, 4, 5, 6, 7, 8),
            "GetGroupNames": ("_FRAME",),
            "GetGroupEntities": (10, 30),
            "GetBeamsConnectedAtNode": (10, 30),
            "GetBeamLength": 4.0,
        },
        "Property": {
            "GetBeamPropertyAll": tuple(range(1, 11)),
            "GetPlateMaterialName": "CONCRETE",
            "GetPlateThickness": (0.1, 0.2, 0.3, 0.4),
            "GetMaterialProperty": (200e6, 0.3, 76.8, 1.2e-5, 0.05),
            "GetMemberReleaseSpecEx": ([0, 1, -1, -2, -3, 0], [1, 2, 3, 4, 5, 6], 0.7, [0.1, 0.2, 0.3]),
        },
        "Load": {
            "GetLoadAndFactorForCombination": ((201, 203), (1.2, -0.9, 0.0)),
            "GetReferenceLoadCaseNumbers": (7, 9),
            "GetReferenceLoadCaseTitle": "Reference dead",
            "GetReferenceLoadType": 1,
        },
        "Output": {
            "GetIntermediateMemberForcesAtDistance": (1, -2, 3, -4, 5, -6),
            "GetMinMaxAxialForce": (-10, 0.2, 20, 3.2),
            "GetMinMaxShearForce": (-30, 0.3, 40, 3.3),
            "GetMinMaxBendingMoment": (-50, 0.4, 60, 3.4),
            "GetMaxSectionDisplacement": (-0.01, 2.0),
            "GetAllPlateCenterStressesAndMoments": (1, 2, 3, 4, 5, 6, 7, 8),
            "GetPlateCenterNormalPrincipalStresses": (10, -20, 30, -40),
            "GetPlateCenterVonMisesStresses": (25, 45),
            "GetMemberSteelDesignResults": ("AISC", "PASS", 1.05, 1.1, 203, 2.0, "H1", "W12", (90, 80, 70), 60),
        },
    }
    for group, methods in additions.items():
        for name, value in methods.items():
            setattr(getattr(staad, group), name, Mock(return_value=value))
    return staad


@pytest.fixture
def tools(extended):
    return build_registry(extended).bind(CallBudget())


def test_plate_and_solid_incidence(tools, extended):
    extended.Geometry.GetPlateList.return_value = (101, 103)
    extended.Geometry.GetPlateIncidence.side_effect = [(1, 2, 3, 0), (3, 4, 5, 6)]
    assert tools.geometry.get_plates() == [
        {"id": 101, "node_ids": [1, 2, 3], "node_count": 3},
        {"id": 103, "node_ids": [3, 4, 5, 6], "node_count": 4},
    ]
    assert tools.geometry.get_solids([201, 201]) == [{"id": 201, "node_slots": [1, 2, 3, 4, 5, 6, 7, 8]}]
    extended.Geometry.GetSolidIncidence.return_value = (1, 2, 3, 4, 5, 6, 0, 0)
    assert tools.geometry.get_solids([201])[0]["node_slots"][-2:] == [0, 0]


@pytest.mark.parametrize("slots", [(1, 2), (1, 2, 3, 4, 5, 6, 7, -1), (1, 2, 3, 4, 5, 6, 7, True)])
def test_invalid_solid_incidence(tools, extended, slots):
    extended.Geometry.GetSolidIncidence.return_value = slots
    with pytest.raises(ValueError, match="Invalid solid incidence"):
        tools.geometry.get_solids([201])


@pytest.mark.parametrize(
    "kind,number", [("nodes", 1), ("members", 2), ("plates", 3), ("solids", 4), ("geometry", 5), ("floor", 6)]
)
def test_group_types_and_connectivity(tools, extended, kind, number):
    assert tools.geometry.get_groups(kind) == [{"name": "_FRAME", "entity_type": kind, "entity_ids": [10, 30]}]
    extended.Geometry.GetGroupNames.assert_called_once_with(number)
    assert tools.geometry.get_connected_members([1, 1]) == [{"node_id": 1, "member_ids": [10, 30]}]
    extended.Geometry.GetBeamsConnectedAtNode.return_value = ()
    assert tools.geometry.get_connected_members([2]) == [{"node_id": 2, "member_ids": []}]


def test_property_field_order_and_release_semantics(tools, extended):
    section = tools.properties.get_member_properties_full([10])[0]
    assert section == {
        "id": 10,
        "section": "W12",
        "material": "STEEL",
        "width": 1.0,
        "depth": 2.0,
        "AX": 3.0,
        "AY": 4.0,
        "AZ": 5.0,
        "IZ": 6.0,
        "IY": 7.0,
        "IX": 8.0,
        "flange_thickness": 9.0,
        "web_thickness": 10.0,
    }
    material = tools.properties.get_material_properties(["STEEL", "STEEL"])
    assert material == [
        {
            "name": "STEEL",
            "elasticity": 200e6,
            "poisson_ratio": 0.3,
            "density": 76.8,
            "thermal_expansion": 1.2e-5,
            "damping_ratio": 0.05,
        }
    ]
    extended.Property.GetMaterialProperty.assert_called_once_with("STEEL")
    releases = tools.properties.get_member_releases([10])
    assert [r["end"] for r in releases] == [0, 1]
    assert releases[0]["release_codes"] == {"FX": 0, "FY": 1, "FZ": -1, "MX": -2, "MY": -3, "MZ": 0}
    assert releases[0]["spring_constants"]["MY"] == 5
    assert releases[0]["mp_factor"] == 0.7
    assert releases[0]["mp_factors"] == {"MX": 0.1, "MY": 0.2, "MZ": 0.3}
    assert len(tools.properties.get_member_releases([10], ends=[1, 1])) == 1
    extended.Property.GetMemberReleaseSpecEx.assert_called_with(10, 1)


def test_plate_thickness_corner_alignment(tools, extended):
    tri = tools.properties.get_plate_properties([101])[0]
    assert tri == {
        "id": 101,
        "material": "CONCRETE",
        "corners": [
            {"node_id": 1, "thickness": 0.1},
            {"node_id": 2, "thickness": 0.2},
            {"node_id": 3, "thickness": 0.3},
        ],
    }
    extended.Geometry.GetPlateIncidence.return_value = (1, 2, 3, 4)
    assert tools.properties.get_plate_properties([103])[0]["corners"][-1] == {"node_id": 4, "thickness": 0.4}


def test_combinations_preserve_trailing_factor(tools, extended):
    combination = tools.loads.get_combinations()[0]
    assert combination == {
        "id": 301,
        "title": "Load 301",
        "terms": [{"load_case": 201, "factor": 1.2}, {"load_case": 203, "factor": -0.9}],
        "trailing_factor": 0.0,
    }
    extended.Load.GetLoadAndFactorForCombination.return_value = ((201,), (1.5, 2.0))
    assert tools.loads.get_combinations([301])[0]["trailing_factor"] == 2.0
    extended.Load.GetLoadAndFactorForCombination.return_value = ((201,), (1.5,))
    assert tools.loads.get_combinations([301])[0]["trailing_factor"] is None
    extended.Load.GetLoadAndFactorForCombination.return_value = ((), ())
    assert tools.loads.get_combinations([301])[0]["terms"] == []
    extended.Load.GetLoadAndFactorForCombination.return_value = ((201, 203), (1.0,))
    with pytest.raises(ValueError, match="factor array"):
        tools.loads.get_combinations([301])
    assert tools.loads.get_reference_load_cases() == [
        {"id": 7, "title": "Reference dead", "load_type": 1},
        {"id": 9, "title": "Reference dead", "load_type": 1},
    ]


def test_stations_validate_all_members_before_results(tools, extended):
    rows = tools.analysis.get_member_forces_at_distance([10, 10], [201, 201], [0, 2, 4])
    assert len(rows) == 3
    assert rows[1] == {
        "member_id": 10,
        "load_case": 201,
        "distance": 2,
        "coordinate_system": "local",
        "FX": 1,
        "FY": -2,
        "FZ": 3,
        "MX": -4,
        "MY": 5,
        "MZ": -6,
    }
    extended.Output.GetIntermediateMemberForcesAtDistance.assert_any_call(10, 2.0, 201)
    extended.Output.GetIntermediateMemberForcesAtDistance.reset_mock()
    extended.Geometry.GetBeamLength.side_effect = [4, 1]
    with pytest.raises(ValueError, match="exceeds"):
        tools.analysis.get_member_forces_at_distance([10, 30], [201], [2])
    extended.Output.GetIntermediateMemberForcesAtDistance.assert_not_called()


def test_force_extrema_are_signed_and_per_case(tools, extended):
    rows = tools.analysis.get_member_force_extrema([10], [201, 203])
    assert len(rows) == 10
    assert rows[0] == {
        "member_id": 10,
        "load_case": 201,
        "component": "FX",
        "coordinate_system": "local",
        "min": -10,
        "min_position": 0.2,
        "max": 20,
        "max_position": 3.2,
    }
    extended.Output.GetMinMaxAxialForce.assert_any_call(10, 203)
    extended.Output.GetMinMaxShearForce.assert_any_call(10, "FY", 203)
    extended.Output.GetMinMaxBendingMoment.assert_any_call(10, "MZ", 203)
    assert len(tools.analysis.get_member_force_extrema([10], [201], ["MY", "MY"])) == 1
    displacements = tools.analysis.get_max_section_displacements([10], [201])
    assert len(displacements) == 3 and displacements[0]["displacement"] == -0.01
    assert displacements[0]["coordinate_system"] == "global"
    assert tools.analysis.get_max_section_displacements([10], [201], ["Y"])[0]["position"] == 2
    extended.Output.GetMaxSectionDisplacement.assert_called_with(10, "Y", 201)


def test_plate_results_are_distinct_fields(tools, extended):
    assert tools.analysis.get_plate_center_results([101], [201])[0] == {
        "plate_id": 101,
        "load_case": 201,
        "SQX": 1,
        "SQY": 2,
        "MX": 3,
        "MY": 4,
        "MXY": 5,
        "SX": 6,
        "SY": 7,
        "SXY": 8,
    }
    assert tools.analysis.get_plate_principal_stresses([101], [201])[0] == {
        "plate_id": 101,
        "load_case": 201,
        "top_max": 10,
        "top_min": -20,
        "bottom_max": 30,
        "bottom_min": -40,
    }
    assert tools.analysis.get_plate_von_mises_stresses([101], [201])[0] == {
        "plate_id": 101,
        "load_case": 201,
        "top": 25,
        "bottom": 45,
    }
    extended.Output.GetPlateCenterVonMisesStresses.assert_called_once_with(101, 201)


def test_detailed_design_keeps_api_status_and_allowable(tools, extended):
    result = tools.design.get_member_results([10])[0]
    assert result == {
        "member_id": 10,
        "design_code": "AISC",
        "status": "PASS",
        "ratio": 1.05,
        "allowable_ratio": 1.1,
        "critical_load_case": 203,
        "position": 2.0,
        "clause": "H1",
        "section": "W12",
        "forces": {"FX": 90, "MY": 80, "MZ": 70},
        "slenderness": 60,
    }
    # Ratio > 1 must not override a real PASS with allowable_ratio > 1.
    extended.Output.GetMemberSteelDesignResults.side_effect = RuntimeError("private path")
    with pytest.raises(ValueError, match="failed") as error:
        tools.design.get_member_results([50])
    assert "private path" not in str(error.value)


@pytest.mark.parametrize("ratio,allowable", [(-999, 1), (0.5, -1)])
def test_design_negative_sentinels(tools, extended, ratio, allowable):
    extended.Output.GetMemberSteelDesignResults.return_value = (
        "AISC",
        "PASS",
        ratio,
        allowable,
        203,
        0,
        "H1",
        "W12",
        [0, 0, 0],
        1,
    )
    with pytest.raises(ValueError, match="unavailable"):
        tools.design.get_member_results([10])


EMPTY_QUERIES = [
    "tools.geometry.get_plates([])",
    "tools.geometry.get_solids([])",
    "tools.geometry.get_connected_members([])",
    "tools.properties.get_plate_properties([])",
    "tools.properties.get_member_properties_full([])",
    "tools.properties.get_material_properties([])",
    "tools.properties.get_member_releases([])",
    "tools.loads.get_combinations([])",
    "tools.design.get_member_results([])",
    "tools.analysis.get_member_forces_at_distance([], [201], [0])",
    "tools.analysis.get_member_forces_at_distance([10], [], [0])",
    "tools.analysis.get_member_forces_at_distance([10], [201], [])",
    "tools.analysis.get_member_force_extrema([], [201])",
    "tools.analysis.get_max_section_displacements([], [201])",
    "tools.analysis.get_plate_center_results([], [201])",
    "tools.analysis.get_plate_principal_stresses([101], [])",
    "tools.analysis.get_plate_von_mises_stresses([], [])",
]


@pytest.mark.parametrize("code", EMPTY_QUERIES)
def test_empty_batches(code, extended):
    response = PTCRuntime(Executor()).execute(code, extended)
    assert response["success"] and response["result"] == [], response


@pytest.mark.parametrize(
    "code",
    [
        "tools.geometry.get_plates([True])",
        "tools.geometry.get_solids([-1])",
        "tools.geometry.get_groups('beams')",
        "tools.geometry.get_connected_members(['1'])",
        "tools.properties.get_member_properties_full([0])",
        "tools.properties.get_plate_properties([1.0])",
        "tools.properties.get_material_properties([''])",
        "tools.properties.get_material_properties(['x' * 257])",
        "tools.properties.get_member_releases([10], [2])",
        "tools.loads.get_combinations([False])",
        "tools.analysis.get_member_forces_at_distance([10], [201], [-1])",
        "tools.analysis.get_member_forces_at_distance([10], [201], [float('inf')])",
        "tools.analysis.get_member_force_extrema([10], [201], ['MX'])",
        "tools.analysis.get_max_section_displacements([10], [201], ['local_y'])",
        "tools.analysis.get_plate_center_results([101], [0])",
        "tools.analysis.get_plate_principal_stresses([101], ['201'])",
        "tools.analysis.get_plate_von_mises_stresses([101], [False])",
        "tools.design.get_member_results([0])",
    ],
)
def test_invalid_parameters_before_api(code, extended):
    result = PTCRuntime(Executor()).execute(code, extended)
    assert not result["success"] and "Invalid arguments" in result["error"]
    extended.Output.AreResultsAvailable.assert_not_called()


@pytest.mark.parametrize(
    "code",
    [
        "tools.analysis.get_member_forces_at_distance([10], [201], [0,1])",
        "tools.analysis.get_member_force_extrema([10], [201])",
        "tools.analysis.get_max_section_displacements([10], [201])",
        "tools.analysis.get_plate_center_results([101], [201,203])",
        "tools.geometry.get_groups()",
        "tools.geometry.get_connected_members([1])",
        "tools.loads.get_combinations()",
    ],
)
def test_aggregate_row_budgets(monkeypatch, code, extended):
    monkeypatch.setattr("openstaad_mcp.ptc.base.MAX_ROWS", 1)
    result = PTCRuntime(Executor()).execute(code, extended)
    assert not result["success"] and "row limit" in result["error"]


@pytest.mark.parametrize(
    "code",
    [
        "tools.analysis.get_member_forces_at_distance([10], [201], [0])",
        "tools.analysis.get_member_force_extrema([10], [201])",
        "tools.analysis.get_max_section_displacements([10], [201])",
        "tools.analysis.get_plate_center_results([101], [201])",
        "tools.analysis.get_plate_principal_stresses([101], [201])",
        "tools.analysis.get_plate_von_mises_stresses([101], [201])",
        "tools.design.get_member_results([10])",
    ],
)
def test_unavailable_results(code, extended):
    extended.Output.AreResultsAvailable.return_value = False
    result = PTCRuntime(Executor()).execute(code, extended)
    assert not result["success"] and "unavailable" in result["error"]


@pytest.mark.parametrize("values", [[1], [1, 2, 3], [1, float("nan")], [1, float("inf")], [1, True], [1, "2"]])
def test_bad_upstream_numeric_values(values):
    with pytest.raises(ValueError):
        values_record(("x", "y"), values)


def test_examples_for_extended_queries(extended):
    for name in ("member_envelope.py", "plate_report.py", "design_details.py"):
        path = Path(__file__).resolve().parents[2] / "examples" / "ptc" / name
        response = PTCRuntime(Executor()).execute(path.read_text(encoding="utf-8"), extended)
        assert response["success"], response
        assert response["stdout"] == ""
