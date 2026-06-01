"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Tests for the domain reporting tools (fetch_model_summary, fetch_member_forces,
fetch_support_reactions, fetch_design_summary).

All tests use duck-typed mock objects — no COM or STAAD.Pro required.
"""

from __future__ import annotations

import pytest

from openstaad_mcp.domain_tools import (
    _MAX_ITEMS,
    fetch_design_summary,
    fetch_member_forces,
    fetch_model_summary,
    fetch_support_reactions,
)


# ── Mock objects ──────────────────────────────────────────────────────


class MockGeometry:
    def __init__(self, node_count=10, beam_count=8, plate_count=0, solid_count=0,
                 beam_list=None, node_list=None):
        self._node_count = node_count
        self._beam_count = beam_count
        self._plate_count = plate_count
        self._solid_count = solid_count
        self._beam_list = beam_list if beam_list is not None else list(range(1, beam_count + 1))
        self._node_list = node_list if node_list is not None else list(range(1, node_count + 1))

    def GetNodeCount(self): return self._node_count
    def GetMemberCount(self): return self._beam_count
    def GetPlateCount(self): return self._plate_count
    def GetSolidCount(self): return self._solid_count
    def GetBeamList(self): return self._beam_list
    def GetNodeList(self): return self._node_list
    def IsZUp(self): return False


class MockLoad:
    def __init__(self, load_cases=None):
        self._cases = load_cases if load_cases is not None else (1, 2)

    def GetPrimaryLoadCaseNumbers(self): return self._cases


class MockOutput:
    def __init__(self, results_available=True, force_unit="KIP", moment_unit="KIP-IN"):
        self._available = results_available
        self._force_unit = force_unit
        self._moment_unit = moment_unit
        # Design ratios keyed by beam ID: ratio or sentinel
        self._design_ratios: dict[int, float] = {}

    def AreResultsAvailable(self): return self._available
    def GetOutputUnitForForce(self): return self._force_unit
    def GetOutputUnitForMoment(self): return self._moment_unit

    def GetMemberEndForces(self, beam_no, end, lc, local):
        return [1.0 * end, -2.0, 0.5, 0.1, -0.2, 0.3]

    def GetSupportReactions(self, node_id, lc):
        return [0.0, 25.0 + node_id, 0.0, 0.0, 0.0, 0.0]

    def GetMemberSteelDesignRatio(self, bid):
        return self._design_ratios.get(bid, -999)  # -999 = not designed

    def GetMemberSteelDesignResults(self, bid):
        ratio = self._design_ratios.get(bid, 1.0)
        # (code, status, ratio, allow, lc, location, clause, section, forces, klr)
        return ("AISC", "FAIL" if ratio > 1.0 else "PASS", ratio, 1.0, 1, 0.5, "H1-1a",
                "W10X33", [0.0] * 6, 50.0)


class MockSupport:
    def __init__(self, support_nodes=None):
        self._nodes = support_nodes if support_nodes is not None else [1, 5]

    def GetSupportNodes(self): return self._nodes


class MockStaad:
    def __init__(
        self,
        node_count=10, beam_count=8, plate_count=2, solid_count=0,
        load_cases=None, support_nodes=None,
        results_available=True,
        design_ratios=None,
        beam_list=None,
    ):
        self.Geometry = MockGeometry(
            node_count=node_count,
            beam_count=beam_count,
            plate_count=plate_count,
            solid_count=solid_count,
            beam_list=beam_list,
        )
        self.Load = MockLoad(load_cases=load_cases)
        self.Output = MockOutput(results_available=results_available)
        self.Support = MockSupport(support_nodes=support_nodes)
        if design_ratios:
            self.Output._design_ratios = design_ratios

    def GetSTAADFile(self): return "C:\\Models\\test.std"
    def GetApplicationVersion(self): return "STAAD.Pro CONNECT Edition V25"
    def GetBaseUnit(self): return "English"


# ── fetch_model_summary ────────────────────────────────────────────


class TestFetchModelSummary:
    def test_returns_geometry_counts(self):
        staad = MockStaad(node_count=42, beam_count=35, plate_count=4, solid_count=1)
        result = fetch_model_summary(staad)
        assert result["node_count"] == 42
        assert result["beam_count"] == 35
        assert result["plate_count"] == 4
        assert result["solid_count"] == 1

    def test_returns_units_and_file(self):
        result = fetch_model_summary(MockStaad())
        assert result["units"] == "English"
        assert result["model_path"] == "C:\\Models\\test.std"
        assert result["staad_version"] == "STAAD.Pro CONNECT Edition V25"

    def test_axis_up_default_is_y(self):
        result = fetch_model_summary(MockStaad())
        assert result["axis_up"] == "Y"

    def test_axis_up_z_when_is_z_up(self):
        staad = MockStaad()
        staad.Geometry.IsZUp = lambda: True
        result = fetch_model_summary(staad)
        assert result["axis_up"] == "Z"


# ── fetch_member_forces ────────────────────────────────────────────


class TestFetchMemberForces:
    def test_returns_force_unit(self):
        result = fetch_member_forces(MockStaad())
        assert result["force_unit"] == "KIP"
        assert result["moment_unit"] == "KIP-IN"

    def test_result_count_equals_members_times_load_cases(self):
        staad = MockStaad(beam_count=5, load_cases=(1, 2, 3))
        result = fetch_member_forces(staad)
        assert result["result_count"] == 5 * 3
        assert result["member_count"] == 5
        assert result["load_case_count"] == 3

    def test_forces_list_has_correct_shape(self):
        staad = MockStaad(beam_count=3, load_cases=(1,))
        result = fetch_member_forces(staad)
        assert len(result["forces"]) == 3
        entry = result["forces"][0]
        assert "member_id" in entry
        assert "load_case" in entry
        assert "start" in entry and "end" in entry
        assert set(entry["start"].keys()) == {"FX", "FY", "FZ", "MX", "MY", "MZ"}

    def test_not_truncated_when_under_cap(self):
        staad = MockStaad(beam_count=5, load_cases=(1, 2))
        result = fetch_member_forces(staad)
        assert result["truncated"] is False
        assert result["showing"] == result["result_count"]

    def test_truncated_when_over_cap(self):
        n = _MAX_ITEMS + 50
        beam_list = list(range(1, n + 1))
        staad = MockStaad(beam_count=n, beam_list=beam_list, load_cases=(1,))
        result = fetch_member_forces(staad)
        assert result["result_count"] == n
        assert result["showing"] == _MAX_ITEMS
        assert result["truncated"] is True
        assert len(result["forces"]) == _MAX_ITEMS

    def test_result_count_is_pretuncation_total(self):
        # result_count must reflect true total even when truncated
        n = _MAX_ITEMS + 10
        beam_list = list(range(1, n + 1))
        staad = MockStaad(beam_count=n, beam_list=beam_list, load_cases=(1, 2))
        result = fetch_member_forces(staad)
        assert result["result_count"] == n * 2
        assert result["showing"] <= _MAX_ITEMS

    def test_results_not_available_returns_error(self):
        staad = MockStaad(results_available=False)
        result = fetch_member_forces(staad)
        assert "error" in result

    def test_filtered_by_member_ids(self):
        staad = MockStaad(beam_count=8, load_cases=(1,))
        result = fetch_member_forces(staad, member_ids=[2, 4])
        assert result["member_count"] == 2
        assert result["result_count"] == 2

    def test_filtered_by_load_cases(self):
        staad = MockStaad(beam_count=3, load_cases=(1, 2, 3))
        result = fetch_member_forces(staad, load_cases=[1])
        assert result["load_case_count"] == 1
        assert result["result_count"] == 3


# ── fetch_support_reactions ────────────────────────────────────────


class TestFetchSupportReactions:
    def test_returns_force_unit(self):
        result = fetch_support_reactions(MockStaad())
        assert result["force_unit"] == "KIP"
        assert result["moment_unit"] == "KIP-IN"

    def test_discovers_support_nodes_automatically(self):
        staad = MockStaad(support_nodes=[1, 3, 5], load_cases=(1,))
        result = fetch_support_reactions(staad)
        assert result["support_node_count"] == 3
        assert result["result_count"] == 3

    def test_reactions_have_correct_shape(self):
        staad = MockStaad(support_nodes=[1], load_cases=(1,))
        result = fetch_support_reactions(staad)
        entry = result["reactions"][0]
        assert entry["node_id"] == 1
        assert entry["load_case"] == 1
        assert all(k in entry for k in ("FX", "FY", "FZ", "MX", "MY", "MZ"))

    def test_not_truncated_when_under_cap(self):
        staad = MockStaad(support_nodes=[1, 2, 3], load_cases=(1, 2))
        result = fetch_support_reactions(staad)
        assert result["truncated"] is False

    def test_truncated_when_over_cap(self):
        nodes = list(range(1, _MAX_ITEMS + 10))
        staad = MockStaad(support_nodes=nodes, load_cases=(1,))
        result = fetch_support_reactions(staad)
        assert result["result_count"] == len(nodes)
        assert result["showing"] == _MAX_ITEMS
        assert result["truncated"] is True

    def test_filtered_by_node_ids(self):
        staad = MockStaad(support_nodes=[1, 3, 5, 7], load_cases=(1,))
        result = fetch_support_reactions(staad, node_ids=[1, 5])
        assert result["support_node_count"] == 2

    def test_results_not_available_returns_error(self):
        result = fetch_support_reactions(MockStaad(results_available=False))
        assert "error" in result


# ── fetch_design_summary ───────────────────────────────────────────


class TestFetchDesignSummary:
    def test_all_pass_when_no_failures(self):
        ratios = {1: 0.8, 2: 0.6, 3: 0.9}
        staad = MockStaad(
            beam_list=list(ratios.keys()),
            beam_count=len(ratios),
            design_ratios=ratios,
        )
        result = fetch_design_summary(staad)
        assert result["all_pass"] is True
        assert result["fail_count"] == 0
        assert result["pass_count"] == 3
        assert result["controlling_ratio"] is None

    def test_failures_detected(self):
        ratios = {1: 0.8, 2: 1.35, 3: 0.9, 4: 1.08}
        staad = MockStaad(
            beam_list=list(ratios.keys()),
            beam_count=len(ratios),
            design_ratios=ratios,
        )
        result = fetch_design_summary(staad)
        assert result["all_pass"] is False
        assert result["fail_count"] == 2
        assert result["pass_count"] == 2
        assert result["controlling_ratio"] == pytest.approx(1.35, rel=1e-3)

    def test_failed_members_never_truncated(self):
        # Even when failures exceed _MAX_ITEMS, they must all appear
        n_fail = _MAX_ITEMS + 20
        ratios = {i: 1.5 for i in range(1, n_fail + 1)}
        staad = MockStaad(
            beam_list=list(ratios.keys()),
            beam_count=n_fail,
            design_ratios=ratios,
        )
        result = fetch_design_summary(staad)
        assert result["fail_count"] == n_fail
        assert len(result["failed_members"]) == n_fail  # ALL failures present

    def test_passes_truncated_before_failures(self):
        # 5 failures + many passes → failures stay, passes may be truncated
        n_pass = _MAX_ITEMS + 50
        n_fail = 5
        fail_ids = list(range(1, n_fail + 1))
        pass_ids = list(range(n_fail + 1, n_fail + n_pass + 1))
        ratios = {i: 1.5 for i in fail_ids}
        ratios.update({i: 0.7 for i in pass_ids})
        staad = MockStaad(
            beam_list=fail_ids + pass_ids,
            beam_count=n_fail + n_pass,
            design_ratios=ratios,
        )
        result = fetch_design_summary(staad)
        assert result["fail_count"] == n_fail
        assert len(result["failed_members"]) == n_fail  # all failures
        assert result["pass_count"] == n_pass
        assert len(result["passing_sample"]) < n_pass   # passes truncated
        assert result["truncated"] is True

    def test_counts_are_authoritative_even_when_truncated(self):
        n = _MAX_ITEMS + 100
        ratios = {i: 0.5 for i in range(1, n + 1)}
        staad = MockStaad(
            beam_list=list(ratios.keys()),
            beam_count=n,
            design_ratios=ratios,
        )
        result = fetch_design_summary(staad)
        assert result["pass_count"] == n    # true total, not truncated count
        assert result["total_designed"] == n
        assert result["result_count"] == n

    def test_undesigned_members_skipped(self):
        # -999 = not designed, should not appear in results
        ratios = {1: 0.8}  # only beam 1 is designed
        staad = MockStaad(
            beam_list=[1, 2, 3],
            beam_count=3,
            design_ratios=ratios,
        )
        result = fetch_design_summary(staad)
        assert result["total_designed"] == 1

    def test_results_not_available_returns_error(self):
        result = fetch_design_summary(MockStaad(results_available=False))
        assert "error" in result

    def test_compliance_assertion_fields_present(self):
        ratios = {1: 1.2, 2: 0.8}
        staad = MockStaad(
            beam_list=list(ratios.keys()),
            beam_count=2,
            design_ratios=ratios,
        )
        result = fetch_design_summary(staad)
        # These are the compliance assertion fields — must always be present
        for key in ("all_pass", "pass_count", "fail_count", "total_designed",
                    "controlling_ratio", "result_count", "failed_members"):
            assert key in result, f"Compliance assertion field '{key}' missing"
