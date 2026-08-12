---
name: staad-loading
description: "Use when defining load cases, applying self-weight, nodal loads, member loads (uniform, concentrated, trapezoidal, linear varying), plate pressure, floor loads, temperature loads, wind loads, seismic loads, load combinations, load lists, reference loads, notional loads, repeat loads, response spectrum loads, direct analysis parameters, or querying load data. Covers: CreateNewPrimaryLoad, CreateNewPrimaryLoadEx (typed), SetLoadActive (required before adding items), AddSelfWeightInXYZ, AddNodalLoad, AddMemberUniformForce (directions 1-9), AddMemberConcForce, AddMemberTrapezoidal, AddMemberLinearVari, AddElementPressure (uniform), AddElementTrapPressureEx (variable/hydrostatic), AddMemberFloorLoad, AddTemperatureLoad, AddWindLoad, AddWindDefinitionASCE7Parameters, AddSeismicLoad, AddSeismicDefFloorWeight/MemberWeight/ElementWeight/WallArea, ModifySeismicDefinitionParams, AddNotionalLoad, AddAutoCombinationRepeat, AddResponseSpectrumLoad, AddDirectAnalysisDefinitionParameter, CreateLoadList, CreateNewLoadCombination, AddLoadAndFactorToCombination, GetLoadAndFactorForCombination, GetNoOfLoadAndFactorPairsForCombination, GetNodalLoads, GetUDLLoads, GetTrapLoads, GetConcForces, GetConcMoments, GetLinearVaryingLoads, GetElementPressureLoads, GetElementConcLoads, GetReferenceLoadByIndex, GetMemberLoadInfo, GetNodalLoadInfo, GetElementLoadInfo, MergeLoadsOnBeam, SplitLoadsOnBeam, load envelopes, querying loads. Requires staad-core."
---

# STAAD.Pro Loading

## Instructions

- Define the shorthand once per script: `load = staad.Load`

### Load Cases

- `load.CreateNewPrimaryLoadEx(title, loadType)` → load case ID, auto-assigned and typed (preferred — also available: `CreateNewPrimaryLoad(title)` untyped, `CreateNewPrimaryLoadEx2(title, loadType, loadCaseNo)` for an explicit case number)
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
load.AddSelfWeightInXYZ(3 if geo.IsZUp() else 2, -1.0)

# Apply to specific elements only
load.AddSelfWeightInXYZToGeometry(elementIds, 3 if geo.IsZUp() else 2, -1.0)
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
load.AddMemberFloorLoadEx(rangeType, direction, pressure, grpOrOneWay, YMIN, YMAX, ZMIN, ZMAX, XMIN, XMAX)
# AddMemberFloorLoad(pressure, YMIN, YMAX, ZMIN, ZMAX, XMIN, XMAX) also available — fixed to Y-range/two-way only
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

**Advanced seismic weight definitions** (each adds to the currently active seismic definition):
```python
load.AddSeismicDefElementWeight(pressure, elementIds)
load.AddSeismicDefMemberWeight(seismicType, loadType, weight, startDist, endDist, memberIds)  # loadType: 1=uniform, 2=concentrated
load.AddSeismicDefFloorWeight(rangeType, loadDirection, pressure, grpOrOneWay, yMin, yMax, zMin, zMax, xMin, xMax)
load.AddSeismicDefWallArea(seismicType, direction, sizeArray)   # IS 1893-2016 only; direction: "X" or "Z"

# Modify/add a single named parameter in the active seismic definition (param names/values are code-specific — see openstaadpy docstring for the full per-code table)
load.ModifySeismicDefinitionParams(paramName, value)  # e.g. load.ModifySeismicDefinitionParams("ZONE", 0.2)
```

### Notional & Repeat Loads

```python
# Notional load: combines primary + reference load cases with per-direction factors
load.AddNotionalLoad(primaryLoadCaseIds, primaryFactors, primaryDirections, refLoadCaseIds, refFactors, refDirections)
# directions: 1-3=X/Y/Z (Primary), 4-6=X/Y/Z (Global) — see openstaadpy docstring

count = load.GetNotionalLoadCount()
factor_count = load.GetNoLoadFactorDirectionInNotionalLoad(index)   # 1-based index
notional_items = load.GetNotionalLoadByIndex(index)   # list of (direction, loadCaseId, factor) tuples

# Repeat load: auto-generate a repeat combination from a design code/category
load.AddAutoCombinationRepeat(code, category, loadList, startLoadCaseNo, generatedCount, includeReference, includeNotional, notionalFactor, gb50017, floorCount, considerX, considerNegX, considerZ, considerNegZ)

count = load.GetRepeatLoadCount()
pair_count = load.GetNoLoadFactorInRepeatLoad(index)   # 1-based index
case_to_factor = load.GetRepeatLoadByIndex(index)      # dict of {loadCaseId: factor}
```

### Direct Analysis Definition

```python
load.AddDirectAnalysisDefinitionParameter(paramType, memberIds, paramValue)  # paramType: 0=FLEX, 2=AXIAL (AXIAL ignores paramValue, pass 0)
load.DeleteDirectAnalysisDefinitionParameter(paramType)
load.DeleteDirectAnalysisDefinition()   # deletes the whole definition
```

### Response Spectrum Load
Adds a response-spectrum load item to the active load case. `rsaCode` selects the seismic code (Generic/IS1893/Eurocode/IBC/SNiP/etc.), `rsaCombination` selects the modal combination rule (0=SRSS, 1=ABS, 2=CQC, 3=ASCE, 4=TEN, 5=CSM, 6=GRP). The parameter keyword lists (`set1Names`/`set1Vals`) are code-specific — see the openstaadpy docstring for the full per-code keyword table:
```python
load.AddResponseSpectrumLoad(rsaCode, rsaCombination, set1Names, set1Vals, set2Names, set2Vals, dataPairs)
# set2Names/set2Vals (spectrum generation) and dataPairs (period/acceleration pairs) are mutually exclusive — pass [] for whichever is unused
```

### Wind Definition — ASCE 7 Parameters
Generates full ASCE 7 wind parameters/pressure profiles from code inputs (building class/type, exposure category, escarpment data, etc.) instead of manually specifying `AddWindIntensity`/`AddWindExposure`. Parameter lists are large and code-specific — see the openstaadpy docstring for the full per-index breakdown of each list argument:
```python
load.AddWindDefinitionASCE7Parameters(typeNo, code, windSpeed, heightAboveSeaLvl, bldgClass, bldgType, expCat,
                                       escarpment, wallType, isFlexible, escarpmentData, bldgData, unitsData,
                                       factorsUserInput, factors)
# code: 0=ASCE7-1995, 1=ASCE7-2002, 2=ASCE7-2010, 3=ASCE7-2016

pressure_profile = load.ComputeWallWindPressureProfile(loadingCode, windSpeed, bldgClass, bldgType, expCat,
                                                         escarpment, unitsData, escarpmentData, bldgData, wallType)
# ComputeWallWindPressureProfileASCE72016 is the ASCE7-2016-specific variant with an updated parameter set

load.DeleteWindDefinition(typeNo)   # typeNo=0 deletes all wind definitions
```

### Load Combinations

```python
comb = load.CreateNewLoadCombination(title, loadCombNo)
load.AddLoadAndFactorToCombination(loadCombNo, loadNo, factor)

# Auto-generate code combinations
load.AddAutoLoadCombinations(code, category, loadList)

# Query the load cases/factors that make up a combination
load.GetNoOfLoadAndFactorPairsForCombination(loadCombNo)  # int count
load.GetLoadAndFactorForCombination(loadCombNo)           # (loadCaseIds, factors) — for SRSS, factors has one extra trailing element (overall SRSS factor)
load.GetLoadCombinationCaseCount()      # total number of combination cases
load.GetLoadCombinationCaseNumbers()    # list of combination case IDs
```

### Load Lists
A load list groups load case IDs under one index for later reuse (e.g. as input to `CreateLoadEnvelop`/auto-combination functions). `listType`: 0=plain load list, 1=load envelope list.

```python
list_created = load.CreateLoadList(listType, loadCaseIds)   # bool
load.DeleteLoadList(loadListIndex)                          # 1-based index

count = load.GetLoadListCount()
case_count = load.GetLoadCountInLoadList(loadListIndex)      # 1-based index
case_ids = load.GetLoadsInLoadList(loadListIndex)
```

### Reference Loads
A reference load is a **reusable, named container of actual load items** (nodal, member, self-weight, etc.), defined once and then applied — with its own scale factor — to one or more primary load cases. It is NOT a way to combine primary load case numbers directly (that's what `AddRepeatLoad`/`AddAutoCombinationRepeat` are for).

```python
# Step 1 — define the reference load container and populate it with real load items
ref_id = load.CreateNewReferenceLoad(refId, title, loadType)  # refId: caller-chosen, must not collide with an existing reference load ID
load.SetReferenceLoadActive(ref_id)
load.AddNodalLoad(node_ids, FX, FY, FZ, MX, MY, MZ)   # or AddSelfWeightInXYZ / AddMemberUniformForce / etc. — any normal load-adding call

# Step 2 — apply the reference load to a primary case, with its own factor
load.SetLoadActive(primary_case_id)
load.AddReferenceLoad([ref_id], [0.75])   # varRefLoadCaseNoIds are REFERENCE load IDs (from Step 1), not primary case numbers
```
Verified live by inspecting the generated STD file: this produces `LOAD R<refId> ... JOINT LOAD ...` (the reference load's own contents) followed by `LOAD <primary_case_id> ... REFERENCE LOAD / R<refId> 0.75` inside the primary case — the correct, non-circular structure. The same reference load can be applied to multiple primary cases with different factors by repeating Step 2.

`AddRepeatLoad(loadCaseList, factorList)` is the separate mechanism for combining *primary* load cases (repeat-load style), unrelated to reference loads.

**Do NOT call `AddReferenceLoad` while a reference load (rather than a primary case) is active.** Nesting one reference load inside another (`REFERENCE LOAD / R<a> ... R<b> ...` inside another reference load's own definition) is NOT valid STAAD syntax — user-confirmed this produces a syntax error, even though the underlying COM call itself doesn't raise and the text gets written to the STD file without an in-process error. Only call `AddReferenceLoad` while a **primary** load case is active (Step 2 above).

Querying reference loads (count-then-getter, same pattern as other load items):
```python
count        = load.GetReferenceLoadCount()          # reference load items in the active load case
case_count   = load.GetReferenceLoadCaseCount()       # reference load *case* items
case_numbers = load.GetReferenceLoadCaseNumbers()

set_count = load.GetNoOfSetsInReferenceLoad(index)    # 1-based index into reference load items
case_ids, factors = load.GetReferenceLoadByIndex(index)
load_type = load.GetReferenceLoadType(loadNo)         # 0-23, same codes as CreateNewPrimaryLoadEx
title     = load.GetReferenceLoadCaseTitle(loadNo)

load.ClearReferenceLoadCase(loadCaseNos)              # clears items but keeps the case
load.DeleteReferenceLoadCases(loadCaseNos)            # deletes the case entirely
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
load.RemoveLoadCasesFromEnvelop(envNo, loadCaseList)   # remove specific cases without deleting the envelope
```

Querying envelopes:
```python
count = load.GetEnvelopeCount()
env_ids = load.GetEnvelopeIDs()
env_type, case_count = load.GetLoadEnvelopeDetails(envNo)   # env_type per the table above
case_ids = load.GetLoadListfromLoadEnvelope(envNo)
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

Query the actual applied load items (count first, then the matching getter — same `nBeamNo`/`nNodeNo` pattern for all):

| Item | Count | Getter | Returns |
|------|-------|--------|---------|
| Nodal load | `GetNodalLoadCount(nodeNo)` | `GetNodalLoads(nodeNo)` | `(FX, FY, FZ, MX, MY, MZ)` lists |
| Uniform force (UDL) | `GetUDLLoadCount(beamNo)` | `GetUDLLoads(beamNo)` | `(dir, force, D1, D2, D3)` lists |
| Uniform moment | `GetUNIMomentCount(beamNo)` | `GetUNIMoments(beamNo)` | same shape as UDL |
| Trapezoidal | `GetTrapLoadCount(beamNo)` | `GetTrapLoads(beamNo)` | per-item tuples |
| Concentrated force | `GetConcForceCount(beamNo)` | `GetConcForces(beamNo)` | per-item tuples |
| Concentrated moment | `GetConcMomentCount(beamNo)` | `GetConcMoments(beamNo)` | per-item tuples |
| Linear varying | `GetLinearVaryingLoadCount(beamNo)` | `GetLinearVaryingLoads(beamNo)` | per-item tuples |
| Element pressure | `GetElementPressureLoadCount(plateNo)` | `GetElementPressureLoads(plateNo)` | per-item tuples |

```python
n = load.GetUDLLoadCount(beamNo)
dirs, forces, d1, d2, d3 = load.GetUDLLoads(beamNo)  # empty lists if n == 0
```

Element concentrated loads (plate-scoped, separate from element pressure loads above):
```python
count = load.GetElementConcLoadCount(plateNo)
conc_loads = load.GetElementConcLoads(plateNo)   # list of (direction, pressure, x1, y1) tuples
```

### Load Item Introspection
Lower-level access to raw load items within a load case, keyed by a numeric load-type code (e.g. 4000=SelfWeight, 3110=Nodal Load, 3210=Uniform Force, 3710=Temperature — see `GetLoadTypeCount`'s openstaadpy docstring for the full code table):
```python
item_count = load.GetLoadItemsCount(loadCaseNo)
item_type = load.GetLoadItemType(loadCaseNo, loadItemIndex)

type_count = load.GetLoadTypeCount(loadType)              # count of loads of a specific type in the active load case
entity_count = load.GetListSizeForLoadType(loadType, loadIndex)  # entities (nodes/beams/plates) affected by one such load item

# Raw per-item data by zero-based load index (lower-level than the beam/node-scoped Get*Loads above)
direction, forces, distances = load.GetMemberLoadInfo(loadIndex)   # forces/distances: [W1,W2,W3]/[D1,D2,D3]
nodal_forces = load.GetNodalLoadInfo(loadIndex)                     # [FX,FY,FZ,MX,MY,MZ]
element_loads = load.GetElementLoadInfo(loadIndex)                  # list of (direction, w1..w4, x1,y1,x2,y2) tuples

is_dynamic = load.IsDynamicLoadIncluded(loadCaseNo)
```

### Load Verification

`GetAssignmentListForLoadType(loadType, index)` — index is **within that load type only**, not the overall load item index.

### Modifying/Deleting

```python
load.ClearPrimaryLoadCase(loadCaseNos, isReferenceLoad=False)
load.DeletePrimaryLoadCases(loadCaseNos, isReferenceLoads=False)
load.SetLoadType(loadCaseNumber, loadType)
```

### Merging/Splitting Loads Between Beams
Useful after `SplitBeam`/geometry edits shift loads across beam IDs:
```python
load.BeginLoadMerging()   # batch mode — improves performance for many Merge/Split calls
load.MergeLoadsOnBeam(beamToKeep, beamToMerge)   # moves loads from beamToMerge onto beamToKeep
load.SplitLoadsOnBeam(beamOld, beamNew)          # copies applicable loads from beamOld onto beamNew
load.EndLoadMerging()
```

### Load Attributes & Floor Queries
```python
load.GetAttribute(loadCaseId)                 # bool — whether attribute info exists for the case
load.RemoveAttribute(loadCaseId)
load.SetASDLoadAttribute(loadCaseId, strengthType, allowStressIncrease)  # Allowable Stress Design attribute
load.SetLSDLoadAttribute(loadCaseId)                                      # Limit State Design attribute

# Floor-range queries (same 6-coordinate range + direction pattern as AddMemberFloorLoad)
beam_count = load.GetBeamCountAtFloor(xMin, xMax, yMin, yMax, zMin, zMax, direction)  # direction: 1=XRange, 2=YRange, 3=ZRange
beam_to_area = load.GetInfluenceArea(xMin, xMax, yMin, yMax, zMin, zMax, direction)   # dict of {beamId: influence_area}
```

## Examples

- [self-weight.py](./scripts/self-weight.py) — create a primary load case with self-weight
- [hydrostatic-tank.py](./scripts/hydrostatic-tank.py) — assign hydrostatic pressure to a plate tank
- [load-lists-and-reference-loads.py](./scripts/load-lists-and-reference-loads.py) — group load cases into a load list, build a reference load

## Gotchas

- `SetLoadActive` is mandatory before adding items — skipping it assigns loads to the wrong case
- `AddElementHydrostaticPressure` may silently fail on some plate topologies — prefer `AddElementTrapPressureEx`
- Group plates with the same corner elevation signature into one `AddElementTrapPressureEx` call (not one per plate)
- `GetPrimaryLoadCaseNumbers()` returns a tuple — convert with `list()` before indexing
- Member load directions: 1-3=Local, 4-6=Global, 7-9=Projected
- `CreateLoadList` can return `False` even on success — verified live: the list was actually created (`GetLoadListCount()` incremented and `GetLoadsInLoadList()` returned the correct case IDs) despite `CreateLoadList` returning `False`. Verify via `GetLoadListCount()`/`GetLoadsInLoadList()` rather than trusting the return value.
- `CreateNewReferenceLoad(refId, title, loadType)` takes **3 args, not 2** — `refId` is a caller-chosen reference number ID, not auto-assigned. Populate the reference load with real load items (`AddNodalLoad`, etc.) while it's active via `SetReferenceLoadActive`, then switch to a primary case (`SetLoadActive`) and call `AddReferenceLoad([refId], [factor])` to apply it — see the Reference Loads section above.
- `AddReferenceLoad(varRefLoadCaseNoIds, factors)` takes **REFERENCE load IDs, not primary load case numbers**, and must only be called while a **primary** load case is active. Calling it while a reference load is active (to "nest" reference loads) produces a real syntax error — confirmed via the STAAD.Pro reopen dialog itself: `"(2) Errors, (0) Warnings found in input file."` The underlying COM call doesn't raise and the text still gets written into the STD file's `REFERENCE LOAD` block, so the failure is silent until STAAD actually re-parses the file (see staad-core for how to force a genuine re-parse). Passing primary case numbers here instead of reference load IDs is a related mistake that produces the same kind of broken `REFERENCE LOAD` block.
- `refId` passed to `CreateNewReferenceLoad` must not collide with an existing **reference** load case number (separate namespace from primary case numbers — verified live: a `refId` equal to an existing primary case number is fine on its own). Always compute a free ID: `safe_ref_id = max(list(load.GetReferenceLoadCaseNumbers()), default=0) + 1`.
