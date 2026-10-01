---
name: staad-analysis
description: 'Use when running structural analysis, solving the model, or executing the STAAD.Pro solver. Covers: PerformAnalysis (adds PERFORM ANALYSIS command — call once only), AnalyzeEx (preferred solver — analysis + design, returns status; requires SaveModel first), GetAnalysisErrorMessages / GetAnalysisWarningMessages (STAAD.Pro v26+), GetAnalysisStatus, P-Delta analysis (PerformPDeltaAnalysisEx, PerformPDeltaAnalysisNoConverge), buckling analysis (PerformBucklingAnalysisEx), cable analysis (PerformCableAnalysisEx), direct analysis AISC (PerformDirectAnalysis), nonlinear analysis (PerformNonlinearAnalysisEx), print options, floor diaphragm base elevation (Set/DeleteFloorDiaphragmBaseCommand — writes BASE into an existing FLOOR DIAPHRAGM block), seismic checks on an existing floor diaphragm (Set/DeleteCheckSoftStoryCommand, Set/DeleteCheckIrregularitiesCommand), DeleteAllAnalysisCommands, CreateSteelDesignCommand. Two steps required for static analysis. Requires staad-core.'
---

# STAAD.Pro Analysis

## Instructions

### Linear Static Analysis (two steps)
1. `cmd.PerformAnalysis(printOption)` — adds the `PERFORM ANALYSIS` command. Call **ONCE only**.
2. `staad.SaveModel(True)` + `staad.AnalyzeEx(1, 0, 1)` — saves the file, then runs the solver.

Both steps are required. `PerformAnalysis` alone does NOT run the solver.

### Running the Solver — `AnalyzeEx`
`AnalyzeEx` is the solver function to use — it returns a status code and runs both analysis and design.

**Rule:** when a method has an `*Ex` variant, use the `*Ex` form. The older non-`Ex` methods (`AnalyzeModel`,
`PerformBucklingAnalysis`, `PerformCableAnalysis`) remain available for legacy scripts.

```python
cmd = staad.Command
cmd.PerformAnalysis(0)  # adds the PERFORM ANALYSIS command — call once only, before AnalyzeEx
staad.SetSilentMode(True)
staad.SaveModel(True)
status = staad.AnalyzeEx(1, 0, 1)  # silent, visible, waitTillComplete
staad.SetSilentMode(False)
# status: 2=OK, 3=warnings, 4=errors, -1=terminated
```

### Analysis Messages *(Requires STAAD.Pro v26+)*

After a run, retrieve the solver's error/warning text. These COM functions exist
only on **STAAD.Pro v26+** — confirm the connected instance's version from
`list_instances` / `get_status` before calling (see staad-core → Version
Compatibility). On older STAAD they raise an "update STAAD.Pro" error.

These methods live on the root `staad` object.

```python
errors = staad.GetAnalysisErrorMessages()     # solver error messages
warnings = staad.GetAnalysisWarningMessages()  # solver warning messages
```

`GetAnalysisStatus()` raises an exception when the run returned an error
(negative) status code — `execute_code` reports it; no `try/except` needed unless
you want to continue after a failure.

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
```python
cmd = staad.Command
cmd.PerformPDeltaAnalysisEx(
    NoOfIterations=20, PrintOption=0,
    bSmallDelta=1,            # 1=P-small-delta, 0=P-large-delta
    AddGeometricStiffness=1   # 1=include geometric stiffness
)

# Fixed iteration count with no convergence check:
cmd.PerformPDeltaAnalysisNoConverge(NoOfIterations=5, PrintOption=0)
```

### Buckling Analysis
```python
cmd.PerformBucklingAnalysisEx(
    Method=0,                # 0=Iterative, 1=Eigen
    MaxNoOfIterations=15, PrintOption=0
)
```

### Cable Analysis
```python
cmd.PerformCableAnalysisEx(
    AdvancedCableAnalysis=1,
    AdvOptions=[1, 0],   # [REFORM, KGEOM]
    Params=[145, 300, 1e-4, 0.0, 1.0, 1, 0.0],
    PrintOption=0
)
```

### Direct Analysis (AISC)
```python
cmd.PerformDirectAnalysis(
    Option=1,                      # 1=LRFD, 2=ASD
    Params=[0.01, 0.01, 1, 15],    # [TAUTOL, DISPTOL, ITERDIRECT, PDiter]
    AddOptions=[0, 0],             # [REDUCEDEI, TBITER]
    PrintOption=0
)
```

### Nonlinear Analysis
```python
cmd.PerformNonlinearAnalysisEx(
    PrintOption=0, Arclength=0.0,
    NoOfIterations=5, Tolerance=0.0009,
    Steps=10, Rebuild=0,
    AddGeometricStiffness=1,
    DispLimitData=[joint, DOF, target]  # DOF: 1-3=trans, 4-6=rot
)
```

### Floor Diaphragm Base Elevation
These methods write the `BASE` elevation line of an **existing** `FLOOR DIAPHRAGM` block; they
leave the diaphragms themselves unchanged. The model needs a `FLOOR DIAPHRAGM` command with at least one
`DIA` data line (defined in the `STAAD.Pro` UI or `.std` input) — OpenSTAAD has no method that
creates diaphragms.

```python
# Required input already in the model:
#   FLOOR DIAPHRAGM
#   DIA 1 TYPE RIG HEI 3
#   DIA 2 TYPE RIG HEI 6
ok = cmd.SetFloorDiaphragmBaseCommand(2.54)  # elevation in current input length unit → writes "BASE 2.54"
ok = cmd.DeleteFloorDiaphragmBaseCommand()   # removes the BASE line
```

- Both return `1` on success and `0` on failure, without raising — check the return value.
- `SetFloorDiaphragmBaseCommand` returns `0` when the model has no `FLOOR DIAPHRAGM` + `DIA` data. With a
  `BASE` line already present it updates the value in place (one `BASE` line per model).
- `DeleteFloorDiaphragmBaseCommand` returns `0` when there is no `BASE` line to remove.
- Call `SaveModel(True)` to persist the change to the `.std` file.

### Seismic Check Commands
Same prerequisite and return convention as the base command: an existing `FLOOR DIAPHRAGM` block with `DIA`
data, `1` = added/updated in place, `0` = not applied (missing diaphragm or unsupported code).

```python
cmd.SetCheckSoftStoryCommand(DesignCode=2)       # 1=IS1893 2002, 2=ASCE7 05/10/16, 3=IS1893 2016
cmd.SetCheckIrregularitiesCommand(DesignCode=2)  # 2=ASCE 7 2016, 3=IS1893 2016
cmd.DeleteCheckSoftStoryCommand()                # 0 when no CHECK SOFT STORY line exists
cmd.DeleteCheckIrregularitiesCommand()           # 0 when no CHECK IRREGULARITIES line exists
```

### Delete Commands
```python
cmd.DeleteAllAnalysisCommands()
```

### Steel Design via Command (Low-Level)
```python
cmd.CreateSteelDesignCommand(
    NDesignCode=1067, NCommandNo=9380,
    IntValues=[1], FloatValues=[], StringValues=[],
    NAssignList=[1, 2, 3]
)
```
For workflows, prefer the staad-steel-design skill which uses the `Design` sub-module.

## Example
See [run-analysis.py](./scripts/run-analysis.py) for a complete working example.
See [check-analysis-results.py](./scripts/check-analysis-results.py) for the recommended status/error check before querying `Output` results.

## Gotchas
- Do NOT call `PerformAnalysis` more than once — it adds duplicate commands
- Call `SaveModel` before `AnalyzeEx` — the engine reads from the `.std` file on disk
- Wrap `AnalyzeEx` in `SetSilentMode(True/False)` to prevent blocking dialogs
- `AnalyzeEx(1, 0, 1)` runs both analysis and design; the legacy `AnalyzeModel` runs analysis only
- **Compression-only springs/supports (elastic mat, plate mat with `springType=1`) are incompatible with P-Delta, Nonlinear, Buckling, and Cable analysis** — the engine uses member/spring deactivation iterations that cannot coexist with geometric nonlinearity or those other solver loops. The engine will throw an error. Use plain `PerformAnalysis` + `AnalyzeEx` for models with compression-only supports.
- **After `AnalyzeEx` returns status `4` (errors) or `-1` (terminated), do NOT call `Output` getters directly** — querying results from a failed/incomplete run has been observed to raise a misleading, unrelated-looking `COMError: Memory is locked.` instead of a clear "results not available" message. Always check the status code and `out.AreResultsAvailable()` first, and read `staad.GetAnalysisErrorMessages()` to see the actual cause (e.g. a member missing a material) — see [check-analysis-results.py](./scripts/check-analysis-results.py)
- If a script needs to change properties/loads and re-run analysis in a loop (e.g. iteratively resizing members until a result target is met), each `SaveModel`+`AnalyzeEx` cycle can take several seconds — looping more than a few iterations inside a single `execute_code` call risks hitting the tool's execution timeout with no partial results returned. Split long iterative loops across multiple `execute_code` calls (one or a few iterations per call) instead of one large loop
