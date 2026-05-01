# Execution Flow: Agent → MCP → WASM → COM → STAAD

Step-by-step trace of a single `execute_code` call, from the AI agent's request to the COM dispatch into STAAD.Pro and back. Each step references the exact file, function, and line where it happens.

## Step 0: Build time (once, by developer)

`extism-js` compiles `evaluator.js` + `evaluator.d.ts` into `evaluator.wasm`.

| What | Where |
|------|-------|
| Build script | [`src/openstaad_mcp/sandbox/evaluator_src/build.ps1`](../src/openstaad_mcp/sandbox/evaluator_src/build.ps1) line 77 |
| Command | `extism-js evaluator.js -i evaluator.d.ts -o evaluator.wasm` |
| JS source | [`src/openstaad_mcp/sandbox/evaluator_src/evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) |
| Host interface declaration | [`src/openstaad_mcp/sandbox/evaluator_src/evaluator.d.ts`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.d.ts) |
| Output artifact | [`src/openstaad_mcp/sandbox/evaluator.wasm`](../src/openstaad_mcp/sandbox/evaluator.wasm) (~2.4 MB) |

The build compiles QuickJS-ng (JS engine) + the evaluator code into a standalone WASM binary. Binaryen's `wasm-merge` links the pieces. This binary ships with the package and does not change at runtime.

## Step 1: Server startup (once, at process start)

Python imports `wasm_executor.py`, which reads the WASM bytes into memory and verifies integrity.

| What | Where |
|------|-------|
| Read bytes | [`src/openstaad_mcp/sandbox/wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 66: `_EVALUATOR_BYTES = _EVALUATOR_PATH.read_bytes()` |
| SHA-256 verify | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) lines 73-87: compares against `evaluator.wasm.sha256` |
| WasmExecutor instantiated | [`src/openstaad_mcp/server.py`](../src/openstaad_mcp/server.py) line 399: `_register_tools(mcp, registry, WasmExecutor())` |

After this, `_EVALUATOR_BYTES` (the raw WASM) lives in Python process memory for the lifetime of the server. No disk reads on subsequent calls.

## Step 2: Agent sends `execute_code` tool call

The AI agent sends a JSON-RPC request over stdio or HTTP. FastMCP routes it to the `execute_code` handler.

| What | Where |
|------|-------|
| Tool definition | [`src/openstaad_mcp/server.py`](../src/openstaad_mcp/server.py) line 168: `async def execute_code(code: str, instance: str | None = None, ctx: Context | None = None)` |
| Parameters | `code` (JS string), `instance` (optional STAAD alias) |

## Step 3: Pre-flight consent gate

Before any execution, the server scans the submitted code for destructive method names. If found, it triggers MCP elicitation (a host-mediated user dialog).

| What | Where |
|------|-------|
| Scan for destructive methods | [`server.py`](../src/openstaad_mcp/server.py) line 216: `detected = {m for m in ALL_DESTRUCTIVE_METHOD_NAMES if m in code}` — [`ALL_DESTRUCTIVE_METHOD_NAMES`](../src/openstaad_mcp/sandbox/constants.py#L134) |
| Trigger elicitation | [`server.py`](../src/openstaad_mcp/server.py) line 230: `elicit_result = await ctx.elicit(...)` |
| Set `allow_destructive` | [`server.py`](../src/openstaad_mcp/server.py) line 237: `allow_destructive = True` (only after human approval) |

If the user declines or elicitation is unavailable, execution is rejected before any WASM or COM work happens.

## Step 4: `connect_and_run` spins a COM worker thread

The server resolves the target STAAD instance and dispatches to a short-lived daemon thread that initializes a COM STA apartment.

| What | Where |
|------|-------|
| Resolve target | [`server.py`](../src/openstaad_mcp/server.py) line 204: `target = _resolve_target(instance)` |
| Call `connect_and_run` | [`server.py`](../src/openstaad_mcp/server.py) line 267: `return connect_and_run(_run, target.file_path)` |
| Thread + CoInitialize | [`src/openstaad_mcp/connection.py`](../src/openstaad_mcp/connection.py) line 288: `pythoncom.CoInitialize()` |
| COM connect | [`connection.py`](../src/openstaad_mcp/connection.py) line 291: `staad = os_analytical.connect(file_path)` |
| Run callback | [`connection.py`](../src/openstaad_mcp/connection.py) line 292: `result_box[0] = fn(staad)` |

The callback `_run(staad)` is defined in `server.py` line 261-263:
```python
def _run(staad: Any) -> dict[str, Any]:
    return exc.execute(code, staad, allow_destructive=allow_destructive).to_dict()
```

This calls `WasmExecutor.execute()` with the live COM root object.

## Step 5: `WasmExecutor.execute()` creates a fresh Extism plugin

A new `_CallState` is created (handle table, deadline, buffers), host functions are built as closures over it, and Extism instantiates the WASM plugin.

| What | Where |
|------|-------|
| Size check | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 238: reject if `len(code_bytes) > self._max_code` |
| Create [`_CallState`](../src/openstaad_mcp/sandbox/wasm_executor.py#L187) | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 245: `state = _CallState(handle_table={0: staad_object}, ...)` |
| Build host functions | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 251: `functions = self._build_host_functions(state)` |
| Build manifest | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 252-256: `{"wasm": [{"data": _EVALUATOR_BYTES}], "memory": {"max_pages": ...}, "timeout_ms": ...}` |
| Instantiate plugin | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 263: `plugin = extism.Plugin(manifest, wasi=True, functions=functions)` — [`WasmExecutor`](../src/openstaad_mcp/sandbox/wasm_executor.py#L208) |

At this point, Wasmtime validates and compiles the WASM to native machine code (cached internally by Wasmtime across plugin instances). The three Python host functions (`com_get`, `com_invoke`, `console_output`) are registered as imports the WASM module can call.

## Step 6: `plugin.call("execute", code_bytes)` enters WASM

Extism invokes the exported `execute` function inside the WASM module. Control transfers from Python into the Wasmtime runtime, which runs the compiled WASM (QuickJS-ng).

| What | Where |
|------|-------|
| Python side | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 264: `raw = plugin.call("execute", code_bytes)` |
| WASM side entry | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 121: `function execute()` |
| Read input | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 122: `const code = Host.inputString()` |
| Module export | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 118: `module.exports = { execute }` |

## Step 7: Global hardening (inside WASM, before user code)

Before evaluating user code, the evaluator neuters dangerous Extism SDK globals to prevent user code from obtaining raw host-function references.

| What | Where |
|------|-------|
| Neuter `Host.getFunctions` | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 133: `Host.getFunctions = function() { return {}; }` |
| Clear `Host.__hostFunctions` | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 134: `Host.__hostFunctions = []` |
| Wrap `Host.invokeFunc` | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) lines 139-145: rejects negative memory offsets |
| Remove `fetch` | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 150: `globalThis.fetch = undefined` |

The module-scope closures (`com_get`, `com_invoke`, `console_output`) captured at line 15 still hold their original references and work normally through the Proxy. User code can no longer reach them directly.

## Step 8: QuickJS evaluates the user's JavaScript

The evaluator wraps the user code in a `new Function` and calls it, injecting `staad` (a Proxy) and `console` as arguments.

| What | Where |
|------|-------|
| Create `staad` Proxy | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 152: `const staad = makeProxyForHandle(0)` |
| Try as expression | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 160: `fn = new Function('staad', 'console', '"use strict";\nreturn (' + code + ');')` |
| Fallback to statements | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 162: `fn = new Function('staad', 'console', '"use strict";\n' + code)` |
| Execute | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 167: `const value = fn(staad, sandboxConsole)` |

## Step 9: User code accesses `staad.Geometry` → Proxy `get` trap fires

When JS reads a property on the `staad` object, the Proxy intercepts it.

| What | Where |
|------|-------|
| Proxy `get` trap | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 79: `get(_target, prop, _receiver)` |
| Root handle (0) path | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 84: calls `hostCall(com_get, { handle: 0, prop: prop })` |

## Step 10: `hostCall` marshals JSON across the WASM boundary

The `hostCall` helper serializes the request to JSON, writes it to WASM linear memory, and invokes the host function via its captured reference.

| What | Where |
|------|-------|
| Serialize to JSON | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 20: `const mem = Memory.fromString(JSON.stringify(payload))` |
| Call host function | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 21: `const offset = fn(mem.offset)` |
| Read response | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 22: `const resp = Memory.find(offset).readString()` |
| Parse response | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 23: `return JSON.parse(resp)` |

At line 21, execution leaves WASM and enters the Python host function. This happens on the **same thread** (critical for COM STA).

## Step 11: Python `com_get` host function resolves the sub-object

Control is now back in Python. The host function validates the request and does a single `getattr` on the COM root object.

| What | Where |
|------|-------|
| Deadline check | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 299: `state.assert_deadline()` |
| Parse JSON | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) lines 300-302 |
| Reject non-root | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 308: `if handle != 0: return error` |
| Allowlist check | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 310: `if prop not in ALLOWED_SUB_OBJECTS: return error` — [`ALLOWED_SUB_OBJECTS`](../src/openstaad_mcp/sandbox/constants.py#L26) |
| Cache hit check | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 313: `if prop in state.sub_object_handles: return cached handle` |
| `getattr` on COM object | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 317: `sub = getattr(state.handle_table[0], prop)` |
| Store in handle table | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) lines 321-324: assigns handle N, caches it |
| Return JSON | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 325: `return json.dumps({"handle": h})` |

The response crosses back into WASM. The JS Proxy wraps the new handle in another Proxy via `makeProxyForHandle(resp.handle)` at [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 85.

## Step 12: User code calls a method → `com_invoke` host function

When JS calls `geo.GetNodeCount()`, the sub-object Proxy's `get` trap returns a method wrapper (line 93 `makeMethod(prop)`). Invoking that wrapper calls `hostCall(com_invoke, {handle: 1, method: "GetNodeCount", args: []})`.

Control enters Python's `com_invoke` host function. Seven sequential gates:

| Gate | What | Where |
|------|------|-------|
| 0 | Deadline check | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 329: `state.assert_deadline()` |
| 1 | JSON parse + type coercion | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) lines 330-334 |
| 2 | Handle-table lookup | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 340: `if handle not in state.handle_table` |
| 3 | Global deny list | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 342: `if method in DENIED_METHODS` — [`DENIED_METHODS`](../src/openstaad_mcp/sandbox/constants.py#L84) |
| 4 | Per-object allowlist | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) lines 345-366: root → [`ALLOWED_ROOT_METHODS`](../src/openstaad_mcp/sandbox/constants.py#L48); sub-object → [`ALLOWED_SUB_OBJECT_METHODS`](../src/openstaad_mcp/sandbox/constants.py#L153)`[obj_name]` |
| 5 | Consent gate | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) lines 369-380: `if method in destructive_set and not state.allow_destructive` — [`DESTRUCTIVE_METHODS`](../src/openstaad_mcp/sandbox/constants.py#L108) |
| 6 | `getattr` + `callable()` | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) lines 382-386 |

## Step 13: COM IDispatch call into STAAD.Pro

All gates pass. Python calls the COM method on the live STAAD dispatch object.

| What | Where |
|------|-------|
| Dispatch call | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 389: `raw = fn(*args)` |
| Serialize return | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 394: `value =` [`_serialize_com_return`](../src/openstaad_mcp/sandbox/wasm_executor.py#L146)`(raw)` |
| Return JSON | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 399: `return json.dumps({"result": value})` |

`fn(*args)` is a pywin32 `IDispatch.Invoke` call. This is the actual inter-process (or in-process) COM call to the STAAD.Pro engine. It happens on the STA thread created in Step 4.

## Step 14: Result flows back through the chain

```
STAAD.Pro
  → pywin32 IDispatch returns Python int/float/str/tuple
    → _serialize_com_return() normalizes to JSON-safe types
      → json.dumps({"result": value})
        → Extism writes response to WASM linear memory
          → evaluator.js Memory.find(offset).readString()
            → JSON.parse(resp)
              → JS variable holds the value
```

| Direction | Boundary | Mechanism |
|-----------|----------|-----------|
| STAAD → Python | COM IDispatch | pywin32 `Dispatch.__getattr__` → `_ApplyTypes_` |
| Python → WASM | Host function return | Extism writes JSON string to WASM `Memory` at a returned offset |
| WASM → JS variable | `hostCall` return | `JSON.parse(Memory.find(offset).readString())` → `resp.result` |

## Step 15: Execution completes, output returned to agent

QuickJS finishes evaluating. The evaluator serializes the final result and writes it to Extism output.

| What | Where |
|------|-------|
| Capture result | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 167: `output = { ok: true, result: value }` |
| Serialize | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 174: `text = JSON.stringify(output)` |
| Write output | [`evaluator.js`](../src/openstaad_mcp/sandbox/evaluator_src/evaluator.js) line 179: `Host.outputString(text)` |
| Python reads | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 264: `raw = plugin.call("execute", code_bytes)` returns the output bytes |
| Parse payload | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) line 268: `payload = self._parse_payload(raw)` |
| Build [`ExecutionResult`](../src/openstaad_mcp/sandbox/wasm_executor.py#L107) | [`wasm_executor.py`](../src/openstaad_mcp/sandbox/wasm_executor.py) lines 278-285 |
| Return to `connect_and_run` | [`server.py`](../src/openstaad_mcp/server.py) line 262: `.to_dict()` |
| JSON-RPC response to agent | FastMCP serializes the dict as the tool result |

## Summary diagram

```
┌──────────┐   JSON-RPC    ┌─────────────────┐  connect_and_run  ┌────────────────┐
│ AI Agent │ ──────────────→│ server.py:168   │ ────────────────→ │ connection.py  │
│          │                │ execute_code()  │                   │ :254 (STA thd) │
└──────────┘                └─────────────────┘                   └───────┬────────┘
                                                                          │ fn(staad)
                                                                          ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│ wasm_executor.py                                                                 │
│                                                                                  │
│  :245  _CallState(handle_table={0: staad_object})                                │
│  :251  _build_host_functions(state)                                              │
│  :263  plugin = extism.Plugin(manifest, functions=[com_get, com_invoke, ...])    │
│  :264  raw = plugin.call("execute", code_bytes)                                  │
│         │                                                                        │
│         │ ┌─── WASM BOUNDARY (Wasmtime linear memory) ───────────────────────┐   │
│         │ │                                                                   │   │
│         │ │  evaluator.js                                                     │   │
│         │ │  :122  code = Host.inputString()                                  │   │
│         │ │  :152  staad = makeProxyForHandle(0)                              │   │
│         │ │  :167  value = fn(staad, sandboxConsole)                          │   │
│         │ │         │                                                         │   │
│         │ │         │ staad.Geometry → Proxy get trap (:84)                   │   │
│         │ │         │   hostCall(com_get, {handle:0, prop:"Geometry"})         │   │
│         │ │         │     ─── crosses to Python ──→  com_get (:299)           │   │
│         │ │         │     ←── returns {handle: 1} ──                          │   │
│         │ │         │                                                         │   │
│         │ │         │ geo.GetNodeCount() → makeMethod wrapper (:68)           │   │
│         │ │         │   hostCall(com_invoke, {handle:1, method, args})         │   │
│         │ │         │     ─── crosses to Python ──→  com_invoke (:329)        │   │
│         │ │         │       7 gates → getattr → fn(*args) → COM → STAAD      │   │
│         │ │         │     ←── returns {result: 42} ──                         │   │
│         │ │         │                                                         │   │
│         │ │  :179  Host.outputString(JSON.stringify({ok: true, result: 42}))  │   │
│         │ └──────────────────────────────────────────────────────────────────┘   │
│         │                                                                        │
│  :268  payload = _parse_payload(raw)                                             │
│  :278  return ExecutionResult(success=True, result=42, ...)                      │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Threading model

All of this happens on a **single thread**:
- `connect_and_run` spins a daemon thread ([`connection.py`](../src/openstaad_mcp/connection.py) line 305)
- That thread calls `CoInitialize()` (STA apartment)
- `WasmExecutor.execute()` runs on that thread
- `plugin.call()` runs on that thread
- Extism host functions execute on the **calling thread** (verified in Phase 0)
- COM calls happen on that same STA thread

No cross-thread marshaling. No async. No pipes. The WASM boundary is purely a memory isolation layer, not a process or thread boundary.
