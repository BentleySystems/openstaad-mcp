# Sandbox Replacement Plan

**Status:** v2.0.0 implementation complete; adversarial testing done (see Phase 6) **Last updated:** 2026-04-23
**Author:** Dave Hanson

## The problem

The `execute_code` tool runs AI-generated Python inside a hand-rolled sandbox: an AST walker, a restricted `__builtins__` dict, and `exec()`. The April 2026 security audit found five High-severity bypasses (OMCP-001, 003, 004, 007, 008) that all exploit the same root cause: Python's object model. Dunders, MRO traversal, descriptor access. The raw COM dispatch object is injected straight into `exec()` globals, and no amount of AST filtering can fully lock down what Python lets you do with a live object reference.

Fixing these one at a time is whack-a-mole. The real problem is not any single bypass. The real problem is that the Python language itself is the attack surface.

## What we are doing

Replacing `exec()` with a WebAssembly sandbox powered by Extism and QuickJS-ng. AI-generated code switches from Python to JavaScript. The Python MCP server, COM bridge, connection management, skills system, and everything else stays exactly as-is.

No real external users yet, so the cost of breaking `execute_code`'s input language is close to zero. The only consumer is AI agents, and they are equally fluent in JavaScript. The STAAD COM method names are identical regardless of wrapper language. `staad.Geometry.AddNode(0, 0, 0)` reads the same in both.

## Why this approach

The current sandbox gives user code a live COM pointer inside the same Python process. Every COM call is a direct in-process IDispatch invocation on the STA thread. That is fast, simple, and exactly how it should work, except the user code has the entire Python runtime to play with around it.

What we need is a way to keep that same in-process, same-thread, synchronous COM dispatch, but run the user code somewhere it cannot reach Python internals. WebAssembly does exactly this. Code inside a WASM module runs in its own linear memory address space, enforced by the runtime at the hardware level. It cannot see host memory, cannot follow pointers into the Python heap, and cannot call any function the host does not explicitly provide. There is no `__mro__`, no `__class__`, no `__subclasses__()`, because those are Python concepts and the WASM module is not running Python.

Extism is the framework that makes this practical. It provides a Python Host SDK (`pip install extism`, v1.1.1, BSD-3, Windows MSVC x86_64 supported) that loads WASM modules in-process and lets you define host functions in Python that the WASM code can call. Calls are synchronous and happen on the calling thread, which means our existing `connect_and_run` STA threading model works unchanged.

The JavaScript engine inside the WASM module is QuickJS-ng, an actively maintained community fork of Bellard's QuickJS (v0.14.0, 98 contributors, commits landing daily). It targets the latest ECMAScript living standard and runs the full test262 conformance suite on every change. Extism's JS PDK compiles QuickJS-ng into a self-contained WASM module that can evaluate JavaScript strings. The entire engine is about 200KB compiled.

The bottom line: we get hardware-enforced memory isolation, in-process synchronous execution, no subprocess lifecycle to manage, no pipe framing to debug, no Windows Defender false positives from extracted binaries, and the COM dispatch path does not change at all.

## Architecture

### Current (v1)

```
AI Agent
  |
  +--> MCP JSON-RPC (stdio or http)
         |
         +--> FastMCP / Python MCP Server
                |
                +--> execute_code tool
                       |
                       +--> AST validator (sandbox/ast.py)
                       +--> exec() with restricted globals (sandbox/executor.py)
                       |      |
                       |      +--> user Python code runs here
                       |      +--> raw COM IDispatch object in exec() globals
                       |      +--> staad.Geometry.AddNode(0,0,0) is a live COM call
                       |
                       +--> pywin32 COM dispatch (in-process, STA thread)
                       +--> STAAD.Pro
```

The problem: user code and the COM object share one Python process, one address space, one type system. The AST filter is the only barrier, and Python's object model gives user code ways around it.

### Target (v2)

```
AI Agent
  |
  +--> MCP JSON-RPC (stdio or http)
         |
         +--> FastMCP / Python MCP Server
                |
                +--> execute_code tool
                       |
                       +--> Extism Plugin (WASM linear memory, hardware-isolated)
                       |      |
                       |      +--> QuickJS-ng evaluates user JavaScript
                       |      +--> staad.Geometry.AddNode(0,0,0)
                       |      +--> JS Proxy intercepts access:
                       |             - sub-object access  -> com_get(handle=0, prop)
                       |             - method call        -> com_invoke(handle, method, args)
                       |
                       +--> Python host functions receive the call
                       +--> single getattr on handle table entry, allowlist-gated
                       +--> pywin32 COM dispatch (in-process, same STA thread)
                       +--> STAAD.Pro
```

Everything outside the WASM box is unchanged. The MCP server, FastMCP, transport (stdio/http), skills system, connection management, instance registry, `connect_and_run`, the STA threading model, all of it stays Python.

## Key design decisions

### 1. How user code calls COM methods

User code needs to call `staad.Geometry.GetNodeCount()` and have that turn into a real COM dispatch call on the Python side. Inside the WASM module, the `staad` object is a JavaScript Proxy that intercepts property access and method calls, builds a handle-method-args request, and calls a host function that Python provides. The Proxy never builds path arrays or chains — each host call is a single step (see JS Proxy protocol below).

From the user's (really the AI agent's) perspective:

```javascript
const geo = staad.Geometry;
const n1 = geo.AddNode(0, 0, 0);
const n2 = geo.AddNode(0, 120, 0);
const b1 = geo.AddBeam(n1, n2);
console.log(`Beam ${b1}: node ${n1} to ${n2}`);
```

On the Python side, three host functions handle this — one for sub-object resolution, one for method calls, one for console output. Each does exactly one `getattr` on a known object, never a chain. Per-call state lives in a `_CallState` dataclass (handle table, deadline, stdout buffer, `allow_destructive` flag), created fresh for each `execute()` call.

The pseudocode below matches the real implementation in `sandbox/wasm_executor.py` (updated 2026-04-27). Comments mark the seven sequential gates in `com_invoke` — every COM call must pass all seven before `fn(*args)` fires.

```python
# Module-level constants (defined once in sandbox/constants.py)
ALLOWED_SUB_OBJECTS = {"Geometry", "Property", "Support", "Load", "Command",
                       "Output", "Design", "Table", "View"}
ALLOWED_ROOT_METHODS = {...}            # 23 methods — see "Root allowlist" below
ALLOWED_SUB_OBJECT_METHODS = {          # deny-by-default per sub-object
    "Geometry": frozenset({...}),       # 695 methods across 9 sub-objects
    "Property": frozenset({...}),       # generated from openstaadpy wrappers
    ...                                 # SetStandardProfileDBFolder excluded
}
DENIED_METHODS = {"SetStandardProfileDBFolder"}  # global deny list
DESTRUCTIVE_METHODS = {                 # consent-gated (Control 4)
    "_root": {"NewSTAADFile", "OpenSTAADFile", "CloseSTAADFile",
              "SaveModel", "Quit"},
    "View":  {"ExportView"},
    "Table": {"SaveReport", "SaveReportAll", "SaveTable"},
}
PATH_ARGUMENT_INDICES = {               # UNC validation targets
    ("_root", "NewSTAADFile"):  (0,),   # arg 0 = file path
    ("_root", "OpenSTAADFile"): (0,),
    ("View",  "ExportView"):    (0,),
}


@dataclass
class _CallState:
    """Mutable per-call state shared across host functions."""
    handle_table: dict[int, Any]        # 0=root, 1..N=sub-objects
    sub_object_handles: dict[str, int]  # cache: name → handle
    next_handle: int = 1
    stdout_buf: bytearray               # console.log capture
    stderr_buf: bytearray               # console.error capture
    deadline: float = 0.0               # wall-clock deadline (monotonic)
    allow_destructive: bool = False     # set True only after MCP elicitation

    def assert_deadline(self) -> None:
        if time.monotonic() > self.deadline:
            raise _SandboxError("timeout")


def _build_host_functions(state: _CallState) -> list:

    @host_fn()
    def com_get(request: str) -> str:
        """Sub-object resolution. Only valid on handle 0."""
        try:
            state.assert_deadline()                              # deadline check
            parsed = json.loads(request)
            handle = int(parsed.get("handle", -1))               # type coercion
            prop = str(parsed.get("prop", ""))
        except _SandboxError:
            raise
        except Exception:
            return json.dumps({"error": "Invalid com_get request"})

        if handle != 0:
            return json.dumps({"error": "com_get is only valid on the root object"})
        if prop not in ALLOWED_SUB_OBJECTS:
            return json.dumps({"error": f"Sub-object {prop!r} is not allowed"})

        # Cache by property name — pywin32 may return distinct wrapper
        # objects across calls, so identity comparison is unreliable.
        if prop in state.sub_object_handles:
            return json.dumps({"handle": state.sub_object_handles[prop]})

        try:
            sub = getattr(state.handle_table[0], prop)
        except Exception as exc:
            return json.dumps({"error": _sanitize_com_error(f"staad.{prop}", exc)})

        h = state.next_handle
        state.next_handle += 1
        state.handle_table[h] = sub
        state.sub_object_handles[prop] = h
        return json.dumps({"handle": h})

    @host_fn()
    def com_invoke(request: str) -> str:
        """Method call on any handle — the security boundary.

        Seven sequential gates; every COM call must pass all seven.
        """
        # ── Gate 0: Deadline check ──
        # Cooperative wall-clock check (belt-and-suspenders with Wasmtime's
        # epoch-based preemptive timeout in the manifest).
        try:
            state.assert_deadline()

            # ── Gate 1: Parse & type coercion ──
            # json.loads produces Python dicts/lists/strings/numbers — no
            # injected Python objects. int()/str() coerce the values so an
            # attacker cannot smuggle a dict-with-__str__ as a method name.
            parsed = json.loads(request)
            handle = int(parsed.get("handle", -1))
            method = str(parsed.get("method", ""))
            args = parsed.get("args", [])
            if not isinstance(args, list):
                return json.dumps({"error": "args must be an array"})
        except _SandboxError:
            raise
        except Exception:
            return json.dumps({"error": "Invalid com_invoke request"})

        # ── Gate 2: Handle table lookup ──
        # Only handles registered by com_get (or handle 0 = root) are valid.
        # Forged/guessed IDs hit this check.
        if handle not in state.handle_table:
            return json.dumps({"error": "Invalid handle"})

        # ── Gate 3: Global deny list ──
        if method in DENIED_METHODS:
            return json.dumps({"error": f"Method {method!r} is not allowed"})

        # ── Gate 4: Per-object positive allowlist ──
        # Root handle: method must be in ALLOWED_ROOT_METHODS (23 entries).
        # Sub-object handles: method must be in ALLOWED_SUB_OBJECT_METHODS
        # for that specific sub-object (deny-by-default, 695 total).
        # __proto__, __class__, __dict__, constructor, toString, valueOf
        # etc. are all rejected here — they are not in any allowlist.
        if handle == 0:
            obj_name = "_root"
            if method not in ALLOWED_ROOT_METHODS:
                return json.dumps({"error": f"Method {method!r} is not allowed on the root object"})
        else:
            obj_name = None
            for name, h in state.sub_object_handles.items():
                if h == handle:
                    obj_name = name
                    break
            if obj_name is not None:
                allowed = ALLOWED_SUB_OBJECT_METHODS.get(obj_name, frozenset())
                if method not in allowed:
                    return json.dumps({"error": f"Method {method!r} is not allowed on {obj_name}"})

        # ── Gate 5: Consent gate (Control 4 — MCP elicitation) ──
        # Filesystem-write and session-destructive methods require explicit
        # human approval via the host confirmation dialog. allow_destructive
        # is only True when the server layer obtained consent via
        # Context.elicit() — a protocol-level exchange the LLM cannot
        # self-confirm.
        destructive_set = DESTRUCTIVE_METHODS.get(obj_name or "", frozenset())
        if method in destructive_set and not state.allow_destructive:
            return json.dumps({"error": f"Method {method!r} is blocked ..."})

        # ── Gate 6: UNC path validation (NTLM relay prevention) ──
        # Always enforced, even after user approval. Checks string args at
        # known path-argument positions for \\ prefix.
        path_indices = PATH_ARGUMENT_INDICES.get((obj_name or "", method))
        if path_indices is not None:
            for idx in path_indices:
                if idx < len(args) and isinstance(args[idx], str) and _is_unc_path(args[idx]):
                    return json.dumps({"error": f"UNC paths are not permitted in {method!r} ..."})

        # ── Gate 7: Attribute resolution + callable check ──
        # Only now does getattr fire. If the attribute exists but is not
        # callable (e.g. a sub-object reference accessed via com_invoke
        # instead of com_get), reject before dispatch.
        target = state.handle_table[handle]
        try:
            fn = getattr(target, method)
        except Exception as exc:
            return json.dumps({"error": _sanitize_com_error(f"..{method}", exc)})
        if not callable(fn):
            return json.dumps({"error": f"Attribute {method!r} is not callable"})

        # ── Dispatch ──
        try:
            raw = fn(*args)
        except Exception as exc:
            return json.dumps({"error": _sanitize_com_error(f"..{method}", exc)})

        # ── Serialise return value ──
        try:
            value = _serialize_com_return(raw)
        except TypeError as exc:
            return json.dumps({"error": f"Unsupported COM return type from {method!r}: {exc}"})

        return json.dumps({"result": value})

    @host_fn()
    def console_output(request: str) -> str:
        """Route console.log/console.error from WASM to Python buffers."""
        try:
            state.assert_deadline()
            parsed = json.loads(request)
            stream = str(parsed.get("stream", "stdout"))
            text = str(parsed.get("text", ""))
        except _SandboxError:
            raise
        except Exception:
            return ""
        buf = state.stderr_buf if stream == "stderr" else state.stdout_buf
        # Silent truncation beyond MAX_STDOUT_BYTES — no trap, no exception.
        remaining = MAX_STDOUT_BYTES - len(buf)
        if remaining > 0:
            buf.extend((text + "\n").encode("utf-8", errors="replace")[:remaining])
        return ""

    return [com_get, com_invoke, console_output]


def _is_unc_path(value: str) -> bool:
    """Return True if value begins with ``\\\\`` (UNC or extended-length path)."""
    return value.startswith("\\\\")


def _sanitize_com_error(where: str, exc: BaseException) -> str:
    """Short, non-revealing error string for the WASM side.

    Full traceback logged server-side at DEBUG. For pywintypes.com_error,
    extracts only the HRESULT and description — helpFile and source fields
    (which can leak DLL paths and module names) are stripped.
    """
    logger.debug("COM error in %s", where, exc_info=True)
    cls = type(exc).__name__
    if hasattr(exc, "args") and isinstance(exc.args, tuple) and len(exc.args) >= 2:
        hresult, description, *_ = exc.args
        if isinstance(hresult, int):
            desc = str(description) if description else "no description"
            return f"COM error in {where!r}: {cls}: [{hresult:#010x}] {desc}"
    # Non-COM exceptions — class name only, not str(exc) which may
    # contain tracebacks or path information.
    return f"COM error in {where!r}: {cls}"


def _serialize_com_return(value):
    """Normalise COM return values to JSON-compatible types.

    Per the COM surface audit, every return is a scalar or a container
    of scalars. Anything else is a bug caught by TypeError → error JSON.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_serialize_com_return(x) for x in value]
    raise TypeError(f"Unexpected COM return type: {type(value).__name__}")
```

**JS Proxy protocol:** The JS Proxy inside the WASM module does **not** hardcode sub-object names. For handle 0 (root), the `get` trap always calls `com_get({handle: 0, prop})` first. If the Python side returns a handle (property is in `ALLOWED_SUB_OBJECTS`), the Proxy wraps it in a new sub-object Proxy. If `com_get` returns an error (property is not a sub-object), the Proxy falls back to returning a method-call wrapper that will send `com_invoke`. For non-root handles, all property access produces method-call wrappers directly.

This means:
- `staad.Geometry` → `com_get` succeeds → sub-object Proxy for handle 1. - `staad.GetBaseUnit()` → `com_get` fails ("not a sub-object") → falls through to `com_invoke({handle: 0, method: "GetBaseUnit", args: []})`.
- `geo.AddNode(0,0,0)` → handle ≠ 0, so directly `com_invoke({handle: 1, method: "AddNode", args: [0,0,0]})`.

Sub-object resolution is one host call; root method calls are two (failed `com_get` + `com_invoke`); sub-object method calls are one (`com_invoke` only).

Key points:
- **No chain.** Each host function call does exactly one `getattr`. The JS Proxy on the WASM side is what builds the chain of calls — `staad.Geometry` is one host call, `.AddNode(0,0,0)` is a second host call.
- **Seven sequential gates in `com_invoke`.** Every COM method call passes through: (0) deadline check, (1) JSON parse + type coercion, (2) handle-table lookup, (3) global deny list, (4) per-object positive allowlist, (5) consent gate, (6) UNC path validation, (7) `getattr` + `callable()` check. Only after all seven does `fn(*args)` fire.
- **Allowlist on root.** Handle 0 is gated: only `ALLOWED_SUB_OBJECTS` names pass `com_get`, and only `ALLOWED_ROOT_METHODS` (23 entries) pass `com_invoke`. Everything else is rejected before `getattr` runs.
- **Sub-objects are deny-by-default.** Handles 1–9 are gated by `ALLOWED_SUB_OBJECT_METHODS` (695 methods across 9 sub-objects). Any method not explicitly listed is rejected. `SetStandardProfileDBFolder` is excluded from both the sub-object allowlist and added to `DENIED_METHODS` (belt-and-suspenders).
- **Consent gate (Control 4).** `DESTRUCTIVE_METHODS` (file-write and session-destructive operations) require `state.allow_destructive == True`, which is set only when the server layer obtains human approval via `Context.elicit()` — a host-mediated dialog the LLM cannot self-confirm.
- **UNC path validation.** `PATH_ARGUMENT_INDICES` maps `(obj_name, method)` → argument positions that contain file paths. `_is_unc_path()` blocks `\\\\` prefixes to prevent NTLM relay. Always enforced, even after consent. Known gap: forward-slash UNC (`//attacker/share/`) is not caught — documented as an accepted risk since COM APIs on Windows use backslash conventions.
- **`callable()` check.** After `getattr` succeeds but before dispatch, the result is verified as callable. This prevents sub-object property references (e.g., `Geometry` on root) from being "called" via `com_invoke` — they must go through `com_get`.
- **Error sanitization.** `_sanitize_com_error()` strips DLL paths and module names from `pywintypes.com_error` — only the HRESULT and human-readable description reach the WASM side. Non-COM exceptions return only the class name.
- **No path parsing.** The handle + single name design means there is literally no way to construct a multi-step traversal.
- **`com_get` never returns serialized values or callable flags.** It has exactly one success response type: `{"handle": N}`.
- **Sub-object audit methodology.** The claim that "sub-object methods return only primitives/tuples and have no hidden side effects beyond the deny list" is load-bearing. It was established by: (1) enumerating all 727 methods via `docs/plan-research-support/enumerate-com-api.py` against a live STAAD.Pro 2026 instance on 2026-04-15; (2) keyword scan of method names for `File`, `Save`, `Write`, `Export`, `Folder`, `Path`, `Dir`, `Open`, `Close`, `Delete`, `Remove`, `Quit`, `Exit`, `Kill`, `Run`, `Exec`, `Shell`, `Process`, `System`; (3) manual review of every hit. The primitive-return claim is inferred from `openstaadpy` wrappers, which document return types for every wrapped method — no SAFEARRAY, VT_DISPATCH, or VT_UNKNOWN anywhere in the wrappers. **The audit must be re-run on every STAAD.Pro major-version upgrade.** New methods are auto-allowed unless they hit the deny list, so additions need human review before that version is supported.

Everything is synchronous and in-process. No subprocess, no pipes, no async. The host functions run on the same thread that called `plugin.call()`, which is the STA thread from `connect_and_run`. COM threading works exactly as it does today.

**Root allowlist.** The current `ALLOWED_ROOT_METHODS` set (see the sketch above — analysis, units, file/process control, job info, status) is deliberately kept broad. Rationale: the methods on it either (a) have no file-path argument and no destructive side effect (units, status, info, analysis), (b) are used by existing skill scripts as required workflow steps (`SaveModel`, `NewSTAADFile`), or (c) gated by the consent gate (`DESTRUCTIVE_METHODS`) — only callable when the user approves via host elicitation (`Quit`, `CloseSTAADFile`, `OpenSTAADFile`). The consent gate ensures that even if prompt injection tricks the LLM into calling a write method, execution is blocked because approval requires a human to confirm a host-side dialog.

### 2. The WASM evaluator module

We pre-build a single `.wasm` file that contains the QuickJS-ng runtime and the `staad` Proxy setup. This gets shipped with the release artifact. At runtime, the AI-generated JavaScript is passed as input data to this module, which evaluates it. No compilation at runtime, no external toolchain.

The Extism JS PDK compiles JS source into WASM using the `extism-js` CLI (QuickJS-ng + Wizer for snapshotting). We build our evaluator once and ship the `.wasm` binary. It is roughly 1-2MB.

### 3. COM object handles

When user code accesses `staad.Geometry`, the Proxy calls a host function. The Python side calls `getattr(staad, "Geometry")`, which returns a COM dispatch sub-object. We cannot pass that pointer into WASM, so we store it in a handle table and return an opaque integer ID. The JS Proxy maps that ID to a new nested Proxy, so further calls like `geo.AddNode(0, 0, 0)` route to the correct dispatch object.

After reviewing every skill script, it turns out the COM graph is completely flat. There are exactly 9 sub-objects (Geometry, Property, Support, Load, Command, Output, Design, Table, View), and none of their methods return further dispatch objects -- only primitives, tuples, and integer IDs. So the handle table never has more than 10 entries (root + 9 sub-objects), sub-object handles are cached on first access, and the whole table is scoped to a single `connect_and_run` call. When execution finishes, the dict falls out of scope and Python's COM wrappers handle reference release before `CoUninitialize`. No explicit cleanup, no leak risk.

This turned out to be the simplest part of the design rather than the hardest.

### 4. Skill scripts stay Python for now, switch to JS later

The skill scripts (portal-frame.py, hydrostatic-tank.py, etc.) are read by AI agents via `read_skills`. They teach the agent what COM methods to call and in what order. Nobody types this code by hand.

We will rewrite these to JavaScript as a separate task. The COM method names, argument order, and patterns are identical. The only difference is `const` vs no keyword and semicolons. AI agents do not care either way, but having the examples match the execution language is cleaner.

This is a low-priority task. The sandbox replacement is the security-critical work.

### 5. Breaking v2.0 release

Clean cut. No parallel sandbox support. We have very few users right now and this is the best time to make a breaking change. The friction cost of migrating a handful of early adopters is orders of magnitude lower than doing this later.

## What changes for users

We do not have real external users yet — this is the cheapest time to make breaking changes. The only consumer of `execute_code` is AI agents. They generate code, we run it. The COM API surface is identical.

| Aspect | Before (v1) | After (v2) |
|--------|-----------|----------|
| Code language in sandbox | Python | JavaScript |
| `staad.Geometry.GetNodeCount()` | Works | Works (same) |
| `JSON`, `Math` | Injected as proxied modules | Built-in to JavaScript |
| `print(...)` | Works | `console.log(...)` |
| Output capture | stdout hijack | console.log routing |
| MCP tools | No change | `read_analysis_output` added (reads .ANL/.LOG files for non-steel design results) |
| Installation | No change | No change |
| Transport stdio | No change | No change |
| Transport http | `--token` optional | **No flags needed** — server auto-generates bearer token, pushes to OneTimeSecret, displays OTS share URL in terminal auth banner (fixes OMCP-006, OMCP-012). If OTS unreachable, raw token shown in banner. |
| Multi-instance support | No change | No change |

The AI agent just needs to know it is writing JavaScript instead of Python. The `execute_code` tool description tells it that. The skill scripts show the patterns.

## Implementation phases

These phases are the logical sequence, not a calendar. AI agents will execute the build end-to-end. The phases exist so we can validate at each boundary before moving on.

### Phase 0: Spike — **DONE 2026-04-20**

Proved the concept end-to-end in an isolated venv at `docs/plan-research-support/src/`. One-shot harness (`phase0_spike.py`) covers all go/no-go items. Delete the folder to roll back; nothing under `src/openstaad_mcp/` was touched.

- [x] Install `extism` Python SDK, verify it loads and runs a trivial WASM module on Windows — extism 1.1.1 + extism-sys 1.21.0 wheels installed cleanly.
- [x] Build a minimal JS evaluator WASM using `extism-js` — 2.4 MB module, compiled with `extism-js` 1.5.1 + binaryen 129.
- [x] Python harness loads evaluator via `extism.Plugin` and round-trips through `com_get`, `com_invoke`, `console_output` host functions against a mock STAAD object graph.
- [x] Round-trip `staad.Geometry.AddNode(0, 0, 0)` returns the expected value. - [x] User code cannot reach filesystem, process, Deno/Bun/Node globals, or `WebAssembly` (all `undefined`). `fetch` **does** exist as a JS global (QuickJS-ng provides it), but traps at the WASM boundary with a missing-host-import error because we do not provide `extism_http_request`. Agents should be told "network is unavailable" rather than "there is no fetch," because the latter is technically false.
- [x] Handle-based sub-object resolution works (`staad.Geometry` → handle 1, cached; subsequent accesses do not re-run `getattr`).
- [x] State isolation between `plugin.call()` invocations. **Finding:** Extism does **not** auto-reset globals within a single `Plugin` instance — a `globalThis.__leak = 42` in call N is still visible in call N+1. The v2 production pattern is therefore **one fresh `extism.Plugin` per `execute_code` invocation**, not plugin reuse. Plugin construction cost is small enough (~tens of ms, dominated by WASM validation which Wasmtime caches) to make this viable; confirmed by latency measurements below.
- [x] Latency per COM call through the host function boundary — measured **~180 µs/call** over 1000 sequential `AddNode` calls on a mid-range Windows dev box. Comfortably inside the plan's <1 ms target.
- [x] Extism host functions execute on the **calling thread**. Verified twice: from the main thread, and from a Python worker thread (mimicking `connect_and_run`'s STA thread). `threading.get_ident()` inside every host function equals the thread that called `plugin.call()`. This is the load-bearing COM-apartment requirement.
- [ ] ~~PyInstaller smoke test.~~ Deferred to Phase 4. Extism ships Wasmtime as a standard wheel (`extism-sys`) with a normal native DLL; there is no reason to expect PyInstaller to mishandle it. If it does, Phase 4 catches it and we fix the spec file then — not a go/no-go for the architecture.

**Exit criteria — all met:** working round-trip, <1 ms per host call (actual: 180 µs), host functions on calling thread, no host-reachable fs/net/process surface.

**If Phase 0 had failed:** we would have abandoned this plan. The WASM approach only makes sense if Extism works cleanly on Windows and runs host functions on the calling thread. Both confirmed.

### Phase 1: Production sandbox — **DONE 2026-04-22**

Build the real thing.

- [x] **Evaluator WASM module (`evaluator.wasm`)**
  - Proxy factory for `staad` with property access interception and handle-based sub-object resolution (one level: root + 9 sub-objects) - `console.log` / `console.error` capture, routed back to host - Result capture: last expression value or explicit `return <value>` (auto-returns single-expression bodies; falls back to raw statement body for multi-statement code — user returns explicitly) - Error capture: try/catch wrapper, clean error messages - Execution timeout via cooperative deadline check in every host function (plan said fuel metering; implementation uses wall-clock deadline — simpler, equivalent guarantee for COM-bound workloads)
- [x] **Python-side executor (`sandbox/wasm_executor.py`)** - Load and **validate** the evaluator WASM bytes once at startup (read file into memory, keep around). Instantiate a fresh `extism.Plugin` from those bytes for each `execute_code` call — Phase 0 proved globals persist inside a single `Plugin` instance, so reuse is unsafe. Plugin construction from pre-loaded bytes is cheap (tens of ms) because Wasmtime caches module compilation. - Define host functions per call (closure over `handle_table`, `staad_object`, `console_buffer`): `com_get`, `com_invoke`, `console_output` - Handle-based COM dispatch: each host function call does exactly one `getattr` on a known object via its handle (no chains, no path arrays — see Key Decision #1) - COM handle table: root + 9 sub-object handles, lazily cached, scoped to `connect_and_run` call (no explicit cleanup needed) - Handle COM return types: `int`, `float`, `str`, `bool`, `None`, `tuple`, `list` — all map directly to JSON - Return `ExecutionResult` (same dataclass as current executor) - **Default limits:** execution timeout 30 seconds, WASM memory 64 MiB, captured stdout 256 KiB. All three are constants in `wasm_executor.py` — no user-facing config in v2.0.0; revisit only if real usage shows these are wrong. - **Trap / limit semantics:** when execution exceeds the timeout, exceeds memory, or the WASM module traps, return `ExecutionResult(success=False, result=None, error="sandbox error: <category>")` where `<category>` is one of `timeout`, `memory limit exceeded`, `stdout limit exceeded`, or `trap`. No Python traceback, no WASM internals, no file paths ever cross the boundary. Full details logged server-side at DEBUG. - **`console_output` host function.** QuickJS `console.log` / `console.error` inside the WASM module are rewired to call a `console_output(stream: str, text: str)` host function. The Python side appends to an in-memory buffer; once the 256 KiB cap is reached, further calls are silently dropped (no exception, no trap — truncation is friendlier to agents than a hard fail mid-script). The captured buffer is returned on the `ExecutionResult.stdout` / `.stderr` fields.
- [x] **COM type serialization**
  - Python `int`, `float`, `str`, `bool`, `None` map directly to JSON - Tuples and lists map to JS arrays - Mixed-type tuples (e.g. `GetMemberSteelDesignResults` returns 10 elements of mixed str/float/int/list) map to JSON arrays with mixed element types - Sentinel values (`-999` = not designed, `-1` = no results) pass through as integers; JS code handles them as normal numbers
- [x] **Security validation (must pass before Phase 2)** — agent-written coverage in place; owner-authored adversarial pass complete (see Phase 6). - [x] No filesystem access from user code (WASM has no filesystem capability) - [x] No network access — `fetch` exists as a JS global but traps at the WASM import boundary because `extism_http_request` is not provided. `tests/sandbox/test_wasm_executor.py::TestIsolation::test_no_fetch` asserts the trap/block path. **Confirmed with Burp Collaborator (2026-04-23): zero OOB hits from 7 exfil vectors (fetch, XHR, WebSocket, import, Request, eval+fetch, UNC via OpenSTAADFile).** - [x] No host memory access (WASM linear memory is isolated — inherent to Extism) - [x] No Python object traversal (no Python objects exist inside WASM — inherent to design) - [x] console.log output size limits enforced (`TestLimits::test_stdout_truncated`) - [x] Execution timeout enforced (`TestLimits::test_timeout_trips`, cooperative deadline check on every host function) - [x] Memory limit enforced via Extism manifest `WASM_MAX_MEMORY_PAGES=1024` - [x] Verify WASM state does not leak between `plugin.call()` invocations (`TestIsolation::test_globals_do_not_leak_between_calls`; fresh `extism.Plugin` per call) - [x] **Owner-authored adversarial test pass (2026-04-23).** 42 tests across two files (`tests/adversarial/test_omcp009_prompt_injection.py` 12 tests, `test_omcp009_modern_pi.py` 30 tests). Full attack chain: payloads planted in live .std via COM, saved to disk, read back. Burp Collaborator OOB verification. See Phase 6 for details.

### Phase 2: Integration — **DONE 2026-04-22**

Wire it in and swap the executor.

- [x] Replace `Executor` usage in `server.py` with `WasmExecutor` - [x] Update `execute_code` tool docstring: "Execute JavaScript code against the OpenSTAAD API"
- [x] Update parameter descriptions
- [x] Delete old sandbox code: `sandbox/ast.py`, `sandbox/executor.py`, `sandbox/module_proxy.py`, `sandbox/const.py`
- [x] Integration test: full round-trip from MCP tool call through WASM sandbox to live STAAD and back (`tests/test_integration.py`; 5/5 passing against a live STAAD.Pro 25.00.01.424 instance)

### Phase 3: Skill scripts and docs — **MOSTLY DONE 2026-04-22**

Phase 3 is independent of Phases 4–6. It can run in parallel with them or be deferred. Agents can execute v2 without it — they will just see Python examples and translate to JS on the fly — but catching them up is cleaner.

- [x] Rewrite the example scripts in `staad_skills/*/scripts/*.py` to `.js`. All 15 scripts converted; old `.py` files deleted.
- [x] Rewrote the 11 `SKILL.md` files where they contained Python snippets (code fences, idioms, example links). Also cleaned `staad-design/assets/DESIGN_CODES.md`.
- [ ] **Outstanding:** update `execute_code` examples in README.md - [ ] **Outstanding:** add a brief note on the security model in the README

### Phase 4: Build and distribution — **PARTIAL**

- [x] Bundle `evaluator.wasm` in PyInstaller spec (added to `datas` in `mcpb/openstaad-mcp.spec`)
- [x] Bundle `extism_sys` shared library in PyInstaller spec (`extism`, `extism_sys` added to `hiddenimports`)
- [x] Update `.mcpb` manifest (version → 2.0.0; `execute_code` description rewritten for JavaScript sandbox; long_description updated)
- [ ] **Outstanding:** test the full `.mcpb` bundle flow on a clean Claude Desktop install (owner to run on clean-Windows box)
- [ ] **Outstanding:** test `uvx` install flow

### Phase 5: Testing and hardening — **PARTIAL**

- [x] Port existing sandbox test suite to test the WASM executor (`tests/sandbox/test_wasm_executor.py`, 23 tests; old AST/executor/module_proxy tests deleted)
- [x] Test COM object lifecycle: sub-objects usable across multiple calls within one script (`TestHandleCache::test_same_sub_object_cached_within_call`)
- [x] Test with real STAAD.Pro instance, not just mocks (`tests/test_integration.py`, 5/5 passing against STAAD.Pro 25.00.01.424 PID 47220; covers `GetNodeCount`, `GetMemberCount`, `GetBaseUnit`, `IsZUp`, console capture, multi-statement scripts)
- [ ] **Outstanding:** performance measurement (latency per COM call; Phase 0 spike measured ~180 µs/call, production re-measure not done)
- [ ] **Outstanding:** stress test (large output, rapid sequential `execute_code` calls)
- [ ] **Outstanding:** live STAAD *write* path (AddNode/AddBeam round-trip against a real model) — all live tests so far are read-only

Security validation (isolation, limits, state reset) is in Phase 1. It must pass before integration.

### Phase 6: Release

**Release gate — all must be true before tagging:**
- All Phase 5 tests green (performance, stress, COM lifecycle) - Phase 1 security validation tests green
- At least one successful end-to-end test with a real STAAD.Pro instance (not mocks)
- OMCP-002 fix shipped in 2.0.0 (standalone PR, independent of sandbox work). `_read_skill` canonicalises with `Path.resolve()` and enforces `candidate.is_relative_to(skills_root.resolve())`. That single containment check handles `..`, absolute paths, Windows backslashes, drive letters, and symlinks pointing outside the tree. Validated by tests that all of these return errors (not file contents): `["../../../etc/passwd"]`, `["/etc/passwd"]`, `["staad-analysis/../../../etc/passwd"]`, `["..\\..\\windows\\win.ini"]`, `["C:/Windows/win.ini"]`, `[""]`, `["staad\x00/../etc"]`. And that these still work: `["staad-analysis"]`, `["staad-design/assets/STEEL_CODES"]`, `["staad-core/assets/FUNCTION_SKILL_MAP.md"]`.
- OMCP-006 fix shipped: HTTP transport auto-generates a bearer token and delivers it via a OneTimeSecret share URL displayed in the terminal auth banner. No escape hatch, no dev flag. If OTS is unreachable, the raw token is shown in the banner.
- `.mcpb` install flow tested end-to-end on a clean Claude Desktop instance (one that does not have the dev environment installed). Owner runs this.

**Breaking changes in 2.0.0** — document in release notes: - `execute_code` accepts JavaScript, not Python.
- HTTP transport bearer token auto-generated and delivered via OTS share URL in terminal banner (no `--email` flag).
- Old `sandbox/ast.py`, `sandbox/executor.py`, `sandbox/module_proxy.py` removed.

**Rollback:** v1.x remains available via `pip install openstaad-mcp<2.0`. No hot rollback path; users pin the old version if 2.0.0 has showstoppers.

**Post-release judgment call:** no formal metrics. Owner decides whether v2 "worked" based on: do agents use it without breaking, do any new sandbox escapes surface, does performance feel acceptable. If the answer is no, we revisit — v1.x is still installable.

- [x] Version bump to 2.0.0 (`pyproject.toml`, `src/openstaad_mcp/__init__.py`, `mcpb/manifest.json`)
- [x] Changelog and release notes (`CHANGELOG.md`)
- [ ] **Outstanding:** tag and publish

### What changed in v2.0.0

A consolidated summary of everything that shipped (or will ship) in the 2.0.0 tag.

#### New

- **WASM sandbox.** `execute_code` now runs AI-generated JavaScript inside a WebAssembly isolate (Extism + QuickJS-ng + Wasmtime). No filesystem, network, or host-memory access from user code. Hardware-enforced memory boundary.
- **Allowlist-gated COM bridge.** Two host functions (`com_get`, `com_invoke`) are the only way out of the sandbox. Root object gated by `ALLOWED_ROOT_METHODS` (26 methods) and `ALLOWED_SUB_OBJECTS` (9 names). Sub-objects gated by `ALLOWED_SUB_OBJECT_METHODS` (deny-by-default, 727 methods across 9 sub-objects, generated 2026-04-26). Global deny list blocks `SetStandardProfileDBFolder`.
- **Per-call isolation.** Fresh WASM plugin per `execute_code` call. No state leaks between calls.
- **Execution limits.** 30s wall-clock timeout, 64 MiB WASM memory, 256 KiB stdout/stderr, 256 KiB max code size.
- **DNS rebinding defence.** `HostHeaderMiddleware` rejects requests with non-allowlisted `Host` headers (HTTP 421, before auth). Default: loopback only. Extend via `--allowed-host`.
- **Mandatory HTTP auth.** Server auto-generates bearer token and delivers via OneTimeSecret share URL in terminal auth banner. No `--email` flag needed. Token never appears on CLI.
- **Bounded COM threads.** `MAX_COM_THREADS=20` semaphore caps concurrent or abandoned COM worker threads. Fail-fast `RuntimeError` at the limit.
- **Error sanitisation.** COM exceptions caught in host functions, replaced with generic messages. No Python tracebacks, file paths, or module names cross the WASM boundary.
- **Adversarial test suite.** 42 owner-authored red-team tests (prompt injection, sandbox escape, Burp Collaborator OOB verification).

#### Changed

- **`execute_code` language: Python → JavaScript.** Clean break, no compatibility shim.
- **All 15 skill scripts rewritten from Python to JavaScript.** 11 SKILL.md files updated.
- **`read_skills` path traversal hardened (OMCP-002).** `Path.resolve()` + `is_relative_to()` containment. Tests cover `../`, absolute, backslash, drive letter, null byte vectors.
- **Skill script paths.** Removed hardcoded `C:\Temp` from `create-new-model.js` and `take-screenshot.js`; replaced with user-prompt placeholders.
- **PyInstaller spec updated.** Bundles `evaluator.wasm`, `extism`/`extism_sys` shared libraries, `fastmcp` metadata.
- **`.mcpb` manifest and version bumped to 2.0.0.**

#### Security findings resolved

| Finding | Was | Now |
|---------|-----|-----|
| OMCP-001: `str.format()` dunder bypass | High — exploitable via `exec()` | **Eliminated.** No Python `exec()`. JS has no dunders. |
| OMCP-002: Path traversal in `read_skills` | High — `../` in skill name leaked files | **Fixed.** `Path.resolve()` + containment check. |
| OMCP-003: COM internal attributes bypass | High — `__class__`, `__mro__` reachable | **Eliminated.** COM objects never enter WASM. |
| OMCP-004: Executor deadlock after timeout | High — threading lock held forever | **Eliminated.** No threading lock. Synchronous WASM execution. |
| OMCP-005: COM API filesystem write / NTLM | Medium — `SetStandardProfileDBFolder` | **Fixed.** Consent gate blocks destructive methods by default (MCP elicitation). UNC paths always rejected. Deny list blocks `SetStandardProfileDBFolder`. |
| OMCP-006: HTTP unauthenticated by default | High — any local process could call tools | **Fixed.** Bearer token auto-generated via OTS share URL in terminal banner, no escape hatch. |
| OMCP-007: Unbounded resource consumption | High — no memory/time/output limits | **Fixed.** WASM memory cap, timeout, stdout cap. |
| OMCP-008: `mro()` type hierarchy leak | High — exposed Python internals | **Eliminated.** No Python type system inside WASM. |
| OMCP-009: Prompt injection via COM output | Medium — COM strings flow to agent | **Accepted risk.** 42 adversarial tests confirm. Agent-layer concern. |
| OMCP-010: Missing DNS-rebinding defence | Medium — Host header not checked | **Fixed.** `HostHeaderMiddleware`, 32 tests. |
| OMCP-011: Stack trace info disclosure | Low — Python tracebacks in errors | **Improved.** `_sanitize_com_error()` strips internals. |
| OMCP-012: Token in process args | Info — `--token` visible in `ps` | **Fixed.** `--token` removed. Bearer token auto-generated in memory and delivered via OTS email. Never on CLI or disk. |

#### Removed

- `sandbox/ast.py` — AST-walking validator for Python `exec()`. - `sandbox/executor.py` — Python `exec()`-based code executor (root cause of OMCP-001, 003, 004, 008).
- `sandbox/module_proxy.py` — Proxy modules injected into `exec()` globals. - `sandbox/const.py` — Old sandbox constants (replaced by `sandbox/constants.py`).
- All 15 Python skill scripts (replaced by JavaScript equivalents). - Old sandbox test suite (replaced by `tests/sandbox/test_wasm_executor.py`, 23 tests).

#### Known issues shipping with v2.0.0

- **QuickJS-NG CVEs.** Five CVEs affect bundled QuickJS-NG ~v0.11.0. Mitigated by WASM isolation. Tracking upstream for extism-js update. See README "Known security issues".
- ~~**Open `getattr()` on COM sub-objects.**~~ **RESOLVED 2026-04-26.** Sub-object handles are now gated by `ALLOWED_SUB_OBJECT_METHODS` (deny-by-default). Must be re-generated on major-version upgrades via `enumerate-com-api.py --generate-allowlist`.

### Outstanding work before 2.0.0 tag

A consolidated list of everything still open, grouped by whether it blocks the release.

#### Release-blocking

1. **Owner-authored adversarial test specs for the sandbox.** — **DONE 2026-04-23.**
   - What: a red-team pass written by the project owner (not the implementing agent), attacking the WASM boundary with malicious-agent scenarios. - Why separate from agent tests: the agent wrote `tests/sandbox/test_wasm_executor.py` to its own threat model, which is the same threat model it used to build the thing it's testing. That's a defensive baseline, not an adversarial audit. Owner specs close that loop. - Scope: minimum coverage — QuickJS CVE-class escapes (prototype pollution, getter/setter abuse, `Proxy` trap confusion); host-function argument abuse (oversized JSON, malformed JSON, non-UTF-8 bytes, nested objects deeper than stack); handle-table confusion (forged handles, handle reuse across calls, integer overflow in handle IDs); timing side channels (deadline bypass via recursive JS with no host calls); allowlist bypass via Unicode normalisation of method names; COM error path forcing untrusted strings back into the error channel. - Deliverable: `tests/adversarial/test_omcp009_prompt_injection.py` (12 tests) and `tests/adversarial/test_omcp009_modern_pi.py` (30 tests). 42 tests total. - **Results:** - **Sandbox containment: confirmed.** 7 outbound exfil vectors tested with Burp Collaborator (`tgdabsg4mkr7ttn6lpst6ettlkrdf33s.oastify.com`), unique subdomain per vector. Zero DNS hits. fetch() and eval+fetch cause WASM traps. XMLHttpRequest, WebSocket, Request are undefined. import() returns a Promise that never resolves. - **Prompt injection vectors: confirmed flowing through.** 19 PI payloads planted in live .std file via COM (load case titles, member unique IDs), saved to disk, read back. All survive the round-trip. Includes OpenAI/Anthropic/Llama delimiters, fake tool output, fake error+fix, fake design code warnings, fake Bentley advisories (sabotage), social engineering, split payloads across multiple load cases. - **STAAD COM Unicode stripping: new finding.** STAAD's IDispatch layer replaces all non-ASCII Unicode with '?' during COM round-trip. Zero-width chars, RTL overrides, and Cyrillic homoglyphs all stripped. Natural defense against Unicode-based PI tricks; the WASM sandbox preserves them but STAAD does not. - **OpenSTAADFile UNC: modal dialogs, not a crash.** Passing a UNC path to `OpenSTAADFile` (allowlisted) causes STAAD.Pro to display a blocking modal error dialog ("cannot be accessed, please check your network"). STAAD does not crash — after the user dismisses the dialog, it continues normally. The original Apr-23 notes reported a crash with `System.ArgumentNullException` in `MappedDriveResolver.ResolveToUNC()` and PII leak via `Exception.log`, but this **did not reproduce** on Apr-26 live MCP testing (3 UNC variants, all returned `null`, no crash, no new crash artifacts). The crash and PII claims are retracted. The actual finding is a UX nuisance: an agent manipulated by PI (OMCP-009) could spam modal dialogs. Filed as OMCP-013 (Low). Cross-refs OMCP-005 (path unvalidated). No DNS hit confirmed (Burp Collaborator). - **Prototype pollution, eval/Function, Proxy abuse, timing side channels:** all tested, all contained or non-exploitable in practice. See test output for details. - Acceptance: all 42 tests pass (30 in modern_pi, 12 in prompt_injection). No WASM escapes. PI risk confirmed as accepted (OMCP-009 residual risk unchanged).

2. **Clean-Windows `.mcpb` install test.**
   - What: build the PyInstaller artifact, package into `.mcpb`, install on a Windows machine that does *not* have the development environment, Python, or Extism installed, and run a full agent round-trip in Claude Desktop. - Why: the Phase 0 spike ran on dev-configured boxes. PyInstaller + native DLL bundling + Extism + Wasmtime has never been smoke-tested on a fresh machine. Most likely failure modes are missing VC++ runtime, `extism_sys` DLL not found at extracted path, or `evaluator.wasm` not on `sys.path` after freezing. - Scope: one clean Windows 11 VM or laptop; `.mcpb` install via Claude Desktop's extension UI; agent round-trip that calls `execute_code` at least once and `read_skills` at least once; verify no error dialogs and no missing-DLL / missing-file errors in logs. - Acceptance: agent round-trip completes without manual intervention. - **Blocks 2.0.0 tag.**

3. **Changelog and release notes** documenting the breaking changes in the "Breaking changes in 2.0.0" section above.
   - **DONE 2026-04-26.** See `CHANGELOG.md` in repo root.

#### Nice-to-have (not blocking)

4. ~~**README updates (Phase 3).**~~ **DONE 2026-04-26.** Security-model note with cross-references to audit findings added. No stale Python examples remain; example workflow section uses natural-language prompts.

5. **`uvx` install smoke (Phase 4).** Confirm `uvx openstaad-mcp --transport stdio` works on a machine with Python but without the dev checkout. Not blocking because the `.mcpb` path is the supported distribution channel; `uvx` is for developers.

6. **Production performance re-measurement (Phase 5).** Phase 0 spike measured ~180 µs/call on a mock STAAD object. Re-measure against the production `WasmExecutor` + live STAAD to confirm the per-call-fresh-`Plugin` pattern did not regress it. Not blocking because single-user workloads are latency-tolerant and Phase 0's margin was >5x.

7. **Stress test (Phase 5).** Rapid sequential `execute_code` calls, large stdout output, large script source. Not blocking because single-user agent workloads do not exercise these patterns; stress tests catch regressions later, not correctness now.

8. **Live STAAD write path (Phase 5).** `AddNode`/`AddBeam` round-trip against a real model. All live tests so far are read-only. Not blocking because COM write calls use the same host-function path as reads.

9. **findings-index.md update.** OMCP-012 status → Fixed. Add OMCP-013 (UNC path modal dialogs).

10. **Test-count references.** **DONE 2026-04-27.** 316 total collected. **308 passed, 6 skipped, 2 xfailed** with STAAD running; without STAAD the integration and some adversarial tests fail (expected). 2 pre-existing float failures in test_integration.py.

11. **Sub-object method allowlist.** **DONE 2026-04-26.** `ALLOWED_SUB_OBJECT_METHODS` added to `constants.py` (deny-by-default, 727 methods across 9 sub-objects). Enforcement added in `wasm_executor.py`. New test for allowlist rejection. See "DONE: Generated sub-object method allowlist" section below.

12. **OMCP-005 consent gate.** **DONE 2026-04-26.** Filesystem-write and session-destructive COM methods gated by `DESTRUCTIVE_METHODS` in `constants.py`. `execute_code` detects destructive method names in submitted code and triggers **MCP elicitation** — a host-mediated confirmation dialog the user must approve. The LLM cannot self-confirm this gate. UNC paths always rejected via `_is_unc_path()`. 15 new tests (`TestConsentGate` 11 + `TestUNCPathBlocking` 4). Adversarial tests updated. Implements Control 4 (Explicit Consent) from security architecture. See [Consent gate design](#consent-gate-design).

13. **Evaluator.js global hardening.** **DONE 2026-04-27.** `Host.getFunctions()` neutered (returns `{}`), `Host.__hostFunctions` emptied, `Host.invokeFunc` wrapped to reject negative memory offsets (CFFI OverflowError DoS prevention), `fetch` removed. 9 unit tests in `TestGlobalHardening` (test_redteam_deep.py). 19 MCP integration tests in `test_mcp_live.py` verify hardening end-to-end via live server.

#### Worth doing but not on the release critical path

8. ~~**Fuel metering or preemptive JS interruption.**~~ **Resolved — already preemptive.** The original concern was that the timeout was purely cooperative (only checked when a host function fires). This turned out to be wrong: `WasmExecutor.execute()` passes `"timeout_ms"` in the Extism plugin manifest, which configures Wasmtime's epoch-based interruption. Wasmtime increments the epoch on a background thread and traps execution mid-instruction when the budget expires — this is preemptive, not cooperative. A `while(true){}` with zero host calls is terminated by the runtime. Confirmed by `test_timeout_trips` (1 s budget, `while (true) {}`, passes). The cooperative `assert_deadline()` in host functions is belt-and-suspenders for the case where a single COM call blocks beyond the deadline — it fires on the next host-function entry. No further work needed.

## Security findings addressed

| Finding | Status after v2 |
|---------|-----------------|
| OMCP-001: str.format() dunder bypass | **Gone.** No Python exec, no Python attribute model. JavaScript has no dunders. |
| OMCP-002: Path traversal in read_skills | **Release-blocking, fixed as separate PR.** Not a sandbox issue — it's an input-validation bug in the `read_skills` MCP tool. `read_skills` itself stays (it's how agents load skill content on demand); only `_read_skill`'s path handling gets hardened. Ships in 2.0.0. See Phase 6 release gate. |
| OMCP-003: COM internal attributes bypass | **Gone.** COM objects never enter the WASM address space. User code only sees JSON results. |
| OMCP-004: Executor deadlock after timeout | **Gone.** No threading lock. WASM execution is synchronous, timeout via Extism `timeout_ms` (Wasmtime epoch-based interruption) plus cooperative `assert_deadline()` in host functions. |
| OMCP-005: COM API filesystem write / NTLM relay | ~~**Accepted risk.**~~ **Fixed 2026-04-26.** Consent gate (`DESTRUCTIVE_METHODS` in `constants.py`) blocks filesystem-write and session-destructive methods by default. `execute_code` triggers MCP elicitation (host-mediated user confirmation) when destructive methods are detected. UNC paths in path-accepting method arguments are always rejected (NTLM relay prevention). Deny list blocks `SetStandardProfileDBFolder`. See [COM API security surface](#com-api-security-surface) and [Consent gate design](#consent-gate-design). |
| OMCP-006: HTTP unauthenticated by default | **Fixed in v2.** HTTP mode auto-generates a bearer token in memory and delivers it via a OneTimeSecret share URL in the terminal auth banner. No `--email` flag needed. Stdio mode is unaffected. |
| OMCP-007: Unbounded resource consumption | **Fixed.** WASM memory limit, QuickJS time limit, stdout size cap. |
| OMCP-008: mro() type hierarchy leak | **Gone.** No MRO in JavaScript. No Python type system inside WASM at all. |
| OMCP-009: Indirect prompt injection via COM output | **Unchanged by design.** COM return values still flow to the AI agent. We considered host-side output sanitisation and rejected it — any useful sanitiser needs semantic understanding of agent-consumed content, which belongs at the application layer (the calling agent's system prompt and tool-use policy), not in an MCP server. The stdout 256 KiB cap does limit output-flooding attacks as a side effect. |
| OMCP-010: Missing DNS-rebinding defence (originally filed as missing Sec-Fetch-Site) | **Fixed in v2.** New [`HostHeaderMiddleware`](../src/openstaad_mcp/http_security.py) runs before bearer-auth and rejects any request whose `Host` header is not in the allowlist with HTTP 421. Default allowlist is loopback only (`127.0.0.1`, `localhost`, `::1`, `[::1]`); operators extend it via the repeatable `--allowed-host` CLI flag for tunnel/reverse-proxy deployments. 32 tests in [`tests/test_http_security.py`](../tests/test_http_security.py). Sec-Fetch-Site itself is still not implemented and stays accepted: with loopback bind, bearer auth, and Host-allowlist already in place, fetch-metadata adds nothing. (Earlier plan revisions claimed the MCP SDK's `TransportSecurityMiddleware` handled Host/Origin — fastmcp 3.2.4 does not actually wire that class in, hence the real middleware.) |
| OMCP-011: Stack trace info disclosure | **Improved.** QuickJS errors do not leak Python internals or file paths. COM errors are wrapped by the host function. |
| OMCP-012: Token in process args | **Fixed in v2.** `--token` removed. Bearer token auto-generated in memory and delivered via OneTimeSecret share URL in terminal auth banner. Token never appears on CLI or disk. |

## COM API security surface

The WASM sandbox eliminates the Python object model attack surface, but user code still calls COM methods via host functions. Each host function call does exactly one `getattr` on a known object via its handle — no chains, no path arrays (see Key Decision #1). The root object is gated by allowlist. The security boundary for OMCP-005 is inside `com_get` / `com_invoke` on the Python side.

We enumerated the full COM API surface from a live STAAD.Pro instance on 2026-04-15 (script: `docs/plan-research-support/enumerate-com-api.py`). The API is pure late-bound IDispatch with no type library, meaning there are no hidden methods beyond what you call by name. The `openstaadpy` wrappers document the complete surface: **727 methods** across root + 9 sub-objects.

### Security-sensitive methods found

These are the methods that perform file I/O, accept arbitrary paths, or have destructive side effects:

#### Root object — file system and process control

| Method | Signature | Risk |
|--------|-----------|------|
| `NewSTAADFile` | `(fileName: str, lengthUnit: int, forceUnit: int)` | **Arbitrary file write.** Creates a new `.std` file at any path the process can write to. |
| `OpenSTAADFile` | `(file: str)` | **Arbitrary file read.** Opens a model from any path. Could probe filesystem structure. |
| `CloseSTAADFile` | `()` | **Disruptive.** Closes the current model. No file path, but destroys the user's working state. |
| `SaveModel` | `(saveSilent: bool = False)` | **Overwrites current file.** No arbitrary path — saves to the already-open `.std` file. |
| `Quit` | `()` | **Kills the STAAD.Pro process.** |
| `GetSTAADFile` | `(bFullPath: bool = True)` | Read-only. Returns current model path. Low risk (info disclosure of a local file path). |
| `GetSTAADFileFolder` | `()` | Read-only. Returns model folder path. Same low risk. |

#### View sub-object — file export

| Method | Signature | Risk |
|--------|-----------|------|
| `ExportView` | `(FileLocation: str, FileName: str, FileFormat: int, Overwrite: bool)` | **Arbitrary file write.** Writes a screenshot image to any path. This is the primary OMCP-005 vector for file writes. |

#### Property sub-object — folder redirection

| Method | Signature | Risk |
|--------|-----------|------|
| `SetStandardProfileDBFolder` | `(folder_name: str)` | **UNC path injection / NTLM relay.** Redirects where STAAD looks for section profile databases. If pointed at `\\attacker\share`, STAAD will attempt SMB auth, leaking the user's NTLM hash. This is the primary OMCP-005 vector for NTLM relay. |
| `GetStandardProfileDBFolder` | `()` | Read-only. Returns current folder. Low risk. |
| `GetDefaultStandardProfileDBFolder` | `()` | Read-only. Returns default folder. Low risk. |

#### Methods that are NOT risks despite keyword matches

These showed up in our scan but are safe after manual review:

- `GetAnalysisStatus(modelPath)` — reads status, does not open or write files - `Table.SaveReport`, `Table.SaveReportAll`, `Table.SaveTable` — save to STAAD's internal report store, not arbitrary file paths
- `View.SaveView(viewName)` — saves a named view configuration inside the model, not to the filesystem
- `View.OpenView(viewName)` — opens a saved view by name, not a file path - `View.CopyPicture()` — copies to clipboard, no file write
- `Load.ComputeWallWindPressureProfile(...)` — pure computation, "Profile" is a wind loading term
- `Property.*Profile*` methods — read/write section profile data within the model, not filesystem paths

### Skill script dependencies on sensitive methods

We audited every skill script and SKILL.md. Several skills depend on methods from the sensitive list:

| Method | Used by | Why it is needed |
|--------|---------|-----------------|
| `SaveModel(True)` | `portal-frame.py`, `run-analysis.py`, `aisc360-design.py`, `create-floor-plates.py`, staad-core SKILL.md | Flushes in-memory geometry to the `.std` file before support/load assignment or analysis. This is a **required workflow step** — without it, geometry added via `AddNode`/`AddBeam` is invisible to the solver and to operations that read from the file. |
| `NewSTAADFile(path, ...)` | `create-new-model.py`, staad-core SKILL.md | Creates a new model. Documented as "only call when user explicitly requests it." Takes an arbitrary path. |
| `OpenSTAADFile(path)` | staad-core SKILL.md (not in any script) | Opens a different model file. Takes an arbitrary path. |
| `CloseSTAADFile()` | staad-core SKILL.md (not in any script) | Closes the current model. Documented as "never call without user explicitly asking." |
| `GetSTAADFile()` | `create-new-model.py` | Read-only, returns current model path. |
| `Quit()` | staad-core SKILL.md (not in any script) | Documented as "use with caution." |
| `ExportView(location, name, ...)` | `take-screenshot.py`, staad-view SKILL.md | Writes a screenshot to disk. Takes an arbitrary file path. |
| `SetStandardProfileDBFolder` | **Not used in any skill.** | Not needed. Can be blocked outright. |

### Design requirements for `com_get` / `com_invoke`

These are not bugs to fix — the code hasn't been written yet. They are requirements the implementation must satisfy from the start.

1. **Handle-based dispatch with single `getattr`.** Each host function call resolves exactly one attribute on a known object via its handle. No path arrays, no loops, no chains. The handle table design (section 3 above) and the allowlist pseudocode (section 1 above) together eliminate arbitrary traversal by construction.

2. **Root object gating.** Handle 0 (root) only allows the 9 sub-object names via `com_get` and the explicit `ALLOWED_ROOT_METHODS` set via `com_invoke`. Everything else is rejected before `getattr` runs.

3. **Deny list.** `SetStandardProfileDBFolder` is blocked on any handle (unused, pure NTLM relay vector). The deny list is checked before `getattr` on every call.

4. **Error sanitization.** Both `com_get` and `com_invoke` must catch all Python exceptions and return a generic error message (e.g. `"COM error: Geometry.AddNode failed"`) to the WASM side. Log the full traceback server-side at DEBUG level. Never return Python tracebacks, file paths, or module names across the host function boundary.

5. **WASM state isolation.** WASM linear memory must be reset between `plugin.call()` invocations. One `execute_code` call must not see state from a previous call. Validated in Phase 0 as a go/no-go gate.

### ~~Accepted risks~~ Consent-gated operations (OMCP-005 — Fixed 2026-04-26)

The following COM API behaviors previously required manual agent discipline. As of 2026-04-26, they are gated by `DESTRUCTIVE_METHODS` in `constants.py`
and enforced by MCP elicitation in `execute_code`. When destructive method names are detected in submitted code, the server triggers a host-mediated confirmation dialog that the user must approve — the LLM cannot self-confirm.
UNC paths in path-accepting arguments are always rejected (NTLM relay prevention).

<a id="consent-gate-design"></a>

**Consent gate design (Control 4 — Explicit Consent):** - `DESTRUCTIVE_METHODS` classifies filesystem-write and session-destructive methods by object name.
- `PATH_ARGUMENT_INDICES` maps path-accepting methods to their argument positions for UNC validation.
- `com_invoke` checks both before dispatching to COM: destructive methods require `allow_destructive=True` on the executor call; UNC paths are always rejected.
- `execute_code` pre-flight scans the submitted JS code for destructive method names (`ALL_DESTRUCTIVE_METHOD_NAMES`). If any are found, it triggers **MCP elicitation** via `Context.elicit()` — a host-mediated dialog the human must approve. Only after explicit human approval does the sandbox receive `allow_destructive=True`.
- This is LLM-proof: the old `confirm_destructive_operations` parameter (which the LLM could self-set) has been removed. Elicitation is a protocol-level exchange between the MCP server and the host application (Claude Desktop, VS Code), presented directly to the user. The LLM has no opportunity to intercept or auto-confirm it.
- If the MCP host does not support elicitation, destructive operations fail with an explicit error explaining that user approval is required but unavailable.

**Methods gated by `DESTRUCTIVE_METHODS`:**

| Object | Method | Risk | Gated |
|--------|--------|------|-------|
| Root | `NewSTAADFile` | Creates `.std` file at arbitrary path | Yes |
| Root | `OpenSTAADFile` | Opens file (+ UNC path validation) | Yes |
| Root | `CloseSTAADFile` | Closes model (data-loss risk) | Yes |
| Root | `SaveModel` | Writes current model to disk | Yes |
| Root | `Quit` | Terminates STAAD.Pro | Yes |
| View | `ExportView` | Writes image file to arbitrary path | Yes |
| Table | `SaveReport` | Writes report file | Yes |
| Table | `SaveReportAll` | Writes all report files | Yes |
| Table | `SaveTable` | Writes table file | Yes |

**UNC path validation (always enforced, even after user approval):**

| Object | Method | Validated arg index |
|--------|--------|-------------------|
| Root | `NewSTAADFile` | 0 (path) |
| Root | `OpenSTAADFile` | 0 (path) |
| View | `ExportView` | 0 (fileLocation) |

**Residual accepted risks:**

1. **With user approval, file writes are permitted.** `ExportView` writes image files and `NewSTAADFile` creates `.std` files at user-specified paths. The elicitation gate makes this an explicit user decision, not an agent-autonomous action.

2. **`SaveModel` overwrites the current file.** Multiple skill scripts depend on it as a required workflow step. With the consent gate, it only executes when the user has approved via the host dialog.

3. **Model-mutation methods are not gated.** `AddNode`, `AddBeam`, property assignments, etc. modify the in-memory STAAD model. This is the expected use of the tool and does not write to the filesystem. An unwanted mutation can be undone by not saving.

## Risks and things I am not sure about yet

1. **Extism + PyInstaller bundling.** Extism has first-class Windows support (`x86_64-pc-windows-msvc` is a named release target, 15 Host SDKs, 11 PDKs, active Dylibso team behind it). The Python SDK installs cleanly via `pip` (confirmed Phase 0). Wasmtime ships as a standard native wheel via `extism-sys`. PyInstaller bundling is expected to work without special handling. If the Phase 4 `.mcpb` build reveals DLL bundling issues, the fix is a spec-file tweak, not an architectural problem.

2. **COM object handle lifecycle.** ~~Solved, no longer a risk.~~ After reviewing every skill script, the COM object graph is flat. There are exactly 9 sub-objects (`Geometry`, `Property`, `Support`, `Load`, `Command`, `Output`, `Design`, `Table`, `View`), all accessed directly from the root `staad` object. None of their methods return further dispatch objects. They only return primitives, tuples, and integer IDs. The handle table design falls out naturally from this:

   - Handle 0 is always the root `staad` object.
   - Sub-object handles (1-9) are created lazily: the first time user code accesses `staad.Geometry`, the host function calls `getattr(staad, "Geometry")`, stores the result in the handle table as handle 1, and returns 1 to the JS Proxy. Subsequent accesses to `staad.Geometry` return the cached handle 1 without another COM call. - No method call ever returns a dispatch object, so the table never grows beyond 10 entries (root + 9 sub-objects). - The handle table is a plain `dict[int, Any]` created fresh inside each `connect_and_run` call. When execution finishes, the dict goes out of scope, Python releases the COM references, and `pythoncom.CoUninitialize()` cleans up the STA apartment. No explicit cleanup code needed. No leak possible. - **No numeric cap on the handle table.** We considered a cap (20 entries) as a safety belt, but it is redundant. The only code path that creates a handle is `com_get` on handle 0 with a `prop` in `ALLOWED_SUB_OBJECTS` — a set of exactly 9 names. The allowlist already makes it impossible to create more than 10 entries (root + 9). A numeric cap would only fire if the allowlist logic had a bug, and if the allowlist logic has a bug the cap is not the right fix. Correctness comes from the allowlist, not from counting.

3. **Array return values.** ~~Solved, no longer a risk.~~ After cataloging every COM method return type across all skill scripts and SKILL.md files, there are zero SAFEARRAYs, VT_EMPTY, or VT_NULL values anywhere. The COM layer is fully wrapped by the Python API — every return is a stdlib Python type (`int`, `float`, `str`, `bool`, `None`, `tuple`, `list`). All of these map directly to JSON. The most complex return is `GetMemberSteelDesignResults`: a 10-element mixed tuple `(str, str, float, float, int, float, str, str, [float,float,float], float)`, which is just a JSON array with mixed element types. JavaScript handles that natively.

4. **QuickJS-ng language level.** ~~Not a risk.~~ QuickJS-ng targets the latest ECMAScript living standard, not ES2020 as originally assumed. The project runs the full test262 conformance suite on every change and has added modern features including Iterator Helpers, `Promise.try`, `Error.isError`, Set operations, `Float16Array`, `WeakRef`, and `FinalizationRegistry`. Our scripts are simple COM call sequences so we would have been fine either way, but this means AI agents can generate modern JS without hitting unexpected syntax errors.

5. **WASM module loading time.** Loading a 1-2MB WASM module via Wasmtime should be fast (<50ms). We load once at server startup and reuse across calls, so this is only ever a cold-start cost. Worth measuring in Phase 0, but not a real concern.

6. **Numeric fidelity (JS vs Python).** Not a risk. STAAD does a lot of math, but almost none of it runs in the sandbox — the solver is a native Fortran/C++ engine inside STAAD.Pro. The sandbox just orchestrates COM calls and does light pre/post arithmetic (bay spacings, load sums, unit conversions). Both languages use IEEE 754 double-precision floats for all non-integer math, so results are bit-identical. The only meaningful difference is that Python `int` is arbitrary precision while JS numbers top out at 2^53 ≈ 9×10^15 — well above anything a STAAD model produces (node IDs, beam IDs, load case numbers are all under a million; coordinates and forces are floats anyway). JSON serialization across the host boundary is also lossless for doubles. The infamous "JS type coercion" quirks (`[] + {}`, `"5" - 1`) are about operator behaviour on mixed types, not numeric precision, and do not apply to code that passes numbers into COM calls. Phase 5's real-STAAD tests will assert that a known model produces the same analysis results as v1 as a belt-and-suspenders check.


## Post-v2.0.0 security TODOs

### ~~TODO: Bearer token rotation via onetimesecret.com~~ — DONE

Implemented in v2.0.0. `--token` removed; server auto-generates a bearer token in memory at startup and delivers it via a OneTimeSecret share URL displayed in the terminal auth banner. If OTS is unreachable, the raw token is shown in the banner. Token never appears on CLI or disk. See [`ots_delivery.py`](../src/openstaad_mcp/ots_delivery.py) and [`http-auth-ots-design.md`](http-auth-ots-design.md).

**Tracking:** OMCP-012 — **Fixed in v2.0.0.**

### TODO: WASM binary integrity verification

The `evaluator.wasm` binary is pre-built by `build.ps1` and shipped with the release artifact. There is currently no mechanism to verify that the shipped binary matches a reproducible build. Planned improvement: add a CI step that rebuilds `evaluator.wasm` from source using pinned tool versions (extism-js v1.6.0, binaryen v129), computes a SHA-256 hash, and embeds it in the release metadata. The server should verify the hash at startup and refuse to load a tampered binary.

### TODO: Code signing for release artifacts

The PyInstaller-built `.exe` and the `.mcpb` bundle should be code-signed with a Bentley code signing certificate. Without signing, Windows Defender SmartScreen will flag the binary on first run, and users have no way to verify provenance. Ensure `codesign_identity` is set in the PyInstaller spec and that CI has access to the signing key.

### DONE: Generated sub-object method allowlist (2026-04-26)

Sub-object handles (Geometry, Property, Support, Load, Command, Output, Design, Table, View) are now gated by a per-sub-object method allowlist in `constants.py` (`ALLOWED_SUB_OBJECT_METHODS`). This flips the posture from deny-list to **deny-by-default** — any method not explicitly listed is rejected before `getattr` fires. Full enforcement is shown in the `com_invoke` pseudocode in Key Decision #1 (Gate 4).

The allowlist was generated by enumerating all methods from the `openstaadpy` wrapper classes (same 727-method surface audited 2026-04-15). `SetStandardProfileDBFolder` is intentionally excluded from the Property allowlist (also remains in `DENIED_METHODS` as a belt-and-suspenders measure).

**Upgrade workflow:** (1) install new STAAD.Pro, (2) run `enumerate-com-api.py --generate-allowlist`, (3) diff against the current allowlist for new/removed methods, (4) reviewer eyeballs additions for file/network/process keywords, (5) merge the updated allowlist.

### TODO: QuickJS-NG CVE tracking

extism-js v1.6.0 uses rquickjs 0.11, which bundles QuickJS-NG ~v0.11.0 (Oct 2025). Several CVEs affect this version range:

- CVE-2026-0821, CVE-2026-0822, CVE-2026-1144, CVE-2026-1145: heap overflow / OOB, affect ≤0.11.0
- CVE-2026-3979: UAF, affects ≤0.12.1

**Mitigating factor:** QuickJS-NG runs inside the WASM sandbox (Wasmtime). Memory corruption in the JS engine affects only WASM linear memory and cannot escape the isolate. Host functions validate all inputs via JSON parsing and handle-table lookups, so corrupted WASM state cannot forge valid COM calls. The practical exploit chain is: trigger QJS memory corruption → gain arbitrary read/write within WASM linear memory → craft a valid JSON payload that passes host-function validation → invoke a dangerous COM method. The last step is already gated by the root allowlist and deny list.

**Action:** QuickJS-NG v0.13.0 (Mar 2026) and v0.14.0 (Apr 2026) fix all known CVEs. Monitor the extism/js-pdk repo for a release that updates rquickjs past 0.11. When available, update `build.ps1` to the new extism-js version and rebuild `evaluator.wasm`. No upstream release exists yet — v1.6.0 (Feb 2026) is the latest.

## Security architecture control mapping

How openstaad-mcp maps to the [Bentley MCP Security Architecture](plan-research-support/security-architecture.md) controls:

| Control | Applicability | Implementation |
|---------|--------------|----------------|
| **Control 1: User-Context Authorization** | N/A | Local single-user desktop tool — no backend API, no OAuth token propagation, no multi-tenant authorization. The user running STAAD.Pro _is_ the security context. |
| **Control 2: Curated Tool Environment** | Partial | Single first-party server; no Discovery Service, no third-party MCP servers. Tool trust via code-signed PyInstaller `.mcpb` artifact. |
| **Control 3: Two-Layer Sandboxing** | **Full (execute_code)** | Layer 1 (infrastructure): WASM isolate (Extism + QuickJS-ng + Wasmtime) constrains LLM-generated code to linear memory — no FS, no network, no OS access. Layer 2 (capability): COM allowlists on the Python host side limit the API surface to audited methods only (deny-by-default). Read-only tools run at process isolation only. |
| **Control 4: Explicit Consent** | **Server-side full** | Pre-flight scan detects destructive method names in submitted code before WASM execution. Triggers MCP elicitation (`Context.elicit()`) — a host-mediated confirmation dialog the user must approve. The LLM cannot self-confirm this gate. Runtime sandbox provides fallback enforcement. If the MCP host does not support elicitation, destructive operations fail with an explicit error. |
| **Control 5: Runtime Monitoring** | Partial | Behavioral baselines defined in [TCMs](tool-capability-manifests.md). No external runtime monitor deployed; logging to Python `logging` module. COM thread semaphore provides fail-fast resource bounding. |
| **Control 6: AI/LLM Gateway** | N/A | Local desktop tool; no central gateway. |
| **Control 7: LLM Input Parameterization & Filtering** | Partial | User code is isolated in WASM (data cannot become instructions on the host). COM output flows unsanitized to agent (accepted risk — see [Prompt Injection Risk Commentary](prompt-injection-risk.md)). |
| **Control 8: MCP Server Proxying** | N/A | First-party server only. |

### Traceability to § 10: "Code Mode" isolation requirements

openstaad-mcp is a **User "Code Mode"** implementation per [Security Architecture § 10](plan-research-support/security-architecture.md#10-isolation-requirements-for-code-mode).
The four baseline requirements and their enforcement:

| § 10 Requirement | Status | Enforcement |
|------------------|--------|-------------|
| **(1) No external network access** | **Met** | WASM isolate has zero network capability — no `fetch`, `XMLHttpRequest`, `WebSocket`, `import()`. HTTP transport binds to `127.0.0.1` only; `HostHeaderMiddleware` rejects non-loopback `Host` headers. |
| **(2) No arbitrary OS access** | **Met** | LLM-generated code runs inside Wasmtime linear memory. No `process`, `child_process`, `os`, or syscall access. Only transitive OS access is via COM host functions gated by allowlists. |
| **(3) No arbitrary filesystem access** | **Met** | `fileSystemAccess: "none"` in WASM sandbox. Filesystem writes occur only through COM methods in `DESTRUCTIVE_METHODS`, gated behind MCP elicitation (Control 4). UNC paths are always rejected. |
| **(4) Controlled API access** | **Met** | COM surface is deny-by-default: `ALLOWED_ROOT_METHODS` (23), `ALLOWED_SUB_OBJECTS` (9), `ALLOWED_SUB_OBJECT_METHODS` (695). Destructive methods require progressive user consent via elicitation. `DENIED_METHODS` blocks known-dangerous methods unconditionally. |

## What we are NOT doing

- Not rewriting the MCP server. Python + FastMCP stays. - Not replacing pywin32 or openstaadpy. The COM bridge stays Python.
- Not adding new MCP tools or changing the MCP protocol (with the exception of `read_analysis_output`, a read-only tool added post-sandbox-rewrite to surface concrete/timber/aluminum design results that are inaccessible via COM).
- Not supporting both Python and JS user code at the same time. Clean break. - Not building our own sandbox from scratch. Extism and WASM do the isolation.
- Not providing deprecation periods, migration shims, or `--allow-insecure` escape hatches. We have no real users yet. 2.0.0 makes the breaks it needs to make, documents them in the release notes, and moves on. This is the cheapest time to do this; it gets more expensive every month.
