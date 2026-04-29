---
name: staad-core
description: 'ALWAYS load first for any STAAD.Pro automation. Covers: JavaScript sandbox (staad pre-injected — import/require blocked), sub-module access (Geometry, Property, Support, Load, Command, Output, Design), units and axis check via execute_code, unit conversion (English=inches/KIP, Metric=meters/kN), GetBaseUnit, IsZUp, SetSilentMode required before UpdateStructure/AnalyzeModel/AnalyzeEx/SaveModel/file operations, UpdateStructure semantics, file operations (OpenSTAADFile, CloseSTAADFile), application control (ShowApplication, GetApplicationVersion, Quit). Do not auto-save.'
---

# STAAD.Pro Core — Sandbox & Model Setup

## Instructions

### Sandbox
- Pre-injected names (do NOT import): `staad`, `console`
- `import` / `require` / network / filesystem are **physically unavailable** — user code runs inside a WebAssembly isolate that only exposes `staad` and `console`
- Standard JavaScript built-ins (`JSON`, `Math`, `Array`, `Object`, `Number`, `String`, `Map`, `Set`, `Date`, etc.) are available as usual
- `staad` is already connected and ready — do NOT call any initialization function
- Sub-modules: `const geo = staad.Geometry;`, `const prop = staad.Property;`, `const sup = staad.Support;`, `const load = staad.Load;`, `const cmd = staad.Command;`, `const out = staad.Output;`, `const design = staad.Design;`

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
  - `staad.Geometry.IsZUp()` → `true` if Z is up
  - `staad.GetInputUnitForLength()` / `staad.GetInputUnitForForce()` → current input unit strings
- `English` = inches + KIP; `Metric` = meters + kN
- Y-up: vertical axis is Y; Z-up: vertical axis is Z
- Convert all user-provided dimensions to the base unit before passing to the API
- Do NOT change the unit system unless the user explicitly asks
- `staad.SetInputUnits(lengthUnit, forceUnit)` → change input units (integer codes)

### Base Unit vs Input Unit — CRITICAL
- `GetBaseUnit()` returns the **internal** base unit, which is almost always `"English"` (inches + KIP) regardless of what `SetInputUnits` or `NewSTAADFile` specifies
- `NewSTAADFile(path, 4, 5)` creates a model with Meter/kN **input** units, but `GetBaseUnit()` still returns `"English"` — the base unit does not change
- **All COM API methods** (`AddNode`, `AddBeam`, `GetNodeCoordinates`, etc.) operate in the **base unit** (inches for English), **not** the input unit
- If the user provides dimensions in meters, you **must** convert to inches before calling API methods on an English-base model

```javascript
// Conversion helper — call once per script
const baseUnit = staad.GetBaseUnit();
const toBaseLength = (val, fromUnit) => {
  if (baseUnit === 'English') {
    if (fromUnit === 'm')  return val * 39.3701;   // meters → inches
    if (fromUnit === 'mm') return val * 0.0393701;  // mm → inches
    if (fromUnit === 'ft') return val * 12.0;       // feet → inches
  } else {  // Metric base
    if (fromUnit === 'in') return val * 0.0254;     // inches → meters
    if (fromUnit === 'ft') return val * 0.3048;     // feet → meters
    if (fromUnit === 'mm') return val * 0.001;      // mm → meters
  }
  return val;  // already in base unit
};
const toBaseForce = (val, fromUnit) => {
  if (baseUnit === 'English') {
    if (fromUnit === 'kN') return val * 0.2248;     // kN → KIP
    if (fromUnit === 'N')  return val * 0.000224809; // N → KIP
    if (fromUnit === 'kgf') return val * 0.00220462; // kgf → KIP
  } else {  // Metric base
    if (fromUnit === 'KIP') return val * 4.44822;   // KIP → kN
  }
  return val;
};
```

- **Last resort — STD command file approach:** For complex models where unit conversion is error-prone (mixed unit sections, concrete design commands, repeat loads), write the model as a `.std` command text file with explicit `UNIT` commands and open it via `OpenSTAADFile(path)`. The STAAD command language handles unit switches natively (e.g., `UNIT METER KN` then `UNIT KGF METER`). Only use this when API-based modeling with unit conversion has failed or would be unreliable.

### SetSilentMode
`SetSilentMode(true)` MUST be called before these operations (they trigger UI dialogs that block automation):
- `NewSTAADFile`, `OpenSTAADFile`, `CloseSTAADFile`
- `UpdateStructure`, `SaveModel`
- `AnalyzeModel`, `AnalyzeEx`

Always restore with `SetSilentMode(false)` at the end of the script.

### UpdateStructure vs SaveModel
- `UpdateStructure()` = **reload from disk** — it discards all in-memory `AddNode`/`AddBeam` state that has not yet been written to disk. If you call it after adding geometry in the same script, **all that geometry is lost**.
- `SaveModel(true)` = write current in-memory state to disk **without reloading** — use this to flush geometry before assigning supports/loads in the same script session.
- **Rule:** whenever geometry was added in-memory and the next step requires file-based state (supports, loads, sections), use `SaveModel(true)` — not `UpdateStructure()`.
- `UpdateStructure` is only safe to call when the current in-memory state already matches what is on disk.
- Do NOT call after `AddNode`/`AddBeam` just to query geometry — COM geometry APIs read from the in-memory buffer immediately.

### SaveModel — REQUIRE EXPLICIT USER INTENT
- Do NOT call `SaveModel()` casually — only when:
  1. The user explicitly asks to save, **or**
  2. You are about to run analysis (the engine reads the `.std` file from disk), **or**
  3. Geometry was added in-memory and the next step needs file-based state (supports, loads)

### File Operations — REQUIRE EXPLICIT USER INTENT
**NEVER call these without the user explicitly asking:**
- `staad.NewSTAADFile(path, lenUnit, forceUnit)` — creates a brand-new model file and discards the current one. `AddNode`/`AddBeam` may fail in the same `execute_code` call — run geometry in a follow-up call after the file is created.
- `staad.OpenSTAADFile(path)` — closes the current model and opens a different file
- `staad.CloseSTAADFile()` — closes the current model

Always work on the **currently open model**. If the user says "create a model", that means add geometry/properties to the current open model — not create a new file.

- After any file operation, `staad` and all sub-objects remain valid — do NOT reinitialize
- Use `staad.GetSTAADFile()` to verify which file is open (returns full path; empty string if none)
- `staad.GetSTAADFileFolder()` returns the folder path
- **Confirm file opened:** After `OpenSTAADFile`, always call `GetSTAADFile()` to verify — do NOT call `OpenSTAADFile` again if the first call returned no error

### Application Control
- `staad.ShowApplication()` — show the STAAD.Pro window
- `staad.GetApplicationVersion()` → version string
- `staad.IsPhysicalModel()` → true if physical model mode
- `staad.Quit()` — close the application (use with caution)

### Analysis Shortcuts
- `staad.AnalyzeEx(silentMode, hiddenMode, waitTillComplete)` → status code
  - Return codes: `2` = OK, `3` = warnings, `4` = errors, `-1` = terminated
  - Always use `silentMode=1, waitTillComplete=1` for automation
- `staad.AnalyzeModel()` — simplified, no return value

## Example
See [create-new-model.js](./scripts/create-new-model.js) for a complete working example.

## Gotchas
- `import` / `require` are blocked — only `staad` and `console` are available (plus JS built-ins)
- `staad` stays valid after `OpenSTAADFile`/`CloseSTAADFile` — never reinitialize
- Use `staad.GetSTAADFile()` to get the current model path after a file switch
- Always wrap `UpdateStructure`/`AnalyzeModel`/`AnalyzeEx`/`SaveModel` inside `SetSilentMode(true/false)`
- **Never** call `NewSTAADFile`, `OpenSTAADFile`, `CloseSTAADFile`, or `SaveModel` without explicit user instruction
- `UpdateStructure` **discards** in-memory geometry not yet on disk — use `SaveModel(true)` instead when you need to flush before support/load assignment
- `AnalyzeEx` runs both analysis AND design; `AnalyzeModel` runs analysis only
- COM methods return native JS values: scalars come back as-is; COM tuples/arrays come back as JS arrays; `null` is used where Python would see `None`
