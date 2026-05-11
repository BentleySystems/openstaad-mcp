# Execution Flow: Simple Beam Creation (no file I/O)

**Purpose:** Show what happens when the user asks the agent to do something simple like "add a beam from (0,0,0) to (10,0,0) with a W12X26 section." No files involved, just a single `execute_code` tool call.

## Scenario

User says: "Add a beam from the origin to (10,0,0) and assign it a W12X26 section."

The agent makes one tool call: `execute_code`.

---

## What the agent sends (JSON over MCP protocol)

```json
{
  "tool": "execute_code",
  "arguments": {
    "code": "const n1 = staad.Geometry.AddNode(0, 0, 0);\nconst n2 = staad.Geometry.AddNode(10, 0, 0);\nconst beam = staad.Geometry.AddBeam(n1, n2);\nstaad.Property.AssignBeamProperty(beam, 'W12X26');\nreturn `Beam ${beam} created (nodes ${n1}-${n2}), section W12X26`;"
  }
}
```

---

## Python server (MCP handler)

```python
# ---- PYTHON SERVER PROCESS (openstaad-mcp) ----

def handle_execute_code(code, instance=None):

    # 1. Pre-flight checks
    #    - Code size check: len(code.encode()) <= 256 KiB
    #    - Destructive method scan: looks for method names in the code string
    #      that are flagged as destructive (e.g. "PerformAnalysis", "DeleteNode")
    #    - If destructive methods found: triggers elicitation (user approval)
    #    - In this case: AddNode, AddBeam, AssignBeamProperty are state-changing
    #      but not flagged as "destructive" in the high-risk sense.
    #      The tool itself is already destructiveHint=true, so host confirms.

    # 2. Resolve target instance
    target = registry.resolve_instance(instance)  # finds running STAAD.Pro

    # 3. Execute in WASM sandbox
    result = wasm_executor.execute(
        code=code,
        input_data=None,       # no __input for plain execute_code
        instance=target,
    )

    # 4. Return result to agent
    return {
        "success": True,
        "result": result.return_value,  # "Beam 1 created (nodes 1-2), section W12X26"
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration_seconds": result.elapsed,
    }
```

---

## WASM sandbox (QuickJS inside WebAssembly)

```javascript
// ---- INSIDE WASM ISOLATE ----
// No __input here (this is plain execute_code)
// The staad object is a Proxy that intercepts all property access and method calls

const n1 = staad.Geometry.AddNode(0, 0, 0);       // → host function → Python → COM
const n2 = staad.Geometry.AddNode(10, 0, 0);       // → host function → Python → COM
const beam = staad.Geometry.AddBeam(n1, n2);        // → host function → Python → COM
staad.Property.AssignBeamProperty(beam, "W12X26");  // → host function → Python → COM

return `Beam ${beam} created (nodes ${n1}-${n2}), section W12X26`;
```

---

## The COM boundary in detail

Every time JS code accesses `staad.Something.Method(args)`, the Proxy intercepts it. Here is the exact sequence for `staad.Geometry.AddNode(0, 0, 0)`:

### Step 1: JS Proxy intercepts property access

```javascript
// Inside evaluator.js (already loaded in WASM before user code runs)
// staad is a Proxy for handle 0 (root COM object)

staad.Geometry
// Proxy "get" trap fires for property "Geometry"
// → calls hostCall("com_get", {handle: 0, property: "Geometry"})
// → Python looks up handle 0, accesses .Geometry attribute
// → .Geometry is a COM sub-object, Python assigns it handle 1
// → returns JSON: {"handle": 1}
// → JS creates a new Proxy for handle 1
```

### Step 2: JS Proxy intercepts method call

```javascript
staad.Geometry.AddNode(0, 0, 0)
// Proxy "get" trap fires for property "AddNode" on handle 1
// → returns a callable function that, when invoked, does:
//   hostCall("com_call", {handle: 1, method: "AddNode", args: [0, 0, 0]})
```

### Step 3: Host function crosses WASM boundary

```
WASM → Extism host function "hostCall"
  → Reads JSON from WASM linear memory: {"handle": 1, "method": "AddNode", "args": [0, 0, 0]}
  → Python handler receives this
```

### Step 4: Python dispatches to COM via openstaadpy

```python
# In Python (wasm_executor.py host function handler):

def handle_com_call(handle, method, args):
    obj = handle_table[handle]          # handle 1 = staad_com.Geometry
    # Allowlist check: is "AddNode" permitted?
    check_allowlist("Geometry", "AddNode")  # passes
    # Call the real COM method via openstaadpy
    result = getattr(obj, method)(*args)    # staad_com.Geometry.AddNode(0, 0, 0)
    return {"value": result}                # {"value": 1}
```

### Step 5: openstaadpy dispatches to STAAD.Pro

```python
# Inside openstaadpy (os_analytical module):
# obj.Geometry is a win32com.client.Dispatch wrapper
# .AddNode(0, 0, 0) is a standard COM IPC call

# Win32 COM marshalling:
#   Python process → Windows COM runtime → STAAD.Pro process
#   STAAD.Pro creates node at coordinates (0, 0, 0)
#   STAAD.Pro returns node number (integer 1)
#   Windows COM runtime → Python process
#   win32com converts to Python int: 1
```

### Step 6: Result flows back to WASM

```
Python: returns {"value": 1} as JSON string
  → writes JSON to WASM linear memory via Extism
  → WASM host function returns
  → JS reads JSON from memory
  → Proxy callable returns: 1
  → const n1 = 1
```

### Full sequence repeated for all four calls:

```
staad.Geometry.AddNode(0, 0, 0)
  WASM → Python → openstaadpy → COM → STAAD.Pro → returns 1 → Python → WASM
  n1 = 1

staad.Geometry.AddNode(10, 0, 0)
  WASM → Python → openstaadpy → COM → STAAD.Pro → returns 2 → Python → WASM
  n2 = 2

staad.Geometry.AddBeam(1, 2)
  WASM → Python → openstaadpy → COM → STAAD.Pro → returns 1 → Python → WASM
  beam = 1

staad.Property.AssignBeamProperty(1, "W12X26")
  WASM → Python → openstaadpy → COM → STAAD.Pro → void → Python → WASM
```

Total: 4 COM round-trips. Each is a cross-process IPC call (Python process ↔ STAAD.Pro process via Windows COM). Typical latency: <1ms per call for simple operations.

---

## What the agent gets back

```json
{
  "success": true,
  "result": "Beam 1 created (nodes 1-2), section W12X26",
  "stdout": "",
  "stderr": "",
  "duration_seconds": 0.12
}
```

---

## Where data lives

```
Agent context:       code string (~200 B) + response (~150 B)
                     Total: ~350 B in context window

Python server:       routes host function calls, checks allowlists
                     holds COM object handle table (10 entries max)
                     stateless between tool calls

WASM sandbox:        JS variables (n1, n2, beam) live in QuickJS heap
                     inside WASM linear memory (128 MiB allocation)
                     destroyed after execution completes

COM (openstaadpy):   os_analytical.connect() holds dispatch object
                     each method call is Windows COM IPC to STAAD.Pro

STAAD.Pro process:   model state modified (2 nodes + 1 beam + property)
                     persists until user saves or closes
```

---

## The COM layer: openstaadpy

The MCP server uses `openstaadpy` as the COM bridge:

```python
from openstaadpy import os_analytical
staad = os_analytical.connect(r"D:\project\example.std")
```

This connects to the running STAAD.Pro instance that has that file open. The returned object is a COM dispatch wrapper. Method calls on it (`staad.Geometry.AddNode(...)`) are standard Windows COM inter-process communication.

openstaadpy is the same library users install with `pip install openstaadpy` for their own automation scripts. The COM API is identical regardless of whether it's called from a standalone Python script or from inside our MCP server's host function handler. The MCP architecture just adds the WASM isolation layer and allowlist checks in between.

---

## "Show me the code for that" (standalone Python script)

User says: "Give me the Python for what you just did."

The agent translates its JS code into a standalone script using the same library (openstaadpy) that the MCP server uses internally:

```python
"""
Standalone script: add a beam from origin to (10,0,0) with W12X26 section.

Requirements: pip install openstaadpy
Prerequisite: STAAD.Pro must be running with your model open.
"""
from openstaadpy import os_analytical

# Connect to running STAAD instance
staad = os_analytical.connect(r"D:\project\example.std")

# Create nodes and beam
n1 = staad.Geometry.AddNode(0, 0, 0)
n2 = staad.Geometry.AddNode(10, 0, 0)
beam = staad.Geometry.AddBeam(n1, n2)

# Assign section
staad.Property.AssignBeamProperty(beam, "W12X26")

print(f"Beam {beam} created (nodes {n1}-{n2}), section W12X26")
```

The COM calls are byte-for-byte identical to what the sandbox executed. The differences:

| Aspect | MCP sandbox | Standalone script |
|--------|-------------|-------------------|
| Language | JavaScript (QuickJS in WASM) | Python |
| COM bridge | Proxy → host function → openstaadpy | openstaadpy directly |
| Isolation | WASM memory boundary + allowlist | None (full COM access) |
| Approval gate | Host confirms via destructiveHint | None (user runs it themselves) |
| File path | Implicit (server knows which model) | Explicit in `connect()` call |

The user can save this script, tweak it (change coordinates, section, add more beams), and run it directly with `python add_beam.py` whenever they want. No MCP server needed.
