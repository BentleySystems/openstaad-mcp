// evaluator.d.ts — host interface for the WASM sandbox.
// Compiled by extism-js into evaluator.wasm.

declare module 'main' {
  export function execute(): I32;
}

declare module 'extism:host' {
  interface user {
    com_get(ptr: I64): I64;
    com_invoke(ptr: I64): I64;
    console_output(ptr: I64): I64;
  }
}
