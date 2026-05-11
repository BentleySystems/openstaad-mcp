# Execution Flow: File I/O (read_and_execute + execute_and_write)

**Purpose:** Show exactly what happens, where data lives, and which process handles what when the file I/O compound tools run.

## Scenario

User says: "Import beam_schedule.csv, create beams with those sections, run analysis, then export member forces to member_forces.xlsx."

The agent makes two tool calls:
1. `read_and_execute` (CSV in, create beams, run analysis)
2. `execute_and_write` (extract forces, write xlsx)

---

## Tool call 1: `read_and_execute`

### What the agent sends (JSON over MCP protocol)

```json
{
  "tool": "read_and_execute",
  "arguments": {
    "path": "D:\\project\\beams.csv",
    "code": "for (const [x1,y1,z1,x2,y2,z2,sec] of __input) {\n  const n1 = staad.Geometry.AddNode(x1,y1,z1);\n  const n2 = staad.Geometry.AddNode(x2,y2,z2);\n  staad.Property.AssignBeamProperty(staad.Geometry.AddBeam(n1,n2), sec);\n}\nstaad.Command.PerformAnalysis();\nreturn __input.length + ' beams created and analyzed';"
  }
}
```

### Python server (MCP handler)

```python
# ---- PYTHON SERVER PROCESS (openstaad-mcp) ----

def handle_read_and_execute(path, code, instance=None, sheet_name=None, ...):

    # 1. Path validation (all in Python, no COM yet)
    model_path = com_connection.get_staad_file()       # COM call: GetSTAADFile()
    model_dir = Path(model_path).resolve().parent
    resolved = Path(path).resolve()
    assert not str(resolved).startswith("\\\\")        # UNC reject
    assert resolved.is_relative_to(model_dir)          # containment
    assert resolved.exists()                           # existence

    # 2. Read file (Python only, no sandbox involvement)
    rows = []
    with open(resolved, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)                                    # skip header
        for row in reader:
            # Typed cell conversion: try int, then float, else keep str
            converted = []
            for val in row:
                try:    converted.append(int(val))
                except ValueError:
                    try:    converted.append(float(val))
                    except ValueError: converted.append(val)
            rows.append(converted)

    assert len(rows) <= 100_000                         # row cap
    assert all(len(r) <= 500 for r in rows)             # col cap

    # 3. Stash sample rows for response (before sending to sandbox)
    sample_rows = rows[:5]

    # 4. Send to WASM sandbox with __input pre-bound
    result = wasm_executor.execute(
        code=code,
        input_data=rows,          # injected as frozen __input inside WASM
        instance=instance,
    )
    # rows freed from Python memory after this point

    # 5. Return to agent (bulk data never enters this response)
    return {
        "success": True,
        "result": result.return_value,    # "47 beams created and analyzed"
        "stdout": result.stdout,
        "stderr": result.stderr,
        "input_summary": {
            "total_rows": len(rows),
            "columns": ["x1","y1","z1","x2","y2","z2","section"],
            "sample_rows": sample_rows,
        },
        "duration_seconds": result.elapsed,
    }
```

### WASM sandbox (QuickJS inside WebAssembly)

```javascript
// ---- INSIDE WASM ISOLATE (QuickJS engine) ----
// __input is already bound and Object.freeze'd before this code runs.
// __input = [[0,0,0, 120,0,0, "W12X26"], [0,0,0, 0,120,0, "W10X19"], ...]

for (const [x1, y1, z1, x2, y2, z2, sec] of __input) {

    // Each of these calls exits WASM via host function → Python → COM → STAAD
    const n1 = staad.Geometry.AddNode(x1, y1, z1);
    const n2 = staad.Geometry.AddNode(x2, y2, z2);
    const beam = staad.Geometry.AddBeam(n1, n2);
    staad.Property.AssignBeamProperty(beam, sec);
}

// This also exits WASM → Python → COM → STAAD
staad.Command.PerformAnalysis();

return __input.length + " beams created and analyzed";
```

### What happens at the COM boundary (per iteration)

The `staad` object in JS is a Proxy. Every property access or method call on it gets intercepted, serialized to JSON, and sent to Python via an Extism host function. Python then dispatches the call to the real COM object obtained via `openstaadpy` (`os_analytical.connect(file_path)`).

```
WASM JS: staad.Geometry.AddNode(0, 0, 0)
  → JS Proxy intercepts .Geometry → host function returns sub-object handle
  → JS Proxy intercepts .AddNode(0,0,0) → host function call:
    → Python receives JSON: {"handle": 1, "method": "AddNode", "args": [0, 0, 0]}
    → Python looks up handle 1 → it's the Geometry sub-object from openstaadpy
    → Python calls: staad_com.Geometry.AddNode(0, 0, 0)
      → openstaadpy dispatches via win32com to STAAD.Pro process (COM IPC)
      → STAAD.Pro creates node in model, returns node number 1
    → Python returns JSON: {"value": 1}
  ← WASM JS receives: 1

WASM JS: staad.Geometry.AddNode(120, 0, 0)
  → same flow, STAAD returns node number 2

WASM JS: staad.Geometry.AddBeam(1, 2)
  → same flow, STAAD returns beam number 1

WASM JS: staad.Property.AssignBeamProperty(1, "W12X26")
  → same flow, STAAD assigns section

... repeat for each row in __input ...

WASM JS: staad.Command.PerformAnalysis()
  → Python receives: {"handle": 5, "method": "PerformAnalysis", "args": []}
  → Python checks allowlist: PerformAnalysis is a DESTRUCTIVE method
  → Elicitation/confirmation fires (user must approve)
  → User approves
  → Python calls: staad_com.Command.PerformAnalysis()
    → openstaadpy dispatches to STAAD.Pro
    → STAAD runs full structural analysis (may take seconds)
    → Returns when complete
  ← WASM JS receives: null (void method)
  ← JS execution continues
```

### What the agent gets back

```json
{
  "success": true,
  "result": "47 beams created and analyzed",
  "stdout": "",
  "stderr": "",
  "input_summary": {
    "total_rows": 47,
    "columns": ["x1","y1","z1","x2","y2","z2","section"],
    "sample_rows": [[0,0,0,120,0,0,"W12X26"], [0,0,0,0,120,0,"W10X19"]]
  },
  "duration_seconds": 4.2
}
```

The agent never held the 47 rows in its context window. It sent code (~500 bytes) and received a summary (~300 bytes).

---

## Tool call 2: `execute_and_write`

### What the agent sends

```json
{
  "tool": "execute_and_write",
  "arguments": {
    "code": "const beams = staad.Geometry.GetBeamList();\nconst cases = staad.Load.GetPrimaryLoadCaseNumbers();\nconst rows = [];\nfor (const b of beams) {\n  for (const lc of cases) {\n    const f = staad.Output.GetMemberEndForces(b, 0, lc, 0);\n    rows.push([b, lc, f[0], f[1], f[2], f[3], f[4], f[5]]);\n  }\n}\nreturn rows;",
    "path": "D:\\project\\member_forces.xlsx",
    "columns": ["Member", "LC", "Fx", "Fy", "Fz", "Mx", "My", "Mz"]
  }
}
```

### Python server

```python
# ---- PYTHON SERVER PROCESS ----

def handle_execute_and_write(code, path, columns, instance=None, overwrite=False):

    # 1. Run code in sandbox (no file involvement yet)
    result = wasm_executor.execute(code=code, instance=instance)
    rows = result.return_value    # Python list of lists, e.g. 141 rows

    # 2. Validate return shape
    assert isinstance(rows, list)
    assert all(isinstance(r, list) for r in rows)
    assert len(rows) <= 100_000
    assert all(len(r) == len(columns) for r in rows)   # column count match

    # 3. Path validation
    resolved = Path(path).resolve()
    # ... same checks as read_and_execute ...
    if resolved.exists() and not overwrite:
        return {"success": False, "error": "FILE_EXISTS", ...}

    # 4. Write to file (Python only, sandbox is done)
    tmp = resolved.parent / f".~omcp_{uuid4().hex[:8]}.tmp"
    try:
        wb = openpyxl.Workbook(write_only=True)
        ws = wb.create_sheet()
        ws.append(columns)                              # header row
        for row in rows:
            ws.append(row)                              # data rows
        wb.save(str(tmp))
        os.replace(str(tmp), str(resolved))             # atomic move
    finally:
        tmp.unlink(missing_ok=True)                     # cleanup on failure

    # 5. Return summary to agent (141 rows never enter agent context)
    return {
        "success": True,
        "path": str(resolved),
        "rows_written": len(rows),
        "columns": columns,
        "sample_rows": rows[:5],
        "duration_seconds": result.elapsed,
    }
```

### WASM sandbox

```javascript
// ---- INSIDE WASM ISOLATE ----
// No __input here (this is execute_and_write, not read_and_execute)

const beams = staad.Geometry.GetBeamList();          // → COM → returns [1,2,...,47]
const cases = staad.Load.GetPrimaryLoadCaseNumbers(); // → COM → returns [1,2,3]

const rows = [];
for (const b of beams) {
    for (const lc of cases) {
        // Each call: WASM → Python → openstaadpy → COM → STAAD
        const f = staad.Output.GetMemberEndForces(b, 0, lc, 0);
        rows.push([b, lc, f[0], f[1], f[2], f[3], f[4], f[5]]);
    }
}
// 47 beams x 3 load cases = 141 rows
return rows;   // goes to Python server memory, NOT to agent context
```

### COM boundary for the extraction

```
WASM JS: staad.Geometry.GetBeamList()
  → Python: staad_com.Geometry.GetBeamList()
    → openstaadpy → COM → STAAD returns array of beam numbers
  ← Python returns JSON: {"value": [1, 2, 3, ... 47]}
  ← WASM JS receives: [1, 2, 3, ... 47]

WASM JS: staad.Load.GetPrimaryLoadCaseNumbers()
  → same flow, returns [1, 2, 3]

WASM JS: staad.Output.GetMemberEndForces(1, 0, 1, 0)
  → Python: staad_com.Output.GetMemberEndForces(1, 0, 1, 0)
    → openstaadpy → COM → STAAD returns 6-element force array
  ← Python returns JSON: {"value": [-12.4, 3.2, 0.0, 0.0, 0.0, 45.6]}
  ← WASM JS receives: [-12.4, 3.2, 0.0, 0.0, 0.0, 45.6]

... repeat 141 times (47 beams x 3 LCs) ...
```

### What the agent gets back

```json
{
  "success": true,
  "path": "D:\\project\\member_forces.xlsx",
  "rows_written": 141,
  "columns": ["Member", "LC", "Fx", "Fy", "Fz", "Mx", "My", "Mz"],
  "sample_rows": [[1, 1, -12.4, 3.2, 0.0, 0.0, 0.0, 45.6], [1, 2, -8.1, 5.7, 0.0, 0.0, 0.0, 32.1]],
  "duration_seconds": 3.1
}
```

---

## Where data lives at each stage

```
                    Tool call 1                      Tool call 2
                    read_and_execute                 execute_and_write

Agent context:      code string (~500 B)             code string (~400 B)
                    response summary (~300 B)        response summary (~300 B)
                    NEVER sees 47 CSV rows           NEVER sees 141 force rows

Python server:      reads CSV → list of lists        receives return value (list of lists)
                    injects into WASM as __input     writes to xlsx via openpyxl
                    freed after injection            freed after file write

WASM sandbox:       __input (frozen, read-only)      builds rows array in JS heap
                    COM calls via staad Proxy        COM calls via staad Proxy
                    returns string summary           returns rows array → Python

COM (openstaadpy):  AddNode, AddBeam, Analyze        GetBeamList, GetMemberEndForces
                    one IPC call per method          one IPC call per method
                    dispatched to STAAD.Pro          dispatched to STAAD.Pro
```

---

## The COM layer: openstaadpy

The MCP server uses `openstaadpy` (Bentley's official Python package for STAAD automation) as the COM bridge. Specifically:

```python
from openstaadpy import os_analytical
staad = os_analytical.connect(file_path)
```

This returns a COM dispatch object connected to the running STAAD.Pro instance that has `file_path` open. All subsequent attribute access and method calls on this object are standard Windows COM IPC to the STAAD.Pro process.

The WASM sandbox never touches openstaadpy directly. The path is:

```
JS code → Proxy intercept → Extism host function → Python handler
  → allowlist check → openstaadpy COM dispatch → STAAD.Pro process
```

openstaadpy is the same library that users use directly when they write standalone Python scripts. The COM methods are identical. The only difference is the execution context: standalone scripts call methods directly in Python, while our architecture calls them from inside a WASM isolate via a Proxy-to-host-function bridge.

---

## "Show me the code for that" (standalone Python script)

After both tool calls complete, the user says: "Give me the Python script for what you just did."

The agent translates the JS it executed into a standalone Python script using openstaadpy. The COM calls are identical, only the language syntax changes:

```python
"""
Standalone script: import beams.csv, assign sections, run analysis,
export member forces to member_forces.xlsx.

Requirements: pip install openstaadpy openpyxl
Prerequisite: STAAD.Pro must be running with D:\project\example.std open.
"""
import csv
from pathlib import Path
from openstaadpy import os_analytical
import openpyxl

# Connect to running STAAD instance
staad = os_analytical.connect(r"D:\project\example.std")

# --- Phase 1: Import beams from CSV ---
beams_csv = Path(r"D:\project\beams.csv")
with open(beams_csv, newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    next(reader)  # skip header
    for row in reader:
        x1, y1, z1, x2, y2, z2 = (float(v) for v in row[:6])
        sec = row[6]
        n1 = staad.Geometry.AddNode(x1, y1, z1)
        n2 = staad.Geometry.AddNode(x2, y2, z2)
        beam = staad.Geometry.AddBeam(n1, n2)
        staad.Property.AssignBeamProperty(beam, sec)

# --- Phase 2: Run analysis ---
staad.Command.PerformAnalysis()

# --- Phase 3: Export member forces to xlsx ---
beams = staad.Geometry.GetBeamList()
cases = staad.Load.GetPrimaryLoadCaseNumbers()

wb = openpyxl.Workbook()
ws = wb.active
ws.append(["Member", "LC", "Fx", "Fy", "Fz", "Mx", "My", "Mz"])

for b in beams:
    for lc in cases:
        f = staad.Output.GetMemberEndForces(b, 0, lc, 0)
        ws.append([b, lc, f[0], f[1], f[2], f[3], f[4], f[5]])

wb.save(r"D:\project\member_forces.xlsx")
print(f"Exported {len(beams) * len(cases)} rows to member_forces.xlsx")
```

The script is self-contained. No MCP server, no WASM sandbox, no agent. The user runs it directly with `python export_forces.py`. The COM calls (`staad.Geometry.AddNode`, `staad.Output.GetMemberEndForces`, etc.) are byte-for-byte identical to what the sandbox executed. The only differences are Python syntax and direct file I/O instead of the compound tool broker.
