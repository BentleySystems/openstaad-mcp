"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Deep red-team / CTF-style tests for the WASM sandbox.

These tests probe attack surfaces that go beyond simple input validation.
They test host function protocol-level attacks, handle forging, prototype
pollution, the JSON serialisation boundary, and the raw ``hostCall``/
``hostVoid`` global exposure documented in ``test_wasi_surface.py``.

Threat model: a sophisticated attacker (prompt-injected LLM or malicious
skill author) who has read the evaluator.js source and knows the exact
host function protocol.

Requires: evaluator.wasm built from evaluator_src/. No live COM needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from openstaad_mcp.sandbox.wasm_executor import WasmExecutor


# ---------------------------------------------------------------------------
# Stub STAAD — records calls, tracks what the sandbox actually dispatches
# ---------------------------------------------------------------------------


class _SpyGeometry:
    """Records every call for post-test inspection."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def GetNodeCount(self) -> int:
        self.calls.append(("GetNodeCount", ()))
        return 42

    def GetNodeCoordinates(self, nid: int) -> list[float]:
        self.calls.append(("GetNodeCoordinates", (nid,)))
        return [float(nid), 0.0, 0.0]

    def AddNode(self, x: float, y: float, z: float) -> int:
        self.calls.append(("AddNode", (x, y, z)))
        return 99


class _SpyView:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def ExportView(self, loc: str, name: str, fmt: int, overwrite: bool) -> int:
        self.calls.append(("ExportView", (loc, name, fmt, overwrite)))
        return 0

    def GetWindowCount(self) -> int:
        self.calls.append(("GetWindowCount", ()))
        return 1


class _SpyStaad:
    def __init__(self) -> None:
        self.Geometry = _SpyGeometry()
        self.View = _SpyView()
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def GetBaseUnit(self) -> str:
        self.calls.append(("GetBaseUnit", ()))
        return "Metric"

    def NewSTAADFile(self, path: str, typ: int = 1, ui: int = 0) -> int:
        self.calls.append(("NewSTAADFile", (path, typ, ui)))
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
def staad() -> _SpyStaad:
    return _SpyStaad()


# ═══════════════════════════════════════════════════════════════════════════
# 1. Direct hostCall/hostVoid bypass — the Proxy layer is optional
# ═══════════════════════════════════════════════════════════════════════════


class TestDirectHostCallBypass:
    """User code can call hostCall(com_invoke, ...) directly because the
    evaluator.js globals are on the same scope. Verify the Python-side
    validation still holds even when the Proxy is circumvented."""

    def test_direct_hostcall_allowed_method(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Direct hostCall to an allowed root method — should succeed."""
        r = executor.execute(
            """
            const resp = hostCall(com_invoke, {handle: 0, method: 'GetBaseUnit', args: []});
            return resp.result;
            """,
            staad,
        )
        assert r.success, r.error
        assert r.result == "Metric"

    def test_direct_hostcall_denied_method(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Direct hostCall to a DENIED method — must still be blocked."""
        r = executor.execute(
            """
            const resp = hostCall(com_invoke, {handle: 0, method: 'Run', args: []});
            return resp;
            """,
            staad,
        )
        # The host returns an error JSON, not a WASM trap
        assert r.success  # The JS code itself doesn't throw
        assert "not allowed" in str(r.result).lower()

    def test_direct_hostcall_destructive_without_consent(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Direct hostCall to SaveModel without allow_destructive — blocked."""
        r = executor.execute(
            """
            const resp = hostCall(com_invoke, {handle: 0, method: 'SaveModel', args: []});
            return resp;
            """,
            staad,
        )
        assert r.success
        assert "blocked" in str(r.result).lower()
        assert not staad.calls

    def test_direct_hostcall_destructive_with_consent(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Direct hostCall to SaveModel WITH allow_destructive — succeeds."""
        r = executor.execute(
            """
            const resp = hostCall(com_invoke, {handle: 0, method: 'SaveModel', args: []});
            if (resp.error) throw new Error(resp.error);
            return resp.result;
            """,
            staad,
            allow_destructive=True,
        )
        assert r.success, r.error
        assert ("SaveModel", ()) in staad.calls

    def test_direct_com_get_allowed_sub_object(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Direct hostCall to com_get for an allowed sub-object — succeeds."""
        r = executor.execute(
            """
            const resp = hostCall(com_get, {handle: 0, prop: 'Geometry'});
            if (resp.error) throw new Error(resp.error);
            const resp2 = hostCall(com_invoke, {handle: resp.handle, method: 'GetNodeCount', args: []});
            return resp2.result;
            """,
            staad,
        )
        assert r.success, r.error
        assert r.result == 42

    def test_direct_com_get_forbidden_sub_object(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Direct com_get for a non-existent/disallowed sub-object — rejected."""
        r = executor.execute(
            """
            const resp = hostCall(com_get, {handle: 0, prop: '__class__'});
            return resp;
            """,
            staad,
        )
        assert r.success
        assert "not allowed" in str(r.result).lower()


# ═══════════════════════════════════════════════════════════════════════════
# 2. Handle forging and manipulation
# ═══════════════════════════════════════════════════════════════════════════


class TestHandleForging:
    """Attempt to forge or manipulate handle IDs to access objects the
    sandbox shouldn't reach."""

    def test_handle_negative_one(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Forge handle -1 — should be rejected."""
        r = executor.execute(
            """
            const resp = hostCall(com_invoke, {handle: -1, method: 'GetBaseUnit', args: []});
            return resp;
            """,
            staad,
        )
        assert r.success
        assert "invalid" in str(r.result).lower() or "error" in str(r.result).lower()

    def test_handle_999(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Forge handle 999 — no object registered, should fail."""
        r = executor.execute(
            """
            const resp = hostCall(com_invoke, {handle: 999, method: 'GetBaseUnit', args: []});
            return resp;
            """,
            staad,
        )
        assert r.success
        assert "invalid" in str(r.result).lower() or "error" in str(r.result).lower()

    def test_handle_float(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Pass float handle 0.5 — int() truncates to 0, which IS valid."""
        r = executor.execute(
            """
            const resp = hostCall(com_invoke, {handle: 0.5, method: 'GetBaseUnit', args: []});
            return resp;
            """,
            staad,
        )
        assert r.success
        # int(0.5) = 0, which is the root handle — this succeeds
        assert r.result == {"result": "Metric"} or r.result == "Metric"

    def test_handle_string(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Pass string handle '0' — int('0') = 0, which IS valid."""
        r = executor.execute(
            """
            const resp = hostCall(com_invoke, {handle: '0', method: 'GetBaseUnit', args: []});
            return resp;
            """,
            staad,
        )
        assert r.success
        # int('0') = 0 — accepted. Not a vulnerability since handle 0 is always valid.

    def test_handle_nan(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Pass NaN as handle — JSON serialises NaN to null."""
        r = executor.execute(
            """
            const resp = hostCall(com_invoke, {handle: NaN, method: 'GetBaseUnit', args: []});
            return resp;
            """,
            staad,
        )
        assert r.success
        # JSON.stringify converts NaN to null, int(None) raises → error branch
        result_str = str(r.result).lower()
        assert "invalid" in result_str or "error" in result_str

    def test_handle_after_sub_object_resolved(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Verify handle 1 (sequential) exists only after com_get resolves it."""
        r = executor.execute(
            """
            // Before resolving, handle 1 doesn't exist
            const before = hostCall(com_invoke, {handle: 1, method: 'GetNodeCount', args: []});

            // Resolve Geometry (should get handle 1)
            const geo = hostCall(com_get, {handle: 0, prop: 'Geometry'});

            // Now handle 1 exists
            const after = hostCall(com_invoke, {handle: geo.handle, method: 'GetNodeCount', args: []});

            return {before: before, handle: geo.handle, after: after};
            """,
            staad,
        )
        assert r.success, r.error
        result = r.result
        # Before resolution, handle 1 should fail
        assert "error" in str(result.get("before", {})).lower() or "invalid" in str(result.get("before", {})).lower()
        # After resolution, should succeed
        assert result.get("after", {}).get("result") == 42


# ═══════════════════════════════════════════════════════════════════════════
# 3. Prototype pollution and special property names
# ═══════════════════════════════════════════════════════════════════════════


class TestPrototypePollution:
    """Attempt prototype pollution and dunder-style attacks through the
    COM method dispatch."""

    def test_proto_as_method_name(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Try to invoke __proto__ as a method on the root object."""
        r = executor.execute(
            """
            const resp = hostCall(com_invoke, {handle: 0, method: '__proto__', args: []});
            return resp;
            """,
            staad,
        )
        assert r.success
        # __proto__ is not in ALLOWED_ROOT_METHODS
        assert "not allowed" in str(r.result).lower()

    def test_constructor_as_method_name(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Try to invoke 'constructor' on the root."""
        r = executor.execute(
            """
            const resp = hostCall(com_invoke, {handle: 0, method: 'constructor', args: []});
            return resp;
            """,
            staad,
        )
        assert r.success
        assert "not allowed" in str(r.result).lower()

    def test_proto_as_sub_object(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Try to resolve __proto__ as a sub-object."""
        r = executor.execute(
            """
            const resp = hostCall(com_get, {handle: 0, prop: '__proto__'});
            return resp;
            """,
            staad,
        )
        assert r.success
        assert "not allowed" in str(r.result).lower()

    def test_proto_pollution_via_json(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Attempt proto pollution via crafted JSON. The JSON.parse in
        Python (json.loads) ignores __proto__ by default, but test it."""
        r = executor.execute(
            r"""
            // Craft a raw JSON string with __proto__ key
            const payload = '{"handle":0,"method":"GetBaseUnit","args":[],"__proto__":{"polluted":true}}';
            const mem = Memory.fromString(payload);
            const offset = com_invoke(mem.offset);
            const resp = Memory.find(offset).readString();
            return JSON.parse(resp);
            """,
            staad,
        )
        assert r.success, r.error
        # Python's json.loads treats __proto__ as a regular key, not as
        # prototype chain injection. The call should succeed normally.
        assert r.result.get("result") == "Metric"

    def test_toString_as_method_name(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Try to call toString on the root handle — not in allowlist."""
        r = executor.execute(
            """
            const resp = hostCall(com_invoke, {handle: 0, method: 'toString', args: []});
            return resp;
            """,
            staad,
        )
        assert r.success
        assert "not allowed" in str(r.result).lower()

    def test_valueOf_as_method_name(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Try to call valueOf on the root handle."""
        r = executor.execute(
            """
            const resp = hostCall(com_invoke, {handle: 0, method: 'valueOf', args: []});
            return resp;
            """,
            staad,
        )
        assert r.success
        assert "not allowed" in str(r.result).lower()

    def test_dunder_class_as_method(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Try Python dunder __class__ as a method name."""
        r = executor.execute(
            """
            const resp = hostCall(com_invoke, {handle: 0, method: '__class__', args: []});
            return resp;
            """,
            staad,
        )
        assert r.success
        assert "not allowed" in str(r.result).lower()

    def test_dunder_dict_as_method(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Try Python dunder __dict__ — could leak internal state."""
        r = executor.execute(
            """
            const resp = hostCall(com_invoke, {handle: 0, method: '__dict__', args: []});
            return resp;
            """,
            staad,
        )
        assert r.success
        assert "not allowed" in str(r.result).lower()


# ═══════════════════════════════════════════════════════════════════════════
# 4. JSON boundary attacks
# ═══════════════════════════════════════════════════════════════════════════


class TestJsonBoundary:
    """Attack the JSON serialisation layer between WASM and Python."""

    def test_malformed_json_to_com_invoke(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Send invalid JSON to com_invoke. Python json.loads should fail
        gracefully."""
        r = executor.execute(
            """
            const mem = Memory.fromString('{not valid json}}}');
            const offset = com_invoke(mem.offset);
            const resp = Memory.find(offset).readString();
            return JSON.parse(resp);
            """,
            staad,
        )
        assert r.success, r.error
        assert "invalid" in str(r.result).lower() or "error" in str(r.result).lower()

    def test_empty_string_to_com_invoke(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Send empty string — json.loads('') raises ValueError."""
        r = executor.execute(
            """
            const mem = Memory.fromString('');
            const offset = com_invoke(mem.offset);
            const resp = Memory.find(offset).readString();
            return JSON.parse(resp);
            """,
            staad,
        )
        assert r.success, r.error
        assert "invalid" in str(r.result).lower() or "error" in str(r.result).lower()

    def test_null_json_to_com_invoke(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Send the literal 'null' — json.loads('null') returns None."""
        r = executor.execute(
            """
            const mem = Memory.fromString('null');
            const offset = com_invoke(mem.offset);
            const resp = Memory.find(offset).readString();
            return JSON.parse(resp);
            """,
            staad,
        )
        assert r.success, r.error
        assert "invalid" in str(r.result).lower() or "error" in str(r.result).lower()

    def test_array_json_to_com_invoke(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Send a JSON array instead of object — parsed.get() will fail."""
        r = executor.execute(
            """
            const mem = Memory.fromString('[0, "GetBaseUnit", []]');
            const offset = com_invoke(mem.offset);
            const resp = Memory.find(offset).readString();
            return JSON.parse(resp);
            """,
            staad,
        )
        assert r.success, r.error
        assert "invalid" in str(r.result).lower() or "error" in str(r.result).lower()

    def test_very_deeply_nested_json(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Send deeply nested JSON to test for stack overflow in json.loads."""
        r = executor.execute(
            """
            // Build 200-deep nested object
            let json = '{"handle":0,"method":"GetBaseUnit","args":[';
            for (let i = 0; i < 200; i++) json += '{"a":';
            json += 'null';
            for (let i = 0; i < 200; i++) json += '}';
            json += ']}';
            const mem = Memory.fromString(json);
            const offset = com_invoke(mem.offset);
            const resp = Memory.find(offset).readString();
            return JSON.parse(resp);
            """,
            staad,
        )
        assert r.success, r.error
        # Either the call succeeds (200 depth is fine for Python json.loads)
        # or it errors gracefully

    def test_huge_json_payload(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Send a very large JSON payload — test for resource exhaustion."""
        r = executor.execute(
            """
            // 1MB of 'A' chars as a single string argument
            const big = 'A'.repeat(1024 * 1024);
            const resp = hostCall(com_invoke, {handle: 0, method: 'GetBaseUnit', args: [big]});
            return resp;
            """,
            staad,
        )
        # GetBaseUnit takes 0 args, but the extra arg in the args array won't
        # cause a json.loads issue — it'll be passed through. The stub will
        # raise TypeError for extra args.
        assert r.success, r.error

    def test_unicode_escape_in_method_name(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Use unicode escapes in the JSON to try to smuggle method names
        past the Python-side string comparison."""
        r = executor.execute(
            r"""
            // "Quit" via unicode escapes in raw JSON
            const payload = '{"handle":0,"method":"\\u0051\\u0075\\u0069\\u0074","args":[]}';
            const mem = Memory.fromString(payload);
            const offset = com_invoke(mem.offset);
            const resp = Memory.find(offset).readString();
            return JSON.parse(resp);
            """,
            staad,
        )
        assert r.success, r.error
        # json.loads decodes \u escapes, so method becomes "Quit".
        # The DESTRUCTIVE_METHODS check should block it.
        assert "blocked" in str(r.result).lower() or "not allowed" in str(r.result).lower()
        assert not staad.calls

    def test_duplicate_keys_in_json(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """JSON with duplicate 'method' keys — Python json.loads takes the
        last value. Verify the attacker can't hide a method name."""
        r = executor.execute(
            r"""
            // First method is allowed, second is destructive — json.loads takes last
            const payload = '{"handle":0,"method":"GetBaseUnit","args":[],"method":"Quit"}';
            const mem = Memory.fromString(payload);
            const offset = com_invoke(mem.offset);
            const resp = Memory.find(offset).readString();
            return JSON.parse(resp);
            """,
            staad,
        )
        assert r.success, r.error
        # json.loads takes last key → method = "Quit" → blocked
        assert "blocked" in str(r.result).lower() or "not allowed" in str(r.result).lower()
        assert not staad.calls


# ═══════════════════════════════════════════════════════════════════════════
# 5. Cross-handle method confusion
# ═══════════════════════════════════════════════════════════════════════════


class TestCrossHandleConfusion:
    """Try to call methods from one sub-object's allowlist on a different
    sub-object's handle."""

    def test_geometry_method_on_view_handle(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Resolve View, then try to call GetNodeCount (a Geometry method)
        on the View handle."""
        r = executor.execute(
            """
            const view = hostCall(com_get, {handle: 0, prop: 'View'});
            if (view.error) throw new Error(view.error);
            const resp = hostCall(com_invoke, {handle: view.handle, method: 'GetNodeCount', args: []});
            return resp;
            """,
            staad,
        )
        assert r.success, r.error
        # GetNodeCount is not in View's allowlist
        assert "not allowed" in str(r.result).lower()

    def test_view_method_on_geometry_handle(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Resolve Geometry, then try ExportView on Geometry handle."""
        r = executor.execute(
            """
            const geo = hostCall(com_get, {handle: 0, prop: 'Geometry'});
            const resp = hostCall(com_invoke, {handle: geo.handle, method: 'ExportView', args: ['C:/temp', 'shot', 1, true]});
            return resp;
            """,
            staad,
        )
        assert r.success, r.error
        # ExportView is not in Geometry's allowlist
        assert "not allowed" in str(r.result).lower()

    def test_root_method_on_sub_object_handle(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Resolve Geometry, then try SaveModel (a root method) on it."""
        r = executor.execute(
            """
            const geo = hostCall(com_get, {handle: 0, prop: 'Geometry'});
            const resp = hostCall(com_invoke, {handle: geo.handle, method: 'SaveModel', args: []});
            return resp;
            """,
            staad,
            allow_destructive=True,
        )
        assert r.success, r.error
        # SaveModel is not in Geometry's allowlist
        assert "not allowed" in str(r.result).lower()
        assert not staad.calls


# ═══════════════════════════════════════════════════════════════════════════
# 6. Non-callable attribute access
# ═══════════════════════════════════════════════════════════════════════════


class TestNonCallableAccess:
    """Attempt to invoke attributes that exist on the Python object but
    are not methods (e.g. sub-object references through com_invoke
    instead of com_get)."""

    def test_invoke_sub_object_attribute_directly(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Try to 'invoke' 'Geometry' as a method on root — it's an
        attribute, not callable. The 'not callable' check should fire."""
        r = executor.execute(
            """
            const resp = hostCall(com_invoke, {handle: 0, method: 'Geometry', args: []});
            return resp;
            """,
            staad,
        )
        assert r.success, r.error
        result_str = str(r.result).lower()
        # Either "not allowed" (if Geometry isn't in ALLOWED_ROOT_METHODS)
        # or "not callable" — either way, blocked
        assert "not allowed" in result_str or "not callable" in result_str


# ═══════════════════════════════════════════════════════════════════════════
# 7. Timing and re-entrancy
# ═══════════════════════════════════════════════════════════════════════════


class TestTimingAndReentrancy:
    """Test timeout enforcement and edge cases in call ordering."""

    def test_many_rapid_host_calls(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Make hundreds of host calls in a tight loop — test that the
        deadline check fires and the host doesn't deadlock."""
        r = executor.execute(
            """
            let count = 0;
            try {
                for (let i = 0; i < 10000; i++) {
                    const resp = hostCall(com_invoke, {handle: 0, method: 'GetBaseUnit', args: []});
                    if (resp.error) break;
                    count++;
                }
            } catch (e) {
                return {count: count, error: e.message};
            }
            return {count: count};
            """,
            staad,
        )
        # Either completes (fast stub) or times out — either is fine
        assert r.success or "timeout" in (r.error or "")

    def test_resolve_same_sub_object_twice(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Resolve 'Geometry' twice — should return the same handle
        (cached in sub_object_handles)."""
        r = executor.execute(
            """
            const g1 = hostCall(com_get, {handle: 0, prop: 'Geometry'});
            const g2 = hostCall(com_get, {handle: 0, prop: 'Geometry'});
            return {h1: g1.handle, h2: g2.handle, same: g1.handle === g2.handle};
            """,
            staad,
        )
        assert r.success, r.error
        assert r.result["same"] is True

    def test_resolve_all_sub_objects_then_use(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Resolve multiple sub-objects, then use them. Verify handles
        are stable and correctly dispatch to different objects."""
        r = executor.execute(
            """
            const geo = hostCall(com_get, {handle: 0, prop: 'Geometry'});
            const view = hostCall(com_get, {handle: 0, prop: 'View'});

            // Use Geometry
            const nc = hostCall(com_invoke, {handle: geo.handle, method: 'GetNodeCount', args: []});

            // Use View
            const wc = hostCall(com_invoke, {handle: view.handle, method: 'GetWindowCount', args: []});

            return {geo: geo.handle, view: view.handle, nc: nc, wc: wc};
            """,
            staad,
        )
        assert r.success, r.error
        assert r.result["geo"] != r.result["view"]
        nc = r.result["nc"]
        wc = r.result["wc"]
        assert nc.get("result") == 42, f"Geometry.GetNodeCount unexpected: {nc}"
        assert wc.get("result") == 1, f"View.GetWindowCount unexpected: {wc}"


# ═══════════════════════════════════════════════════════════════════════════
# 8. Scope escapes — can user code modify the evaluator's own globals?
# ═══════════════════════════════════════════════════════════════════════════


class TestScopeEscape:
    """Try to modify the evaluator's own functions or the Extism SDK
    globals to corrupt subsequent behaviour."""

    def test_overwrite_host_call(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Try to overwrite the hostCall global with a malicious version.
        Since each execute() creates a fresh plugin, this can't persist
        across calls, but verify it doesn't affect the current call."""
        r = executor.execute(
            """
            // Save reference
            const original = hostCall;

            // Overwrite (if allowed)
            try {
                hostCall = function(fn, payload) {
                    payload.method = 'Quit';
                    return original(fn, payload);
                };
            } catch(e) {
                return 'overwrite failed: ' + e.message;
            }

            // Now try a normal call
            const resp = hostCall(com_invoke, {handle: 0, method: 'GetBaseUnit', args: []});
            return resp;
            """,
            staad,
        )
        # If the overwrite succeeded, the call should have method='Quit'
        # which would be blocked by the consent gate
        if r.success and isinstance(r.result, dict):
            if "blocked" in str(r.result).lower():
                # The overwrite worked! But the consent gate still caught it.
                pass
            elif r.result.get("result") == "Metric":
                # Overwrite didn't happen (const or strict mode prevented it)
                pass
        # Either way, Quit must not have been called
        assert ("Quit", ()) not in staad.calls

    def test_overwrite_com_invoke(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Try to replace the com_invoke host function reference."""
        r = executor.execute(
            """
            try {
                com_invoke = null;
                return 'replaced com_invoke with null';
            } catch(e) {
                return 'cannot replace: ' + e.message;
            }
            """,
            staad,
        )
        assert r.success, r.error
        # If const, it should say "cannot replace"
        # If let, it replaces but only affects this call (fresh plugin per call)

    def test_modify_memory_class(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Try to tamper with the Extism Memory class to intercept data."""
        r = executor.execute(
            """
            try {
                const origFromString = Memory.fromString;
                Memory.fromString = function(s) {
                    // Intercept all host communication
                    return origFromString.call(Memory, s.replace('GetBaseUnit', 'Quit'));
                };
                const resp = hostCall(com_invoke, {handle: 0, method: 'GetBaseUnit', args: []});
                return resp;
            } catch(e) {
                return 'failed: ' + e.message;
            }
            """,
            staad,
        )
        # The Memory.fromString patch may or may not stick, but either way
        # Quit must be blocked without consent
        if r.success and isinstance(r.result, dict):
            if "blocked" in str(r.result).lower():
                pass  # Interception worked but consent gate held
        assert ("Quit", ()) not in staad.calls

    def test_fresh_plugin_per_call(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Verify that modifying globals in one call doesn't leak to the next."""
        # Call 1: set a global marker
        r1 = executor.execute(
            """
            globalThis.__pwned = true;
            return globalThis.__pwned;
            """,
            staad,
        )
        assert r1.success
        assert r1.result is True

        # Call 2: check if the marker persists
        r2 = executor.execute(
            """
            return globalThis.__pwned === undefined ? 'clean' : 'LEAKED';
            """,
            staad,
        )
        assert r2.success, r2.error
        assert r2.result == "clean", "Global state leaked between plugin instantiations!"


# ═══════════════════════════════════════════════════════════════════════════
# 9. Global hardening — Host.getFunctions() neutering & offset validation
# ═══════════════════════════════════════════════════════════════════════════


class TestGlobalHardening:
    """Verify the evaluator.js execute()-time hardening that prevents
    user code from obtaining raw host-function references and from
    passing negative memory offsets to Host.invokeFunc (CFFI DoS vector).
    """

    def test_get_functions_returns_empty(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Host.getFunctions() must return an empty object after hardening."""
        r = executor.execute(
            """
            const fns = Host.getFunctions();
            return Object.keys(fns);
            """,
            staad,
        )
        assert r.success, r.error
        assert r.result == [], f"Host.getFunctions() leaked keys: {r.result}"

    def test_host_functions_array_empty(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Host.__hostFunctions must be an empty array."""
        r = executor.execute(
            """
            return Array.isArray(Host.__hostFunctions)
                ? Host.__hostFunctions.length
                : 'not an array';
            """,
            staad,
        )
        assert r.success, r.error
        assert r.result == 0, f"__hostFunctions not empty: {r.result}"

    def test_invoke_func_rejects_negative_offset(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Host.invokeFunc with a negative offset must throw, not reach CFFI."""
        r = executor.execute(
            """
            try {
                Host.invokeFunc('com_get', -1);
                return 'REACHED CFFI';
            } catch(e) {
                return e.message;
            }
            """,
            staad,
        )
        assert r.success, r.error
        assert r.result == "invalid memory offset", f"Unexpected: {r.result}"
        # Verify no COM calls actually fired
        assert not staad.calls

    def test_invoke_func_rejects_large_negative(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Large negative offsets also blocked."""
        r = executor.execute(
            """
            try {
                Host.invokeFunc('com_invoke', -9999999999);
                return 'REACHED CFFI';
            } catch(e) {
                return e.message;
            }
            """,
            staad,
        )
        assert r.success, r.error
        assert "invalid memory offset" in r.result

    def test_invoke_func_allows_valid_offset(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Normal COM calls via the Proxy (which use valid positive offsets)
        must still work after the invokeFunc wrapper is installed."""
        r = executor.execute("staad.GetBaseUnit()", staad)
        assert r.success, r.error
        assert r.result == "Metric"

    def test_normal_proxy_calls_unaffected(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """Sub-object access and method calls through the Proxy still work."""
        r = executor.execute("staad.Geometry.GetNodeCount()", staad)
        assert r.success, r.error
        assert r.result == 42

    def test_cannot_recover_raw_functions_from_neutered_host(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """After neutering, there's no way to get a raw com_get/com_invoke ref
        from Host — the closure captured at module init is the only copy."""
        r = executor.execute(
            """
            const fns = Host.getFunctions();
            const keys = Object.keys(fns);
            const hasComGet = typeof fns.com_get === 'function';
            const hasComInvoke = typeof fns.com_invoke === 'function';
            return {keys, hasComGet, hasComInvoke};
            """,
            staad,
        )
        assert r.success, r.error
        assert r.result["keys"] == []
        assert r.result["hasComGet"] is False
        assert r.result["hasComInvoke"] is False

    def test_fetch_neutered(
        self, executor: WasmExecutor, staad: _SpyStaad
    ) -> None:
        """fetch must be undefined after hardening."""
        r = executor.execute("typeof fetch", staad)
        assert r.success, r.error
        assert r.result == "undefined"
