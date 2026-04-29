---
name: staad-results
description: 'Use when fetching analysis output: member end forces, bending moments, shear forces, axial forces, node displacements, support reactions, plate center/corner stresses, solid stresses, modal frequencies, buckling factors, time-history responses, steel design ratios. Covers: AreResultsAvailable (always check first), GetPrimaryLoadCaseNumbers (returns array — index directly), GetMemberEndForces, GetMinMaxBendingMoment (dir is string not int), GetMinMaxShearForce, GetMinMaxAxialForce, GetNodeDisplacements, GetSupportReactions, GetAllPlateCenterStressesAndMoments, GetAllSolidNormalStresses, GetNoOfModesExtracted, GetModeFrequency, GetBucklingFactor, GetTimeHistoryResponse, GetMemberSteelDesignResults, output units. Requires staad-core and staad-analysis.'
---

# STAAD.Pro Analysis Results

## Instructions

- Define shorthands once per script: `const out = staad.Output;`, `const load = staad.Load;`

### Always Check First
- **Cache load case numbers BEFORE analysis** — `GetPrimaryLoadCaseNumbers()` may return `[]` after reload, so fetch them before `AnalyzeEx` and reuse the cached array for all post-processing queries
- After analysis, verify results by calling a result method directly with a cached case number (e.g. `GetSupportReactions(nodeId, cachedCase)`)
- `AreResultsAvailable()` often returns `false` even when results are queryable — do not use it as a gate
- Do NOT use `OpenSTAADFile` to force-reload — it triggers a consent prompt and is unnecessary

### Load Cases
- `load.GetPrimaryLoadCaseNumbers()` → returns a native JS array — index directly
- `load.GetLoadCombinationCaseNumbers()` → combination case numbers
- **Fetch once before analysis, cache for all post-processing** — do not re-query after analysis/reload

### Output Units
```javascript
out.GetOutputUnitForForce();         // e.g. "KIP"
out.GetOutputUnitForMoment();        // e.g. "KIP-IN"
out.GetOutputUnitForDisplacement();  // e.g. "in"
out.GetOutputUnitForStress();        // e.g. "KSI"
out.GetOutputUnitForDimension();
out.GetOutputUnitForRotation();
```

**CRITICAL — COM return units:**
All COM result methods return values in the model's **base English units** (KIP, inches, KSI, KIP-IN),
regardless of what input units the model uses. The `GetOutputUnitFor*` functions return the
**display unit** from STAAD output (used in the `.ANL` file), NOT the unit of COM return values.

| COM returns in | To convert to metric |
|----------------|---------------------|
| KIP (force) | × 4.44822 → kN; × 453.592 → kg |
| inches (length) | × 0.0254 → m; × 2.54 → cm |
| KSI (stress) | × 6894.76 → kN/m² (kPa) |
| KIP-IN (moment) | × 0.11298 → kN-m |
| KIP-IN/IN (moment/width) | × 4.44822 → kN-m/m |
| KIP/IN (force/width) | × 175.127 → kN/m |

### Node Results

| Function | Returns |
|----------|---------|
| `GetNodeDisplacements(nid, lc)` | `[UX, UY, UZ, rX, rY, rZ]` |
| `GetSupportReactions(nid, lc)` | `[FX, FY, FZ, MX, MY, MZ]` (global) |

### Member Forces

| Function | Returns | Notes |
|----------|---------|-------|
| `GetMemberEndForces(bid, end, lc, local)` | `[FX,FY,FZ,MX,MY,MZ]` | end: 0=StartA, 1=EndB; local: 0=Local, 1=Global |
| `GetMinMaxAxialForce(bid, lc)` | `[min, minPos, max, maxPos]` | position along member |
| `GetMinMaxShearForce(bid, dir, lc)` | `[min, minPos, max, maxPos]` | dir: `'FY'` or `'FZ'` (string) |
| `GetMinMaxBendingMoment(bid, dir, lc)` | `[min, minPos, max, maxPos]` | dir: `'MY'` or `'MZ'` (string) |
| `GetMemberEndDisplacements(bid, end, lc)` | `[X,Y,Z,rX,rY,rZ]` | |

```javascript
// Member end forces — all 4 arguments are required
const startLocal = out.GetMemberEndForces(bid, 0, lc, 0);  // start, local coords
const endGlobal  = out.GetMemberEndForces(bid, 1, lc, 1);  // end, global coords
// Returns [FX, FY, FZ, MX, MY, MZ]
```
| `GetMaxSectionDisplacement(bid, dir, lc)` | `[maxDisp, position]` | dir: `"X"`, `"Y"`, `"Z"` |
| `GetMaxBeamStresses(bid, lc)` | stress array | |

### Intermediate Forces
```javascript
out.GetIntermediateMemberForcesAtDistance(bid, distance, lc);
out.GetIntermediateMemberTransDisplacements(bid, distance, lc);
out.GetIntermediateDeflectionAtDistance(bid, distance, lc);
```

### Plate Results
```javascript
// Separate methods (preferred — reliable via COM)
out.GetAllPlateCenterForces(plateNo, lc);    // → [SQX, SQY, SX, SY, SXY]
out.GetAllPlateCenterMoments(plateNo, lc);   // → [MX, MY, MXY]

// Principal & Von Mises
out.GetPlateCenterNormalPrincipalStresses(plateNo, lc);         // → [topSmax, topSmin, botSmax, botSmin]
out.GetAllPlateCenterPrincipalStressesAndAngles(plateNo, lc);   // → [topSmax, topSmin, topAngle, botSmax, botSmin, botAngle]
out.GetPlateCenterVonMisesStresses(plateNo, lc);                // → [vonTop, vonBot]

// Combined method (may fail via COM — use separate methods above instead)
// out.GetAllPlateCenterStressesAndMoments(plateNo, lc);  // → [SQX, SQY, MX, MY, MXY, SX, SY, SXY]

// Corner forces
out.GetPlateCornerForces(plateNo, cornerCode, lc);  // cornerCode = node number
// → [FX, FY, FZ, MX, MY, MZ]

// Stress at arbitrary point
out.GetPlateStressAtPoint(plateNo, lc, stressPoint, facingPoint);  // [x,y,z] arrays
```

### Solid Results
```javascript
out.GetAllSolidNormalStresses(solidNo, corner, lc);    // corner 1-8
out.GetAllSolidShearStresses(solidNo, corner, lc);
out.GetAllSolidPrincipalStresses(solidNo, corner, lc);
out.GetAllSolidVonMisesStresses(solidNo, corner, lc);
```

### Modal Analysis Results
```javascript
const nModes  = out.GetNoOfModesExtracted();
const freq    = out.GetModeFrequency(modeNo);                 // Hz
const disp    = out.GetModalDisplacementAtNode(modeNo, nid);  // [X,Y,Z,rX,rY,rZ]
const factors = out.GetModalMassParticipationFactors(modeNo);
```

### Buckling Results
```javascript
if (out.IsBucklingAnalysisResultsAvailable()) {
    const n = out.GetNoOfBucklingFactors();
    const factor = out.GetBucklingFactor(modeNo);
    const disp = out.GetBucklingModeDisplacementAtNode(modeNo, nid);  // [X,Y,Z,rX,rY,rZ]
}
```

### Time-History Results
```javascript
const [delta, nSteps] = out.GetTimeHistoryIntegrationStepInfo();
// DOF: 1-3=trans, 4-6=rot; responseType: 0=disp, 1=vel, 2=accel
const responses = out.GetTimeHistoryResponse(lc, nid, dof, responseType);
const respAtT = out.GetTimeHistoryResponseAtTime(lc, nid, dof, responseType, time);
const [respMin, respMax] = out.GetTimeHistoryResponseMinMax(lc, nid, dof, responseType);
```

### Nonlinear Results
```javascript
const nSteps = out.GetNLLoadStep(lc);
const [loadLevel, displacements] = out.GetNLNodeDisplacements(nid, lc, loadStep);
```

### Steel Design Results
```javascript
// Single-block (all codes)
const [codeName, status, ratio, allow, lc, loc, clause, section, forces, klr] = out.GetMemberSteelDesignResults(bid);
// status: 'PASS' or 'FAIL'; ratio > 1.0 = failure

const ratio = out.GetMemberSteelDesignRatio(bid);          // -999=not designed, -1=no analysis
const maxR  = out.GetMemberSteelDesignMaxFailureRatio();   // model-wide max
const minR  = out.GetMemberSteelDesignMinFailureRatio();   // model-wide min

// Multi-block (AISC 360 etc.)
if (out.IsMultipleMemberSteelDesignResultsAvailable()) {
    const nBlocks = out.GetSteelDesignParameterBlockCount();
    const blkName = out.GetSteelDesignParameterBlockNameByIndex(i);
    const r = out.GetMultipleMemberSteelDesignRatio(blkName, bid);
    const maxRatio = out.GetMultipleMemberSteelDesignMaxRatio(bid);
}
```

### Physical Member Forces
```javascript
out.GetPMemberEndForces(memberNo, end, lc, localOrGlobal);
out.GetPMemberIntermediateForcesAtDistance(memberNo, distance, lc);
```

### Foundation Results
```javascript
out.GetStaticCheckResult(lc);
out.GetMatInfluenceAreas(nodeList);
out.GetBasePressures(lc, nodeList);
```

## Concrete, Timber & Aluminum Design Results

The COM API has **no methods** for reading concrete, timber, or aluminum design results.
Use the `read_analysis_output` MCP tool instead:

```
read_analysis_output(file_type="anl")
```

The `.ANL` file contains full design output for all materials:
- **Concrete**: required reinforcement, interaction ratios, crack widths, governing load cases
- **Timber**: utilization ratios, governing stress checks, load case details
- **Aluminum**: capacity ratios, buckling checks, governing clauses

This is the only way to programmatically access non-steel design results.
See the `staad-design` skill for the full design workflow.

## Example
See [fetch-forces.js](./scripts/fetch-forces.js) for a complete working example.

## Gotchas
- `GetMinMaxShearForce` and `GetMinMaxBendingMoment` `dir` argument is a **string** (`'FY'`, `'MZ'`), not an integer
- `GetMemberEndForces` at end 0 (StartA) and end 1 (EndB) have opposite sign conventions
- `GetPrimaryLoadCaseNumbers()` returns a JS array — use `cases[0]` directly
- `GetMemberSteelDesignResults` throws an error for members not in the design brief
- Always call `AreResultsAvailable()` before any output query
