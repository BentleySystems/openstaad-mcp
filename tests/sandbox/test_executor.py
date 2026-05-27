"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Tests for the sandboxed code executor.
"""

from textwrap import dedent

import pytest

from openstaad_mcp.sandbox.const import ALLOWED_BUILTIN_EXCEPTIONS
from openstaad_mcp.sandbox.executor import Executor


class MockStaad:
    """Fake OpenSTAAD root for testing without COM."""

    class Geometry:
        @staticmethod
        def GetNodeCount():
            return 42

        @staticmethod
        def GetNodeCoordinates(node_id):
            return (1.0, 2.0, 3.0)

        @staticmethod
        def GetBeamCount():
            return 10

        @staticmethod
        def GetBeamList():
            return [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    class Output:
        @staticmethod
        def GetBeamEndForces(beam_no, load_case):
            return [100.0, -50.0, 25.0, 10.0, -5.0, 2.5]

    class Load:
        pass

    class Property:
        pass

    class Support:
        pass

    class Command:
        pass

    class View:
        pass

    class Table:
        pass

    class Design:
        pass

    @staticmethod
    def GetApplicationVersion():
        return "STAAD.Pro CONNECT Edition V25"

    @staticmethod
    def IsAnalyzing():
        return False


@pytest.fixture
def staad():
    return MockStaad()


@pytest.fixture
def executor():
    return Executor()


class TestResultCapture:
    """Test that results are captured correctly."""

    def test_last_expression(self, staad, executor):
        r = executor.execute("1 + 2", staad)
        assert r.success
        assert r.result == 3

    def test_explicit_result_variable(self, staad, executor):
        r = executor.execute("result = 42", staad)
        assert r.success
        assert r.result == 42

    def test_result_variable_takes_priority(self, staad, executor):
        code = dedent(
            """
            result = 'explicit'
            99
            """
        )
        r = executor.execute(code, staad)
        assert r.success
        assert r.result == "explicit"

    def test_staad_method_call(self, staad, executor):
        r = executor.execute("staad.Geometry.GetNodeCount()", staad)
        assert r.success
        assert r.result == 42

    def test_staad_complex_workflow(self, staad, executor):
        code = dedent(
            """
            coords = staad.Geometry.GetNodeCoordinates(1)
            result = {"x": coords[0], "y": coords[1], "z": coords[2]}
            """
        )
        r = executor.execute(code, staad)
        assert r.success
        assert r.result == {"x": 1.0, "y": 2.0, "z": 3.0}

    def test_list_result(self, staad, executor):
        code = dedent(
            """
            forces = staad.Output.GetBeamEndForces(1, 1)
            result = forces
            """
        )
        r = executor.execute(code, staad)
        assert r.success
        assert r.result == [100.0, -50.0, 25.0, 10.0, -5.0, 2.5]

    def test_none_result(self, staad, executor):
        r = executor.execute("x = 1", staad)
        assert r.success
        assert r.result is None

    def test_json_module_available(self, staad, executor):
        code = 'result = json.dumps({"a": 1})'
        r = executor.execute(code, staad)
        assert r.success
        assert r.result == '{"a": 1}'

    def test_math_module_available(self, staad, executor):
        code = "result = math.sqrt(144)"
        r = executor.execute(code, staad)
        assert r.success
        assert r.result == 12.0


class TestStdoutCapture:
    """Test that print() output is captured."""

    def test_print_captured(self, staad, executor):
        r = executor.execute('print("hello world")', staad)
        assert r.success
        assert "hello world" in r.stdout

    def test_multiple_prints(self, staad, executor):
        code = dedent(
            """
            print("line 1")
            print("line 2")
            """
        )
        r = executor.execute(code, staad)
        assert r.success
        assert "line 1" in r.stdout
        assert "line 2" in r.stdout

    def test_stderr_empty_on_success(self, staad, executor):
        r = executor.execute('print("hello")', staad)
        assert r.success
        assert r.stderr == ""


class TestStderrCapture:
    """Test that stderr output is captured."""

    def test_stderr_field_present_on_error(self, staad, executor):
        r = executor.execute("1 / 0", staad)
        assert not r.success
        assert isinstance(r.stderr, str)

    def test_stderr_field_present_on_success(self, staad, executor):
        r = executor.execute("x = 1", staad)
        assert r.success
        assert isinstance(r.stderr, str)


class TestDurationCapture:
    """Test that execution duration is captured."""

    def test_duration_positive_on_success(self, staad, executor):
        r = executor.execute("x = 1 + 2", staad)
        assert r.success
        assert r.duration_seconds > 0.0

    def test_duration_positive_on_error(self, staad, executor):
        r = executor.execute("1 / 0", staad)
        assert not r.success
        assert r.duration_seconds >= 0.0

    def test_duration_zero_on_validation_error(self, staad, executor):
        r = executor.execute("import os", staad)
        assert not r.success
        assert r.duration_seconds == 0.0


class TestToDict:
    """Test that to_dict() returns all fields."""

    def test_to_dict_keys(self, staad, executor):
        r = executor.execute("1 + 2", staad)
        d = r.to_dict()
        assert set(d.keys()) == {
            "success",
            "result",
            "stdout",
            "stderr",
            "error",
            "duration_seconds",
        }


class TestErrorHandling:
    """Test that errors are properly reported."""

    def test_runtime_error(self, staad, executor):
        r = executor.execute("1 / 0", staad)
        assert not r.success
        assert isinstance(r.error, str)
        assert "ZeroDivisionError" in r.error

    def test_name_error(self, staad, executor):
        r = executor.execute("undefined_variable", staad)
        assert not r.success
        assert isinstance(r.error, str)
        assert "NameError" in r.error

    def test_attribute_error(self, staad, executor):
        r = executor.execute("staad.NonExistent.Method()", staad)
        assert not r.success
        assert isinstance(r.error, str)
        assert "AttributeError" in r.error

    def test_validation_error_reported(self, staad, executor):
        r = executor.execute("import os", staad)
        assert not r.success
        assert isinstance(r.error, str)
        assert "not allowed" in r.error

    def test_syntax_error(self, staad, executor):
        r = executor.execute("def f(", staad)
        assert not r.success
        assert isinstance(r.error, str)
        assert "syntax error" in r.error.lower()

    def test_error_includes_stdout(self, staad, executor):
        code = dedent(
            """
            print("before error")
            1 / 0
            """
        )
        r = executor.execute(code, staad)
        assert not r.success
        assert "before error" in r.stdout
        assert isinstance(r.error, str)
        assert "ZeroDivisionError" in r.error


class TestSandboxIsolation:
    """Ensure the sandbox blocks dangerous operations."""

    def test_import_blocked(self, staad, executor):
        r = executor.execute("import os", staad)
        assert not r.success

    def test_open_blocked(self, staad, executor):
        r = executor.execute('open("file.txt")', staad)
        assert not r.success

    def test_eval_blocked(self, staad, executor):
        r = executor.execute('eval("1+1")', staad)
        assert not r.success

    def test_dunder_blocked(self, staad, executor):
        r = executor.execute("staad.__class__", staad)
        assert not r.success

    def test_builtins_not_leaking(self, staad, executor):
        """Ensure __builtins__ is not the full module."""
        r = executor.execute("result = type(__builtins__)", staad)
        # This should fail because __builtins__ is in BLOCKED_BUILTINS
        assert not r.success


class TestModuleProxySandboxEscape:
    """Regression tests for the module-graph traversal sandbox-escape vector.

    Two independent layers block this:
    1. AST: visit_Attribute rejects non-whitelisted attrs on known module Names.
    2. Runtime: _ModuleProxy raises AttributeError for any attr not in the
       per-module whitelist, covering aliased access the AST cannot track.
    """

    # ------------------------------------------------------------------
    # Exact PoC from the sandbox-escape bug report (AST layer blocks it)
    # ------------------------------------------------------------------

    def test_json_codecs_traversal_blocked(self, staad, executor):
        """CVE-style PoC: json.codecs.builtins must not be reachable."""
        code = dedent(
            """
            b = json.codecs.builtins
            ns = {}
            b.exec("import os; result = os.getcwd()", {"__builtins__": b}, ns)
            result = ns["result"]
            """
        )
        r = executor.execute(code, staad)
        assert not r.success, "Sandbox escape via json.codecs.builtins must be blocked"

    # ------------------------------------------------------------------
    # AST-layer: direct non-whitelisted attribute access on module Names
    # ------------------------------------------------------------------

    def test_json_non_whitelisted_attr_blocked_by_ast(self, staad, executor):
        r = executor.execute("result = json.codecs", staad)
        assert not r.success

    def test_json_loader_attr_blocked_by_ast(self, staad, executor):
        r = executor.execute("result = json.__loader__", staad)
        assert not r.success

    def test_math_non_whitelisted_attr_blocked_by_ast(self, staad, executor):
        r = executor.execute("result = math.__spec__", staad)
        assert not r.success

    # ------------------------------------------------------------------
    # Runtime-proxy layer: aliased access the AST cannot track
    # ------------------------------------------------------------------

    def test_json_non_whitelisted_attr_blocked_by_proxy(self, staad, executor):
        """Alias bypasses AST check; _ModuleProxy must block at runtime."""
        code = dedent(
            """
            j = json
            result = j.codecs
            """
        )
        r = executor.execute(code, staad)
        assert not r.success

    def test_json_dunder_attr_blocked_by_proxy(self, staad, executor):
        code = dedent(
            """
            j = json
            result = j.__class__
            """
        )
        r = executor.execute(code, staad)
        assert not r.success

    def test_math_non_whitelisted_attr_blocked_by_proxy(self, staad, executor):
        code = dedent(
            """
            m = math
            result = m.__loader__
            """
        )
        r = executor.execute(code, staad)
        assert not r.success

    # ------------------------------------------------------------------
    # Proxy immutability: confirm namespace poisoning is blocked
    # ------------------------------------------------------------------

    def test_json_proxy_attribute_assignment_blocked(self, staad, executor):
        """Cross-call namespace poisoning must not be possible."""
        r = executor.execute("json.dumps = None", staad)
        assert not r.success

    # ------------------------------------------------------------------
    # Regression guard: whitelisted attrs must still work
    # ------------------------------------------------------------------

    def test_json_dumps_still_works(self, staad, executor):
        r = executor.execute('result = json.dumps({"key": 1})', staad)
        assert r.success
        assert r.result == '{"key": 1}'

    def test_json_loads_still_works(self, staad, executor):
        r = executor.execute("result = json.loads('{\"a\": 2}')", staad)
        assert r.success
        assert r.result == {"a": 2}

    def test_math_sqrt_still_works(self, staad, executor):
        r = executor.execute("result = math.sqrt(9)", staad)
        assert r.success
        assert r.result == 3.0

    def test_math_pi_still_works(self, staad, executor):
        r = executor.execute("result = math.pi > 3", staad)
        assert r.success
        assert r.result is True


class TestFormatStringDunderBlocked:
    """str.format() dunder traversal must be blocked end-to-end."""

    def test_format_dunder_class_blocked(self, staad, executor):
        r = executor.execute('result = "{0.__class__}".format(staad)', staad)
        assert not r.success

    def test_format_dunder_init_globals_blocked(self, staad, executor):
        r = executor.execute('"{0.__init__.__globals__}".format(staad)', staad)
        assert not r.success

    def test_format_map_dunder_blocked(self, staad, executor):
        r = executor.execute('"{x.__class__}".format_map({"x": staad})', staad)
        assert not r.success


class TestMroBlocked:
    """mro() must be blocked to prevent type hierarchy leaks."""

    def test_int_mro_blocked(self, staad, executor):
        r = executor.execute("result = int.mro()", staad)
        assert not r.success

    def test_str_mro_blocked(self, staad, executor):
        r = executor.execute("result = str.mro()", staad)
        assert not r.success


class TestDeadlockPrevention:
    """Executor must not permanently deadlock after timeout."""

    def test_lock_timeout_returns_error(self, staad, executor):
        """If the lock is held, execute returns an error instead of blocking."""
        # Manually acquire the lock to simulate a stuck thread
        executor._exec_lock.acquire()
        try:
            r = executor.execute("result = 1", staad)
            assert not r.success
            assert "busy" in r.error.lower() or "timed out" in r.error.lower()
        finally:
            executor._exec_lock.release()

    def test_normal_execution_still_works(self, staad, executor):
        """Normal execution acquires and releases the lock correctly."""
        r1 = executor.execute("result = 1", staad)
        assert r1.success
        r2 = executor.execute("result = 2", staad)
        assert r2.success
        assert r2.result == 2


class TestLimitedStdout:
    """Stdout buffer must be bounded during execution."""

    def test_large_print_truncated(self, staad, executor):
        """Printing beyond MAX_EXECUTION_STDOUT is silently discarded."""
        from openstaad_mcp.sandbox.const import MAX_EXECUTION_STDOUT

        code = f'print("A" * {MAX_EXECUTION_STDOUT + 1000})'
        r = executor.execute(code, staad)
        assert r.success
        assert len(r.stdout) <= MAX_EXECUTION_STDOUT + 1  # +1 for newline from print

    def test_many_prints_truncated(self, staad, executor):
        """Many print calls are capped at the buffer limit."""
        code = 'for i in range(100000): print("A" * 100)'
        r = executor.execute(code, staad)
        assert r.success
        from openstaad_mcp.sandbox.const import MAX_EXECUTION_STDOUT

        assert len(r.stdout) <= MAX_EXECUTION_STDOUT + 100  # small margin


class TestStackTraceSanitization:
    """Error tracebacks must not leak filesystem paths."""

    def test_error_no_real_paths(self, staad, executor):
        """Runtime errors should not contain real filesystem paths."""
        r = executor.execute("1 / 0", staad)
        assert not r.success
        assert "ZeroDivisionError" in r.error
        # Should contain <sandbox> but not real paths
        assert "<sandbox>" in r.error or "(in external code)" in r.error
        # Should NOT contain typical Windows path patterns
        import re

        assert not re.search(r"C:\\Users\\", r.error)
        assert not re.search(r"site-packages", r.error)

    def test_sandbox_line_numbers_preserved(self, staad, executor):
        """Sandbox frame line numbers should still be available."""
        code = dedent(
            """
            x = 1
            y = 2
            z = 1/0
            """
        )
        r = executor.execute(code, staad)
        assert not r.success
        assert "ZeroDivisionError" in r.error


class TestOutputSanitization:
    """Result values must be length-limited."""

    def test_large_string_result_truncated(self, staad, executor):
        code = 'result = "A" * 200000'
        r = executor.execute(code, staad)
        assert r.success
        assert len(str(r.result)) <= 110000  # some margin for truncation message


class TestExceptionHandling:
    """Exception classes must be available in the sandbox."""

    @pytest.mark.parametrize("exc_name", ALLOWED_BUILTIN_EXCEPTIONS)
    def test_builtin_exception_available(self, staad, executor, exc_name):
        """Each built-in exception class can be referenced by name."""
        code = f"result = issubclass({exc_name}, Exception)"
        r = executor.execute(code, staad)
        assert r.success, f"{exc_name} should be available in sandbox: {r.error}"
        assert r.result is True

    def test_catch_exception_from_api_call(self, staad, executor):
        """catch Exception from a failing call."""
        code = dedent(
            """
            try:
                r = staad.Geometry.NonExistentMethod()
                result = {"data": r}
            except Exception as e:
                result = {"error": str(e)}
            """
        )
        r = executor.execute(code, staad)
        assert r.success, f"try/except Exception should work: {r.error}"
        assert "error" in r.result

    def test_catch_zero_division(self, staad, executor):
        """Catch a specific built-in exception by name."""
        code = dedent(
            """
            try:
                x = 1 / 0
            except ZeroDivisionError as e:
                result = str(e)
            """
        )
        r = executor.execute(code, staad)
        assert r.success, f"try/except ZeroDivisionError should work: {r.error}"
        assert "division" in r.result.lower()

    def test_exception_hierarchy_catch(self, staad, executor):
        """except Exception catches ValueError (subclass)."""
        code = dedent(
            """
            try:
                int("not_a_number")
            except Exception as e:
                result = str(e)
            """
        )
        r = executor.execute(code, staad)
        assert r.success, f"except Exception should catch ValueError: {r.error}"
        assert "invalid literal" in r.result

    def test_isinstance_with_exception_type(self, staad, executor):
        """isinstance() works with exception types inside a handler."""
        code = dedent(
            """
            try:
                1 / 0
            except Exception as e:
                result = isinstance(e, ZeroDivisionError)
            """
        )
        r = executor.execute(code, staad)
        assert r.success, f"isinstance with exception type should work: {r.error}"
        assert r.result is True

    def test_raise_and_except(self, staad, executor):
        """raise ValueError(...) + catch it works."""
        code = dedent(
            """
            try:
                raise ValueError("test message")
            except ValueError as e:
                result = str(e)
            """
        )
        r = executor.execute(code, staad)
        assert r.success, f"raise + catch should work: {r.error}"
        assert r.result == "test message"

    def test_raise_and_multiple_excepts(self, staad, executor):
        """Multiple except clauses with different exception types."""
        code = dedent(
            """
            try:
                d = {}
                d["missing"]
            except KeyError:
                result = "key_error"
            except ValueError:
                result = "value_error"
            """
        )
        r = executor.execute(code, staad)
        assert r.success, f"multiple except clauses should work: {r.error}"
        assert r.result == "key_error"

    def test_tuple_except(self, staad, executor):
        """except (TypeError, ValueError) tuple syntax works."""
        code = dedent(
            """
            try:
                int("bad")
            except (TypeError, ValueError):
                result = "caught"
            """
        )
        r = executor.execute(code, staad)
        assert r.success, f"except tuple should work: {r.error}"
        assert r.result == "caught"

    def test_bare_except(self, staad, executor):
        """bare except: (no exception type)."""
        code = dedent(
            """
            try:
                1 / 0
            except:
                result = "caught"
            """
        )
        r = executor.execute(code, staad)
        assert r.success, f"bare except should work: {r.error}"
        assert r.result == "caught"

    def test_base_exception_not_available(self, staad, executor):
        """BaseException must NOT be available (could catch SystemExit etc.)."""
        code = "result = BaseException"
        r = executor.execute(code, staad)
        assert not r.success, "BaseException should not be available in sandbox"

    def test_system_exit_not_available(self, staad, executor):
        """SystemExit must NOT be available."""
        code = "result = SystemExit"
        r = executor.execute(code, staad)
        assert not r.success, "SystemExit should not be available in sandbox"

    def test_keyboard_interrupt_not_available(self, staad, executor):
        """KeyboardInterrupt must NOT be available."""
        code = "result = KeyboardInterrupt"
        r = executor.execute(code, staad)
        assert not r.success, "KeyboardInterrupt should not be available in sandbox"


class TestInputInjection:
    """Tests for ``__input`` data injection into the sandbox."""

    def test_input_none_when_no_data(self, staad, executor):
        """``input_data`` is None when no input_data is provided (backward compat)."""
        r = executor.execute("result = input_data", staad)
        assert r.success
        assert r.result is None

    def test_input_contains_provided_data(self, staad, executor):
        data = (("a", "b"), (1, 2), (3, 4))
        r = executor.execute("result = [list(row) for row in input_data]", staad, input_data=data)
        assert r.success
        assert r.result == [["a", "b"], [1, 2], [3, 4]]

    def test_input_deeply_immutable(self, staad, executor):
        """Sandbox code cannot mutate ``input_data`` (tuples are immutable)."""
        data = (("a", "b"), (1, 2))
        r = executor.execute(
            dedent(
                """
                try:
                    input_data[0] = "mutated"
                    result = "mutation succeeded"
                except TypeError:
                    result = "immutable"
                """
            ),
            staad,
            input_data=data,
        )
        assert r.success
        assert r.result == "immutable"

    def test_input_iterable(self, staad, executor):
        """Sandbox code can iterate over ``input_data``."""
        data = ((10,), (20,), (30,))
        r = executor.execute(
            "result = sum(row[0] for row in input_data)",
            staad,
            input_data=data,
        )
        assert r.success
        assert r.result == 60

    def test_input_indexable(self, staad, executor):
        """Sandbox code can index into ``input_data``."""
        data = (("x",), (42,))
        r = executor.execute("result = input_data[1][0]", staad, input_data=data)
        assert r.success
        assert r.result == 42

    def test_input_no_carryover(self, staad, executor):
        """``input_data`` does not persist across executions."""
        executor.execute("x = input_data", staad, input_data=((1,),))
        r = executor.execute("result = input_data", staad)
        assert r.success
        assert r.result is None

    def test_input_dict_shape(self, staad, executor):
        """Dict-shaped input_data (XLSX multi-sheet) works."""
        data = {"Sheet1": {"columns": ("a",), "rows": ((1,), (2,))}}
        r = executor.execute(
            "result = len(input_data['Sheet1']['rows'])",
            staad,
            input_data=data,
        )
        assert r.success
        assert r.result == 2
