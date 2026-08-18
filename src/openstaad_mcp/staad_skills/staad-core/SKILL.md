---
name: staad-core
description: "ALWAYS load first for any STAAD.Pro automation. Covers: Python sandbox (staad pre-injected — import blocked), sub-module access (Geometry, Property, Support, Load, Command, Output, Design), units and axis check via execute_code, unit conversion (English=inches/KIP, Metric=meters/kN), GetBaseUnit, IsZUp, SetSilentMode required before UpdateStructure/AnalyzeModel/AnalyzeEx/SaveModel/file operations, UpdateStructure semantics, application control (ShowApplication, GetApplicationVersion, Quit), job metadata (GetFullJobInfo, GetShortJobInfo, SetFullJobInfo, SetShortJobInfo). Do not auto-save."
---

# STAAD.Pro Core — Sandbox & Model Setup

## Instructions

### Sandbox

- Pre-injected names (do NOT import): `staad`, `input_data`, `json`, `math`
- `import` statements, `dir()`, `getattr()`, ... are **BLOCKED** — use skills for discovery, only use pre-injected names in code
- `staad` is already connected and ready — do NOT call any initialization function
- `input_data` is injected if `input_data_path` is provided in `execute_code` params — use it to feed large datasets into the sandbox without hardcoding
- Sub-modules: `geo = staad.Geometry`, `prop = staad.Property`, `sup = staad.Support`, `load = staad.Load`, `cmd = staad.Command`, `out = staad.Output`, `design = staad.Design`
- If `output_data_path` is provided, write the `result` variable to that file path instead of returning it in the context (use for large/tabular data). The `execute_code` return value will contain a summary of the `result` content instead (e.g. number of rows, columns and a sample of rows).
- Both `input_data_path` and `output_data_path` must be on the user LOCAL filesystem and inside MCP roots or configured `allowed_dirs`. On Claude Desktop, users can configure allowed directories in the extension settings and Claude can use the filesystem `copy_file_to_claude` tool to move files to Claude's filesystem.

### Discovery

Before writing any script:

1. Call `discover_api` → lists available skills and usage guidance
2. Call `read_skills` with skill names → detailed instructions for that domain

Never guess or invent function names — only use names from the skill documentation.

### Multi-Instance

- Call `list_instances` to see all running STAAD.Pro instances (lightweight ROT scan)
- Call `get_status(instance)` to verify a specific instance is reachable
- Pass `instance` (alias like `staadPro1`) to `execute_code` when multiple instances are running

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
  - `staad.GetBaseUnit()` → `"English"` or `"Metric"` (unit family only, NOT the exact unit — see below)
  - `staad.Geometry.IsZUp()` → `True` if Z is up
  - `staad.GetInputUnitForLength()` / `staad.GetInputUnitForForce()` → the ACTUAL current input unit strings (e.g. `"Feet"`/`"Inch"`, `"Kilopound"`) that every load/geometry numeric input must match
- Do NOT assume `English` always means inches/KIP or `Metric` always means meters/kN — the active length/force unit can change independently within either family (confirmed live: an `English` model had `GetInputUnitForLength()` return `"Feet"`, not inches). Always query `GetInputUnitForLength()`/`GetInputUnitForForce()` and convert user-provided values to those exact units before any COM call that takes a numeric magnitude (loads, dimensions, etc.)
- Y-up: vertical axis is Y; Z-up: vertical axis is Z
- Do NOT change the unit system unless the user explicitly asks
- `staad.SetInputUnits(lengthUnit, forceUnit)` → change input units (integer codes) — see **[UNIT_CODES.md](./assets/UNIT_CODES.md)** for the full length/force code tables

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

# Close the current model
staad.CloseSTAADFile()
```

- **`CloseSTAADFile()` can pop up a modal dialog** (e.g. unsaved-changes prompt) that blocks the COM call from returning — the same class of issue as `AnalyzeEx` triggering a save dialog. If it times out, the executor gets stuck until the dialog is dismissed in the STAAD.Pro window.
- **After `CloseSTAADFile()`, the instance may disappear from `list_instances`/`get_status`** — instance discovery scans the Windows ROT for monikers ending in `.std`; with no file open there's nothing to find. Open a `.std` file again to make the instance visible.
- **`OpenSTAADFile(path)` on the file that's already open is a no-op** — it does NOT force a fresh re-parse from disk. To verify that a file saved via the API actually re-parses correctly (e.g. to catch a syntax error introduced by a COM call), open a **different** `.std` file first, then `OpenSTAADFile(path)` back to the target — this forces STAAD to genuinely re-parse it and, if the file has bad syntax, pop the real `"(N) Errors, (N) Warnings found in input file. Would you like to edit the input file?"` dialog (confirmed live). Avoid `CloseSTAADFile()` for this purpose — it carries its own dialog/instance-visibility risk (see the gotcha above).

### Application Control

- `staad.ShowApplication()` — show the STAAD.Pro window
- `staad.GetApplicationVersion()` → version string
- `staad.IsPhysicalModel()` → True if physical model mode
- `staad.Quit()` — close the application (use with caution)
- `staad.GetErrorMessage()` → last error message text thrown by OpenSTAAD (e.g. missing license, missing named view)

### Job Metadata

- `staad.GetShortJobInfo()` → `(job_name, job_id, job_status)`
- `staad.SetShortJobInfo(job_name, job_id, job_status)`
- `staad.GetFullJobInfo()` → `[job_name, job_client, eng_name, eng_date, job_number, revision, part_name, reference, checker_name, checker_date, approver_name, approval_date, comments]` (13 fields)
- `staad.SetFullJobInfo(job_name, job_client, eng_name, eng_date, job_number, revision, part_name, reference, checker_name, checker_date, approver_name, approval_date, comments)` — only `job_name` is required, the rest default to `""`

### Analysis Shortcuts

- `staad.AnalyzeEx(silentMode, hiddenMode, waitTillComplete)` → status code
  - Return codes: `2` = OK, `3` = warnings, `4` = errors, `-1` = terminated
  - Always use `silentMode=1, waitTillComplete=1` for automation
- `staad.AnalyzeModel()` — simplified, no return value

## Gotchas

- `import`, `dir()`, `getattr()`, ... are blocked — only `staad`, `input_data`, `json`, `math` are available
- If `input_data_path` is provided, `input_data` is injected as an immutable variable — use it to feed large datasets into the sandbox without hardcoding
- If `output_data_path` is provided, write the `result` variable to that file path instead of returning it in the context (use for large/tabular data). The `execute_code` return value will contain a summary of the `result` content instead (e.g. number of rows, columns and a sample of rows).
- Both `input_data_path` and `output_data_path` must be on the user LOCAL filesystem and inside MCP roots or configured `allowed_dirs`. On Claude Desktop, users can configure allowed directories in the extension settings and Claude can use the filesystem `copy_file_to_claude` tool to move files to Claude's filesystem.
- Use `staad.GetSTAADFile()` to get the current model path after a file switch
- Always wrap `UpdateStructure`/`AnalyzeModel`/`AnalyzeEx`/`SaveModel` inside `SetSilentMode(True/False)`
- **Never** call `SaveModel` without explicit user instruction
- `UpdateStructure` **discards** in-memory geometry not yet on disk — use `SaveModel(True)` instead when you need to flush before support/load assignment
- `AnalyzeEx` runs both analysis AND design; `AnalyzeModel` runs analysis only

