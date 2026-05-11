1. We ship a prebuilt WASM binary. QuickJS (JS engine) is baked inside it.
2. Agent sends JS code.
3. We load the WASM binary, feed it the code, it runs.
4. Inside WASM, `staad` is a fake object. When code calls `staad.Geometry.AddNode(0,0,0)`, the fake intercepts it, packages it as JSON (`{"method": "AddNode", "args": [0,0,0]}`), and hands it to Python.
5. Python receives that JSON, calls the real COM method on STAAD.Pro via openstaadpy, gets the result, sends it back as JSON.
6. The JS code receives the return value and continues. Steps 4-6 repeat for every COM call in the code.
7. When the JS code finishes (hits `return`), the return value is serialized to JSON, read out of WASM memory by Python, and sent to the agent as the tool response.

