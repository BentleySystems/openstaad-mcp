At build time, we compile QuickJS-ng (a small JS engine) plus our evaluator code (the "shell" that the user's code runs inside.) into a standalone WASM binary. That binary ships with the package and never changes at runtime.

When the agent sends code, we spin up a fresh instance of that WASM module. The code runs inside it. WebAssembly gives us hardware-enforced memory isolation: no filesystem, no network, no host memory access. The only way out is three host functions we expose: resolve a sub-object, call a method, or write to console.

Every method call passes through seven validation gates on the Python side before it touches the real COM object. Allowlists, deny lists, consent dialogs for destructive operations. 

Once all gates pass, Python does the actual COM IDispatch call into STAAD.Pro, gets the result back, serializes it to JSON, and hands it back into the WASM module. The COM dispatch itself is unchanged, same in-process IDispatch on the same thread.

Fresh sandbox per call. No state leaks. 60ms end-to-end