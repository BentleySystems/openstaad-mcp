# OMCP-014: CFFI OverflowError DoS via Negative Host-Function Offset

## Overview
| Field | Value |
|-------|-------|
| ID | OMCP-014 |
| Title | CFFI OverflowError DoS via Negative Host-Function Offset |
| Severity | Medium |
| CVSS Score | 5.3 |
| Auth Required | No (stdio transport) / Yes (HTTP transport) |
| Local/Remote | Local (stdio) / Remote (HTTP) |
| Status | Fixed in v2.0.0 |
| Category | Product Code Finding |

## SVS Mapping
- **TASVS**: N/A
- **ASVS**: ASVS-11.1.4 - Application logic protects against denial of service

## CWE Reference
- **CWE-400**: Uncontrolled Resource Consumption
- **CWE-681**: Incorrect Conversion between Numeric Types - **CWE-839**: Numeric Range Comparison Without Minimum Check

## Vulnerability Details

### Description

The Extism Python SDK (v1.1.1) uses CFFI to call into the Wasmtime-based runtime. When a host function is invoked from WASM, the SDK's
`handle_args` callback receives an i64 memory offset and passes it to `extism_current_plugin_memory_length` via CFFI. The C function expects an
unsigned 64-bit offset, but the Python CFFI layer converts the signed i64 directly, causing an `OverflowError` when the value is negative.

On Windows, this unhandled exception surfaces as a **blocking modal error dialog** ("Python has stopped working" or similar), freezing the MCP
server process until a human dismisses the dialog. This is a denial of service — the server becomes unresponsive to all clients.

The attack vector is the Extism JS PDK's `Host.getFunctions()` API, which returns an array of callable host-function wrappers. User code running inside the WASM sandbox can call any host function with arbitrary
arguments, including negative offsets:

```javascript
// Inside the WASM sandbox
const fns = Host.getFunctions();
fns.com_invoke(-1);  // Triggers CFFI OverflowError → blocking dialog
```

### Affected Code

**SDK file:** `extism.py` (extism 1.1.1), `handle_args` callback (~line 929)
```python
def handle_args(plugin_ptr, inputs, n_inputs, outputs, n_outputs, ud):
    # ...
    offs = lib.extism_current_plugin_memory_at_offset(plugin_ptr, inp.v.i64)
    length = lib.extism_current_plugin_memory_length(plugin_ptr, inp.v.i64)
    # OverflowError when inp.v.i64 < 0 — CFFI cannot convert to unsigned
```

**Evaluator file (pre-fix):** `evaluator.js`
```javascript
// Host.getFunctions() returned raw callable references
// Host.__hostFunctions contained the raw function array
// Both allowed user code to invoke host functions with arbitrary offsets
```

### Root Cause Analysis
- **Vulnerable code explanation**: The Extism JS PDK exposes `Host.getFunctions()` which returns raw host-function references. The Python SDK's CFFI bridge does not validate that memory offsets are non-negative before passing them to C. The combination allows sandbox-internal code to trigger a host-side crash.
- **Attack prerequisites**: Ability to invoke the `execute_code` MCP tool and submit JavaScript that calls `Host.getFunctions()`.
- **Impact assessment**: Full server denial of service. The blocking dialog freezes the process; no MCP requests are processed until the dialog is dismissed. On headless deployments, this is permanent until the process is killed.

## Proof of Concept

```javascript
// PoC: trigger CFFI OverflowError via negative offset
const fns = Host.getFunctions();
fns.com_invoke(-1);
```

When executed inside the WASM sandbox (pre-fix), this causes:
```
OverflowError: can't convert negative number to unsigned
```
On Windows, this manifests as a blocking error dialog.

Variant using `Host.invokeFunc` directly:
```javascript
Host.invokeFunc("com_invoke", -9999);
```

## Fix

Implemented in `evaluator.js` — runtime hardening inside `execute()` runs before any user code:

1. **`Host.getFunctions()`** overwritten to return `{}` — user code
   cannot obtain raw host-function references.
2. **`Host.__hostFunctions`** set to `[]` — the backing array is emptied.
3. **`Host.invokeFunc`** wrapped with an offset validator:
   ```javascript
   const _origInvokeFunc = Host.invokeFunc;
   Host.invokeFunc = function(name, offset) {
     if (typeof offset === 'number' && offset < 0) {
       throw new Error('invalid memory offset');
     }
     return _origInvokeFunc.call(Host, name, offset);
   };
   ```
4. **`fetch`** set to `undefined` (defense in depth; the Extism polyfill
   already traps, but removal gives a clearer error).

The module-scope closures (`com_get`, `com_invoke`, `console_output`) captured at evaluator init time retain their original references and
continue to work normally through the `staad` Proxy object. User code interacts exclusively via the Proxy and never needs direct host-function
access.

### Why not fix in the SDK?

The OverflowError is arguably a bug in Extism Python SDK 1.1.1, but: - The SDK is not under our control and updating it is not immediate.
- Even if the SDK handled negative offsets gracefully, exposing raw host functions to user code is an unnecessary attack surface.
- The evaluator-side fix is defense in depth — it works regardless of SDK behavior.

## Verification

### Unit tests (9 tests in `TestGlobalHardening`, `tests/sandbox/test_redteam_deep.py`)
- `test_get_functions_returns_empty` — confirms `Host.getFunctions()` returns `{}` - `test_host_functions_array_empty` — confirms `Host.__hostFunctions` is `[]`
- `test_invoke_func_rejects_negative_offset` — confirms `-1` is rejected - `test_invoke_func_rejects_large_negative` — confirms `-9999999` is rejected
- `test_invoke_func_allows_valid_offset` — confirms valid offsets still work - `test_normal_proxy_calls_unaffected` — confirms COM Proxy still functions
- `test_cannot_recover_raw_functions_from_neutered_host` — confirms prototypes/constructor cannot recover original functions
- `test_fetch_neutered` — confirms `fetch` is `undefined`

### MCP integration tests (19 tests in `tests/test_mcp_live.py`)
- `TestHardeningViaMCP` (6 tests) — exercises hardening through the real MCP server via stdio transport
- `TestAllowlistViaMCP` (3 tests) — verifies allowlist enforcement E2E - `TestSmoke`, `TestExecuteCode`, `TestProtocolEdgeCases` — general server health and edge case coverage

### WASM rebuild
Evaluator rebuilt with extism-js 1.6.0 + binaryen 129.
SHA-256: `5F9146EEE2AF2C708E7FCAFEC0976F598DA95CD5E9B499B356C1174A0CE69B90`

## Timeline
- **2026-04-27**: Discovered during red-team testing of WASM sandbox - **2026-04-27**: Fix implemented, WASM rebuilt, tests added, verified E2E
