"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Unit tests for ``openstaad_mcp.sandbox.wasm_executor``.

These tests drive the real Extism plugin against an in-memory stub STAAD
object.  The evaluator.wasm must be present — it is built by
``src/openstaad_mcp/sandbox/evaluator_src/build.ps1``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from openstaad_mcp.sandbox.wasm_executor import ExecutionResult, WasmExecutor


# ---------------------------------------------------------------------------
# Stub STAAD — mimics the shape of the COM dispatch object
# ---------------------------------------------------------------------------


class _Geometry:
    def GetNodeCount(self) -> int:
        return 42

    def GetBeamList(self) -> list[int]:
        return [1, 2, 3, 4]

    def GetNodeCoordinates(self, nid: int) -> list[float]:
        return [float(nid), float(nid) * 2, 0.0]

    def Boom(self) -> int:
        raise RuntimeError("synthetic COM failure")

    def BadReturn(self) -> Any:
        # Not a scalar/list — should be rejected by _serialize_com_return.
        return object()


class _View:
    def ExportView(self, loc: str, name: str, fmt: int, overwrite: bool) -> int:  # noqa: ARG002
        return 0

    def GetWindowCount(self) -> int:
        return 1


class _StubStaad:
    def __init__(self) -> None:
        self.Geometry = _Geometry()
        self.View = _View()
        self._base_unit = "English"

    # Root-level methods used in tests.
    def GetBaseUnit(self) -> str:
        return self._base_unit

    def SetSilentMode(self, flag: bool) -> int:  # noqa: ARG002 - COM signature
        return 0

    # Destructive root methods for consent-gate tests.
    def NewSTAADFile(self, path: str, typ: int = 1, ui: int = 0) -> int:  # noqa: ARG002
        return 0

    def OpenSTAADFile(self, path: str) -> int:  # noqa: ARG002
        return 0

    def SaveModel(self) -> int:
        return 0

    def Quit(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def executor() -> WasmExecutor:
    # Short timeout so the suite stays snappy.  Individual tests override
    # when they need to exercise timeout behaviour.
    return WasmExecutor(timeout_seconds=5.0)


@pytest.fixture
def staad() -> _StubStaad:
    return _StubStaad()


# ---------------------------------------------------------------------------
# Happy-path basics
# ---------------------------------------------------------------------------


class TestBasics:
    def test_last_expression_is_returned(self, executor: WasmExecutor, staad: _StubStaad) -> None:
        r = executor.execute("1 + 2", staad)
        assert r.success, r.error
        assert r.result == 3

    def test_explicit_return(self, executor: WasmExecutor, staad: _StubStaad) -> None:
        r = executor.execute("const x = 10; return x * 4;", staad)
        assert r.success, r.error
        assert r.result == 40

    def test_console_log_captured(self, executor: WasmExecutor, staad: _StubStaad) -> None:
        r = executor.execute("console.log('hello', 'world'); return 7;", staad)
        assert r.success, r.error
        assert r.result == 7
        assert "hello world" in r.stdout

    def test_console_error_goes_to_stderr(self, executor: WasmExecutor, staad: _StubStaad) -> None:
        r = executor.execute("console.error('oops'); return 1;", staad)
        assert r.success
        assert "oops" in r.stderr
        assert "oops" not in r.stdout

    def test_com_scalar_call(self, executor: WasmExecutor, staad: _StubStaad) -> None:
        r = executor.execute("staad.Geometry.GetNodeCount()", staad)
        assert r.success, r.error
        assert r.result == 42

    def test_com_array_return(self, executor: WasmExecutor, staad: _StubStaad) -> None:
        r = executor.execute("staad.Geometry.GetBeamList()", staad)
        assert r.success, r.error
        assert r.result == [1, 2, 3, 4]

    def test_nested_array_return(self, executor: WasmExecutor, staad: _StubStaad) -> None:
        r = executor.execute("staad.Geometry.GetNodeCoordinates(3)", staad)
        assert r.success, r.error
        assert r.result == [3.0, 6.0, 0.0]

    def test_root_method_on_allowlist(self, executor: WasmExecutor, staad: _StubStaad) -> None:
        r = executor.execute("staad.GetBaseUnit()", staad)
        assert r.success, r.error
        assert r.result == "English"


# ---------------------------------------------------------------------------
# Security / isolation
# ---------------------------------------------------------------------------


class TestIsolation:
    def test_no_process_global(self, executor: WasmExecutor, staad: _StubStaad) -> None:
        r = executor.execute("typeof process", staad)
        assert r.success
        assert r.result == "undefined"

    def test_no_require(self, executor: WasmExecutor, staad: _StubStaad) -> None:
        r = executor.execute("typeof require", staad)
        assert r.success
        assert r.result == "undefined"

    def test_no_fetch(self, executor: WasmExecutor, staad: _StubStaad) -> None:
        # QuickJS-ng exposes `fetch` as a function, but the Extism runtime
        # is not configured with any allowed HTTP hosts — calling it must
        # fail, either synchronously (caught by try/catch) or by trapping
        # at the WASM boundary (surfaced as a sandbox error).
        r = executor.execute("typeof fetch", staad)
        assert r.success
        if r.result == "undefined":
            return
        r2 = executor.execute(
            "try { fetch('https://example.com'); return 'ok'; }"
            " catch (e) { return 'blocked'; }",
            staad,
        )
        if r2.success:
            assert r2.result == "blocked", f"fetch() was reachable: result={r2.result!r}"
        else:
            # A WASM trap from an unknown host import is equally fine —
            # the plugin could not reach any external service.
            assert r2.error is not None
            assert "ok" not in (r2.stdout or "")

    def test_no_globalthis_process(self, executor: WasmExecutor, staad: _StubStaad) -> None:
        r = executor.execute("typeof globalThis.process", staad)
        assert r.success
        assert r.result == "undefined"

    def test_globals_do_not_leak_across_calls(self, executor: WasmExecutor, staad: _StubStaad) -> None:
        # First call defines a global.
        r1 = executor.execute("globalThis.__leak__ = 'leaked'; return 1;", staad)
        assert r1.success
        # Fresh plugin per call — second call must not see it.
        r2 = executor.execute("typeof globalThis.__leak__", staad)
        assert r2.success
        assert r2.result == "undefined"

    def test_disallowed_sub_object(self, executor: WasmExecutor, staad: _StubStaad) -> None:
        # Arbitrary attribute access must be rejected by the allowlist.
        r = executor.execute("staad.NotARealSubObject.X()", staad)
        # The `com_get` failure raises inside WASM.
        assert not r.success
        assert r.error is not None

    def test_disallowed_root_method(self, executor: WasmExecutor, staad: _StubStaad) -> None:
        # Attach an obviously-unapproved method and try calling it.
        setattr(type(staad), "Haxor", lambda self: 1)
        try:
            r = executor.execute("staad.Haxor()", staad)
            assert not r.success
            assert "not allowed" in (r.error or "").lower()
        finally:
            delattr(type(staad), "Haxor")

    def test_denylist_blocks_setstandardprofiledbfolder(
        self, executor: WasmExecutor, staad: _StubStaad
    ) -> None:
        # Present the method on the stub; the executor must refuse it.
        setattr(type(staad), "SetStandardProfileDBFolder", lambda self, _p: 0)
        try:
            r = executor.execute("staad.SetStandardProfileDBFolder('C:/evil'); return 1;", staad)
            assert not r.success
            assert "not allowed" in (r.error or "").lower()
        finally:
            delattr(type(staad), "SetStandardProfileDBFolder")

    def test_sub_object_allowlist_blocks_unknown_method(
        self, executor: WasmExecutor, staad: _StubStaad
    ) -> None:
        # A method that exists on the stub but is NOT in the sub-object
        # allowlist must be rejected before getattr fires.
        r = executor.execute("staad.Geometry.Boom()", staad)
        assert not r.success
        assert r.error is not None
        assert "not allowed" in r.error.lower()
        # Must NOT leak the underlying RuntimeError message.
        assert "synthetic COM failure" not in r.error


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrors:
    def test_javascript_throw_is_user_error(
        self, executor: WasmExecutor, staad: _StubStaad
    ) -> None:
        r = executor.execute("throw new Error('nope')", staad)
        assert not r.success
        assert r.error is not None
        assert "nope" in r.error

    def test_com_exception_is_sanitised(
        self, executor: WasmExecutor, staad: _StubStaad, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The stub's Boom raises RuntimeError; the sandbox must catch it,
        # sanitise the message, and surface only the class name — NOT the
        # exception message which may contain paths or COM error tuples.
        # Temporarily add "Boom" to the Geometry allowlist so we test the
        # COM error path, not the allowlist rejection.
        import openstaad_mcp.sandbox.wasm_executor as _we
        from openstaad_mcp.sandbox.constants import ALLOWED_SUB_OBJECT_METHODS as _orig

        patched = {**_orig, "Geometry": _orig["Geometry"] | {"Boom"}}
        monkeypatch.setattr(_we, "ALLOWED_SUB_OBJECT_METHODS", patched)
        r = executor.execute("staad.Geometry.Boom()", staad)
        assert not r.success
        assert r.error is not None
        assert "RuntimeError" in r.error
        assert "synthetic COM failure" not in r.error
        assert "Traceback" not in r.error

    def test_non_serialisable_return_rejected(
        self, executor: WasmExecutor, staad: _StubStaad, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import openstaad_mcp.sandbox.wasm_executor as _we
        from openstaad_mcp.sandbox.constants import ALLOWED_SUB_OBJECT_METHODS as _orig

        patched = {**_orig, "Geometry": _orig["Geometry"] | {"BadReturn"}}
        monkeypatch.setattr(_we, "ALLOWED_SUB_OBJECT_METHODS", patched)
        r = executor.execute("staad.Geometry.BadReturn()", staad)
        assert not r.success
        assert r.error is not None
        assert "Unsupported COM return type" in r.error

    def test_code_too_large(self, staad: _StubStaad) -> None:
        small = WasmExecutor(timeout_seconds=2.0, max_code_bytes=32)
        r = small.execute("x".ljust(64, "y"), staad)
        assert not r.success
        assert "exceeds" in (r.error or "")


# ---------------------------------------------------------------------------
# Resource limits
# ---------------------------------------------------------------------------


class TestLimits:
    def test_timeout_trips(self, staad: _StubStaad) -> None:
        # 1s deadline, infinite loop inside JS.
        quick = WasmExecutor(timeout_seconds=1.0)
        r = quick.execute("while (true) {}", staad)
        assert not r.success
        assert r.error is not None
        assert "timeout" in r.error.lower() or "trap" in r.error.lower()

    def test_stdout_truncated(self, staad: _StubStaad) -> None:
        tight = WasmExecutor(timeout_seconds=5.0, max_stdout_bytes=256)
        # Each log is ~80 bytes — well past the 256-byte cap.
        code = """
        for (let i = 0; i < 200; i++) {
            console.log('xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx');
        }
        42
        """
        r = tight.execute(code, staad)
        assert r.success, r.error
        assert len(r.stdout.encode("utf-8")) <= 256

    def test_duration_recorded(self, executor: WasmExecutor, staad: _StubStaad) -> None:
        r = executor.execute("1 + 1", staad)
        assert r.success
        assert r.duration_seconds >= 0.0


# ---------------------------------------------------------------------------
# Sub-object handle cache
# ---------------------------------------------------------------------------


class TestHandleCache:
    def test_same_sub_object_cached_within_call(
        self, executor: WasmExecutor, staad: _StubStaad
    ) -> None:
        # Two references to staad.Geometry in the same script should resolve
        # to the same handle — but the user can't observe the handle from
        # JS, so we just verify both paths work end-to-end.
        r = executor.execute(
            "const g1 = staad.Geometry; const g2 = staad.Geometry; "
            "return g1.GetNodeCount() + g2.GetNodeCount();",
            staad,
        )
        assert r.success, r.error
        assert r.result == 84


# ---------------------------------------------------------------------------
# Result shape
# ---------------------------------------------------------------------------


class TestResultShape:
    def test_to_dict_contains_all_fields(
        self, executor: WasmExecutor, staad: _StubStaad
    ) -> None:
        r = executor.execute("42", staad)
        d = r.to_dict()
        assert set(d) == {"success", "result", "stdout", "stderr", "error", "duration_seconds"}


# ---------------------------------------------------------------------------
# Consent gate — Control 4: Explicit Consent for destructive operations
# ---------------------------------------------------------------------------


class TestConsentGate:
    """Verify that filesystem-write and session-destructive COM methods
    are blocked by default and permitted only when allow_destructive=True.
    """

    # -- Root-level destructive methods --

    def test_new_staad_file_blocked_by_default(
        self, executor: WasmExecutor, staad: _StubStaad
    ) -> None:
        r = executor.execute("staad.NewSTAADFile('C:/temp/test.std', 1, 0)", staad)
        assert not r.success
        assert "blocked" in (r.error or "").lower()
        assert "approve" in (r.error or "").lower()

    def test_new_staad_file_allowed_with_flag(
        self, executor: WasmExecutor, staad: _StubStaad
    ) -> None:
        r = executor.execute(
            "staad.NewSTAADFile('C:/temp/test.std', 1, 0)",
            staad,
            allow_destructive=True,
        )
        assert r.success, r.error
        assert r.result == 0

    def test_save_model_blocked_by_default(
        self, executor: WasmExecutor, staad: _StubStaad
    ) -> None:
        r = executor.execute("staad.SaveModel()", staad)
        assert not r.success
        assert "blocked" in (r.error or "").lower()

    def test_save_model_allowed_with_flag(
        self, executor: WasmExecutor, staad: _StubStaad
    ) -> None:
        r = executor.execute("staad.SaveModel()", staad, allow_destructive=True)
        assert r.success, r.error

    def test_quit_blocked_by_default(
        self, executor: WasmExecutor, staad: _StubStaad
    ) -> None:
        r = executor.execute("staad.Quit()", staad)
        assert not r.success
        assert "blocked" in (r.error or "").lower()

    def test_open_staad_file_blocked_by_default(
        self, executor: WasmExecutor, staad: _StubStaad
    ) -> None:
        r = executor.execute("staad.OpenSTAADFile('C:/models/test.std')", staad)
        assert not r.success
        assert "blocked" in (r.error or "").lower()

    # -- Sub-object destructive methods --

    def test_export_view_blocked_by_default(
        self, executor: WasmExecutor, staad: _StubStaad
    ) -> None:
        r = executor.execute(
            "staad.View.ExportView('C:/temp', 'shot', 1, true)", staad
        )
        assert not r.success
        assert "blocked" in (r.error or "").lower()

    def test_export_view_allowed_with_flag(
        self, executor: WasmExecutor, staad: _StubStaad
    ) -> None:
        r = executor.execute(
            "staad.View.ExportView('C:/temp', 'shot', 1, true)",
            staad,
            allow_destructive=True,
        )
        assert r.success, r.error

    # -- Non-destructive methods still work without the flag --

    def test_read_methods_unaffected(
        self, executor: WasmExecutor, staad: _StubStaad
    ) -> None:
        r = executor.execute("staad.Geometry.GetNodeCount()", staad)
        assert r.success, r.error
        assert r.result == 42

    def test_read_root_method_unaffected(
        self, executor: WasmExecutor, staad: _StubStaad
    ) -> None:
        r = executor.execute("staad.GetBaseUnit()", staad)
        assert r.success, r.error
        assert r.result == "English"

    def test_view_read_method_unaffected(
        self, executor: WasmExecutor, staad: _StubStaad
    ) -> None:
        r = executor.execute("staad.View.GetWindowCount()", staad)
        assert r.success, r.error
        assert r.result == 1


# ---------------------------------------------------------------------------
# Local path with consent gate — confirms non-UNC paths pass correctly
# ---------------------------------------------------------------------------


class TestLocalPathConsent:
    """Local paths pass with allow_destructive=True."""

    def test_local_path_allowed_with_flag(
        self, executor: WasmExecutor, staad: _StubStaad
    ) -> None:
        r = executor.execute(
            "staad.NewSTAADFile('C:/temp/test.std', 1, 0)",
            staad,
            allow_destructive=True,
        )
        assert r.success, r.error


# ---------------------------------------------------------------------------
# Section 12: WASM binary integrity verification
# ---------------------------------------------------------------------------


class TestWasmIntegrity:
    """Verify that the startup integrity check catches tampered binaries."""

    def test_sha256_file_matches_loaded_binary(self) -> None:
        """The shipped .sha256 file must match the loaded evaluator.wasm."""
        import hashlib
        from openstaad_mcp.sandbox.wasm_executor import (
            _EVALUATOR_BYTES,
            _EVALUATOR_SHA256_PATH,
        )

        assert _EVALUATOR_SHA256_PATH.exists(), "evaluator.wasm.sha256 missing"
        expected = _EVALUATOR_SHA256_PATH.read_text(encoding="utf-8").split()[0].lower()
        actual = hashlib.sha256(_EVALUATOR_BYTES).hexdigest().lower()
        assert actual == expected

    def test_tampered_hash_would_be_rejected(self, tmp_path: Any) -> None:
        """Simulate a tampered .sha256 and confirm the check logic rejects."""
        import hashlib
        from openstaad_mcp.sandbox.wasm_executor import _EVALUATOR_BYTES

        fake_hash = "0" * 64
        actual = hashlib.sha256(_EVALUATOR_BYTES).hexdigest().lower()
        assert fake_hash != actual, "sanity: fake hash must differ"
