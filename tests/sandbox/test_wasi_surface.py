"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

WASI surface audit tests for the WASM sandbox.

The evaluator.wasm is compiled with ``wasi=True`` because QuickJS-ng imports
12 WASI functions (fd_write, fd_read, environ_get, random_get, etc.).
These tests verify that none of those WASI imports are practically reachable
from user JavaScript — even though Wasmtime links stub implementations,
the QuickJS-ng/Extism plugin model routes all I/O through host functions,
not through WASI file descriptors.

Any test that fails here means the WASI surface is wider than expected and
must be investigated as a potential sandbox escape.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from openstaad_mcp.sandbox.wasm_executor import WasmExecutor


# ---------------------------------------------------------------------------
# Stub — minimal STAAD object (no COM needed for these tests)
# ---------------------------------------------------------------------------


class _MinimalStaad:
    """Bare stub with one method to prove the sandbox is alive."""

    def GetBaseUnit(self) -> str:
        return "Metric"


@pytest.fixture
def executor() -> WasmExecutor:
    return WasmExecutor(timeout_seconds=5.0)


@pytest.fixture
def staad() -> _MinimalStaad:
    return _MinimalStaad()


# ---------------------------------------------------------------------------
# Sanity: confirm the sandbox is working
# ---------------------------------------------------------------------------


class TestSanity:
    def test_sandbox_alive(self, executor: WasmExecutor, staad: _MinimalStaad) -> None:
        r = executor.execute("1 + 1", staad)
        assert r.success, r.error
        assert r.result == 2


# ---------------------------------------------------------------------------
# WASI surface: environment variables
# ---------------------------------------------------------------------------


class TestWASIEnvironment:
    """WASI environ_get / environ_sizes_get must not leak host env vars."""

    def test_no_process_env(self, executor: WasmExecutor, staad: _MinimalStaad) -> None:
        """JS ``process.env`` must not exist."""
        r = executor.execute("typeof process", staad)
        assert r.success
        assert r.result == "undefined"

    def test_no_std_module_getenv(self, executor: WasmExecutor, staad: _MinimalStaad) -> None:
        """QuickJS ``std`` module must not be importable."""
        r = executor.execute(
            'try { const std = require("std"); return "loaded: " + typeof std; }'
            ' catch(e) { return "blocked: " + e.message; }',
            staad,
        )
        assert r.success
        assert "blocked" in str(r.result).lower() or r.result == "undefined"

    def test_no_os_module(self, executor: WasmExecutor, staad: _MinimalStaad) -> None:
        """QuickJS ``os`` module must not be importable."""
        r = executor.execute(
            'try { const os = require("os"); return "loaded: " + typeof os; }'
            ' catch(e) { return "blocked: " + e.message; }',
            staad,
        )
        assert r.success
        assert "blocked" in str(r.result).lower() or r.result == "undefined"

    def test_no_dynamic_import(self, executor: WasmExecutor, staad: _MinimalStaad) -> None:
        """Dynamic ``import()`` must not load host modules."""
        r = executor.execute(
            'try { const m = import("std"); return "import-returned"; }'
            ' catch(e) { return "blocked: " + e.message; }',
            staad,
        )
        assert r.success
        # Either blocked outright or returns a rejected Promise (not a usable module)
        assert "loaded" not in str(r.result).lower()


# ---------------------------------------------------------------------------
# WASI surface: file descriptors
# ---------------------------------------------------------------------------


class TestWASIFileDescriptors:
    """WASI fd_read / fd_write / fd_close must not provide useful I/O."""

    def test_no_fs_module(self, executor: WasmExecutor, staad: _MinimalStaad) -> None:
        """No ``fs`` module is available."""
        r = executor.execute(
            'try { const fs = require("fs"); return "loaded"; }'
            ' catch(e) { return "blocked"; }',
            staad,
        )
        assert r.success
        assert r.result == "blocked"

    def test_no_stdin_read(self, executor: WasmExecutor, staad: _MinimalStaad) -> None:
        """Cannot read from stdin (fd 0) via any JS API."""
        r = executor.execute(
            'try { const std = require("std"); const data = std.in.readAsString(); return data; }'
            ' catch(e) { return "blocked"; }',
            staad,
        )
        assert r.success
        assert r.result == "blocked"

    def test_console_log_routes_through_host(
        self, executor: WasmExecutor, staad: _MinimalStaad
    ) -> None:
        """console.log must go through the console_output host function
        (captured in stdout), NOT through WASI fd_write directly."""
        r = executor.execute(
            'console.log("marker_wasi_test_42"); return "done";',
            staad,
        )
        assert r.success
        assert "marker_wasi_test_42" in r.stdout

    def test_no_print_function(self, executor: WasmExecutor, staad: _MinimalStaad) -> None:
        """QuickJS's ``print()`` global (which uses fd_write) must not
        exist or must route through the host function."""
        r = executor.execute("typeof print", staad)
        assert r.success
        if r.result == "undefined":
            return  # Best case: print doesn't exist
        # If print exists, verify it routes through the host console_output
        # (captured in stdout), not through raw WASI fd_write.
        r2 = executor.execute(
            'print("print_wasi_probe_99"); return "done";',
            staad,
        )
        assert r2.success
        # If it went through console_output host function, it appears in stdout
        # If it went through WASI fd_write, it would NOT appear in stdout
        # (it would go to the process's actual stdout instead)
        assert "print_wasi_probe_99" in r2.stdout, (
            "print() output did NOT route through host console_output — "
            "it may be using WASI fd_write directly, bypassing the capture buffer"
        )


# ---------------------------------------------------------------------------
# WASI surface: clock / random
# ---------------------------------------------------------------------------


class TestWASIClockRandom:
    """clock_time_get and random_get are expected to work (QuickJS needs them
    for Date and Math.random). These tests just confirm they don't crash and
    document that they ARE reachable — this is expected and accepted."""

    def test_math_random_works(self, executor: WasmExecutor, staad: _MinimalStaad) -> None:
        """Math.random() uses WASI random_get. Expected to work."""
        r = executor.execute("Math.random()", staad)
        assert r.success
        assert isinstance(r.result, float)
        assert 0.0 <= r.result < 1.0

    def test_date_now_works(self, executor: WasmExecutor, staad: _MinimalStaad) -> None:
        """Date.now() uses WASI clock_time_get. Expected to work."""
        r = executor.execute("Date.now()", staad)
        assert r.success
        assert isinstance(r.result, (int, float))
        assert r.result > 1_000_000_000_000  # post-2001 epoch ms

    def test_random_within_single_call_varies(self, executor: WasmExecutor, staad: _MinimalStaad) -> None:
        """Within one call, successive Math.random() values differ.

        NOTE: Across separate plugin instantiations, Math.random() may
        return identical sequences because the Wizer pre-init snapshot
        bakes in the initial RNG state. This is a known property of the
        extism-js build. Not a security concern here (nothing in the
        sandbox depends on Math.random() for security), but document it.
        """
        r = executor.execute(
            "const a = Math.random(); const b = Math.random(); return [a, b, a !== b];",
            staad,
        )
        assert r.success, r.error
        assert isinstance(r.result, list)
        assert len(r.result) == 3
        # Within a single call, values should differ
        assert r.result[2] is True, f"Math.random() returned same value twice: {r.result}"


# ---------------------------------------------------------------------------
# WASI surface: proc_exit
# ---------------------------------------------------------------------------


class TestWASIProcExit:
    """WASI proc_exit is imported by QuickJS-ng. If reachable from JS it
    would terminate the plugin (Extism catches this as a trap). Verify it
    does NOT crash the host Python process."""

    def test_exit_does_not_crash_host(
        self, executor: WasmExecutor, staad: _MinimalStaad
    ) -> None:
        """Attempting to call exit-like functions must not crash Python."""
        codes = [
            'try { exit(0); } catch(e) { return "blocked: " + e.message; }',
            'try { quit(0); } catch(e) { return "blocked: " + e.message; }',
        ]
        for code in codes:
            r = executor.execute(code, staad)
            # Either a JS error (function not found) or a WASM trap
            # (Extism catches proc_exit). The critical thing is that
            # the Python process is still alive and we got a result.
            assert r is not None, "execute() returned None — host may have crashed"
            # We don't care about success/failure, just that we're still here.

    def test_plugin_works_after_exit_attempt(
        self, executor: WasmExecutor, staad: _MinimalStaad
    ) -> None:
        """After a proc_exit trap, the next call must work (fresh plugin)."""
        executor.execute(
            'try { exit(1); } catch(e) {}',
            staad,
        )
        r = executor.execute("1 + 1", staad)
        assert r.success, r.error
        assert r.result == 2


# ---------------------------------------------------------------------------
# WASI surface: fd_prestat (directory preopens)
# ---------------------------------------------------------------------------


class TestWASIPreopens:
    """WASI fd_prestat_get / fd_prestat_dir_name are used to discover
    filesystem preopens. Without preopens in the manifest, these should
    return ENOENT/EBADF, meaning no directories are accessible."""

    def test_no_file_open(self, executor: WasmExecutor, staad: _MinimalStaad) -> None:
        """Cannot open files via any JS mechanism."""
        attempts = [
            'require("fs").readFileSync("C:\\\\Windows\\\\win.ini", "utf8")',
            'require("std").loadFile("C:\\\\Windows\\\\win.ini")',
            'open("C:\\\\Windows\\\\win.ini")',
        ]
        for attempt in attempts:
            r = executor.execute(
                f'try {{ return {attempt}; }} catch(e) {{ return "blocked"; }}',
                staad,
            )
            assert r.success
            assert r.result == "blocked", (
                f"File access succeeded with: {attempt}"
            )

    def test_no_file_write(self, executor: WasmExecutor, staad: _MinimalStaad) -> None:
        """Cannot write files via any JS mechanism."""
        attempts = [
            'require("fs").writeFileSync("C:\\\\Temp\\\\evil.txt", "pwned")',
            'require("std").open("C:\\\\Temp\\\\evil.txt", "w")',
        ]
        for attempt in attempts:
            r = executor.execute(
                f'try {{ {attempt}; return "wrote"; }} catch(e) {{ return "blocked"; }}',
                staad,
            )
            assert r.success
            assert r.result == "blocked", (
                f"File write succeeded with: {attempt}"
            )


# ---------------------------------------------------------------------------
# WASI surface: network (absence confirmation)
# ---------------------------------------------------------------------------


class TestWASINetwork:
    """Confirm no network capability exists via any WASI or JS path."""

    def test_fetch_unavailable_or_traps(
        self, executor: WasmExecutor, staad: _MinimalStaad
    ) -> None:
        r = executor.execute("typeof fetch", staad)
        assert r.success
        if r.result == "undefined":
            return
        # fetch exists as a global but should trap when called
        r2 = executor.execute(
            'try { fetch("https://example.com"); return "reachable"; }'
            ' catch(e) { return "blocked: " + e.message; }',
            staad,
        )
        if r2.success:
            assert "reachable" not in str(r2.result)
        # A WASM trap (success=False) is also acceptable

    def test_xmlhttprequest_unavailable(
        self, executor: WasmExecutor, staad: _MinimalStaad
    ) -> None:
        r = executor.execute("typeof XMLHttpRequest", staad)
        assert r.success
        assert r.result == "undefined"

    def test_websocket_unavailable(
        self, executor: WasmExecutor, staad: _MinimalStaad
    ) -> None:
        r = executor.execute("typeof WebSocket", staad)
        assert r.success
        assert r.result == "undefined"


# ---------------------------------------------------------------------------
# globalThis surface audit
# ---------------------------------------------------------------------------


class TestGlobalScope:
    """Enumerate the global scope and flag unexpected entries."""

    #: Globals that are expected and acceptable in the QuickJS-ng/Extism
    #: environment. Anything outside this set should be investigated.
    EXPECTED_GLOBALS = {
        # JS built-ins
        "Object", "Function", "Error", "EvalError", "RangeError",
        "ReferenceError", "SyntaxError", "TypeError", "URIError",
        "InternalError", "AggregateError",
        "Array", "parseInt", "parseFloat", "isNaN", "isFinite",
        "decodeURI", "decodeURIComponent", "encodeURI", "encodeURIComponent",
        "escape", "unescape",
        "Infinity", "NaN", "undefined", "globalThis",
        "eval", "JSON", "Math", "console", "Date", "RegExp",
        "Boolean", "Number", "String", "Symbol",
        "Map", "Set", "WeakMap", "WeakSet",
        "ArrayBuffer", "SharedArrayBuffer", "Uint8ClampedArray",
        "Int8Array", "Uint8Array", "Int16Array", "Uint16Array",
        "Int32Array", "Uint32Array", "Float32Array", "Float64Array",
        "Float16Array", "BigInt64Array", "BigUint64Array",
        "DataView", "BigInt",
        "Promise", "Proxy", "Reflect",
        "Iterator",
        "WeakRef", "FinalizationRegistry",
        # Extism-specific SDK globals
        "Host", "Memory", "MemoryHandle", "Var", "Config", "Http",
        "module", "exports",
        # Extism polyfills (web-compat shims bundled in extism-js)
        "Buffer", "DOMException", "Event", "EventTarget",
        "Headers", "Response", "URLPattern",
        "crypto", "global", "self",
        "__core-js_shared__",
        "__consoleWrite",
        "__decodeUtf8BufferToString", "__encodeStringToUtf8Buffer",
        "__getRandomBytes", "__getTime", "__getTimeMs",
        "__shaDigest",
        # QuickJS-ng additions
        "__date_clock",
        # evaluator.js internals — visible on globalThis because
        # extism-js compiles the module into the top-level scope.
        # User code CAN call hostCall/hostVoid directly to craft
        # arbitrary JSON payloads to host functions, but the host
        # functions validate everything (allowlists, consent gate,
        # UNC check), so this is not a bypass. Documented here
        # so the exposure is tracked.
        "execute", "hostCall", "hostVoid",
        "formatArg", "makeLogger", "makeProxyForHandle",
        # May or may not be present depending on QuickJS-ng build
        "print", "fetch", "TextEncoder", "TextDecoder",
        "URL", "URLSearchParams",
        "performance", "atob", "btoa",
        "setTimeout", "clearTimeout", "setInterval", "clearInterval",
        "queueMicrotask", "structuredClone",
        "WebAssembly",
    }

    def test_no_unexpected_globals(
        self, executor: WasmExecutor, staad: _MinimalStaad
    ) -> None:
        """Enumerate globalThis and flag anything not in the expected set."""
        r = executor.execute(
            "Object.getOwnPropertyNames(globalThis).sort()",
            staad,
        )
        assert r.success, r.error
        actual = set(r.result)
        unexpected = actual - self.EXPECTED_GLOBALS
        # Don't hard-fail on new additions — but print them for review.
        if unexpected:
            import warnings
            warnings.warn(
                f"Unexpected globals found in WASM sandbox — review for "
                f"security impact: {sorted(unexpected)}",
                stacklevel=1,
            )
        # Hard-fail only on known-dangerous globals
        dangerous = {"process", "require", "Deno", "Bun", "__dirname", "__filename"}
        leaked = actual & dangerous
        assert not leaked, f"Dangerous globals present in sandbox: {leaked}"
