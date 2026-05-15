---
name: staad-core
description: "ALWAYS load first for any STAAD.Pro automation. Covers: Python sandbox (staad/progress pre-injected — import blocked), sub-module access (Geometry, Property, Support, Load, Command, Output, Design), execution modes (sync/async auto-detected from code keywords — override with timeout= and mode= when you know better; async long-polls with strategy field), unit conversion (English=inches/KIP, Metric=meters/kN), GetBaseUnit, IsZUp, SetSilentMode required before UpdateStructure/AnalyzeModel/AnalyzeEx/SaveModel/file operations, UpdateStructure semantics, application control (ShowApplication, GetApplicationVersion, Quit), progress reporting, timeout guidelines, large model query patterns. Do not auto-save."
---

# STAAD.Pro Core — Sandbox & Model Setup

## Instructions

### Sandbox

- Pre-injected names (do NOT import): `staad`, `json`, `math`, `progress`
- `import` statements are **BLOCKED** — only use pre-injected names
- `staad` is already connected and ready — do NOT call any initialization function
- Sub-modules: `geo = staad.Geometry`, `prop = staad.Property`, `sup = staad.Support`, `load = staad.Load`, `cmd = staad.Command`, `out = staad.Output`, `design = staad.Design`
- `progress(message)` — send a real-time status update (e.g. `progress(f"Node {i}/{total}")`)

### Progress

Call `progress()` inside any loop that iterates over more than ~20 elements, or before any operation that may take more than a few seconds (analysis, bulk queries, large result extraction). This prevents the client from appearing frozen.

```python
node_ids = staad.Geometry.GetNodeList()
total = len(node_ids)
for i, nid in enumerate(node_ids):
    if i % 10 == 0:
        progress(f"Processing node {i}/{total}")
    # ... do work ...
```

Rules:

- Call every 10–50 iterations (not every iteration — avoid flooding).
- Include a counter: `f"{i}/{total}"` is more useful than a static string.
- Call once before long single operations: `progress("Running analysis...")`

### Pre-Execution Check

**ALWAYS** call `get_status` before `execute_code` if a previous execution may still be running. The response includes `executor_busy: true/false`. If `executor_busy` is `true`, the executor is still processing a previous call — wait and retry rather than sending a new execution (it will be rejected with "Executor busy").

```
get_status()
→ {"connected": true, "executor_busy": false, ...}   ← safe to execute
→ {"connected": true, "executor_busy": true, ...}    ← wait and retry
```

### Execution Pattern

Code execution supports two modes via the `mode` parameter:

**Sync mode (default, `mode="sync"`)** — blocks and returns the result directly in one call:

```
execute_code(code="result = staad.Geometry.GetNodeCount()")
→ {"success": true, "result": 220, "stdout": "", "stderr": "", ...}
```

Use for operations expected to finish in under ~60 s: queries, property assignments, small loops. Zero polling overhead.

**Async mode (`mode="async"`)** — returns a `job_id` immediately, then poll with `get_job_result`:

```
execute_code(code="...", mode="async")
→ {"job_id": "abc123def456"}

get_job_result(job_id="abc123def456")
→ {"status": "running", "message": "⏳ Running (8s): Node 50/200", "strategy": "poll", "retry_after_seconds": 10}

[Write message to user, wait ~10 s, then call again]

get_job_result(job_id="abc123def456")
→ {"status": "completed", "success": true, "result": ..., "message": "✅ Completed in 31s"}
```

Use for slow operations (>60 s): analysis, bulk result extraction, large model queries.

Rules:
- Mode and timeout are auto-detected — omit both unless you need to override.
- `get_job_result` returns immediately with the current status (no blocking).
- Check `strategy` in every running response:
  - `"poll"` → write `message` to user, wait `retry_after_seconds`, then call again
  - `"await_user_trigger"` → write `message` to user, stop all autonomous polling; tell the user the job is still running (include job_id) and wait for them to ask
- When `status` is `"completed"` or `"failed"`, the result payload is included directly in the response.

### Reporting Progress to the User

**IMPORTANT:** MCP notifications are NOT visible in the chat UI. The only way the user sees progress is if you **write it in your text response**. Follow this pattern for async operations:

1. Start the job with `mode="async"`
2. Call `get_job_result(job_id)` — returns immediately with current status
3. **Write the `message` field to the user** (e.g. "⏳ Running (18s): Processing plate 40000/111684...")
4. Wait `retry_after_seconds` before calling again
5. Check `strategy`: `"poll"` → repeat steps 2-4; `"await_user_trigger"` → stop, tell user, wait for their request
6. When `status` is `"completed"` or `"failed"`, present the final result

Example conversation flow:
```
→ execute_code(code="...", mode="async")
← {"job_id": "abc123"}

[Tell user: "Starting computation..."]

→ get_job_result(job_id="abc123")
← {"status": "running", "message": "⏳ Running (8s): Reading nodes 5000/52000", "strategy": "poll", "retry_after_seconds": 10}

[Tell user: "⏳ Running (8s): Reading nodes 5000/52000"]
[Wait ~10 s]

→ get_job_result(job_id="abc123")
← {"status": "completed", "success": true, "result": {...}, "message": "✅ Completed in 31s"}

[Present final result to user]
```

For **long analyses (>10 min)** the server returns `strategy="await_user_trigger"`:
```
→ get_job_result(job_id="abc123")
← {"status": "running", "strategy": "await_user_trigger", "message": "⏳ Still running (12 min). Stop polling — tell the user the analysis is still in progress (job_id='abc123') and wait for them to ask for an update."}

[Stop polling. Tell user: "The analysis is still running. I'll check back when you're ready — just ask me (job_id='abc123')."]
```

For **sync mode**: progress is not displayed to the user. If you expect >60 s, prefer async mode.

### Timeout

Timeout and mode are **auto-detected** from code keywords — the server uses a simple heuristic:

| Code pattern | Default timeout | Default mode |
| --- | --- | --- |
| No loops, no analysis/design | 120 s | sync |
| Has `for`/`while` loop | 600 s | async |
| Has `AnalyzeModel`/`AnalyzeEx`/`PerformDesign` | 3600 s | async |

The heuristic doesn't know model size or iteration count — **override when you know better:**

```
execute_code(code="...", timeout=1800, mode="async")
```

#### By script type

| Script type | Examples | Suggested timeout | Mode |
| --- | --- | --- | --- |
| **Quick query** — single property read, node/member count, coordinates of one element | `GetNodeCount`, `GetNodeCoordinates(nid)`, `GetBaseUnit` | omit (120 s default) | omit (sync) |
| **Small mutation** — add one node/beam, assign properties to a known list | `AddNode`, `AddBeam`, `AssignBeamProperty`, `AssignPlateThickness` | omit (120 s default) | omit (sync) |
| **Medium loop** — iterate <500 elements, apply loads/supports, build geometry | Hydrostatic pressure assignment, assign supports to node list, force report for a few beams | omit (600 s default) | omit (async) |
| **Heavy loop** — iterate >5 000 elements with per-element COM calls | Plate area scan (100k plates), bulk coordinate read, result extraction over all members × load cases | `timeout=elements × 0.005` | `mode="async"` |
| **Analysis — linear** — small/medium model (<5 000 nodes) | `AnalyzeEx(1, 0, 1)` on a portal frame or building | omit (3600 s default) | omit (async) |
| **Analysis — linear** — large model (>5 000 nodes, many load cases) | `AnalyzeEx(1, 0, 1)` on a large industrial structure | `timeout=3600` | `mode="async"` |
| **Nonlinear / P-Delta / Buckling** — any model size | `PerformPDeltaAnalysisEx`, `PerformNonlinearAnalysisEx`, `PerformBucklingAnalysisEx` | `timeout=3600` | `mode="async"` |
| **Analysis + Design** — full workflow in one script | `AnalyzeEx` followed by design result extraction loops | `timeout=3600` | `mode="async"` |

#### Estimating timeout for loops

Each COM call takes ~3 ms on average (including marshalling overhead). Use this formula:

```
timeout ≈ elements × calls_per_element × 0.003
```

Common patterns:

- **Single property per element** (1 call/element): `timeout = elements × 0.003`
- **Coordinates + 1 property** (2 calls/element): `timeout = elements × 0.006`
- **Results for all load cases** (elements × LCs calls): `timeout = elements × load_cases × 0.003`
- **Nested loop** (elements × sub-elements): multiply both counts

Examples:
- 50 000 plates × 1 call → `timeout=150` (2.5 min)
- 10 000 beams × 5 load cases → `timeout=150` (2.5 min)
- 100 000 plates × 2 calls → `timeout=600` (10 min)

When in doubt, round up generously — a timeout that's too short kills the operation and wastes all progress.

Always add `progress()` calls inside loops so status is visible during long operations.

### Result Structure for Bulk Queries

Build a **dict keyed by element ID** rather than parallel lists or nested loops. This avoids O(n²) lookups, produces self-describing JSON, and keeps results compact.

**Preferred pattern:**

```python
node_ids = staad.Geometry.GetNodeList()
nodes = {}
total = len(node_ids)
for i, nid in enumerate(node_ids):
    if i % 20 == 0:
        progress(f"Reading node {i}/{total}")
    x, y, z = staad.Geometry.GetNodeCoordinates(nid)
    nodes[nid] = {"x": x, "y": y, "z": z}
result = nodes
```

Rules:

- Use `result = {...}` assignment so the sandbox returns it as the tool result.
- Top-level key: entity type in plural (`"nodes"`, `"beams"`, `"loads"`).
- Each value: a flat dict of properties; avoid deeply nested structures.
- For cross-entity data nest one level: `{beam_id: {"loads": [...]}}`.
- Never use parallel lists (`ids = [...]`, `xs = [...]`) — they break if order differs.

### Large Model Queries

For models with >500 nodes/beams, query counts first and adapt strategy before bulk-fetching.

**Step 1 — count before fetch:**

```python
node_count = staad.Geometry.GetNodeCount()
beam_count = staad.Geometry.GetMemberCount()
progress(f"Model: {node_count} nodes, {beam_count} beams")
```

**Step 2 — choose strategy:**

| Count | Strategy |
| --- | --- |
| < 500 | Fetch all, return full dict |
| 500–2 000 | Fetch all with `progress()`, summarise if result near 200 KB |
| > 2 000 | Targeted ranges or summary statistics |

**Summary statistics (avoids large result):**

```python
node_ids = staad.Geometry.GetNodeList()
xs, ys, zs = [], [], []
for nid in node_ids:
    x, y, z = staad.Geometry.GetNodeCoordinates(nid)
    xs.append(x); ys.append(y); zs.append(z)
result = {
    "node_count": len(node_ids),
    "x_range": [min(xs), max(xs)],
    "y_range": [min(ys), max(ys)],
    "z_range": [min(zs), max(zs)],
}
```

**Sampling for initial exploration:**

```python
step = max(1, node_count // 50)   # ~50 samples
sample_ids = node_ids[::step]
nodes = {}
for nid in sample_ids:
    x, y, z = staad.Geometry.GetNodeCoordinates(nid)
    nodes[nid] = {"x": x, "y": y, "z": z}
result = {"sampled": True, "sample_size": len(sample_ids), "nodes": nodes}
```

Rules:

- Never fetch all coordinates for >2 000 nodes in a single call — the result may be too large.
- Prefer summary statistics for initial exploration; fetch raw data only when the user needs specific elements.

### Typical Workflows

Load skills in this order for common tasks:

| Task | Skills to load |
| --- | --- |
| Query an existing model | `staad-core` → `staad-results` |
| Build a model from scratch | `staad-core` → `staad-geometry` → `staad-properties` → `staad-supports` → `staad-loading` → `staad-analysis` → `staad-results` |
| Run steel design | `staad-core` → `staad-steel-design` |
| Add loads to existing geometry | `staad-core` → `staad-loading` → `staad-analysis` → `staad-results` |
| Export a screenshot | `staad-core` → `staad-view` |
| Robust scripting / error handling | Add `staad-errors` to any of the above |

### Discovery

Before writing any script:

1. Call `discover_api` → lists available skills and usage guidance
2. Call `read_skills` with skill names → detailed instructions for that domain
3. If you already know a function name but not which skill covers it, read `./assets/FUNCTION_SKILL_MAP.md` for a quick function → skill lookup

Never guess or invent function names — only use names from the skill documentation.

### Multi-Instance

- Call `list_instances` to see all running STAAD.Pro instances (lightweight ROT scan)
- Call `get_status(instance)` to verify a specific instance is reachable
- Pass `instance` (alias like `staadPro1`) to `execute_code` when multiple instances are running

### Tool Reference

| Tool | Purpose |
| --- | --- |
| `discover_api` | List available skills |
| `read_skills` | Load skill instructions |
| `list_instances` | List running STAAD.Pro instances |
| `get_status` | Check connection to instance |
| `execute_code` | Run code — timeout/mode auto-detected; pass `timeout=` to override |
| `get_job_result` | Long-poll a running job or collect its result when done |

### Units & Axis

- Before any modeling operation, query units via `execute_code`:
  - `staad.GetBaseUnit()` → `"English"` or `"Metric"`
  - `staad.Geometry.IsZUp()` → `True` if Z is up
  - `staad.GetInputUnitForLength()` / `staad.GetInputUnitForForce()` → current input unit strings
- `English` = inches + KIP; `Metric` = meters + kN
- Y-up: vertical axis is Y; Z-up: vertical axis is Z
- Convert all user-provided dimensions to the base unit before passing to the API
- Do NOT change the unit system unless the user explicitly asks
- `staad.SetInputUnits(lengthUnit, forceUnit)` → change input units (integer codes)

### SetSilentMode

`SetSilentMode(True)` MUST be called before these operations (they trigger UI dialogs that block automation):

- `UpdateStructure`, `SaveModel`
- `AnalyzeModel`, `AnalyzeEx`

Always restore with `SetSilentMode(False)` at the end of the script.

### UpdateStructure vs SaveModel

- `UpdateStructure()` = **reload from disk** — it discards all in-memory `AddNode`/`AddBeam` state that has not yet been written to disk. If you call it after adding geometry in the same script, **all that geometry is lost**.
- `SaveModel(True)` = write current in-memory state to disk **without reloading** — use this to flush geometry before assigning supports/loads in the same script session.
- **Rule:** whenever geometry was added in-memory and the next step requires file-based state (supports, loads, sections), use `SaveModel(True)` — not `UpdateStructure()`.
- `UpdateStructure` is only safe to call when the current in-memory state already matches what is on disk.
- Do NOT call after `AddNode`/`AddBeam` just to query geometry — COM geometry APIs read from the in-memory buffer immediately.

### SaveModel — REQUIRE EXPLICIT USER INTENT

- Do NOT call `SaveModel()` casually — only when:
  1. The user explicitly asks to save, **or**
  2. You are about to run analysis (the engine reads the `.std` file from disk), **or**
  3. Geometry was added in-memory and the next step needs file-based state (supports, loads)

### File Operations — REQUIRE EXPLICIT USER INTENT

Always work on the **currently open model**. If the user says "create a model", that means add geometry/properties to the current open model — not create a new file.

- After any file operation, `staad` and all sub-objects remain valid — do NOT reinitialize
- Use `staad.GetSTAADFile()` to get the current model path
- `staad.GetSTAADFileFolder()` returns the folder path

#### Opening, Creating & Saving Files

The following functions are available but **path-validated** by the sandbox:

- `staad.OpenSTAADFile(filePath)` — open an existing STAAD model file
- `staad.NewSTAADFile(filePath, envCode, unitCode)` — create a new STAAD model file
- `staad.SaveAs(filePath)` — save the current model to a new file path
- `staad.CloseSTAADFile()` — close the currently open model

**Path rules** (enforced automatically — violations raise an error):

- The path **must be absolute** (e.g. `"C:\\Users\\me\\models\\bridge.std"`)
- The file **must end with `.std`**
- UNC paths (`\\\\server\\share\\...`) are **blocked**
- Paths targeting protected OS directories (`Windows`, `Program Files`, `ProgramData`) are **blocked**
- Path traversal (`..`) is **blocked**

```python
# Open an existing model
staad.OpenSTAADFile("C:\\Projects\\Bridge\\bridge_v2.std")

# Create a new model (envCode=1 for general, unitCode depends on unit system)
staad.NewSTAADFile("C:\\Projects\\NewModel\\frame.std", 1, 0)

# Save a copy
staad.SaveAs("C:\\Projects\\Bridge\\bridge_backup.std")

# Close the current model
staad.CloseSTAADFile()
```

### Application Control

- `staad.ShowApplication()` — show the STAAD.Pro window
- `staad.GetApplicationVersion()` → version string
- `staad.IsPhysicalModel()` → True if physical model mode
- `staad.Quit()` — close the application (use with caution)

### Analysis Shortcuts

- `staad.AnalyzeEx(silentMode, hiddenMode, waitTillComplete)` → status code
  - Return codes: `2` = OK, `3` = warnings, `4` = errors, `-1` = terminated
  - Always use `silentMode=1, waitTillComplete=1` for automation
- `staad.AnalyzeModel()` — simplified, no return value

## Gotchas

- `import` is blocked — only `staad`, `json`, `math`, `progress` are available
- Use `staad.GetSTAADFile()` to get the current model path after a file switch
- Always wrap `UpdateStructure`/`AnalyzeModel`/`AnalyzeEx`/`SaveModel` inside `SetSilentMode(True/False)`
- **Never** call `SaveModel` without explicit user instruction
- `UpdateStructure` **discards** in-memory geometry not yet on disk — use `SaveModel(True)` instead when you need to flush before support/load assignment
- `AnalyzeEx` runs both analysis AND design; `AnalyzeModel` runs analysis only
