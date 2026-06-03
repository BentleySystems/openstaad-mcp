---
name: staad-core
description: "ALWAYS load first for any STAAD.Pro automation. Covers: Python sandbox (staad pre-injected — import blocked), sub-module access (Geometry, Property, Support, Load, Command, Output, Design), units and axis check via execute_code, unit conversion (English=inches/KIP, Metric=meters/kN), GetBaseUnit, IsZUp, SetSilentMode required before UpdateStructure/AnalyzeModel/AnalyzeEx/SaveModel/file operations, UpdateStructure semantics, application control (ShowApplication, GetApplicationVersion, Quit). Do not auto-save."
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

- `import`, `dir()`, `getattr()`, ... are blocked — only `staad`, `input_data`, `json`, `math` are available
- If `input_data_path` is provided, `input_data` is injected as an immutable variable — use it to feed large datasets into the sandbox without hardcoding
- If `output_data_path` is provided, write the `result` variable to that file path instead of returning it in the context (use for large/tabular data). The `execute_code` return value will contain a summary of the `result` content instead (e.g. number of rows, columns and a sample of rows).
- Both `input_data_path` and `output_data_path` must be on the user LOCAL filesystem and inside MCP roots or configured `allowed_dirs`. On Claude Desktop, users can configure allowed directories in the extension settings and Claude can use the filesystem `copy_file_to_claude` tool to move files to Claude's filesystem.
- Use `staad.GetSTAADFile()` to get the current model path after a file switch
- Always wrap `UpdateStructure`/`AnalyzeModel`/`AnalyzeEx`/`SaveModel` inside `SetSilentMode(True/False)`
- **Never** call `SaveModel` without explicit user instruction
- `UpdateStructure` **discards** in-memory geometry not yet on disk — use `SaveModel(True)` instead when you need to flush before support/load assignment
- `AnalyzeEx` runs both analysis AND design; `AnalyzeModel` runs analysis only
