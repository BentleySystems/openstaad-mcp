---
name: staad-analysis
description: 'Use when running structural analysis, solving the model, or executing the STAAD.Pro solver. Covers: PerformAnalysis (adds PERFORM ANALYSIS command — call once only), AnalyzeModel (linear static solver — requires SaveModel first), AnalyzeEx (analysis + design in one call — use for design workflows), P-Delta analysis (PerformPDeltaAnalysisEx), buckling analysis (PerformBucklingAnalysis/Ex), cable analysis, direct analysis (AISC), nonlinear analysis (PerformNonlinearAnalysisEx), print options, DeleteAllAnalysisCommands, CreateSteelDesignCommand. Two steps required for static analysis. Requires staad-core.'
---

# STAAD.Pro Analysis

## Instructions

### Linear Static Analysis (two steps)
1. `cmd.PerformAnalysis(printOption)` — adds the `PERFORM ANALYSIS` command. Call **ONCE only**.
2. `staad.SaveModel(True)` + `staad.AnalyzeEx(1, 0, 1)` — saves the file, then runs the solver.

Both steps are required. `PerformAnalysis` alone does NOT run the solver.

### Running the Solver — prefer `AnalyzeEx`
`AnalyzeEx` is the **preferred** solver function — it returns a status code and runs both analysis and design.
`AnalyzeModel` is a simpler alternative with no return value (analysis only, no design).

```python
cmd = staad.Command
staad.SetSilentMode(True)
staad.SaveModel(True)
status = staad.AnalyzeEx(1, 0, 1)  # silent, visible, waitTillComplete
staad.SetSilentMode(False)
# status: 2=OK, 3=warnings, 4=errors, -1=terminated
```

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
cmd.PerformPDeltaAnalysisNoConverge(NoOfIterations=5, PrintOption=0)

cmd.PerformPDeltaAnalysisEx(
    NoOfIterations=20, PrintOption=0,
    bSmallDelta=1,            # 1=P-small-delta, 0=P-large-delta
    AddGeometricStiffness=1   # 1=include geometric stiffness
)
```

### Buckling Analysis
```python
cmd.PerformBucklingAnalysis(MaxNoOfIterations=10, PrintOption=0)

cmd.PerformBucklingAnalysisEx(
    Method=0,                # 0=Iterative, 1=Eigen
    MaxNoOfIterations=15, PrintOption=0
)
```

### Cable Analysis
```python
cmd.PerformCableAnalysis(NoOfIterations=25, PrintOption=0)

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

### Floor Diaphragm
```python
cmd.SetFloorDiaphragmBaseCommand(elevation)
cmd.DeleteFloorDiaphragmBaseCommand()
```

### Seismic Check Commands
```python
cmd.SetCheckSoftStoryCommand(DesignCode=3)
cmd.SetCheckIrregularitiesCommand(DesignCode=3)
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

## Gotchas
- Do NOT call `PerformAnalysis` more than once — it adds duplicate commands
- Must call `SaveModel` before `AnalyzeModel` — the engine reads from the `.std` file on disk
- Wrap `AnalyzeModel`/`AnalyzeEx` in `SetSilentMode(True/False)` to prevent blocking dialogs
- For design workflows always use `AnalyzeEx(1, 0, 1)` — never `AnalyzeModel`
- `AnalyzeEx` runs both analysis AND design; `AnalyzeModel` runs analysis only
- **Compression-only springs/supports (elastic mat, plate mat with `springType=1`) are incompatible with P-Delta, Nonlinear, Buckling, and Cable analysis** — the engine uses member/spring deactivation iterations that cannot coexist with geometric nonlinearity or those other solver loops. The engine will throw an error. Use plain `PerformAnalysis` + `AnalyzeEx` for models with compression-only supports.
