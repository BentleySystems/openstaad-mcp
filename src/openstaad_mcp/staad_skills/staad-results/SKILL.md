---
name: staad-results
description: 'Use when fetching analysis output: member end forces, bending moments, shear forces, axial forces, node displacements, support reactions, plate center/corner stresses, solid stresses, modal frequencies, buckling factors, time-history responses, steel design ratios. Covers: AreResultsAvailable (always check first), GetPrimaryLoadCaseNumbers (returns tuple — wrap in list()), GetMemberEndForces, GetMinMaxBendingMoment (dir is string not int), GetMinMaxShearForce, GetMinMaxAxialForce, GetNodeDisplacements, GetSupportReactions, GetAllPlateCenterStressesAndMoments, GetAllSolidNormalStresses, GetNoOfModesExtracted, GetModeFrequency, GetBucklingFactor, GetTimeHistoryResponse, GetMemberSteelDesignResults; all results are returned in base units — use GetOutputUnitFor* as the conversion target when displaying values to the user. Requires staad-core and staad-analysis.'
---

# STAAD.Pro Analysis Results

## Instructions

- Define shorthands once per script: `out = staad.Output`, `load = staad.Load`

### Always Check First
- `out.AreResultsAvailable()` → `True` if results exist; `False` if analysis has not run
- If `False`, run analysis before querying any results (see staad-analysis skill)
- If the preceding `AnalyzeEx` returned status `4` (errors) or `-1` (terminated), do NOT call any `Output` getter yet — querying results from a failed run has been observed to raise a misleading `COMError: Memory is locked.` instead of a clear failure message. Check the status code and `AreResultsAvailable()` first, then read `staad.GetAnalysisErrorMessages()` for the real cause — see staad-analysis → [check-analysis-results.py](../staad-analysis/scripts/check-analysis-results.py)

### Load Cases
- `load.GetPrimaryLoadCaseNumbers()` → returns a **tuple** — always wrap in `list()` before indexing
- Never hardcode load case numbers — always fetch dynamically

### Output Units — results are in BASE units; convert for display

**Every result getter (`GetMemberEndForces`, `GetNodeDisplacements`,
`GetSupportReactions`, `GetAllPlateCenterStressesAndMoments`, etc.) returns numbers
in the model's base unit system** — the same units used by every input function
(see staad-core → Units & Axis: English=inches/KIP, Metric=meters/kN).
`staad.GetBaseUnit()` is the only source of truth for interpreting a returned value.

`GetOutputUnitFor*` report the unit the **STAAD.Pro UI** is currently configured to
display each result category in. Use them as the **target** of a conversion so the
values you report match what the user sees on screen — never as a description of
what the getters returned.

```python
out.GetOutputUnitForForce()         # e.g. "kN"
out.GetOutputUnitForMoment()        # e.g. "kN-m"
out.GetOutputUnitForDisplacement()  # e.g. "mm"
out.GetOutputUnitForStress()        # e.g. "N/mm2"
out.GetOutputUnitForDimension()     # e.g. "m"
out.GetOutputUnitForRotation()      # e.g. "rad"
out.GetOutputUnitForSectDimension() # e.g. "cm"
out.GetOutputUnitForSectArea()      # e.g. "cm2"
out.GetOutputUnitForSectInertia()   # e.g. "cm4"
out.GetOutputUnitForSectModulus()   # e.g. "cm3"
out.GetOutputUnitForDensity()       # e.g. "kg/m3"
out.GetOutputUnitForDistForce()     # e.g. "kN/m"
out.GetOutputUnitForDistMoment()    # e.g. "kN-m/m"
```

**Base unit → UI unit is rarely 1:1.** On a Metric model the base length is `m`
but the UI displays displacements in `mm` — a factor of 1000. Reporting a raw
`GetNodeDisplacements` value next to the `mm` label without converting overstates
or understates the result by three orders of magnitude, which silently breaks any
serviceability check (e.g. "is the drift under 10 mm?").

**Recommended reporting workflow:**

1. Read the raw value from the getter — it is in base units.
2. Do all engineering comparisons and calculations in base units (convert the
   user's limits/targets into base units, not the other way round).
3. Only when presenting a number to the user, convert it to the matching
   `GetOutputUnitFor*` unit and label it with that unit string.

```python
out = staad.Output
base = staad.GetBaseUnit()                     # 'English' or 'Metric'
disp_unit = out.GetOutputUnitForDisplacement()  # UI display unit, e.g. 'mm'

# Length conversion factors FROM the base length unit (Metric: m, English: in)
per_base_length = {
    'Metric':  {'m': 1.0, 'cm': 100.0, 'mm': 1000.0},
    'English': {'in': 1.0, 'ft': 1.0 / 12.0},
}
factor = per_base_length[base][disp_unit]

ux, uy, uz, rx, ry, rz = out.GetNodeDisplacements(node_id, lc)
print(f'Node {node_id} UY = {uy * factor:.3f} {disp_unit}')   # matches the STAAD.Pro UI
```

Build the factor table only for the unit strings you actually receive — read the
`GetOutputUnitFor*` value at runtime rather than assuming a fixed UI configuration,
and raise/report clearly if the returned string is one you have no factor for.

The `GetOutputUnitFor*` methods raise on error (e.g. if the model has no output
units established yet) — `execute_code` reports any such error.

### Analysis Messages

For the solver's error/warning text after a run (`GetAnalysisErrorMessages` /
`GetAnalysisWarningMessages`), see the staad-analysis skill.

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
out.GetIntermediateMemberAbsTransDisplacements(bid, distance, lc)  # relative displacement in LOCAL X/Y/Z (vs global for the Trans variant above)
```

### Plate Results
See **[PLATE_RESULT_INDICES.md](./assets/PLATE_RESULT_INDICES.md)** for the index→symbol meaning of each return value below.
```python
# Center stresses [SQX, SQY, MX, MY, MXY, SX, SY, SXY]
out.GetAllPlateCenterStressesAndMoments(plateNo, lc)
out.GetAllPlateCenterForces(plateNo, lc)
out.GetAllPlateCenterMoments(plateNo, lc)
out.GetPlateCenterNormalPrincipalStresses(plateNo, lc)
out.GetAllPlateCenterPrincipalStressesAndAngles(plateNo, lc)
out.GetAllPlateCenterPrincipalStressesAndAnglesEx(plateNo, lc)  # adds top/bottom max-shear stress to the 4 principal values, plus per-face angles
out.GetPlateCenterVonMisesStresses(plateNo, lc)

# Corner forces
out.GetPlateCornerForces(plateNo, cornerCode, lc)  # cornerCode = node number

# Stress at arbitrary point
out.GetPlateStressAtPoint(plateNo, lc, stressPoint, facingPoint)  # [x,y,z] lists

# Resultant force/moment along a cut line through a set of plates or a parametric surface
fx_fy_fz_mx_my_mz = out.GetResultantForceAlongLineForPlateList(plateIds, len(plateIds), lc, startXYZ, endXYZ, transformToGlobal, node1, node2, node3)
fx_fy_fz_mx_my_mz = out.GetResultantForceAlongLineForParametricSurface(surfaceName, plateCount, lc, startXYZ, endXYZ, facingXYZ, transformToGlobal, node1, node2, node3)
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
    # Full result tuple for one block (code, status, ratio, allowable, critical lc, clause, section)
    (code, status, ratio, allow, crit_lc, clause, section) = out.GetMultipleMemberSteelDesignResults(blk_name, bid)

# Design section name assigned by a completed design run (raises if not found — pre-analysis use GetSectionPropertyName instead)
section_name = out.GetMemberDesignSectionName(bid)
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
- `GetMinMaxShearForce`/`GetMinMaxBendingMoment` `dir` argument is a **string**, not an integer — `'FY'`/`'FZ'` for shear, `'MY'`/`'MZ'` for moment
- `GetMemberEndForces` at end 0 (StartA) and end 1 (EndB) have opposite sign conventions
- `GetPrimaryLoadCaseNumbers()` returns a tuple — convert with `list()` before indexing
- `GetMemberSteelDesignResults` raises an error for members not in the design brief
- Always call `AreResultsAvailable()` before any output query
- All result getters return values in **base units** (`GetBaseUnit()`). Compare against limits in base units, then convert to the `GetOutputUnitFor*` unit only when displaying to the user
- Base and UI units are often different by orders of magnitude — a Metric model returns displacements in **m** while the UI shows **mm** (×1000). Never label a raw getter value with a `GetOutputUnitFor*` string without converting it first
- Querying any `Output` getter right after a failed/errored `AnalyzeEx` (status `4` or `-1`) can raise `COMError: Memory is locked.` instead of a clear error — check `AreResultsAvailable()` and the analysis status first, see staad-analysis skill
