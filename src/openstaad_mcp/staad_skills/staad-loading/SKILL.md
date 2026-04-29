---
name: staad-loading
description: 'Use when defining load cases, applying self-weight, nodal loads, member loads (uniform, concentrated, trapezoidal, linear varying), plate pressure, floor loads, temperature loads, wind loads, seismic loads, load combinations, or querying load data. Covers: CreateNewPrimaryLoad, CreateNewPrimaryLoadEx (typed), SetLoadActive (required before adding items), AddSelfWeightInXYZ, AddNodalLoad, AddMemberUniformForce (directions 1-9), AddMemberConcForce, AddMemberTrapezoidal, AddMemberLinearVari, AddElementPressure (uniform), AddElementTrapPressureEx (variable/hydrostatic), AddMemberFloorLoad, AddTemperatureLoad, AddWindLoad, AddSeismicLoad, CreateNewLoadCombination, AddLoadAndFactorToCombination, load envelopes, querying loads. Requires staad-core.'
---

# STAAD.Pro Loading

## Instructions

- Define the shorthand once per script: `const load = staad.Load;`

### Load Cases
- `load.CreateNewPrimaryLoad(title)` → load case ID
- `load.CreateNewPrimaryLoadEx(title, loadType)` → typed case - `load.CreateNewPrimaryLoadEx2(title, loadType, loadCaseNo)` → typed with explicit number
- Always call `load.SetLoadActive(lcId)` **before** adding any items to that case

**Load type codes:** 0=Dead, 1=Live, 3=Wind, 4=Seismic-H, 5=Snow, 7=Fluid/Hydrostatic

### Self-Weight
```javascript
load.AddSelfWeightInXYZ(direction, factor);
// direction: 1=X, 2=Y, 3=Z; factor: -1.0 for gravity
// Use staad.Geometry.IsZUp(): dir 2 if Y-up, dir 3 if Z-up

// Apply to specific elements only
load.AddSelfWeightInXYZToGeometry(elementIds, direction, factor);
```

### Nodal Loads
```javascript
load.AddNodalLoad(nodeIds, FX, FY, FZ, MX, MY, MZ);

// Support displacement (prescribed)
load.AddSupportDisplacement(nodeIds, direction, value);
```

### Member Loads

**Uniform force** (full or partial span):
```javascript
// direction: 1-3=LocalXYZ, 4-6=GlobalXYZ, 7-9=ProjectedXYZ
load.AddMemberUniformForce(beamIds, direction, force, D1, D2, D3);
// D1=start, D2=end distances; D1=D2=0 → full span

load.AddMemberUniformMoment(beamIds, direction, moment, D1, D2, D3);
```

**Concentrated force/moment:**
```javascript
load.AddMemberConcForce(beamIds, direction, force, D1, D2);
// D1=distance from start, D2=eccentricity

load.AddMemberConcMoment(beamIds, direction, moment, D1, D2);
```

**Trapezoidal/linear varying:**
```javascript
load.AddMemberTrapezoidal(beamIds, direction, W1, W2, D1, D2);
// W1 at D1, W2 at D2

load.AddMemberLinearVari(beamIds, direction, W1, W2, W3);
// W1 at start, W2 at end, W3=midpoint
```

**Other member loads:**
```javascript
load.AddMemberAreaLoad(beamIds, pressure);             // floor/area pressure
load.AddMemberFixedEnd(beamIds, loadStart, loadEnd);   // [FX,FY,FZ,MX,MY,MZ] each
load.AddStrainLoad(beamIds, axialElong);               // strain/thermal
```

### Floor Loads
```javascript
load.AddMemberFloorLoad(pressure, YMIN, YMAX, ZMIN, ZMAX, XMIN, XMAX);
load.AddMemberFloorLoadEx(rangeType, direction, pressure, grpOrOneWay, YMIN, YMAX, ZMIN, ZMAX, XMIN, XMAX);
// rangeType: 0=YRange, 1=XRange, 2=ZRange; grpOrOneWay: 0=two-way, 1=one-way
```

### Plate Loads

| Load type | Function | When to use |
|-----------|----------|-------------|
| Uniform | `AddElementPressure(plateIds, dir, pressure, 0,0,0,0)` | Flat uniform |
| Variable | `AddElementTrapPressureEx(plateIds, loadDir, varyDir, p1,p2,p3,p4)` | Hydrostatic, soil |
| Hydrostatic | `AddElementHydrostaticPressure(...)` | **Avoid** — may silently fail |

For vertical wall plates with hydrostatic pressure:
- `loadDir = 3` (LocalZ — normal to plate surface)
- `varyDir = 1` (LocalX — varies with depth/elevation)

### Temperature Loads
```javascript
load.AddTemperatureLoad(elementIds, tempChange, tempDiffTopBottom, tempDiffSide);
```

### Wind Loads
```javascript
load.AddWindDefinition(typeNo, typeName);
load.AddWindIntensity(typeNo, intensities, heights);
load.AddWindExposure(typeNo, exposureFactor, nodeArray);
load.AddWindLoad(typeNo, direction, fraction, openStructure, YMIN, YMAX, ZMIN, ZMAX, XMIN, XMAX);
```

### Seismic Loads
```javascript
load.AddSeismicDefinition(type, accidental);      // type: 0=IBC, 5=IS1893, etc.
load.AddSeismicDefSelfWeight(weightFactor);
load.AddSeismicDefJointWeight(weight, nodeList);
load.AddSeismicLoad(direction, factor);            // 1=X, 2=Y, 3=Z
```

### Load Combinations
```javascript
const comb = load.CreateNewLoadCombination(title, loadCombNo);
load.AddLoadAndFactorToCombination(loadCombNo, loadNo, factor);

// Auto-generate code combinations
load.AddAutoLoadCombinations(code, category, loadList);
```

### Reference Loads
```javascript
const ref = load.CreateNewReferenceLoad(title, loadType);
load.SetReferenceLoadActive(ref);
// Add loads...
load.AddReferenceLoad(refLoadCaseIds, factorList);  // reference to ref loads
```

### Repeat Loads (Factored Primary Cases)
**Repeat loads** create a new **analyzable** primary load case from factored combinations of existing primary cases. They are **not** the same as `CreateNewLoadCombination`:

| | Repeat Load (`AddRepeatLoad`) | Load Combination (`CreateNewLoadCombination`) |
|---|---|---|
| **Creates** | A new primary load case (analyzed by solver) | A post-processing combination |
| **Use for** | Factored design cases (1.2D + 1.5L) | Envelope/serviceability checks |
| **Results** | Full member forces, design checks run against it | Algebraic sum of existing results |

```javascript
// Example: Create factored load cases for concrete design
// LC1=Dead, LC2=Live already defined

// LC3 = 1.2 × Dead + 1.5 × Live  (factored for strength design)
const lc3 = load.CreateNewPrimaryLoad('1.2D + 1.5L');
load.SetLoadActive(lc3);
load.AddRepeatLoad([1, 2], [1.2, 1.5]);

// LC4 = 1.1 × Dead + 1.3 × Wind
const lc4 = load.CreateNewPrimaryLoad('1.1D + 1.3W');
load.SetLoadActive(lc4);
load.AddRepeatLoad([1, 3], [1.1, 1.3]);
```

- `AddRepeatLoad(loadCaseList, factorList)` — both arrays must be the same length - The repeat load cases are analyzed as real load cases — the solver computes member forces, not just algebraic combinations
- This is the standard approach for factored load cases in concrete and timber design (see `staad-design` skill)

### Load Envelopes
```javascript
load.CreateLoadEnvelop(envNo, envType, loadCaseList);
// envType: 0=None, 1=Stress, 2=Serviceability, 3=Column, 5=Strength
load.AddLoadCasesToEnvelop(envNo, loadCaseList);
load.DeleteLoadEnvelop(envNo);
```

### Querying
```javascript
const cases   = load.GetPrimaryLoadCaseNumbers();      // native JS array
const combos  = load.GetLoadCombinationCaseNumbers();
const count   = load.GetPrimaryLoadCaseCount();
const title   = load.GetLoadCaseTitle(lcNo);
const ltype   = load.GetLoadType(lcNo);
const active  = load.GetActiveLoad();
const isComb  = load.IsCombinationCase(lcNo);
```

### Load Verification
`GetAssignmentListForLoadType(loadType, index)` — index is **within that load type only**, not the overall load item index.

### Modifying/Deleting
```javascript
load.ClearPrimaryLoadCase(loadCaseNos, false);      // false = not reference load load.DeletePrimaryLoadCases(loadCaseNos, false);
load.SetLoadType(loadCaseNumber, loadType);
```

## Examples
- [self-weight.js](./scripts/self-weight.js) — create a primary load case with self-weight
- [hydrostatic-tank.js](./scripts/hydrostatic-tank.js) — assign hydrostatic pressure to a plate tank

## Gotchas
- `SetLoadActive` is mandatory before adding items — skipping it assigns loads to the wrong case
- `AddElementHydrostaticPressure` may silently fail on some plate topologies — prefer `AddElementTrapPressureEx`
- Group plates with the same corner elevation signature into one `AddElementTrapPressureEx` call (not one per plate)
- `GetPrimaryLoadCaseNumbers()` returns a JS array — index directly with `cases[0]`
- Member load directions: 1-3=Local, 4-6=Global, 7-9=Projected
