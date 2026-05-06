"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Tests for the AST-based sandbox validator.
"""

from textwrap import dedent

import pytest

from openstaad_mcp.sandbox.ast import validate_code

# ── Tests for VALID code ─────────────────────────────────────────


class TestValidCode:
    """Code that should pass validation."""

    def test_simple_expression(self):
        assert validate_code("x = 1 + 2").is_valid

    def test_staad_method_call(self):
        assert validate_code("n = staad.Geometry.GetNodeCount()").is_valid

    def test_staad_complex_workflow(self):
        code = dedent(
            """
            coords = staad.Geometry.GetNodeCoordinates(1)
            x, y, z = coords
            result = {"x": x, "y": y, "z": z}
            """
        )
        assert validate_code(code).is_valid

    def test_list_comprehension(self):
        code = "nodes = [staad.Geometry.GetNodeCoordinates(i) for i in range(1, 10)]"
        assert validate_code(code).is_valid

    def test_for_loop(self):
        code = dedent(
            """
            data = []
            for i in range(1, 5):
                data.append(staad.Output.GetBeamEndForces(i, 1))
            result = data
            """
        )
        assert validate_code(code).is_valid

    def test_function_definition(self):
        code = dedent(
            """
            def get_forces(beam_id):
                return staad.Output.GetBeamEndForces(beam_id, 1)
            result = get_forces(1)
            """
        )
        assert validate_code(code).is_valid

    def test_try_except(self):
        code = dedent(
            """
            try:
                val = staad.Geometry.GetNodeCoordinates(999)
            except Exception as e:
                val = str(e)
            result = val
            """
        )
        assert validate_code(code).is_valid

    def test_math_operations(self):
        code = dedent(
            """
            import_val = math.sqrt(144)
            result = math.pi * import_val
            """
        )
        # Note: this uses the pre-injected `math`, no import statement
        assert validate_code(code).is_valid

    def test_json_usage(self):
        code = 'result = json.dumps({"key": "value"})'
        assert validate_code(code).is_valid

    def test_print_allowed(self):
        code = 'print("hello")'
        assert validate_code(code).is_valid

    def test_string_formatting(self):
        code = 'x = f"Node count: {staad.Geometry.GetNodeCount()}"'
        assert validate_code(code).is_valid

    def test_dict_and_list(self):
        code = dedent(
            """
            info = {"beams": [], "nodes": []}
            for i in range(1, 4):
                info["beams"].append(i)
            result = info
            """
        )
        assert validate_code(code).is_valid

    def test_class_definition(self):
        code = dedent(
            """
            class Collector:
                def __init__(self):
                    self.data = []
                def add(self, v):
                    self.data.append(v)
            c = Collector()
            c.add(42)
            result = c.data
            """
        )
        assert validate_code(code).is_valid

    def test_conditional(self):
        code = dedent(
            """
            count = staad.Geometry.GetBeamCount()
            result = "large" if count > 100 else "small"
            """
        )
        assert validate_code(code).is_valid

    def test_while_loop(self):
        code = dedent(
            """
            i = 0
            while i < 5:
                i += 1
            result = i
            """
        )
        assert validate_code(code).is_valid

    def test_lambda(self):
        code = "double = lambda x: x * 2\nresult = double(21)"
        assert validate_code(code).is_valid


# ── Tests for BLOCKED code ──────────────────────────────────────


class TestBlockedCode:
    """Code that must be rejected by the validator."""

    # -- Imports --

    def test_import_os(self):
        r = validate_code("import os")
        assert not r.is_valid

    def test_import_subprocess(self):
        r = validate_code("import subprocess")
        assert not r.is_valid

    def test_from_import(self):
        r = validate_code("from os import system")
        assert not r.is_valid

    def test_from_import_star(self):
        r = validate_code("from pathlib import *")
        assert not r.is_valid

    # -- Dangerous builtins --

    def test_eval_call(self):
        r = validate_code('eval("1+1")')
        assert not r.is_valid

    def test_exec_call(self):
        r = validate_code('exec("x=1")')
        assert not r.is_valid

    def test_compile_call(self):
        r = validate_code('compile("x=1", "<>", "exec")')
        assert not r.is_valid

    def test___import___call(self):
        r = validate_code('__import__("os")')
        assert not r.is_valid

    def test_globals_call(self):
        r = validate_code("g = globals()")
        assert not r.is_valid

    def test_locals_call(self):
        r = validate_code("l = locals()")
        assert not r.is_valid

    def test_getattr_call(self):
        r = validate_code('getattr(staad, "Geometry")')
        assert not r.is_valid

    def test_setattr_call(self):
        r = validate_code('setattr(staad, "x", 1)')
        assert not r.is_valid

    def test_delattr_call(self):
        r = validate_code('delattr(staad, "x")')
        assert not r.is_valid

    def test_open_file(self):
        r = validate_code('f = open("secret.txt")')
        assert not r.is_valid

    def test_input_call(self):
        r = validate_code('x = input("Enter: ")')
        assert not r.is_valid

    def test_breakpoint_call(self):
        r = validate_code("breakpoint()")
        assert not r.is_valid

    def test_exit_call(self):
        r = validate_code("exit()")
        assert not r.is_valid

    # -- Dunder access --

    def test_dunder_class(self):
        r = validate_code("x = staad.__class__")
        assert not r.is_valid

    def test_dunder_subclasses(self):
        r = validate_code("x = ().__class__.__subclasses__()")
        assert not r.is_valid

    def test_dunder_builtins(self):
        r = validate_code("x = __builtins__")
        assert not r.is_valid

    def test_dunder_globals(self):
        r = validate_code("x = staad.__globals__")
        assert not r.is_valid

    def test_dunder_code(self):
        r = validate_code("x = staad.__code__")
        assert not r.is_valid

    def test_dunder_init(self):
        r = validate_code("x = staad.__init__")
        assert not r.is_valid

    def test_dunder_dict(self):
        r = validate_code("x = staad.__dict__")
        assert not r.is_valid

    # -- Unsafe frame and co_code Attribute access --

    def test_gi_frame_not_blocked_by_ast(self):
        code = "g = (x for x in [1])\nf = g.gi_frame"
        result = validate_code(code)
        assert not result.is_valid, "'gi_frame' passes AST validation."

    def test_gi_code_not_blocked_by_ast(self):
        code = "g = (x for x in [1])\nc = g.gi_code"
        result = validate_code(code)
        assert not result.is_valid, "'gi_code' passes AST validation."

    def test_f_code_not_blocked_by_ast(self):
        code = "x.f_code"
        result = validate_code(code)
        assert not result.is_valid, "'f_code' passes AST validation."

    def test_tb_frame_not_blocked_by_ast(self):
        code = "x.tb_frame"
        result = validate_code(code)
        assert not result.is_valid, "'tb_frame' passes AST validation."

    def test_f_globals_not_blocked_by_ast(self):
        code = "x.f_globals"
        result = validate_code(code)
        assert not result.is_valid, "'f_globals' passes AST validation."

    # -- Scope escape --

    def test_global_statement(self):
        r = validate_code("global x")
        assert not r.is_valid

    def test_nonlocal_statement(self):
        code = dedent(
            """
            def outer():
                x = 1
                def inner():
                    nonlocal x
                    x = 2
            """
        )
        r = validate_code(code)
        assert not r.is_valid

    # -- Async constructs --

    def test_async_function(self):
        r = validate_code("async def f(): pass")
        assert not r.is_valid

    def test_async_for(self):
        code = "async def f():\n async for x in y: pass"
        r = validate_code(code)
        assert not r.is_valid

    def test_async_with(self):
        code = "async def f():\n async with x as y: pass"
        r = validate_code(code)
        assert not r.is_valid

    def test_await(self):
        code = "async def f():\n await something()"
        r = validate_code(code)
        assert not r.is_valid

    # -- Adversarial patterns --

    def test_eval_via_string(self):
        """Attempt to call eval through string manipulation."""
        r = validate_code("eval(\"__import__('os').system('rm -rf /')\")")
        assert not r.is_valid

    def test_subclass_walk(self):
        """Classic Python sandbox escape via subclass enumeration."""
        r = validate_code("().__class__.__bases__[0].__subclasses__()")
        assert not r.is_valid

    def test_getattr_dunder(self):
        """Attempt to access dunder via getattr."""
        r = validate_code("getattr(staad, '__class__')")
        assert not r.is_valid

    def test_type_constructor(self):
        """Attempt to create dynamic types."""
        r = validate_code("type('X', (), {'run': lambda s: None})()")
        assert not r.is_valid

    def test_decorator_smuggle(self):
        """Attempt to smuggle code via decorators."""
        code = dedent(
            """
            @eval
            def f():
                pass
            """
        )
        r = validate_code(code)
        assert not r.is_valid

    # -- Syntax errors --

    def test_syntax_error(self):
        r = validate_code("def f(")
        assert not r.is_valid
        assert "syntax error" in r.errors[0].message.lower()

    def test_empty_code(self):
        r = validate_code("")
        assert r.is_valid  # empty code is valid (no-op)

    def test_multiple_violations(self):
        code = dedent(
            """
            import os
            eval("bad")
            x = staad.__class__
            """
        )
        r = validate_code(code)
        assert not r.is_valid
        assert len(r.errors) >= 3


# ── str.format() dunder access ─────────────


class TestFormatStringDunderBlocked:
    """str.format() dunder attribute access must be blocked."""

    def test_format_with_dunder_class(self):
        r = validate_code('result = "{0.__class__}".format(staad)')
        assert not r.is_valid

    def test_format_with_dunder_mro(self):
        r = validate_code('result = "{0.__class__.__mro__}".format([])')
        assert not r.is_valid

    def test_format_with_dunder_init_globals(self):
        r = validate_code('result = "{0.__init__.__globals__}".format(staad)')
        assert not r.is_valid

    def test_format_map_with_dunder(self):
        r = validate_code('result = "{x.__class__}".format_map({"x": staad})')
        assert not r.is_valid

    def test_format_call_blocked(self):
        r = validate_code('"hello {0}".format("world")')
        assert not r.is_valid

    def test_format_map_call_blocked(self):
        r = validate_code('"hello {x}".format_map({"x": "world"})')
        assert not r.is_valid

    def test_fstring_dunder_still_blocked(self):
        """f-strings with dunder access are blocked by visit_Attribute."""
        r = validate_code('f"{staad.__class__}"')
        assert not r.is_valid

    def test_safe_string_constant_allowed(self):
        """Normal strings without dunder patterns should be allowed."""
        r = validate_code('x = "hello world"')
        assert r.is_valid

    def test_format_builtin_blocked(self):
        """The format() builtin should now be blocked."""
        r = validate_code('format(42, "d")')
        assert not r.is_valid


# ── mro() method blocked ───────────────────


class TestMroBlocked:
    """mro() method must be blocked to prevent type hierarchy leak."""

    def test_int_mro_blocked(self):
        r = validate_code("result = int.mro()")
        assert not r.is_valid

    def test_str_mro_blocked(self):
        r = validate_code("result = str.mro()")
        assert not r.is_valid

    def test_list_mro_blocked(self):
        r = validate_code("result = list.mro()")
        assert not r.is_valid


# ── Exception usage in AST ───────────────────────────

# Representative set of exception names to validate AST acceptance.
_EXCEPTION_NAMES = [
    "Exception",
    "ValueError",
    "TypeError",
    "AttributeError",
    "RuntimeError",
    "KeyError",
    "IndexError",
    "ZeroDivisionError",
    "OSError",
    "StopIteration",
    "ArithmeticError",
    "LookupError",
    "OverflowError",
    "NotImplementedError",
    "Warning",
    "DeprecationWarning",
]


class TestExceptionAstValidation:
    """Exception class references must pass AST validation."""

    @pytest.mark.parametrize("exc_name", _EXCEPTION_NAMES)
    def test_try_except_single(self, exc_name):
        code = dedent(f"""
            try:
                x = 1
            except {exc_name} as e:
                result = str(e)
        """)
        assert validate_code(code).is_valid, f"except {exc_name} should pass validation"

    @pytest.mark.parametrize("exc_name", _EXCEPTION_NAMES)
    def test_raise_exception(self, exc_name):
        code = f'raise {exc_name}("test")'
        assert validate_code(code).is_valid, f"raise {exc_name} should pass validation"

    def test_try_except_multiple_tuple(self):
        code = dedent("""
            try:
                x = 1
            except (ValueError, TypeError, KeyError) as e:
                result = str(e)
        """)
        assert validate_code(code).is_valid

    def test_try_except_bare(self):
        code = dedent("""
            try:
                x = 1
            except:
                result = "error"
        """)
        assert validate_code(code).is_valid
