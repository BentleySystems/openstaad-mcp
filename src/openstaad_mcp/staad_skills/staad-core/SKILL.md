---
name: staad-core
description: "ALWAYS load first for any STAAD.Pro automation. Covers: Python sandbox (staad/input_data/progress pre-injected — import blocked), sub-module access (Geometry, Property, Support, Load, Command, Output, Design), execution modes (auto default / native = MCP protocol progress / poll = AI polls get_job_result + writes message to user), progress reporting via progress(), timeout guidelines (default 120s, override with timeout=), large model query patterns, units and axis check via execute_code, unit conversion (English=inches/KIP, Metric=meters/kN), GetBaseUnit, IsZUp, SetSilentMode required before UpdateStructure/AnalyzeModel/AnalyzeEx/SaveModel/file operations, UpdateStructure semantics, application control (ShowApplication, GetApplicationVersion, Quit). Do not auto-save."
---

# STAAD.Pro Core — Sandbox & Model Setup

## Instructions

### Sandbox

- Pre-injected names (do NOT import): `staad`, `input_data`, `json`, `math`, `progress`
- `import` statements, `dir()`, `getattr()`, ... are **BLOCKED** — use skills for discovery, only use pre-injected names in code
- `staad` is already connected and ready — do NOT call any initialization function
- `input_data` is injected if `input_data_path` is provided in `execute_code` params — use it to feed large datasets into the sandbox without hardcoding
- Sub-modules: `geo = staad.Geometry`, `prop = staad.Property`, `sup = staad.Support`, `load = staad.Load`, `cmd = staad.Command`, `out = staad.Output`, `design = staad.Design`
- `progress(message)` — send a real-time status update (e.g. `progress(f"Node {i}/{total}")`)
- If `output_data_path` is provided, write the `result` variable to that file path instead of returning it in the context (use for large/tabular data). The `execute_code` return value will contain a summary of the `result` content instead (e.g. number of rows, columns and a sample of rows).
- Both `input_data_path` and `output_data_path` must be on the user LOCAL filesystem and inside MCP roots or configured `allowed_dirs`. On Claude Desktop, users can configure allowed directories in the extension settings and Claude can use the filesystem `copy_file_to_claude` tool to move files to Claude's filesystem.

### Progress

Call `progress(message)` every 10–50 iterations of a loop (with a counter), and once before any long single op — otherwise the client looks frozen. Don't call it every iteration (flooding).

```python
node_ids = staad.Geometry.GetNodeList()
total = len(node_ids)
for i, nid in enumerate(node_ids):
    if i % 20 == 0:
        progress(f"Node {i}/{total}")
    ...                              # work
# or, before a single long op: progress("Running analysis...")
```

### Before executing

If a prior `execute_code` may still be running, call `get_status` first — it returns `executor_busy`. If `true`, wait and retry; a new execution is rejected while busy.

### Execution modes

`execute_code(mode=...)` chooses how progress reaches the user, via two channels:

- **native** — real-time MCP notifications rendered *by the client* (needs client support).
- **poll** — returns a `job_id`; *you* relay progress by polling `get_job_result` (works on every client).

Pick by expected duration (only you know it — the server can't):

| Work | Mode | Why |
| --- | --- | --- |
| Quick query / small mutation — `GetNodeCount`, `AddNode`, assign to a known list | `native` | nothing to show; one call, no poll overhead |
| Medium/heavy loop — 100s–10 000s of elements | `auto` | server uses native progress if the client supports it, else falls back to poll — best channel per client |
| Analysis / nonlinear / P-Delta / buckling / design | `poll` | guarantees background execution so a long run can't hit a transport timeout |

`auto` (the param default) resolves to native or poll by inspecting the client; use `native`/`poll` explicitly for the ends of the range above.

**Poll loop — when a call returns a `job_id`, follow exactly:**

1. Response has `job_id` + `next_action`. **Write nothing yet** — call `get_job_result(job_id)` immediately.
2. Write the returned `message` to the user.
3. `status == "running"` → call `get_job_result` again immediately (server paces at 10–55 s internally).
4. `status == "completed"` / `"failed"` → present the result; the job is then gone (a later poll returns `"delivered"` — don't re-poll).
5. After **5** consecutive `"running"` (or a job >20 min), stop: tell the user it's still running (include `job_id`) and wait for them to ask before polling again.

### Timeout

Default is **120 s** per call (no auto-detection). Pass `timeout=<seconds>` for longer work; pair long runs with `mode="poll"`:

```
execute_code(code="...", timeout=3600, mode="poll")     # any analysis
```

Estimate loops at ~3 ms per COM call — `timeout ≈ elements × calls_per_element × 0.003` — and round up generously (too short kills the op and wastes progress):

- 1 call/element (single property): `elements × 0.003`
- 2 calls/element (coords + property): `elements × 0.006`
- per load case: `elements × load_cases × 0.003`
- any analysis: `timeout=3600`

e.g. 100 000 plates × 2 calls → `timeout=600` (10 min).

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
| `get_status` | Check connection to an instance (includes `executor_busy`) |
| `execute_code` | Run code — default `mode="auto"`/120 s; pass `mode="poll"` and `timeout=` for long work |
| `get_job_result` | Long-poll a running poll job or collect its result when done |

### Version Compatibility

The MCP is built against a single bundled **openstaadpy** wrapper, identical for
every connected instance — so the wrapper is **never** something to gate on. What
*does* vary is the **STAAD.Pro version** of each running instance. Two consequences:

- **Wrapper behavior is uniform.** Several `Assign*` methods return `bool` and
  **raise on failure** instead of returning a negative `int` code (see
  staad-steel-design, staad-properties, staad-supports). Use `try/except`; do not
  check `if result < 0` for those methods.
- **Some COM functions require STAAD.Pro v26+** (e.g. `GetAnalysisErrorMessages`,
  `GetAnalysisWarningMessages`). On an older connected STAAD they do not exist and
  raise a clear "update STAAD.Pro" error.

**Gate STAAD-v26-only functions using the version you already have** — do NOT add a
check inside the script:

1. Call `list_instances` → each row includes a `version` field; or
   `get_status(instance)` → returns `staad_version`. This is the **STAAD.Pro**
   version, not the wrapper version.
2. If the instance is **STAAD.Pro v26+**, compose the `execute_code` call using the
   v26-only function.
3. If it is **older**, use the legacy path or tell the user the feature needs
   STAAD.Pro v26.

Functions marked *(Requires STAAD.Pro v26+)* in the skills need a connected STAAD of
that version or newer.

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

- `import`, `dir()`, `getattr()`, ... are blocked — only `staad`, `input_data`, `json`, `math`, `progress` are available
- If `input_data_path` is provided, `input_data` is injected as an immutable variable — use it to feed large datasets into the sandbox without hardcoding
- If `output_data_path` is provided, write the `result` variable to that file path instead of returning it in the context (use for large/tabular data). The `execute_code` return value will contain a summary of the `result` content instead (e.g. number of rows, columns and a sample of rows).
- Both `input_data_path` and `output_data_path` must be on the user LOCAL filesystem and inside MCP roots or configured `allowed_dirs`. On Claude Desktop, users can configure allowed directories in the extension settings and Claude can use the filesystem `copy_file_to_claude` tool to move files to Claude's filesystem.
- Use `staad.GetSTAADFile()` to get the current model path after a file switch
- Always wrap `UpdateStructure`/`AnalyzeModel`/`AnalyzeEx`/`SaveModel` inside `SetSilentMode(True/False)`
- **Never** call `SaveModel` without explicit user instruction
- `UpdateStructure` **discards** in-memory geometry not yet on disk — use `SaveModel(True)` instead when you need to flush before support/load assignment
- `AnalyzeEx` runs both analysis AND design; `AnalyzeModel` runs analysis only
