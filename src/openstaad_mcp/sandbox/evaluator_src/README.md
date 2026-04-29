# Sandbox evaluator sources

These are the sources for the WebAssembly sandbox module that runs AI-generated JavaScript in `execute_code`. Compiled with the [Extism JS PDK][pdk] into
`src/openstaad_mcp/sandbox/evaluator.wasm`.

The build toolchain and design choices here are reusable for any product where the only available API bridge is a Python COM automation library and
you need to sandbox AI-generated code. This README is written to be comprehensive enough that someone can adopt the pattern for another product
without re-discovering the gotchas.

## Files

- **`evaluator.js`** — The JS code that runs inside WASM. Contains the `staad` Proxy factory (intercepts `staad.Geometry.AddNode(...)` style property access and method calls), console routing via host functions, the `execute()` entry point that evals user code, and the host-call helpers that marshal JSON across the WASM boundary via Extism's `Host.getFunctions()` / `Memory` API.
- **`evaluator.d.ts`** — TypeScript declaration that defines the host interface. This tells `extism-js` what host functions exist and their signatures. The `extism:host` module declaration is how you tell the WASM module "these functions will be provided by the host at runtime." **This file is not optional.** Without it, the compiled WASM has unresolved imports and `extism.Plugin` will fail to instantiate with a confusing Wasmtime link error.
- **`build.ps1`** — PowerShell script that downloads `extism-js` and `binaryen` to a local tools cache (`%LOCALAPPDATA%\openstaad-mcp\tools`) on first run, then compiles `evaluator.js` → `../evaluator.wasm`.

## Build toolchain and versions

You don't just `pip install` things and go — there is a **compile step** that turns the JS evaluator source into a `.wasm` binary. This happens
once at dev/build time, not at runtime.

| Component | Version | Role | Install |
|-----------|---------|------|---------|
| [Extism Python Host SDK][sdk] | 1.1.1 | Loads WASM plugins in-process, defines host functions in Python | `pip install extism` |
| [extism-sys][sys] | 1.21.0 | Native Wasmtime wheel (x86_64-pc-windows-msvc) | Installed as dependency of `extism` |
| [extism-js][pdk] | 1.6.0 | **Build-time only.** Compiles JS + `.d.ts` into a self-contained `.wasm` (QuickJS-ng + Wizer snapshot) | Downloaded by `build.ps1` |
| [binaryen][binaryen] | 129 | **Build-time only.** Provides `wasm-merge`, used internally by `extism-js` | Downloaded by `build.ps1` |
| QuickJS-ng | ~0.11.0 | JS engine compiled to WASM, ~200 KB. Bundled inside `extism-js` | — |
| Wasmtime | (bundled in extism-sys) | WASM runtime, hardware-enforced linear memory isolation | — |

## Rebuilding

From a PowerShell prompt in the repo root:

```powershell
.\src\openstaad_mcp\sandbox\evaluator_src\build.ps1
```

This runs:

```
extism-js evaluator.js -i evaluator.d.ts -o evaluator.wasm
```

That single command compiles QuickJS-ng + the evaluator code + the host interface declaration into one standalone WASM binary. Binaryen's
`wasm-merge` is used internally by `extism-js` to link the pieces.

**Output:** `evaluator.wasm` (~2.4 MB), placed at
`src/openstaad_mcp/sandbox/evaluator.wasm`. Loaded into memory once at import time by `wasm_executor.py`, then a fresh `extism.Plugin` is
instantiated from those bytes for every `execute_code` call.

## Build toolchain gotchas

- **You need `extism-js` AND `binaryen`.** `extism-js` uses `wasm-merge` from binaryen internally. If binaryen is not on PATH, the build fails with an unhelpful error. `build.ps1` handles this automatically.
- **The `.d.ts` file is not optional.** See above — without it you get unresolved WASM imports and a confusing Wasmtime link error at runtime.
- **`extism-js` versions matter.** v1.6.0 bundles QuickJS-ng ~0.11.0. Newer versions may bundle a different QuickJS-ng with different CVE status. Pin the version in your build script.
- **The output `.wasm` is a build artifact, not generated code.** Treat it like a compiled binary. Check it into the repo (or build in CI) and ship it with the package. It does not change at runtime.

## Security boundary

The evaluator is the *inside* of the WASM sandbox. Code here runs in the same address space as user-generated JavaScript. The security boundary is
the set of host functions Python provides — those are the *only* capabilities that cross into host memory. All fs/net/process access is
physically absent from this environment (no WASI filesystem preopens, no `extism_http_request` import).

### Runtime hardening (execute-time)

Inside `execute()`, before user code runs, the evaluator neuters dangerous Extism SDK globals to prevent user code from obtaining raw
host-function references:

- **`Host.getFunctions()`** — overwritten to return `{}`. Without this, user code can call `Host.getFunctions().com_invoke(offset)` with arbitrary (including negative) offsets, triggering a CFFI OverflowError in the Python SDK that surfaces as a blocking Windows error dialog (DoS vector).
- **`Host.__hostFunctions`** — set to `[]`.
- **`Host.invokeFunc`** — wrapped with an offset validator that rejects negative numbers before they reach the CFFI layer.
- **`fetch`** — set to `undefined` (Extism polyfill traps the WASM when called; removing it gives user code a clearer error).

The module-scope closures (`com_get`, `com_invoke`, `console_output`) captured at init time still hold their original references and work
normally through the Proxy. User code interacts via the `staad` Proxy object and never needs direct access to host functions.

## How the host function bridge works

On the Python side (`wasm_executor.py`), three host functions are defined inside a per-call closure:

- **`com_get({handle, prop})`** — resolves a sub-object by name on handle 0. Returns a new handle integer. Only valid on the root object; only names in `ALLOWED_SUB_OBJECTS` pass the allowlist.
- **`com_invoke({handle, method, args})`** — calls a method on any handle. Checks the deny list, then the per-handle allowlist, then does a single `getattr` + call. Returns the result as JSON.
- **`console_output({stream, text})`** — routes `console.log` / `console.error` from JS to a Python-side buffer (capped at 256 KiB).

Key properties:

- **JSON boundary.** Everything in and out is a JSON string. No pointers, no object references, no shared memory. COM dispatch objects never enter the WASM address space.
- **Per-call closure.** The handle table, console buffer, and deadline are created fresh for each `execute()` call. Nothing leaks across calls.
- **Same-thread execution.** Extism host functions run on the calling thread. This is critical for COM STA apartment threading — if host functions ran on a different thread, every COM call would need cross-apartment marshaling, breaking the STA model. Verified during Phase 0 spike with `threading.get_ident()`.

## Key development findings (Phase 0 spike, 2026-04-20)

These were the go/no-go questions we had to answer before committing to the WASM approach. Documented here so they don't need to be re-discovered
for future products.

1. **Extism loads and runs on Windows.** `pip install extism` installs
   cleanly. `extism-sys` ships Wasmtime as a standard native wheel. No manual DLL placement needed.

2. **Host functions execute on the calling thread.** Non-negotiable for
   COM STA. Confirmed with `threading.get_ident()` inside host functions vs. the thread that called `plugin.call()`.

3. **Latency is acceptable.** ~180 µs per host function round-trip (1000
   sequential calls). Production: ~110 ms for plugin spin-up + 100 sequential host calls. Single `execute_code` end-to-end: ~57 ms.

4. **State isolation requires fresh plugins.** Extism does NOT auto-reset
   globals within a single `Plugin` instance. A `globalThis.__leak = 42` in call N is visible in call N+1. Fix: instantiate a new `extism.Plugin` from pre-loaded WASM bytes for every call. Construction cost is small (tens of ms) because Wasmtime caches module compilation.

5. **No network surface.** `fetch` exists as a JS global in QuickJS-ng
   but traps at the WASM boundary because we don't provide the `extism_http_request` host function. XMLHttpRequest, WebSocket, import() — all absent or non-functional. Confirmed with Burp Collaborator: zero OOB DNS hits across 7 exfil vectors.

6. **No filesystem, no process, no OS access.** WASM linear memory is
   hardware-isolated by Wasmtime. No `process`, `child_process`, `os`, `require`, or syscall access of any kind.

## COM bridge design decisions

These choices are product-specific policy but the patterns are reusable:

- **Handle table.** For STAAD, the COM object graph is flat: root + 9 sub-objects, no deeper nesting, no methods that return dispatch objects. Handle table never exceeds 10 entries. Products with deeper graphs extend naturally (new handle per returned dispatch object), but need handle lifetime management if the graph is large.

- **Allowlist > deny-list.** We started with a deny-list and switched to deny-by-default allowlists for root methods and sub-object methods. Enumerate the full API surface from a live instance, review by hand, and generate the allowlist. See `docs/plan-research-support/enumerate-com-api.py`.

- **Consent gate for destructive methods.** Methods that write to the filesystem or have session-destructive effects are gated behind MCP elicitation — a host-mediated dialog the user must approve. The LLM cannot self-confirm.

- **UNC path rejection.** Any path argument starting with `\\` is rejected unconditionally to prevent NTLM relay. Windows-specific but critical for any COM product that accepts file paths.

## Adapting for another product

1. **Enumerate the COM API surface.** Connect to a running instance, list
   every method on every reachable object. Review for file I/O, network, process control, destructive operations.
2. **Map the object graph depth.** Flat (root + N sub-objects) or nested?
   Determines handle table complexity and whether you need cleanup/GC.
3. **Copy and adapt `evaluator.js`.** The host-call helpers, console
   routing, and entry-point pattern are reusable. The Proxy factory (sub-object names, property-vs-method disambiguation) will differ.
4. **Write a `.d.ts` host interface.** Same three functions work for any
   handle-based COM bridge. Add more if the product needs extra host-side capabilities (file picker, progress callback, etc.).
5. **Build with `extism-js` + binaryen.** `build.ps1` is reusable with
   path changes.
6. **Write Python host functions.** Same closure-per-call pattern. Adapt
   allowlists, deny-lists, and consent policies.
7. **Wire into the MCP server.** Same `extism.Plugin` instantiation,
   manifest pattern (memory limits, timeout), `ExecutionResult` structure.

### Open questions for generalization

- **Deep COM hierarchies.** If methods return dispatch objects (not just primitives), the handle table grows unboundedly. Need a GC or reference-counting strategy.
- **Event callbacks.** Some COM APIs use connection points (event sinks). The current model is strictly request-response. Supporting callbacks requires the host to call into the WASM module (Extism supports `plugin.call()` from host functions) but adds complexity.
- **Large binary data.** The JSON boundary works for scalars and small arrays but would be slow for megabyte-scale transfers. Consider raw Extism memory sharing for bulk data.
- **Non-Windows.** Extism and Wasmtime are cross-platform. The COM bridge (pywin32) is Windows-only, but the sandbox pattern works anywhere you have a Python API that needs isolation.

[pdk]: https://github.com/extism/js-pdk
[sdk]: https://github.com/extism/python-sdk
[sys]: https://pypi.org/project/extism-sys/
[binaryen]: https://github.com/WebAssembly/binaryen
