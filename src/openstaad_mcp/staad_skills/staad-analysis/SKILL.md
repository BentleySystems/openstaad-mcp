---
name: staad-analysis
description: 'Use when running structural analysis, solving the model, or executing the STAAD.Pro solver. Covers: PerformAnalysis (adds PERFORM ANALYSIS command — call once only), AnalyzeModel (linear static solver — requires SaveModel first), AnalyzeEx (analysis + design in one call — use for design workflows), P-Delta analysis (PerformPDeltaAnalysisEx), buckling analysis (PerformBucklingAnalysis/Ex), cable analysis, direct analysis (AISC), nonlinear analysis (PerformNonlinearAnalysisEx), print options, DeleteAllAnalysisCommands, CreateSteelDesignCommand. Two steps required for static analysis. Requires staad-core.'
---

# STAAD.Pro Analysis

## Instructions

### Linear Static Analysis (two steps)
1. `cmd.PerformAnalysis(printOption)` — adds the `PERFORM ANALYSIS` command. Call **ONCE only**.
2. `staad.SaveModel(true)` + `staad.AnalyzeEx(1, 0, 1)` — saves the file, then runs the solver.

Both steps are required. `PerformAnalysis` alone does NOT run the solver.

### Running the Solver — prefer `AnalyzeEx`
`AnalyzeEx` is the **preferred** solver function — it returns a status code and runs both analysis and design.
`AnalyzeModel` is a simpler alternative with no return value (analysis only, no design).

**Always cache load case numbers before running the solver** — they may become unqueryable after analysis completes (see "Reloading Results" below).

```javascript
const cmd = staad.Command;
const load = staad.Load;

// Cache BEFORE analysis
const cases = load.GetPrimaryLoadCaseNumbers();
const combos = load.GetLoadCombinationCaseNumbers();

staad.SetSilentMode(true);
staad.SaveModel(true);
const status = staad.AnalyzeEx(1, 0, 1);  // silent, visible, waitTillComplete
staad.SetSilentMode(false);
// status: 2=OK, 3=warnings, 4=errors, -1=terminated
```

### Reloading Results After Analysis
After `AnalyzeEx` or `AnalyzeModel` returns, results may already be in the COM object's memory. **Do not call `UpdateStructure()` immediately** — it can clear
the load-case list and break subsequent queries.

Follow this pattern:
1. **Cache load case numbers BEFORE running analysis** — `GetPrimaryLoadCaseNumbers()`
   may return empty after reload, so never re-query them post-analysis.
2. After `AnalyzeEx` returns, query a result directly using a cached case number.
3. Only if that returns all zeros, try ONE `UpdateStructure()` call and retry.
4. **NEVER use `OpenSTAADFile` / `CloseSTAADFile` to reload** — they trigger consent
   prompts and are unnecessary.

```javascript
// BEFORE analysis — cache these
const load = staad.Load;
const cases = load.GetPrimaryLoadCaseNumbers();
const combos = load.GetLoadCombinationCaseNumbers();

// Run analysis
staad.SetSilentMode(true);
staad.SaveModel(true);
const status = staad.AnalyzeEx(1, 0, 1);
staad.SetSilentMode(false);
console.log("Analysis status:", status);  // 2=OK, 3=warnings

// Verify results using CACHED case numbers
const out = staad.Output;
let r = out.GetSupportReactions(supportNodes[0], cases[0]);
if (r.every(v => v === 0)) {
  // Fallback: one UpdateStructure attempt
  staad.SetSilentMode(true);
  staad.UpdateStructure();
  staad.SetSilentMode(false);
  r = out.GetSupportReactions(supportNodes[0], cases[0]);
}
console.log("Sample reaction:", JSON.stringify(r));
```

**Known quirks:**
- `AreResultsAvailable()` often returns `false` even when results are queryable — do not use it
- `GetPrimaryLoadCaseNumbers()` may return `[]` after `UpdateStructure()` — always use cached values
- `UpdateStructure()` is consent-free but can clear COM state — use only as a fallback

### Print Options

| Value | Output |
|-------|--------|
| 0 | No print |
| 1 | Load data |
| 2 | Statics check |
| 3 | Statics load |
| 4 | Mode shapes |
| 5 | Both |
| 6 | All |

### P-Delta Analysis
```javascript
const cmd = staad.Command;
cmd.PerformPDeltaAnalysisNoConverge(5, 0);   // iterations, printOption

cmd.PerformPDeltaAnalysisEx(
    20,   // NoOfIterations
    0,    // PrintOption
    1,    // bSmallDelta (1=P-small-delta, 0=P-large-delta)
    1     // AddGeometricStiffness
);
```

### Buckling Analysis
```javascript
cmd.PerformBucklingAnalysis(10, 0);  // maxIterations, printOption

cmd.PerformBucklingAnalysisEx(
    0,   // Method: 0=Iterative, 1=Eigen
    15,  // MaxNoOfIterations
    0    // PrintOption
);
```

### Cable Analysis
```javascript
cmd.PerformCableAnalysis(25, 0);

cmd.PerformCableAnalysisEx(
    1,                                         // AdvancedCableAnalysis
    [1, 0],                                    // [REFORM, KGEOM]
    [145, 300, 1e-4, 0.0, 1.0, 1, 0.0],        // Params
    0                                           // PrintOption
);
```

### Direct Analysis (AISC)
```javascript
cmd.PerformDirectAnalysis(
    1,                            // Option: 1=LRFD, 2=ASD
    [0.01, 0.01, 1, 15],          // [TAUTOL, DISPTOL, ITERDIRECT, PDiter]
    [0, 0],                       // [REDUCEDEI, TBITER]
    0                              // PrintOption
);
```

### Nonlinear Analysis
```javascript
cmd.PerformNonlinearAnalysisEx(
    0,            // PrintOption
    0.0,          // Arclength
    5,            // NoOfIterations
    0.0009,       // Tolerance
    10,           // Steps
    0,            // Rebuild
    1,            // AddGeometricStiffness
    [joint, dof, target]   // DispLimitData: DOF 1-3=trans, 4-6=rot
);
```

### Floor Diaphragm
```javascript
cmd.SetFloorDiaphragmBaseCommand(elevation);
cmd.DeleteFloorDiaphragmBaseCommand();
```

### Seismic Check Commands
```javascript
cmd.SetCheckSoftStoryCommand(3);          // DesignCode
cmd.SetCheckIrregularitiesCommand(3);
```

### Delete Commands
```javascript
cmd.DeleteAllAnalysisCommands();
```

### Steel Design via Command (Low-Level)
```javascript
cmd.CreateSteelDesignCommand(
    1067,       // NDesignCode
    9380,       // NCommandNo
    [1],        // IntValues
    [],         // FloatValues
    [],         // StringValues
    [1, 2, 3]   // NAssignList
);
```
For workflows, prefer the staad-design skill which uses the `Design` sub-module.

## Example
See [run-analysis.js](./scripts/run-analysis.js) for a complete working example.

## Gotchas
- Do NOT call `PerformAnalysis` more than once — it adds duplicate commands - Must call `SaveModel` before `AnalyzeModel` — the engine reads from the `.std` file on disk
- Wrap `AnalyzeModel`/`AnalyzeEx` in `SetSilentMode(true/false)` to prevent blocking dialogs
- For design workflows always use `AnalyzeEx(1, 0, 1)` — never `AnalyzeModel` - `AnalyzeEx` runs both analysis AND design; `AnalyzeModel` runs analysis only
- **Status 3 (warnings) usually still produces valid results** — do NOT treat it as failure. Always check `out.AreResultsAvailable()` after any non-error status
- If `AreResultsAvailable()` returns `false` after a successful analysis (status 2 or 3), call `staad.UpdateStructure()` to reload results from disk, then check again
