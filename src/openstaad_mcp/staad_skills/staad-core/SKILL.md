---
name: staad-core
description: "ALWAYS load first for any STAAD.Pro automation. Covers: Python sandbox (staad pre-injected — import blocked), sub-module access (Geometry, Property, Support, Load, Command, Output, Design), units and axis check via execute_code, standard units convention — setters consume the current input unit setting and convert to base for storage, getters return fixed base units (exception: geometry always uses base units, ignores input unit setting); use GetInputUnitForLength/Force to discover the current unit instead of calling SetInputUnits; GetOutputUnitFor* is a separate UI-display-only subsystem, GetBaseUnit, IsZUp, SetSilentMode required before UpdateStructure/AnalyzeModel/AnalyzeEx/SaveModel/file operations, UpdateStructure semantics, application control (ShowApplication, GetApplicationVersion, Quit), job metadata (GetFullJobInfo, GetShortJobInfo, SetFullJobInfo, SetShortJobInfo). Do not auto-save."
---

# STAAD.Pro Core — Sandbox & Model Setup

## Instructions

### Sandbox

- Pre-injected names (do NOT import): `staad`, `input_data`, `json`, `math`
- `import` statements, `dir()`, `getattr()`, ... are **BLOCKED** — use skills for discovery, only use pre-injected names in code
- `staad` is already connected and ready — do NOT call any initialization function
- `input_data` is injected if `input_data_path` is provided in `execute_code` params — use it to feed large datasets into the sandbox without hardcoding. CSV input is a list of row lists (the detected header is row 0); XLSX input is a `{sheet_name: {"columns": list, "rows": list_of_rows}}` dict.
- Sub-modules: `geo = staad.Geometry`, `prop = staad.Property`, `sup = staad.Support`, `load = staad.Load`, `cmd = staad.Command`, `out = staad.Output`, `design = staad.Design`
- If `output_data_path` is provided, write the `result` variable to that file path instead of returning it in the context (use for large/tabular data). The `execute_code` return value will contain a summary of the `result` content instead (e.g. number of rows, columns and a sample of rows).
- Both `input_data_path` and `output_data_path` must be on the user LOCAL filesystem and inside MCP roots or configured `allowed_dirs`. On Claude Desktop, users can configure allowed directories in the extension settings and Claude can use the filesystem `copy_file_to_claude` tool to move files to Claude's filesystem.
- `get_status` returns the currently configured `allowed_dirs` — the MCP server must be relaunched for a change to allowed directories to take effect, so re-call `get_status` after the user reconfigures them rather than trusting an `allowed_dirs` value from earlier in the conversation.

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

**The API follows one standard convention: setters consume the current input
unit setting and convert it to base units for storage; getters return a
fixed base-unit value.** `staad.GetBaseUnit()` (`"English"` = inches + KIP,
`"Metric"` = meters + kN) tells you the base system; `staad.GetInputUnitForLength()`/
`staad.GetInputUnitForForce()` tell you what unit a setter currently expects.

- `staad.GetBaseUnit()` → `"English"` or `"Metric"` — the model's underlying base unit system, and what every getter returns values in.
- `staad.Geometry.IsZUp()` → `True` if Z is up.
- `staad.GetInputUnitForLength()` / `staad.GetInputUnitForForce()` — **read these to discover what unit a setter currently expects**, instead of calling `SetInputUnits`. E.g. `CreatePlateThicknessProperty([50.0]*4)` while `GetInputUnitForLength()` reports `"Meter"` stores `1968.5` in (`50 × 39.3701`); the same call with `2.0` while it reports `"Feet"` stores `24` in (`2 × 12`). Convert the user's value into whatever unit these getters currently report, then call the setter — this is non-mutating.
- `staad.SetInputUnits(lengthUnit, forceUnit)` → changes the current input unit setting (integer codes, see **[UNIT_CODES.md](./assets/UNIT_CODES.md)**). This **mutates and persists into the saved `.std` file** — only call it when the user explicitly wants to change the model's unit preference, not just to convert a value (prefer the read-then-convert approach above).
- **Exception — coordinate-valued `Add*`/`Get*` geometry functions** (`AddNode`, `GetNodeCoordinates`): always raw base-unit values, no conversion applied regardless of the current input unit setting. Convert user-given coordinates to base units yourself before calling these. (`AddBeam`/`AddPlate` take node ID integers, not coordinates, so this unit exception doesn't apply to them.)
  - **Careful:** the sibling `Create*` family (`CreateNode`, `CreateMultipleNodes`) looks like it only adds "an explicit ID" option, but it actually does NOT share this exception — it follows the standard convention (consumes current input units, converts to base), unlike `AddNode`. See staad-geometry for the live-verified proof. Don't assume `Add*` and `Create*` geometry functions share the same units behavior just because they look like thin variants of each other.
- `staad.Output.GetOutputUnitFor*` (Force, Moment, Displacement, Stress, …) is a separate, unrelated subsystem reporting the label the **STAAD.Pro UI** displays results in — use only as a display/reporting target when presenting values to the user (see staad-results → Output Units), never to decide how to convert an input value.
- **Compound units are built from `GetInputUnitForLength()`/`GetInputUnitForForce()` combined**, not a separate lookup: stress-type parameters (E, G, Fy, Fu) are force/length², unit weight/density is force/length³, distributed loads are force/length. A setter expecting stress never consumes MPa/GPa/psi directly — it consumes whatever `force_unit / length_unit²` those two getters currently report (e.g. kN/m² under Meter+kN, ksi under Inch+Kip). Passing a textbook value in a different unit (e.g. `E=200000` meant as MPa) silently stores the wrong stiffness by whatever factor separates the two units — the size and direction of that error depends on the current unit system, so don't assume a fixed multiplier. Always convert the value into the compound unit built from the current getters before calling the setter (see staad-properties → Materials).

```python
# Standard pattern: discover current input unit, convert the user's value into
# it, call the setter, then read back with a getter — result is base units.
staad.SetSilentMode(True)
length_unit = staad.GetInputUnitForLength()      # e.g. "Meter"
force_unit = staad.GetInputUnitForForce()        # e.g. "KiloNewton"
# ... convert the user's value from whatever unit they gave you into length_unit/force_unit ...
mat_id = staad.Support.CreatePlateMat(2, [subgrade_in_current_units]*3, 0, 0)
subgrade_base = staad.Support.GetPlateMatDetail(mat_id)[1]   # always base units, regardless of current input unit
staad.SetSilentMode(False)
```

If a function isn't covered above and you're unsure of its convention, verify
empirically: call the setter with a known value under one `SetInputUnits`
setting, then again under another, and compare the stored/returned number
against the known conversion factor. If no getter exists at all (e.g.
`AddEnclosedZoneLoad`), verify through a real analysis instead — build a small
symmetric test structure (e.g. a square panel with 4 identical pinned
corners) where equilibrium + symmetry predicts an exact reaction split, run
the solver, and compare `GetSupportReactions` against the hand-calculated
expected value in base units.

Convert all user-provided dimensions into whatever unit the target setter
currently expects (per above) before passing to the API, convert results back
from base units when reporting to the user, and do NOT call `SetInputUnits`
unless the user explicitly asks to change the model's unit setting.

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
- `staad.NewSTAADFile(filePath, lengthUnit, forceUnit)` — create a new STAAD model file. `lengthUnit`/`forceUnit` are integer unit codes (see **[UNIT_CODES.md](./assets/UNIT_CODES.md)**), NOT an environment/template code — e.g. `(4, 5)` = Meter/kN (Metric), `(1, 0)` = Feet/Kip (English). Always creates an **Analytical** model file — there is no parameter to create a Physical Modeller file.
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

# Create a new Metric model (4=Meter, 5=KiloNewton)
staad.NewSTAADFile("C:\\Projects\\NewModel\\frame.std", 4, 5)

# Create a new English model (1=Feet, 0=Kilopound)
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
- If `input_data_path` is provided, `input_data` is injected as fresh lists/dicts — use it to feed large datasets into the sandbox without hardcoding
- If `output_data_path` is provided, write the `result` variable to that file path instead of returning it in the context (use for large/tabular data). The `execute_code` return value will contain a summary of the `result` content instead (e.g. number of rows, columns and a sample of rows).
- Both `input_data_path` and `output_data_path` must be on the user LOCAL filesystem and inside MCP roots or configured `allowed_dirs`. On Claude Desktop, users can configure allowed directories in the extension settings and Claude can use the filesystem `copy_file_to_claude` tool to move files to Claude's filesystem.
- Use `staad.GetSTAADFile()` to get the current model path after a file switch
- Always wrap `UpdateStructure`/`AnalyzeModel`/`AnalyzeEx`/`SaveModel` inside `SetSilentMode(True/False)`
- **Never** call `SaveModel` without explicit user instruction
- `UpdateStructure` **discards** in-memory geometry not yet on disk — use `SaveModel(True)` instead when you need to flush before support/load assignment
- `AnalyzeEx` runs both analysis AND design; `AnalyzeModel` runs analysis only
- Units convention: setters consume the **current input unit setting** and convert to base for storage; getters return a **fixed base-unit value** (`GetBaseUnit()` tells you what that is). Coordinate-valued functions (`AddNode`, `GetNodeCoordinates`) are the exception — always base units, ignores the input unit setting entirely (`AddBeam`/`AddPlate` take node IDs, not coordinates, so this exception is moot for them); but the sibling `Create*` family (`CreateNode`, etc.) does NOT share this exception despite looking like a thin ID-labeling variant — it follows the standard conversion (see staad-geometry). Use `GetInputUnitForLength()`/`GetInputUnitForForce()` to discover what unit a setter currently expects instead of calling `SetInputUnits` (which mutates and persists into the saved model); `GetOutputUnitFor*` is a separate UI-display-only subsystem, useful as a conversion target when reporting values, never as a description of what an input API consumed

