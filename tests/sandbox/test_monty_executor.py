"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Tests for the Monty-based sandboxed executor.

Covers: basic execution, COM bridging, allowlists, deny list, consent gate,
resource limits, isolation, error sanitisation, and red-team attack vectors.
"""

from __future__ import annotations

import pytest

from openstaad_mcp.sandbox.monty_executor import (
    ExecutionResult,
    MontyExecutor,
    _CallState,
    _host_com_get,
    _host_com_invoke,
    _sanitize_output,
    _validate_args,
)
from openstaad_mcp.sandbox.constants import (
    ALLOWED_ROOT_METHODS,
    ALLOWED_SUB_OBJECT_METHODS,
    ALLOWED_SUB_OBJECTS,
    DENIED_METHODS,
    DESTRUCTIVE_METHODS,
    MAX_RESULT_LENGTH,
)


# ---------------------------------------------------------------------------
# Mock STAAD object
# ---------------------------------------------------------------------------


class MockGeometry:
    @staticmethod
    def GetNodeCount():
        return 42

    @staticmethod
    def GetNodeCoordinates(node_id):
        return (1.0, 2.0, 3.0)

    @staticmethod
    def GetBeamList():
        return [1, 2, 3]

    @staticmethod
    def AddNode(x, y, z):
        return 1

    @staticmethod
    def GetBeamLength(beam_no):
        return 5.5


class MockOutput:
    @staticmethod
    def GetNodeDisplacements(node_id, load_case):
        return [0.1, -0.2, 0.3, 0.01, -0.02, 0.03]

    @staticmethod
    def AreResultsAvailable():
        return 1


class MockProperty:
    @staticmethod
    def GetBeamPropertyName(beam_no):
        return "W10X33"


class MockLoad:
    @staticmethod
    def GetPrimaryLoadCaseCount():
        return 3

    @staticmethod
    def GetLoadCaseTitle(lc):
        return f"Load Case {lc}"


class MockView:
    @staticmethod
    def ExportView(directory, filename, view_type, dpi):
        return 0


class MockTable:
    @staticmethod
    def SaveReport(path, fmt):
        return 0


class MockSupport:
    @staticmethod
    def GetSupportCount():
        return 6


class MockDesign:
    pass


class MockCommand:
    pass


class MockStaad:
    """Fake OpenSTAAD root for testing without COM."""

    Geometry = MockGeometry()
    Output = MockOutput()
    Property = MockProperty()
    Load = MockLoad()
    View = MockView()
    Table = MockTable()
    Support = MockSupport()
    Design = MockDesign()
    Command = MockCommand()

    @staticmethod
    def GetApplicationVersion():
        return "STAAD.Pro CONNECT Edition"

    @staticmethod
    def GetSTAADFile():
        return "C:\\test\\model.std"

    @staticmethod
    def GetBaseUnit():
        return 1

    @staticmethod
    def AnalyzeModel():
        return 0

    @staticmethod
    def SetSilentMode(mode):
        return None

    @staticmethod
    def NewSTAADFile(path, length_unit, force_unit):
        return 0

    @staticmethod
    def SaveModel():
        return 0

    @staticmethod
    def Quit():
        return None

    # Denied method — should never be callable
    @staticmethod
    def SetStandardProfileDBFolder(path):
        return 0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def executor():
    return MontyExecutor(timeout_seconds=10.0)


@pytest.fixture
def staad():
    return MockStaad()


# ===========================================================================
# 1. BASIC EXECUTION
# ===========================================================================


class TestBasicExecution:
    """Fundamental execution mechanics."""

    def test_simple_expression(self, executor, staad):
        r = executor.execute("1 + 2", staad)
        assert r.success
        assert r.result == 3

    def test_string_expression(self, executor, staad):
        r = executor.execute('"hello " + "world"', staad)
        assert r.success
        assert r.result == "hello world"

    def test_arithmetic(self, executor, staad):
        r = executor.execute("2 ** 10", staad)
        assert r.success
        assert r.result == 1024

    def test_variable_assignment_and_return(self, executor, staad):
        r = executor.execute("x = 5\ny = 10\nx + y", staad)
        assert r.success
        assert r.result == 15

    def test_list_operations(self, executor, staad):
        r = executor.execute("[1, 2, 3] + [4, 5]", staad)
        assert r.success
        assert r.result == [1, 2, 3, 4, 5]

    def test_dict_operations(self, executor, staad):
        code = '{"a": 1, "b": 2}'
        r = executor.execute(code, staad)
        assert r.success
        assert r.result == {"a": 1, "b": 2}

    def test_function_definition_and_call(self, executor, staad):
        code = """\
def add(a, b):
    return a + b
add(3, 4)
"""
        r = executor.execute(code, staad)
        assert r.success
        assert r.result == 7

    def test_loop(self, executor, staad):
        code = """\
total = 0
for i in range(10):
    total = total + i
total
"""
        r = executor.execute(code, staad)
        assert r.success
        assert r.result == 45

    def test_conditional(self, executor, staad):
        code = """\
x = 42
if x > 40:
    result = "big"
else:
    result = "small"
result
"""
        r = executor.execute(code, staad)
        assert r.success
        assert r.result == "big"

    def test_list_comprehension(self, executor, staad):
        r = executor.execute("[x * 2 for x in range(5)]", staad)
        assert r.success
        assert r.result == [0, 2, 4, 6, 8]

    def test_none_result(self, executor, staad):
        r = executor.execute("x = 5", staad)
        assert r.success
        assert r.result is None

    def test_json_module_available(self, executor, staad):
        code = 'json.dumps({"key": "value"})'
        r = executor.execute(code, staad)
        assert r.success
        assert r.result == '{"key": "value"}'

    def test_json_module_with_import(self, executor, staad):
        code = 'import json\njson.loads(\'[1,2,3]\')'
        r = executor.execute(code, staad)
        assert r.success
        assert r.result == [1, 2, 3]


# ===========================================================================
# 2. STDOUT / STDERR CAPTURE
# ===========================================================================


class TestStdoutCapture:
    """Print output is captured and returned."""

    def test_print_captured(self, executor, staad):
        r = executor.execute('print("hello")', staad)
        assert r.success
        assert "hello" in r.stdout

    def test_multiple_prints(self, executor, staad):
        code = 'print("a")\nprint("b")\nprint("c")'
        r = executor.execute(code, staad)
        assert r.success
        assert "a" in r.stdout
        assert "b" in r.stdout
        assert "c" in r.stdout

    def test_stdout_truncation(self, executor, staad):
        exc = MontyExecutor(max_stdout_chars=100)
        code = 'print("x" * 200)'
        r = exc.execute(code, staad)
        assert r.success
        assert len(r.stdout) <= 120  # 100 + truncation message


# ===========================================================================
# 3. COM BRIDGING — Sub-object resolution
# ===========================================================================


class TestComGet:
    """com_get resolves sub-objects correctly."""

    def test_resolve_geometry(self, executor, staad):
        code = """\
geo = _get_sub(_staad_root, "Geometry")
geo["_name"]
"""
        r = executor.execute(code, staad)
        assert r.success
        assert r.result == "Geometry"

    def test_resolve_all_sub_objects(self, executor, staad):
        for name in ALLOWED_SUB_OBJECTS:
            code = f'_get_sub(_staad_root, "{name}")["_name"]'
            r = executor.execute(code, staad)
            assert r.success, f"Failed to resolve {name}: {r.error}"
            assert r.result == name

    def test_blocked_sub_object(self, executor, staad):
        code = '_get_sub(_staad_root, "NotASubObject")'
        r = executor.execute(code, staad)
        assert not r.success
        assert "not an allowed sub-object" in (r.error or "").lower() or "denied" in (r.error or "").lower()

    def test_com_get_only_on_root(self):
        state = _CallState(staad_object=MockStaad())
        state.handle_table[0] = (MockStaad(), "_root")
        state.handle_table[1] = (MockGeometry(), "Geometry")
        result = _host_com_get(state, 1, "Geometry")
        assert "error" in result


# ===========================================================================
# 4. COM BRIDGING — Method invocation
# ===========================================================================


class TestComInvoke:
    """com_invoke calls methods with proper gating."""

    def test_root_method(self, executor, staad):
        code = 'staad_call("GetApplicationVersion")'
        r = executor.execute(code, staad)
        assert r.success
        assert "STAAD" in str(r.result)

    def test_sub_object_method(self, executor, staad):
        code = 'geo_call("GetNodeCount")'
        r = executor.execute(code, staad)
        assert r.success
        assert r.result == 42

    def test_method_with_args(self, executor, staad):
        code = 'geo_call("GetNodeCoordinates", 1)'
        r = executor.execute(code, staad)
        assert r.success
        # Returned as list (tuple → list through COM bridge)
        assert r.result == [1.0, 2.0, 3.0] or r.result == (1.0, 2.0, 3.0)

    def test_output_method(self, executor, staad):
        code = 'output_call("AreResultsAvailable")'
        r = executor.execute(code, staad)
        assert r.success
        assert r.result == 1

    def test_property_method(self, executor, staad):
        code = 'prop_call("GetBeamPropertyName", 1)'
        r = executor.execute(code, staad)
        assert r.success
        assert r.result == "W10X33"


# ===========================================================================
# 5. ALLOWLIST ENFORCEMENT
# ===========================================================================


class TestAllowlists:
    """Only allowlisted methods can be called."""

    def test_unenumerated_root_method_blocked(self, executor, staad):
        code = 'staad_call("SomeUndefinedMethod")'
        r = executor.execute(code, staad)
        assert not r.success
        assert "not allowed" in (r.error or "").lower()

    def test_unenumerated_sub_method_blocked(self, executor, staad):
        code = 'geo_call("SomeUndefinedGeometryMethod")'
        r = executor.execute(code, staad)
        assert not r.success
        assert "not allowed" in (r.error or "").lower()

    def test_all_allowed_root_methods_are_valid(self):
        """Sanity: the allowlist only contains method names we expect."""
        for m in ALLOWED_ROOT_METHODS:
            assert isinstance(m, str) and len(m) > 0

    def test_all_sub_object_keys_match_allowed_sub_objects(self):
        """Every key in the sub-object method allowlist is a valid sub-object."""
        for key in ALLOWED_SUB_OBJECT_METHODS:
            assert key in ALLOWED_SUB_OBJECTS


# ===========================================================================
# 6. DENY LIST
# ===========================================================================


class TestDenyList:
    """Globally denied methods are blocked even if in an allowlist."""

    def test_denied_method_blocked(self):
        state = _CallState(staad_object=MockStaad())
        state.handle_table[0] = (MockStaad(), "_root")
        for method in DENIED_METHODS:
            with pytest.raises(RuntimeError, match="denied"):
                _host_com_invoke(state, 0, method, [])


# ===========================================================================
# 7. CONSENT GATE (Destructive methods)
# ===========================================================================


class TestConsentGate:
    """Destructive methods require allow_destructive=True."""

    def test_destructive_root_blocked_by_default(self, executor, staad):
        code = 'staad_call("NewSTAADFile", "C:/test.std", 1, 0)'
        r = executor.execute(code, staad, allow_destructive=False)
        assert not r.success
        assert "blocked" in (r.error or "").lower() or "approval" in (r.error or "").lower()

    def test_destructive_root_allowed_with_flag(self, executor, staad):
        code = 'staad_call("NewSTAADFile", "C:/test.std", 1, 0)'
        r = executor.execute(code, staad, allow_destructive=True)
        assert r.success
        assert r.result == 0

    def test_save_model_blocked_by_default(self, executor, staad):
        code = 'staad_call("SaveModel")'
        r = executor.execute(code, staad, allow_destructive=False)
        assert not r.success
        assert "blocked" in (r.error or "").lower() or "approval" in (r.error or "").lower()

    def test_save_model_allowed_with_flag(self, executor, staad):
        code = 'staad_call("SaveModel")'
        r = executor.execute(code, staad, allow_destructive=True)
        assert r.success

    def test_quit_blocked_by_default(self, executor, staad):
        code = 'staad_call("Quit")'
        r = executor.execute(code, staad, allow_destructive=False)
        assert not r.success

    def test_non_destructive_method_always_allowed(self, executor, staad):
        code = 'staad_call("GetBaseUnit")'
        r = executor.execute(code, staad, allow_destructive=False)
        assert r.success


# ===========================================================================
# 8. RESOURCE LIMITS
# ===========================================================================


class TestResourceLimits:
    """Monty enforces CPU, memory, allocation, and recursion limits."""

    def test_timeout_enforcement(self, staad):
        exc = MontyExecutor(timeout_seconds=1.0)
        code = """\
x = 0
while True:
    x = x + 1
"""
        r = exc.execute(code, staad)
        assert not r.success
        assert r.duration_seconds < 5.0  # Should be ~1s, definitely < 5s

    def test_recursion_limit(self, staad):
        exc = MontyExecutor(max_recursion_depth=50)
        code = """\
def recurse(n):
    return recurse(n + 1)
recurse(0)
"""
        r = exc.execute(code, staad)
        assert not r.success

    def test_code_size_limit(self, staad):
        exc = MontyExecutor(max_code_bytes=100)
        code = "x = 1\n" * 100  # ~600 bytes
        r = exc.execute(code, staad)
        assert not r.success
        assert "maximum size" in (r.error or "").lower()

    def test_memory_limit(self, staad):
        exc = MontyExecutor(
            timeout_seconds=5.0,
            max_memory_bytes=1 * 1024 * 1024,  # 1 MiB
            max_allocations=100_000,
        )
        code = """\
data = []
for i in range(1000000):
    data.append("x" * 1000)
"""
        r = exc.execute(code, staad)
        assert not r.success


# ===========================================================================
# 9. ISOLATION — No host access
# ===========================================================================


class TestIsolation:
    """User code cannot access host environment."""

    def test_no_import_subprocess(self, executor, staad):
        """Monty blocks importing non-supported modules."""
        r = executor.execute("import subprocess", staad)
        assert not r.success

    def test_import_os_limited(self, executor, staad):
        """Monty's os module is a stub — dangerous operations are blocked."""
        r = executor.execute('import os\nos.listdir(".")', staad)
        assert not r.success

    def test_no_open(self, executor, staad):
        r = executor.execute('open("test.txt")', staad)
        assert not r.success

    def test_no_eval(self, executor, staad):
        r = executor.execute('eval("1+1")', staad)
        assert not r.success

    def test_no_exec(self, executor, staad):
        r = executor.execute('exec("x=1")', staad)
        assert not r.success

    def test_no_subprocess(self, executor, staad):
        r = executor.execute("import subprocess", staad)
        assert not r.success

    def test_no_os_system(self, executor, staad):
        r = executor.execute("import os; os.system('whoami')", staad)
        assert not r.success

    def test_globals_dont_leak_between_calls(self, executor, staad):
        r1 = executor.execute("leak_var = 'leaked'", staad)
        assert r1.success
        r2 = executor.execute("leak_var", staad)
        assert not r2.success  # Should fail — variable not defined

    def test_no_file_system_access(self, executor, staad):
        r = executor.execute('open("/etc/passwd", "r").read()', staad)
        assert not r.success

    def test_no_network_access(self, executor, staad):
        r = executor.execute("import socket", staad)
        assert not r.success


# ===========================================================================
# 10. HANDLE FORGING / Invalid handles
# ===========================================================================


class TestHandleForging:
    """Forged handles are rejected."""

    def test_invalid_handle(self, executor, staad):
        code = "_call({'_handle': 999, '_name': 'fake'}, 'GetNodeCount')"
        r = executor.execute(code, staad)
        assert not r.success
        assert "invalid handle" in (r.error or "").lower() or "999" in (r.error or "")

    def test_negative_handle(self, executor, staad):
        code = "_call({'_handle': -1, '_name': 'fake'}, 'GetNodeCount')"
        r = executor.execute(code, staad)
        assert not r.success

    def test_handle_table_direct_access(self):
        """Host function validates handle table."""
        state = _CallState(staad_object=MockStaad())
        state.handle_table[0] = (MockStaad(), "_root")
        with pytest.raises(RuntimeError, match="Invalid handle"):
            _host_com_invoke(state, 42, "GetNodeCount", [])


# ===========================================================================
# 11. ARGUMENT VALIDATION
# ===========================================================================


class TestArgValidation:
    """Only JSON-safe arguments pass through to COM."""

    def test_valid_scalar_args(self):
        _validate_args([1, 2.0, "hello", True, None])

    def test_valid_list_args(self):
        _validate_args([[1, 2, 3]])

    def test_invalid_dict_arg(self):
        with pytest.raises(RuntimeError, match="unsupported type"):
            _validate_args([{"key": "value"}])

    def test_invalid_object_arg(self):
        with pytest.raises(RuntimeError, match="unsupported type"):
            _validate_args([object()])


# ===========================================================================
# 12. ERROR SANITISATION
# ===========================================================================


class TestErrorSanitisation:
    """Error messages don't leak system paths or internals."""

    def test_syntax_error_reported(self, executor, staad):
        r = executor.execute("def foo(", staad)
        assert not r.success
        assert r.error is not None

    def test_runtime_error_reported(self, executor, staad):
        r = executor.execute("1 / 0", staad)
        assert not r.success
        assert r.error is not None

    def test_name_error_reported(self, executor, staad):
        r = executor.execute("undefined_variable", staad)
        assert not r.success
        assert r.error is not None


# ===========================================================================
# 13. OUTPUT SANITISATION
# ===========================================================================


class TestOutputSanitisation:
    """Large outputs are truncated."""

    def test_long_string_truncated(self):
        s = "x" * (MAX_RESULT_LENGTH + 100)
        result = _sanitize_output(s)
        assert len(result) <= MAX_RESULT_LENGTH + 20
        assert "truncated" in result

    def test_normal_string_unchanged(self):
        assert _sanitize_output("hello") == "hello"

    def test_nested_list_sanitized(self):
        big = "x" * (MAX_RESULT_LENGTH + 100)
        result = _sanitize_output([big])
        assert "truncated" in result[0]

    def test_none_unchanged(self):
        assert _sanitize_output(None) is None

    def test_number_unchanged(self):
        assert _sanitize_output(42) == 42


# ===========================================================================
# 14. DURATION TRACKING
# ===========================================================================


class TestDuration:
    """Duration is always reported."""

    def test_success_has_duration(self, executor, staad):
        r = executor.execute("1 + 1", staad)
        assert r.success
        assert r.duration_seconds > 0

    def test_error_has_duration(self, executor, staad):
        r = executor.execute("1 / 0", staad)
        assert not r.success
        assert r.duration_seconds >= 0

    def test_syntax_error_has_duration(self, executor, staad):
        r = executor.execute("def foo(", staad)
        assert not r.success
        assert r.duration_seconds >= 0


# ===========================================================================
# 15. ExecutionResult.to_dict()
# ===========================================================================


class TestResultShape:
    """Result dict has all expected fields."""

    def test_all_fields_present(self, executor, staad):
        r = executor.execute("42", staad)
        d = r.to_dict()
        assert "success" in d
        assert "result" in d
        assert "stdout" in d
        assert "stderr" in d
        assert "error" in d
        assert "duration_seconds" in d


# ===========================================================================
# 16. COMPLEX WORKFLOWS
# ===========================================================================


class TestWorkflows:
    """Multi-step workflows using COM bridge."""

    def test_geometry_workflow(self, executor, staad):
        code = """\
count = geo_call("GetNodeCount")
coords = geo_call("GetNodeCoordinates", 1)
beams = geo_call("GetBeamList")
{"nodes": count, "beams": len(beams)}
"""
        r = executor.execute(code, staad)
        assert r.success
        assert r.result["nodes"] == 42

    def test_mixed_operations(self, executor, staad):
        code = """\
version = staad_call("GetApplicationVersion")
node_count = geo_call("GetNodeCount")
f"Version: {version}, Nodes: {node_count}"
"""
        r = executor.execute(code, staad)
        assert r.success
        assert "STAAD" in r.result
        assert "42" in r.result

    def test_data_processing(self, executor, staad):
        code = """\
import json
nodes = geo_call("GetNodeCount")
data = {"node_count": nodes, "status": "ok"}
json.dumps(data)
"""
        r = executor.execute(code, staad)
        assert r.success
        parsed = json.loads(r.result)
        assert parsed["node_count"] == 42


# ===========================================================================
# 17. PER-CALL ISOLATION
# ===========================================================================


class TestPerCallIsolation:
    """Each execute() call is fully isolated."""

    def test_handles_dont_persist(self, executor, staad):
        """Handles from call 1 are not available in call 2."""
        code1 = '_ensure_sub("Geometry")\n"ok"'
        r1 = executor.execute(code1, staad)
        assert r1.success

        # Second call should need to re-resolve
        code2 = 'geo_call("GetNodeCount")'
        r2 = executor.execute(code2, staad)
        assert r2.success
        assert r2.result == 42

    def test_variables_dont_persist(self, executor, staad):
        r1 = executor.execute("persistent_var = 123", staad)
        assert r1.success

        r2 = executor.execute("persistent_var", staad)
        assert not r2.success


# For json.loads in the complex workflow test
import json
