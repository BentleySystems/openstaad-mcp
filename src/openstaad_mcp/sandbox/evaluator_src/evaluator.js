// evaluator.js — production WASM sandbox for openstaad-mcp v2.
//
// Compiled to evaluator.wasm by extism-js. Runs inside a WebAssembly
// linear-memory isolate with no filesystem, network, or host globals.
// The only I/O is via three host functions provided by the Python host:
//
//   com_get({handle, prop})        -> {handle} | {error}
//   com_invoke({handle, method, args})  -> {result} | {error}
//   console_output({stream, text}) -> void
//
// User code runs inside strict mode with only `staad` and `console`
// injected as arguments. All other globals (fetch, WebAssembly, Deno,
// etc.) are either absent or trap at the WASM boundary.

const { com_get, com_invoke, console_output } = Host.getFunctions();

// ---------- Host-call helpers ----------

function hostCall(fn, payload) {
  const mem = Memory.fromString(JSON.stringify(payload));
  const offset = fn(mem.offset);
  const resp = Memory.find(offset).readString();
  return JSON.parse(resp);
}

function hostVoid(fn, payload) {
  const mem = Memory.fromString(JSON.stringify(payload));
  fn(mem.offset);
}

// ---------- console routing ----------

function formatArg(a) {
  if (a === null) return 'null';
  if (a === undefined) return 'undefined';
  if (typeof a === 'string') return a;
  if (typeof a === 'number' || typeof a === 'boolean') return String(a);
  try { return JSON.stringify(a); } catch (_e) { return String(a); }
}

function makeLogger(stream) {
  return function (...args) {
    const text = args.map(formatArg).join(' ');
    hostVoid(console_output, { stream: stream, text: text });
  };
}

const sandboxConsole = {
  log: makeLogger('stdout'),
  info: makeLogger('stdout'),
  debug: makeLogger('stdout'),
  warn: makeLogger('stderr'),
  error: makeLogger('stderr'),
};

// ---------- staad Proxy factory ----------
//
// Each handle (0 = root, 1..N = sub-objects) gets its own Proxy. Property
// access on handle 0 triggers a com_get host call to resolve a sub-object;
// if that fails, the property is treated as a method name and a callable
// wrapper is returned that hits com_invoke. On sub-object handles, every
// property access returns a method wrapper directly.

function makeProxyForHandle(handle) {
  function makeMethod(method) {
    return function (...args) {
      const resp = hostCall(com_invoke, {
        handle: handle,
        method: method,
        args: args,
      });
      if (resp && resp.error) throw new Error(resp.error);
      return resp ? resp.result : undefined;
    };
  }

  return new Proxy({}, {
    get(_target, prop, _receiver) {
      if (typeof prop !== 'string') return undefined;
      // Avoid accidental thenable adoption if a caller does `await staad`.
      if (prop === 'then') return undefined;

      if (handle === 0) {
        const resp = hostCall(com_get, { handle: 0, prop: prop });
        if (resp && resp.handle !== undefined) return makeProxyForHandle(resp.handle);
        // com_get rejects anything that isn't a known sub-object. For any
        // other property on root we interpret it as a root method call.
        return makeMethod(prop);
      }
      return makeMethod(prop);
    },
    set(_target, _prop, _value) {
      // Silently drop writes. Prevents confusing "staad.Foo = 42" silent
      // success in local state that never reaches the host.
      return false;
    },
    has(_target, _prop) {
      return true;
    },
  });
}

// ---------- global hardening ----------
//
// User code runs in the same global scope (via new Function). Without
// cleanup the user can reach Host.getFunctions() and call host functions
// with raw (possibly negative) memory offsets, triggering a CFFI
// OverflowError in the Python SDK that surfaces as a blocking Windows
// error dialog (DoS).
//
// The attack chain requires Host.getFunctions() → raw function ref →
// fn(negativeOffset). We break this chain by neutering getFunctions
// and __hostFunctions inside execute(), before user code runs. Memory,
// hostCall, and the Proxy machinery must stay intact because the staad
// Proxy uses them on every COM call.

// Register the Extism export.
module.exports = { execute };

// ---------- entry point ----------

function execute() {
  const code = Host.inputString();

  // ── Neuter the attack vector ──
  // Host.getFunctions() returns raw host-function references (com_get,
  // com_invoke, console_output).  With a raw ref, user code can call
  // fn(-1) and trigger a CFFI OverflowError in the Python SDK (DoS).
  //
  // We gut getFunctions and __hostFunctions so user code cannot obtain
  // those refs.  Host.invokeFunc is wrapped to reject negative offsets
  // (which would crash the CFFI unsigned-int conversion).
  try { Host.getFunctions = function() { return {}; }; } catch(_e) {}
  try { Host.__hostFunctions = []; } catch(_e) {}

  // Wrap Host.invokeFunc to reject negative memory offsets.
  // The original is saved so the captured closures (com_get, com_invoke,
  // console_output) still work with valid offsets from Memory.fromString.
  try {
    const _origInvokeFunc = Host.invokeFunc;
    Host.invokeFunc = function(name, offset) {
      if (typeof offset === 'number' && offset < 0) {
        throw new Error('invalid memory offset');
      }
      return _origInvokeFunc.call(Host, name, offset);
    };
  } catch(_e) {}

  // Neuter fetch (Extism polyfill — traps the WASM when called, but
  // cleaner to remove so user code gets a clear error).
  try { globalThis.fetch = undefined; } catch(_e) {}

  const staad = makeProxyForHandle(0);

  // Compilation strategy:
  //   1. Try as a single expression  -> auto-return its value.
  //   2. Fall back to statement body -> user must use `return <value>`
  //      explicitly if they want a result. Bare expression statements
  //      in a multi-statement body are not implicitly returned.
  let fn;
  try {
    fn = new Function('staad', 'console', `"use strict";\nreturn (${code});`);
  } catch (_e) {
    fn = new Function('staad', 'console', `"use strict";\n${code}`);
  }

  let output;
  try {
    const value = fn(staad, sandboxConsole);
    output = { ok: true, result: value === undefined ? null : value };
  } catch (e) {
    const msg = (e && e.message) ? String(e.message) : String(e);
    output = { ok: false, error: msg };
  }

  // Serialize. If the result isn't JSON-representable (e.g. a function or a
  // cyclic object), fall back to a string form so we never trap at output.
  let text;
  try {
    text = JSON.stringify(output);
  } catch (_e) {
    text = JSON.stringify({ ok: true, result: String(output.result) });
  }
  Host.outputString(text);
  return 0;
}

// NOTE: module.exports is registered in the global hardening section above.
