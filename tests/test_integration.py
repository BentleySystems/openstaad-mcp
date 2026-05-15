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
from openstaad_mcp.sandbox.executor import Executor

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
    return Executor()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_code(executor: Executor, code: str, staad_instance) -> dict:
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
# 2. Root methods (natural syntax)
# ===========================================================================


class TestExecutorCOMRootMethods:
    """Test root-level STAAD methods through the Monty sandbox."""

    def test_get_application_version(self, executor, staad_instance):
        r = _run_code(executor, "staad.GetApplicationVersion()", staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], str)
        assert len(r["result"]) > 0

    def test_get_staad_file(self, executor, staad_instance):
        r = _run_code(executor, "staad.GetSTAADFile()", staad_instance)
        assert r["success"], r["error"]
        assert r["result"].lower().endswith(".std")

    def test_get_base_unit(self, executor, staad_instance):
        r = _run_code(executor, "staad.GetBaseUnit()", staad_instance)
        assert r["success"], r["error"]
        # Returns a string like "English" or "Metric"
        assert isinstance(r["result"], str)

    def test_get_analysis_status(self, executor, staad_instance):
        r = _run_code(executor, "staad.GetAnalysisStatus()", staad_instance)
        assert r["success"], r["error"]
        assert r["result"] is not None


# ===========================================================================
# 3. Geometry sub-object (natural syntax)
# ===========================================================================


class TestExecutorCOMGeometry:
    """Test Geometry sub-object methods through the Monty sandbox."""

    def test_get_node_count(self, executor, staad_instance):
        r = _run_code(executor, "staad.Geometry.GetNodeCount()", staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], int)
        assert r["result"] > 0

    def test_get_member_count(self, executor, staad_instance):
        r = _run_code(executor, "staad.Geometry.GetMemberCount()", staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], int)
        assert r["result"] >= 0

    def test_get_node_coordinates(self, executor, staad_instance):
        code = """\
count = staad.Geometry.GetNodeCount()
if count > 0:
    result = staad.Geometry.GetNodeCoordinates(1)
else:
    result = "no nodes"
result
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        if r["result"] != "no nodes":
            assert len(r["result"]) == 3

    def test_get_node_list(self, executor, staad_instance):
        r = _run_code(executor, "staad.Geometry.GetNodeList()", staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], list)
        assert len(r["result"]) > 0

    def test_get_beam_list(self, executor, staad_instance):
        r = _run_code(executor, "staad.Geometry.GetBeamList()", staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], list)

    def test_get_beam_length(self, executor, staad_instance):
        code = """\
beams = staad.Geometry.GetBeamList()
if len(beams) > 0:
    result = staad.Geometry.GetBeamLength(beams[0])
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
beams = staad.Geometry.GetBeamList()
if len(beams) > 0:
    result = staad.Geometry.GetMemberIncidence(beams[0])
else:
    result = []
result
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        if r["result"]:
            assert len(r["result"]) >= 2

    def test_alias_pattern(self, executor, staad_instance):
        """Alias syntax: geo = staad.Geometry; geo.GetNodeCount()"""
        code = """\
geo = staad.Geometry
geo.GetNodeCount()
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], int)
        assert r["result"] > 0


# ===========================================================================
# 4. Property sub-object (natural syntax)
# ===========================================================================


class TestExecutorCOMProperty:
    """Test Property sub-object methods."""

    def test_get_beam_section_name(self, executor, staad_instance):
        code = """\
beams = staad.Geometry.GetBeamList()
if len(beams) > 0:
    result = staad.Property.GetBeamSectionName(beams[0])
else:
    result = "no beams"
result
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], str)


# ===========================================================================
# 5. Load sub-object (natural syntax)
# ===========================================================================


class TestExecutorCOMLoad:
    """Test Load sub-object methods."""

    def test_get_primary_load_case_count(self, executor, staad_instance):
        r = _run_code(executor, "staad.Load.GetPrimaryLoadCaseCount()", staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], int)
        assert r["result"] >= 0

    def test_get_load_case_title(self, executor, staad_instance):
        code = """\
count = staad.Load.GetPrimaryLoadCaseCount()
if count > 0:
    result = staad.Load.GetLoadCaseTitle(1)
else:
    result = "no load cases"
result
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], str)


# ===========================================================================
# 6. Support sub-object (natural syntax)
# ===========================================================================


class TestExecutorCOMSupport:
    """Test Support sub-object methods."""

    def test_get_support_count(self, executor, staad_instance):
        r = _run_code(executor, "staad.Support.GetSupportCount()", staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], int)
        assert r["result"] >= 0


# ===========================================================================
# 7. Output sub-object (natural syntax, requires analysis)
# ===========================================================================


class TestExecutorCOMOutput:
    """Test Output sub-object methods (require a model with results)."""

    def test_are_results_available(self, executor, staad_instance):
        r = _run_code(executor, "staad.Output.AreResultsAvailable()", staad_instance)
        assert r["success"], r["error"]
        assert r["result"] in (0, 1)

    def test_get_node_displacements(self, executor, staad_instance):
        code = """\
has_results = staad.Output.AreResultsAvailable()
if has_results == 1:
    count = staad.Load.GetPrimaryLoadCaseCount()
    if count > 0:
        result = staad.Output.GetNodeDisplacements(1, 1)
    else:
        result = "no load cases"
else:
    result = "no results"
result
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        if isinstance(r["result"], list):
            assert len(r["result"]) == 6

    def test_get_support_reactions(self, executor, staad_instance):
        code = """\
has_results = staad.Output.AreResultsAvailable()
if has_results == 1:
    supported = staad.Support.GetSupportedNodes()
    if len(supported) > 0:
        result = staad.Output.GetSupportReactions(supported[0], 1)
    else:
        result = "no supports"
else:
    result = "no results"
result
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        if isinstance(r["result"], list):
            assert len(r["result"]) == 6

    def test_get_member_end_forces(self, executor, staad_instance):
        code = """\
has_results = staad.Output.AreResultsAvailable()
if has_results == 1:
    beams = staad.Geometry.GetBeamList()
    if len(beams) > 0:
        result = staad.Output.GetMemberEndForces(beams[0], 1, 0)
    else:
        result = "no beams"
else:
    result = "no results"
result
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        if isinstance(r["result"], list):
            assert len(r["result"]) >= 6


# ===========================================================================
# 8. MONTY SANDBOX — Multi-step workflows (natural syntax)
# ===========================================================================


class TestExecutorCOMWorkflows:
    """Test complex multi-step code through the sandbox."""

    def test_model_summary(self, executor, staad_instance):
        code = """\
import json
geo = staad.Geometry
nodes = geo.GetNodeCount()
members = geo.GetMemberCount()
supports = staad.Support.GetSupportCount()
load_cases = staad.Load.GetPrimaryLoadCaseCount()
version = staad.GetApplicationVersion()
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
geo = staad.Geometry
beams = geo.GetBeamList()
total = 0.0
for b in beams:
    total = total + geo.GetBeamLength(b)
total
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        assert isinstance(r["result"], (int, float))
        assert r["result"] > 0

    def test_print_output_captured(self, executor, staad_instance):
        code = """\
nodes = staad.Geometry.GetNodeCount()
print(f"Model has {nodes} nodes")
nodes
"""
        r = _run_code(executor, code, staad_instance)
        assert r["success"], r["error"]
        assert "nodes" in r["stdout"]

    def test_data_transformation(self, executor, staad_instance):
        code = """\
import json
geo = staad.Geometry
nodes = geo.GetNodeList()
coords = {}
for n in nodes[:5]:
    c = geo.GetNodeCoordinates(n)
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
# 9. SECURITY ENFORCEMENT (natural syntax, against live COM)
# ===========================================================================


class TestExecutorCOMSecurity:
    """Verify security controls hold against the real COM bridge."""

    def test_denied_method_blocked(self, executor, staad_instance):
        code = 'staad.SetStandardProfileDBFolder("\\\\\\\\evil\\\\share")'
        r = _run_code(executor, code, staad_instance)
        assert not r["success"]
        assert "denied" in (r["error"] or "").lower()

    def test_unenumerated_method_blocked(self, executor, staad_instance):
        code = "staad.Geometry.DeleteEverything()"
        r = _run_code(executor, code, staad_instance)
        assert not r["success"]
        assert "not allowed" in (r["error"] or "").lower()

    def test_destructive_method_blocked_without_consent(self, executor, staad_instance):
        def _run(staad):
            return executor.execute(
                "staad.SaveModel()",
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


class TestExecutorCOMErrors:
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
        code = "staad.Geometry.ThisMethodDoesNotExist123()"
        r = _run_code(executor, code, staad_instance)
        assert not r["success"]
        # Error should not contain Windows paths
        assert "C:\\" not in (r["error"] or "")
