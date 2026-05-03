---
name: staad-loading
description: "Use when defining load cases, applying self-weight, nodal loads, member loads (uniform, concentrated, trapezoidal, linear varying), plate pressure, floor loads, temperature loads, wind loads, seismic loads, load combinations, or querying load data. Covers: CreateNewPrimaryLoad, CreateNewPrimaryLoadEx (typed), SetLoadActive (required before adding items), AddSelfWeightInXYZ, AddNodalLoad, AddMemberUniformForce (directions 1-9), AddMemberConcForce, AddMemberTrapezoidal, AddMemberLinearVari, AddElementPressure (uniform), AddElementTrapPressureEx (variable/hydrostatic), AddMemberFloorLoad, AddTemperatureLoad, AddWindLoad, AddSeismicLoad, CreateNewLoadCombination, AddLoadAndFactorToCombination, load envelopes, querying loads. Requires staad-core."
---

# STAAD.Pro Loading

## Instructions

- Define the shorthand once per script: `load = staad.Load`

### Load Cases

- `load.CreateNewPrimaryLoad(title)` → load case ID
- `load.CreateNewPrimaryLoadEx(title, loadType)` → typed case
- `load.CreateNewPrimaryLoadEx2(title, loadType, loadCaseNo)` → typed with explicit number
- Always call `load.SetLoadActive(lcId)` **before** adding any items to that case

**Load type codes** (full table in the Reference section — LOAD_CODES.md):

| loadType | Meaning   |
| -------- | --------- |
| 0        | Dead      |
| 1        | Live      |
| 3        | Wind      |
| 4        | Seismic-H |
| 5        | Snow      |
| 7        | Fluids    |

### Self-Weight

`load.AddSelfWeightInXYZ(direction, factor)` — direction is an **integer**, factor is a float.

| direction | Axis | When to use                          |
| --------- | ---- | ------------------------------------ |
| 1         | X    | Lateral                              |
| 2         | Y    | Gravity when `IsZUp()==False` (Y-up) |
| 3         | Z    | Gravity when `IsZUp()==True` (Z-up)  |

**factor:** `-1.0` for gravity (negative = downward along the axis)

```python
# Apply to all elements
load.AddSelfWeightInXYZ(3 if staad.Geometry.IsZUp() else 2, -1.0)

# Apply to specific elements only
load.AddSelfWeightInXYZToGeometry(elementIds, 3 if staad.Geometry.IsZUp() else 2, -1.0)
```

### Nodal Loads

```python
load.AddNodalLoad(nodeIds, FX, FY, FZ, MX, MY, MZ)

# Support displacement (prescribed)
load.AddSupportDisplacement(nodeIds, direction, value)
```

### Member Loads

**Uniform force** (full or partial span):

| direction | Coordinate system |     | direction | Coordinate system |
| --------- | ----------------- | --- | --------- | ----------------- |
| 1         | Local X           |     | 4         | Global X          |
| 2         | Local Y           |     | 5         | Global Y          |
| 3         | Local Z           |     | 6         | Global Z          |
|           |                   |     | 7-9       | Projected X/Y/Z   |

```python
# direction: 1-3=LocalXYZ, 4-6=GlobalXYZ, 7-9=ProjectedXYZ
load.AddMemberUniformForce(beamIds, direction, force, D1, D2, D3)
# D1=start, D2=end distances; D1=D2=0 → full span

load.AddMemberUniformMoment(beamIds, direction, moment, D1, D2, D3)
```

**Concentrated force/moment:**

```python
load.AddMemberConcForce(beamIds, direction, force, D1, D2)
# D1=distance from start, D2=eccentricity

load.AddMemberConcMoment(beamIds, direction, moment, D1, D2)
```

**Trapezoidal/linear varying:**

```python
load.AddMemberTrapezoidal(beamIds, direction, W1, W2, D1, D2)
# W1 at D1, W2 at D2

load.AddMemberLinearVari(beamIds, direction, W1, W2, W3)
# W1 at start, W2 at end, W3=midpoint
```

**Other member loads:**

```python
load.AddMemberAreaLoad(beamIds, pressure)        # floor/area pressure
load.AddMemberFixedEnd(beamIds, loadStart, loadEnd)  # [FX,FY,FZ,MX,MY,MZ] each
load.AddStrainLoad(beamIds, axialElong)           # strain/thermal
```

### Floor Loads

| rangeType | Range  |     | grpOrOneWay | Mode    |
| --------- | ------ | --- | ----------- | ------- |
| 0         | YRange |     | 0           | Two-way |
| 1         | XRange |     | 1           | One-way |
| 2         | ZRange |     |             |         |

```python
load.AddMemberFloorLoad(pressure, YMIN, YMAX, ZMIN, ZMAX, XMIN, XMAX)
load.AddMemberFloorLoadEx(rangeType, direction, pressure, grpOrOneWay, YMIN, YMAX, ZMIN, ZMAX, XMIN, XMAX)
```

### Plate Loads

| Load type   | Function                                                             | When to use                   |
| ----------- | -------------------------------------------------------------------- | ----------------------------- |
| Uniform     | `AddElementPressure(plate_ids, dir, pressure, 0,0,0,0)`              | Flat uniform                  |
| Variable    | `AddElementTrapPressureEx(plate_ids, loadDir, varyDir, p1,p2,p3,p4)` | Hydrostatic, soil             |
| Hydrostatic | `AddElementHydrostaticPressure(...)`                                 | **Avoid** — may silently fail |

For vertical wall plates with hydrostatic pressure:

- `loadDir = 3` (LocalZ — normal to plate surface)
- `varyDir = 1` (LocalX — varies with depth/elevation)

### Temperature Loads

```python
load.AddTemperatureLoad(elementIds, tempChange, tempDiffTopBottom, tempDiffSide)
```

### Wind Loads

```python
load.AddWindDefinition(typeNo, typeName)
load.AddWindIntensity(typeNo, intensities, heights)
load.AddWindExposure(typeNo, exposureFactor, nodeArray)
load.AddWindLoad(typeNo, direction, fraction, openStructure, YMIN, YMAX, ZMIN, ZMAX, XMIN, XMAX)
```

### Seismic Loads

| type | Code    |     | direction | Axis |
| ---- | ------- | --- | --------- | ---- |
| 0    | IBC     |     | 1         | X    |
| 5    | IS 1893 |     | 2         | Y    |
|      |         |     | 3         | Z    |

```python
load.AddSeismicDefinition(type, accidental)
load.AddSeismicDefSelfWeight(weightFactor)
load.AddSeismicDefJointWeight(weight, nodeList)
load.AddSeismicLoad(direction, factor)
```

### Load Combinations

```python
comb = load.CreateNewLoadCombination(title, loadCombNo)
load.AddLoadAndFactorToCombination(loadCombNo, loadNo, factor)

# Auto-generate code combinations
load.AddAutoLoadCombinations(code, category, loadList)
```

### Reference Loads

```python
ref = load.CreateNewReferenceLoad(title, loadType)
load.SetReferenceLoadActive(ref)
# Add loads...
load.AddRepeatLoad(loadCaseList, factorList)       # repeat from primary
load.AddReferenceLoad(refLoadCaseIds, factorList)  # reference to ref loads
```

### Load Envelopes

| envType | Category       |
| ------- | -------------- |
| 0       | None           |
| 1       | Stress         |
| 2       | Serviceability |
| 3       | Column         |
| 4       | Connection     |
| 5       | Strength       |
| 6       | Temporary      |

```python
load.CreateLoadEnvelop(envNo, envType, loadCaseList)
load.AddLoadCasesToEnvelop(envNo, loadCaseList)
load.DeleteLoadEnvelop(envNo)
```

### Querying

```python
cases   = load.GetPrimaryLoadCaseNumbers()      # tuple — wrap in list()
combos  = load.GetLoadCombinationCaseNumbers()
count   = load.GetPrimaryLoadCaseCount()
title   = load.GetLoadCaseTitle(lcNo)
ltype   = load.GetLoadType(lcNo)
active  = load.GetActiveLoad()
is_comb = load.IsCombinationCase(lcNo)
```

### Load Verification

`GetAssignmentListForLoadType(loadType, index)` — index is **within that load type only**, not the overall load item index.

### Modifying/Deleting

```python
load.ClearPrimaryLoadCase(loadCaseNos, isReferenceLoad=False)
load.DeletePrimaryLoadCases(loadCaseNos, isReferenceLoads=False)
load.SetLoadType(loadCaseNumber, loadType)
```

## Examples

- [self-weight.py](./scripts/self-weight.py) — create a primary load case with self-weight
- [hydrostatic-tank.py](./scripts/hydrostatic-tank.py) — assign hydrostatic pressure to a plate tank

## Gotchas

- `SetLoadActive` is mandatory before adding items — skipping it assigns loads to the wrong case
- `AddElementHydrostaticPressure` may silently fail on some plate topologies — prefer `AddElementTrapPressureEx`
- Group plates with the same corner elevation signature into one `AddElementTrapPressureEx` call (not one per plate)
- `GetPrimaryLoadCaseNumbers()` returns a tuple — convert with `list()` before indexing
- Member load directions: 1-3=Local, 4-6=Global, 7-9=Projected
