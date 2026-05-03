---
name: staad-results
description: 'ALWAYS load this skill before calling any staad.Output function — it covers the mandatory AreResultsAvailable() check and critical gotchas that affect every results query. Use when fetching analysis output: member end forces, bending moments, shear forces, axial forces, node displacements, support reactions, plate center/corner stresses, solid stresses, modal frequencies, buckling factors, time-history responses, steel design ratios. Covers: AreResultsAvailable (always check first), GetPrimaryLoadCaseNumbers (returns tuple — wrap in list()), GetMemberEndForces, GetMinMaxBendingMoment (dir is string not int), GetMinMaxShearForce, GetMinMaxAxialForce, GetNodeDisplacements, GetSupportReactions, GetAllPlateCenterStressesAndMoments, GetAllSolidNormalStresses, GetNoOfModesExtracted, GetModeFrequency, GetBucklingFactor, GetTimeHistoryResponse, GetMemberSteelDesignResults, output units. Requires staad-core and staad-analysis.'
---

# STAAD.Pro Analysis Results

## Instructions

- Define shorthands once per script: `out = staad.Output`, `load = staad.Load`

### Always Check First
- `out.AreResultsAvailable()` → `True` if results exist; `False` if analysis has not run
- If `False`, run analysis before querying any results (see staad-analysis skill)

### Load Cases
- `load.GetPrimaryLoadCaseNumbers()` → returns a **tuple** — always wrap in `list()` before indexing
- Never hardcode load case numbers — always fetch dynamically

### Output Units
```python
out.GetOutputUnitForForce()         # e.g. "KIP"
out.GetOutputUnitForMoment()        # e.g. "KIP-IN"
out.GetOutputUnitForDisplacement()  # e.g. "in"
out.GetOutputUnitForStress()        # e.g. "KSI"
out.GetOutputUnitForDimension()
out.GetOutputUnitForRotation()
```

### Node Results

| Function | Returns |
|----------|---------|
| `GetNodeDisplacements(nid, lc)` | `[UX, UY, UZ, rX, rY, rZ]` |
| `GetSupportReactions(nid, lc)` | `[FX, FY, FZ, MX, MY, MZ]` (global) |

### Member Forces

| Function | Returns | Notes |
|----------|---------|-------|
| `GetMemberEndForces(bid, end, lc, local)` | `[FX,FY,FZ,MX,MY,MZ]` | end: 0=StartA, 1=EndB; local: 0=Local, 1=Global |
| `GetMinMaxAxialForce(bid, lc)` | `(min, minPos, max, maxPos)` | position along member |
| `GetMinMaxShearForce(bid, dir, lc)` | `(min, minPos, max, maxPos)` | dir: `'FY'` or `'FZ'` (string) |
| `GetMinMaxBendingMoment(bid, dir, lc)` | `(min, minPos, max, maxPos)` | dir: `'MY'` or `'MZ'` (string) |
| `GetMemberEndDisplacements(bid, end, lc)` | `[X,Y,Z,rX,rY,rZ]` | |
| `GetMaxSectionDisplacement(bid, dir, lc)` | `(maxDisp, position)` | dir: `"X"`, `"Y"`, `"Z"` |
| `GetMaxBeamStresses(bid, lc)` | stress tuple | |

### Intermediate Forces
```python
out.GetIntermediateMemberForcesAtDistance(bid, distance, lc)
out.GetIntermediateMemberTransDisplacements(bid, distance, lc)
out.GetIntermediateDeflectionAtDistance(bid, distance, lc)
```

### Plate Results
```python
# Center stresses [SQX, SQY, MX, MY, MXY, SX, SY, SXY]
out.GetAllPlateCenterStressesAndMoments(plateNo, lc)
out.GetAllPlateCenterForces(plateNo, lc)
out.GetAllPlateCenterMoments(plateNo, lc)
out.GetPlateCenterNormalPrincipalStresses(plateNo, lc)
out.GetAllPlateCenterPrincipalStressesAndAngles(plateNo, lc)
out.GetPlateCenterVonMisesStresses(plateNo, lc)

# Corner forces
out.GetPlateCornerForces(plateNo, cornerCode, lc)  # cornerCode = node number

# Stress at arbitrary point
out.GetPlateStressAtPoint(plateNo, lc, stressPoint, facingPoint)  # [x,y,z] lists
```

### Solid Results
```python
out.GetAllSolidNormalStresses(solidNo, corner, lc)    # corner 1-8
out.GetAllSolidShearStresses(solidNo, corner, lc)
out.GetAllSolidPrincipalStresses(solidNo, corner, lc)
out.GetAllSolidVonMisesStresses(solidNo, corner, lc)
```

### Modal Analysis Results
```python
n_modes = out.GetNoOfModesExtracted()
freq    = out.GetModeFrequency(modeNo)               # Hz
disp    = out.GetModalDisplacementAtNode(modeNo, nid) # [X,Y,Z,rX,rY,rZ]
factors = out.GetModalMassParticipationFactors(modeNo)
```

### Buckling Results
```python
if out.IsBucklingAnalysisResultsAvailable():
    n = out.GetNoOfBucklingFactors()
    factor = out.GetBucklingFactor(modeNo)
    disp = out.GetBucklingModeDisplacementAtNode(modeNo, nid)  # [X,Y,Z,rX,rY,rZ]
```

### Time-History Results
```python
delta, n_steps = out.GetTimeHistoryIntegrationStepInfo()
# DOF: 1-3=trans, 4-6=rot; response_type: 0=disp, 1=vel, 2=accel
responses = out.GetTimeHistoryResponse(lc, nid, dof, response_type)
resp_at_t = out.GetTimeHistoryResponseAtTime(lc, nid, dof, response_type, time)
resp_min, resp_max = out.GetTimeHistoryResponseMinMax(lc, nid, dof, response_type)
```

### Nonlinear Results
```python
n_steps = out.GetNLLoadStep(lc)
load_level, displacements = out.GetNLNodeDisplacements(nid, lc, loadStep)
```

### Steel Design Results
```python
# Single-block (all codes)
(code, status, ratio, allow, lc, loc, clause, section, forces, klr) = out.GetMemberSteelDesignResults(bid)
# status: 'PASS' or 'FAIL'; ratio > 1.0 = failure

ratio = out.GetMemberSteelDesignRatio(bid)       # -999=not designed, -1=no analysis
max_r = out.GetMemberSteelDesignMaxFailureRatio() # model-wide max
min_r = out.GetMemberSteelDesignMinFailureRatio() # model-wide min

# Multi-block (AISC 360 etc.)
if out.IsMultipleMemberSteelDesignResultsAvailable():
    n_blocks = out.GetSteelDesignParameterBlockCount()
    blk_name = out.GetSteelDesignParameterBlockNameByIndex(i)
    ratio = out.GetMultipleMemberSteelDesignRatio(blk_name, bid)
    max_ratio = out.GetMultipleMemberSteelDesignMaxRatio(bid)
```

### Physical Member Forces
```python
out.GetPMemberEndForces(memberNo, end, lc, localOrGlobal)
out.GetPMemberIntermediateForcesAtDistance(memberNo, distance, lc)
```

### Foundation Results
```python
out.GetStaticCheckResult(lc)
out.GetMatInfluenceAreas(nodeList)
out.GetBasePressures(lc, nodeList)
```

## Example
See [fetch-forces.py](./scripts/fetch-forces.py) for a complete working example.

## Gotchas
- `GetMinMaxShearForce` and `GetMinMaxBendingMoment` `dir` argument is a **string** (`'FY'`, `'MZ'`), not an integer
- `GetMemberEndForces` at end 0 (StartA) and end 1 (EndB) have opposite sign conventions
- `GetPrimaryLoadCaseNumbers()` returns a tuple — convert with `list()` before indexing
- `GetMemberSteelDesignResults` raises an error for members not in the design brief
- Always call `AreResultsAvailable()` before any output query
