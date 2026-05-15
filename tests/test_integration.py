"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Integration tests — require a running STAAD.Pro instance on Windows.

These tests verify the full pipeline: MontyExecutor → COM bridge → STAAD.Pro.
They should only be run on a Windows machine with STAAD.Pro open and a model
loaded.

Run with::

    pytest tests/test_integration.py -v -m integration
"""

from __future__ import annotations

import json

import pytest

from openstaad_mcp.connection import InstanceRegistry, connect_and_run
from openstaad_mcp.sandbox.monty_executor import MontyExecutor

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def staad_instance():
    """Return the first running STAAD.Pro instance from the ROT."""
    registry = InstanceRegistry()
    instances = registry.get_active_instances()
    if not instances:
        pytest.skip("No STAAD.Pro instances found — start STAAD and open a model")
    return instances[0]


@pytest.fixture
def executor():
    return MontyExecutor()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_code(executor: MontyExecutor, code: str, staad_instance) -> dict:
    """Execute code via the Monty sandbox on a real STAAD.Pro instance."""

    def _run(staad):
        return executor.execute(code, staad).to_dict()

    return connect_and_run(_run, staad_instance.file_path)


# ===========================================================================
# 1. DIRECT COM ACCESS (bypassing sandbox, verifying connection)
# ===========================================================================


class TestDirectCom:
    """Verify raw COM access works before testing the sandbox layer."""

    def test_get_node_count(self, staad_instance):
        count = connect_and_run(
            lambda s: s.Geometry.GetNodeCount(),
            staad_instance.file_path,
        )
        assert isinstance(count, int)
        assert count > 0

    def test_get_beam_count(self, staad_instance):
        count = connect_and_run(
            lambda s: s.Geometry.GetMemberCount(),
            staad_instance.file_path,
        )
        assert isinstance(count, int)
        assert count >= 0

    def test_get_version(self, staad_instance):
        version = connect_and_run(
            lambda s: s.GetApplicationVersion(),
            staad_instance.file_path,
        )
        assert isinstance(version, str)
        assert len(version) > 0

    def test_get_staad_file(self, staad_instance):
        path = connect_and_run(
            lambda s: s.GetSTAADFile(),
            staad_instance.file_path,
        )
        assert isinstance(path, str)
        assert path.lower().endswith(".std")


# ===========================================================================
# 2. MONTY SANDBOX — Root methods
# ===========================================================================


class TestMontyRootMethods:
    """Test root-level STAAD methods through the Monty sandbox."""

    def test_get_application_version(self, executor, staad_instance):
        r = _run_code(executor, 'staad_call("GetApplicationVersion")', staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], str)
        assert len(r["result"]) > 0

    def test_get_staad_file(self, executor, staad_instance):
        r = _run_code(executor, 'staad_call("GetSTAADFile")', staad_instance)
        assert r["success"], r["error"]
        assert r["result"].lower().endswith(".std")

    def test_get_base_unit(self, executor, staad_instance):
        r = _run_code(executor, 'staad_call("GetBaseUnit")', staad_instance)
        assert r["success"], r["error"]
        # Returns a string like "English" or "Metric"
        assert isinstance(r["result"], str)

    def test_get_analysis_status(self, executor, staad_instance):
        r = _run_code(executor, 'staad_call("GetAnalysisStatus")', staad_instance)
        assert r["success"], r["error"]
        # Returns a dict or repr'd dict with ReturnValue, ReturnString, etc.
        assert r["result"] is not None


# ===========================================================================
# 3. MONTY SANDBOX — Geometry sub-object
# ===========================================================================


class TestMontyGeometry:
    """Test Geometry sub-object methods through the Monty sandbox."""

    def test_get_node_count(self, executor, staad_instance):
        r = _run_code(executor, 'geo_call("GetNodeCount")', staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], int)
        assert r["result"] > 0

    def test_get_member_count(self, executor, staad_instance):
        r = _run_code(executor, 'geo_call("GetMemberCount")', staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], int)
        assert r["result"] >= 0

    def test_get_node_coordinates(self, executor, staad_instance):
        code = """\
count = geo_call("GetNodeCount")
if count > 0:
    result = geo_call("GetNodeCoordinates", 1)
else:
    result = "no nodes"
result
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        if r["result"] != "no nodes":
            # Should be a list of 3 floats (x, y, z)
            assert len(r["result"]) == 3

    def test_get_node_list(self, executor, staad_instance):
        r = _run_code(executor, 'geo_call("GetNodeList")', staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], list)
        assert len(r["result"]) > 0

    def test_get_beam_list(self, executor, staad_instance):
        r = _run_code(executor, 'geo_call("GetBeamList")', staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], list)

    def test_get_beam_length(self, executor, staad_instance):
        code = """\
beams = geo_call("GetBeamList")
if len(beams) > 0:
    result = geo_call("GetBeamLength", beams[0])
else:
    result = -1.0
result
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        if r["result"] != -1.0:
            assert isinstance(r["result"], (int, float))
            assert r["result"] > 0

    def test_get_member_incidence(self, executor, staad_instance):
        code = """\
beams = geo_call("GetBeamList")
if len(beams) > 0:
    result = geo_call("GetMemberIncidence", beams[0])
else:
    result = []
result
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        if r["result"]:
            # Incidence = [start_node, end_node]
            assert len(r["result"]) >= 2


# ===========================================================================
# 4. MONTY SANDBOX — Property sub-object
# ===========================================================================


class TestMontyProperty:
    """Test Property sub-object methods."""

    def test_get_beam_section_name(self, executor, staad_instance):
        code = """\
beams = geo_call("GetBeamList")
if len(beams) > 0:
    result = prop_call("GetBeamSectionName", beams[0])
else:
    result = "no beams"
result
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], str)


# ===========================================================================
# 5. MONTY SANDBOX — Load sub-object
# ===========================================================================


class TestMontyLoad:
    """Test Load sub-object methods."""

    def test_get_primary_load_case_count(self, executor, staad_instance):
        r = _run_code(executor, 'load_call("GetPrimaryLoadCaseCount")', staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], int)
        assert r["result"] >= 0

    def test_get_load_case_title(self, executor, staad_instance):
        code = """\
count = load_call("GetPrimaryLoadCaseCount")
if count > 0:
    result = load_call("GetLoadCaseTitle", 1)
else:
    result = "no load cases"
result
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], str)


# ===========================================================================
# 6. MONTY SANDBOX — Support sub-object
# ===========================================================================


class TestMontySupport:
    """Test Support sub-object methods."""

    def test_get_support_count(self, executor, staad_instance):
        r = _run_code(executor, 'support_call("GetSupportCount")', staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], int)
        assert r["result"] >= 0


# ===========================================================================
# 7. MONTY SANDBOX — Output sub-object (requires analysis)
# ===========================================================================


class TestMontyOutput:
    """Test Output sub-object methods (require a model with results)."""

    def test_are_results_available(self, executor, staad_instance):
        r = _run_code(executor, 'output_call("AreResultsAvailable")', staad_instance)
        assert r["success"], r["error"]
        # 0 = no results, 1 = results available
        assert r["result"] in (0, 1)

    def test_get_node_displacements(self, executor, staad_instance):
        code = """\
has_results = output_call("AreResultsAvailable")
if has_results == 1:
    count = load_call("GetPrimaryLoadCaseCount")
    if count > 0:
        result = output_call("GetNodeDisplacements", 1, 1)
    else:
        result = "no load cases"
else:
    result = "no results"
result
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        if isinstance(r["result"], list):
            # 6 DOF: dx, dy, dz, rx, ry, rz
            assert len(r["result"]) == 6

    def test_get_support_reactions(self, executor, staad_instance):
        code = """\
has_results = output_call("AreResultsAvailable")
if has_results == 1:
    supported = support_call("GetSupportedNodes")
    if len(supported) > 0:
        result = output_call("GetSupportReactions", supported[0], 1)
    else:
        result = "no supports"
else:
    result = "no results"
result
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        if isinstance(r["result"], list):
            # 6 DOF: Fx, Fy, Fz, Mx, My, Mz
            assert len(r["result"]) == 6

    def test_get_member_end_forces(self, executor, staad_instance):
        code = """\
has_results = output_call("AreResultsAvailable")
if has_results == 1:
    beams = geo_call("GetBeamList")
    if len(beams) > 0:
        result = output_call("GetMemberEndForces", beams[0], 1, 0)
    else:
        result = "no beams"
else:
    result = "no results"
result
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        if isinstance(r["result"], list):
            # 6 forces at each end → 12 values, or 6 per end
            assert len(r["result"]) >= 6


# ===========================================================================
# 8. MONTY SANDBOX — Multi-step workflows
# ===========================================================================


class TestMontyWorkflows:
    """Test complex multi-step code through the sandbox."""

    def test_model_summary(self, executor, staad_instance):
        code = """\
import json
nodes = geo_call("GetNodeCount")
members = geo_call("GetMemberCount")
supports = support_call("GetSupportCount")
load_cases = load_call("GetPrimaryLoadCaseCount")
version = staad_call("GetApplicationVersion")
json.dumps({
    "nodes": nodes,
    "members": members,
    "supports": supports,
    "load_cases": load_cases,
    "version": version,
})
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        summary = json.loads(r["result"])
        assert summary["nodes"] > 0
        assert isinstance(summary["version"], str)

    def test_compute_total_beam_length(self, executor, staad_instance):
        code = """\
beams = geo_call("GetBeamList")
total = 0.0
for b in beams:
    total = total + geo_call("GetBeamLength", b)
total
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], (int, float))
        assert r["result"] > 0

    def test_print_output_captured(self, executor, staad_instance):
        code = """\
nodes = geo_call("GetNodeCount")
print(f"Model has {nodes} nodes")
nodes
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        assert "nodes" in r["stdout"]

    def test_data_transformation(self, executor, staad_instance):
        code = """\
import json
nodes = geo_call("GetNodeList")
coords = {}
for n in nodes[:5]:
    c = geo_call("GetNodeCoordinates", n)
    coords[str(n)] = c
json.dumps(coords)
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        data = json.loads(r["result"])
        assert len(data) <= 5
        for node_id, coord in data.items():
            assert len(coord) == 3


# ===========================================================================
# 9. SECURITY ENFORCEMENT (against live COM)
# ===========================================================================


class TestMontySecurity:
    """Verify security controls hold against the real COM bridge."""

    def test_denied_method_blocked(self, executor, staad_instance):
        code = 'staad_call("SetStandardProfileDBFolder", "\\\\\\\\evil\\\\share")'
        r = _run_code(executor, code, staad_instance)
        assert not r["success"]
        assert "denied" in (r["error"] or "").lower()

    def test_unenumerated_method_blocked(self, executor, staad_instance):
        code = 'geo_call("DeleteEverything")'
        r = _run_code(executor, code, staad_instance)
        assert not r["success"]
        assert "not allowed" in (r["error"] or "").lower()

    def test_destructive_method_blocked_without_consent(self, executor, staad_instance):
        def _run(staad):
            return executor.execute(
                'staad_call("SaveModel")',
                staad,
                allow_destructive=False,
            ).to_dict()

        r = connect_and_run(_run, staad_instance.file_path)
        assert not r["success"]
        assert "blocked" in (r["error"] or "").lower() or "approval" in (r["error"] or "").lower()

    def test_import_blocked(self, executor, staad_instance):
        r = _run_code(executor, "import subprocess", staad_instance)
        assert not r["success"]

    def test_file_access_blocked(self, executor, staad_instance):
        r = _run_code(executor, 'open("C:/Windows/System32/config/sam")', staad_instance)
        assert not r["success"]

    def test_eval_blocked(self, executor, staad_instance):
        r = _run_code(executor, 'eval("1+1")', staad_instance)
        assert not r["success"]


# ===========================================================================
# 10. ERROR HANDLING
# ===========================================================================


class TestMontyErrors:
    """Error scenarios produce clean, safe error messages."""

    def test_syntax_error(self, executor, staad_instance):
        r = _run_code(executor, "def foo(", staad_instance)
        assert not r["success"]
        assert r["error"] is not None

    def test_runtime_division_by_zero(self, executor, staad_instance):
        r = _run_code(executor, "1 / 0", staad_instance)
        assert not r["success"]
        assert r["error"] is not None

    def test_undefined_variable(self, executor, staad_instance):
        r = _run_code(executor, "nonexistent_var", staad_instance)
        assert not r["success"]

    def test_invalid_com_method_clean_error(self, executor, staad_instance):
        """Calling a non-existent method gives a clean error, not a COM traceback."""
        code = 'geo_call("ThisMethodDoesNotExist123")'
        r = _run_code(executor, code, staad_instance)
        assert not r["success"]
        # Error should not contain Windows paths
        assert "C:\\" not in (r["error"] or "")
