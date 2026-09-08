---
name: staad-supports
description: "Use when creating or assigning supports, boundary conditions, restraints, pins, fixed bases, springs, inclined supports, elastic mat, plate mat, or elastic footing. Covers: CreateSupportFixed (all 6 DOF), CreateSupportPinned, CreateSupportFixedBut (selective releases/springs), CreateInclinedSupport, CreateElasticMat (subgrade modulus), CreatePlateMat, CreateElasticFooting, CreateCompressionOnlySpring, CreateTensionOnlySpring, AssignSupportToNode (single node — loop for multiple), AssignSupportToEntityList, GetSupportCount, GetSupportNodes, GetSupportInformation, GetCountOfPlateMat, GetPlateMatDetail, GetCountOfElasticFooting, GetElasticFootingDetail, RemoveSupportFromNode, RemovePlateMat/RemovePlateMatFromPlate, RemoveElasticFooting/RemoveElasticFootingFromNode, RemoveElasticMat/RemoveElasticMatFromNode, DeleteSupport. Requires staad-core."
---

# STAAD.Pro Supports

## Instructions

### Basic Supports

**Fixed** — restrains all 6 DOF:

```python
fix_id = sup.CreateSupportFixed()
```

**Pinned** — translations restrained, rotations free:

```python
pin_id = sup.CreateSupportPinned()
```

**Fixed-But** — selective releases or springs:

```python
# releaseSpec: [FX,FY,FZ,MX,MY,MZ] → 0=fixed, 1=released, -1=spring
# springSpec: [KFX,KFY,KFZ,KMX,KMY,KMZ] → spring stiffness
sup_id = sup.CreateSupportFixedBut(
    ReleaseSpec=[0, -1, 0, 0, 0, 1],   # FY=spring, MZ=released
    SpringSpec=[0, 100.0, 0, 0, 0, 0]   # KFY=100
)
```

### Inclined Supports

```python
sup_id = sup.CreateInclinedSupport(
    inclinedType=2,   # 1=Pinned, 2=Fixed, 3=FixedBut
    refType=2,        # 0=distances, 1=coordinates, 2=node reference
    refNode=1,
    coord=[0, 0, 0],
    releaseSpec=[0,0,0,0,0,0],
    springSpec=[0,0,0,0,0,0]
)
```

### Elastic Mat Support (Soil Springs)

Spring support distributed over tributary area.
See **[SUPPORT_CODES.md — Direction Codes](./assets/SUPPORT_CODES.md)** for `direction` values and **[SUPPORT_CODES.md — Spring Types](./assets/SUPPORT_CODES.md)** for `springType`.

```python
# Typical case: springs in Y direction (STAAD adds X/Z fixity for stability)
mat_id = sup.CreateElasticMat(
    direction=1,     # 1=Y Direction (use for most foundations)
    subgrade=20.0,   # CURRENT SetInputUnits, e.g. kN/m^3 if input=Meter/kN — converted to base internally, NOT the model's base unit
    printFlag=0,
    springType=0     # 0=Normal (bi-directional); 1=Compression only
)
sup.AssignSupportToEntityList(mat_id, [41, 42, 43])

# GetElasticMatDetail(mat_id) returns subgrade in FIXED base units afterward
# (live-verified: unaffected by later SetInputUnits calls) — see staad-core
# Units & Axis for the verification pattern if the value looks off.

# Y Only (direction=4): springs act ONLY in Y — use only when the model already
# has other supports (e.g. pinned/fixed nodes) providing X and Z restraint.
# Without those, the structure will be unstable in X/Z.
```

### Plate Mat Support

```python
# subgrades: CURRENT SetInputUnits (same convention as CreateElasticMat above)
# GetPlateMatDetail(pm_id) returns a FIXED base-unit value afterward
pm_id = sup.CreatePlateMat(direction, subgrades, printFlag, springType)
```

### Elastic Footing

```python
foot_id = sup.CreateElasticFooting(length, width, direction, subgrade)
```

### Compression/Tension-Only Springs

Marks an **existing** support spring at a node as tension-only or compression-only — per STAAD.Pro's `SPRING TENSION`/`COMPRESSION` command (TR.27.5), this only *marks* a spring that's already there, it does not create one. The node must already have a real spring in that DOF first (via `CreateSupportFixedBut` with `ReleaseSpec=-1` and a real `SpringSpec` value).

**Use `SetSupportSpringBehavior`, NOT `CreateTensionOnlySpring`/`CreateCompressionOnlySpring`** (see Gotchas — the latter are broken and must not be used):

```python
fb_id = sup.CreateSupportFixedBut(ReleaseSpec=[0, -1, 0, 0, 0, 0], SpringSpec=[0, 1000.0, 0, 0, 0, 0])
sup.AssignSupportToEntityList(fb_id, [9])   # real spring in FY at node 9, established first

sup.SetSupportSpringBehavior(1, [9], [0, 1, 0])   # 0=compression-only, 1=tension-only; springFlags=[FX,FY,FZ] enable
```
`compressionOrTensionFlag`: `0` = compression-only, `1` = tension-only (per the openstaadpy source docstring — note this is the OPPOSITE of what might seem intuitive; verified against source, not just live behavior, since `GetSupportInformationEx` does not expose which of the two was actually set). `springFlags` is a 3-element `[FX,FY,FZ]` enable array, matching the directions that already have a real spring. Raises `[-7504] Spring not defined at node.` **only if the node has no spring in ANY direction** — this check is NOT per-direction: if the node has a real spring in FY but you pass `springFlags=[1,0,0]` (FX, which has no spring), the call succeeds silently and creates the same broken, unanalyzable state as `CreateTensionOnlySpring` (confirmed live). Always verify each flagged direction individually against `GetSupportInformationEx(nodeNo)`'s springs array before calling — do not rely on the function to catch a direction-specific mismatch. When the flagged direction does have a real spring, it modifies the existing support **in place** (same support ID, stiffness preserved) — confirmed live: `GetSupportInformationEx(nodeNo)` afterward is unchanged from before the call, and analysis succeeds.

### Assigning Supports

- `sup.AssignSupportToNode(nodeID, supportID)` — assigns to a **SINGLE node**
- Use a `for` loop to assign to multiple nodes
- Before assigning, call `GetSupportInformationEx(nodeNo)` to see what support (if any) is
  already on the node (see Gotchas for the exception it raises on an unsupported node).
  Assigning always **replaces** the support with no error or warning. Report what was there
  before and what it becomes after — do not skip this step, and do not block the assignment
  just because a prior support exists. See
  [assign-fixed-supports.py](./scripts/assign-fixed-supports.py) for a working example of this
  guarded check.

### Workflow

1. Use `execute_code` to call `staad.Geometry.GetNodeCount()` and confirm the model has nodes
2. After adding geometry in the same script, call `SaveModel(True)` before assigning supports (see staad-core for SaveModel vs UpdateStructure)
3. Create support type once → assign to base nodes in a loop

### Querying

| Function                          | Returns                                           |
| --------------------------------- | ------------------------------------------------- |
| `GetSupportCount()`               | total supports                                    |
| `GetSupportNodes()`               | list of supported node IDs                        |
| `GetSupportType(nodeNo)`          | support type code (see SUPPORT_CODES.md)          |
| `GetSupportInformation(nodeNo)`   | `(type, releases, springs)`                       |
| `GetSupportInformationEx(nodeNo)` | `(supportNo, type, releases, springs)` — `type` includes 14=CompressionOnlySpring, 15=TensionOnlySpring (see SUPPORT_CODES.md) |
| `GetSupportName(supportNo)`       | support name                                      |
| `GetCountOfElasticMat()`          | elastic mat count                                 |
| `GetElasticMatDetail(matId)`      | `(direction, subgrade, print, spring, nodeCount)` |
| `GetElasticMatAssignmentList(matId)` | assigned node IDs                             |
| `GetCountOfPlateMat()`            | plate mat count                                   |
| `GetPlateMatSupportId(index)`     | support ID at index (0-based)                     |
| `GetPlateMatDetail(matId)`        | `(direction, subgrade1-3, print, spring, plateCount)` |
| `GetPlateMatAssignmentList(matId)`| assigned plate IDs                                |
| `GetCountOfElasticFooting()`      | elastic footing count                             |
| `GetElasticFootingDetail(footId)` | `(length, width, direction, subgrade, nodeCount)` |
| `GetElasticFootingAssignmentList(footId)` | assigned node IDs                        |
| `GetSupportUniqueID(supportNo)`   | GUID string                                       |

```python
sup.SetSupportUniqueID(supportNo, guid)
```

### Removing

```python
sup.RemoveSupportFromNode([1, 2, 3])   # remove from nodes
sup.DeleteSupport(supportNo)            # delete definition
sup.RemoveElasticMatFromNode(nodeNo)     # remove elastic mat from node
sup.RemoveElasticMat(matId)              # delete elastic mat definition
sup.RemovePlateMatFromPlate(plateNo)     # remove plate mat from plate
sup.RemovePlateMat(matId)                # delete plate mat definition
sup.RemoveElasticFootingFromNode(nodeNo) # remove elastic footing from node
sup.RemoveElasticFooting(footId)         # delete elastic footing definition
```

## Example

See [assign-fixed-supports.py](./scripts/assign-fixed-supports.py) for a complete working example.
See [check-tension-compression-spring.py](./scripts/check-tension-compression-spring.py) for verifying a Tension/Compression-Only spring assignment actually produced a usable spring before running analysis.

## Gotchas

- `AssignSupportToNode` takes a SINGLE node ID — it does NOT accept a list; iterate with a loop
- Support methods (`CreateSupportFixed`, `CreateSupportPinned`, `CreateSupportFixedBut`, `AssignSupportToNode`, `GetSupportNodes`, `GetSupportType`, `GetSupportInformation`, `DeleteSupport`) **raise on failure** instead of returning a negative code — call them directly; `execute_code` reports any uncaught error
- **`GetSupportInformationEx(nodeNo)` raises `[-1] General error.` if the node has no support assigned** — confirmed live. Check `nodeNo in sup.GetSupportNodes()` first, or wrap the call in `try/except`, before querying a node that might be unsupported (see [assign-fixed-supports.py](./scripts/assign-fixed-supports.py) for the guarded pattern).
- When nodes were added in-memory in the same script, call `SaveModel(True)` before assigning supports — do NOT use `UpdateStructure()` (it discards unsaved geometry)
- For `CreateSupportFixedBut`: use `-1` for spring DOFs (not `1`); `1` = released, `0` = fixed, `-1` = spring
- **Compression-only springs are only compatible with plain linear static analysis** — P-Delta, Nonlinear, Buckling, and Cable analysis all error out, because the engine's spring deactivation iterations cannot coexist with those solver modes. Applies to ElasticMat/PlateMat `springType=1` and to `SetSupportSpringBehavior`-marked springs alike.
- **DO NOT use `CreateTensionOnlySpring`/`CreateCompressionOnlySpring` — their signature is `(kFX, kFY, kFZ)`, direction enable flags only, with NO stiffness parameter at all** — so the support they create structurally cannot carry a spring stiffness value; it's not a silent data-loss bug, there's nowhere to put one. Confirmed live this is independent of any pre-existing spring being overwritten: reassigning the exact same already-created support ID (no new `Create...` call) to an unrelated node with NO prior support at all (nothing to destroy) reproduces the identical zero-stiffness result — ruling out "it works but assignment destroys a real spring that was already there." It also always creates a **new** support definition and assigns it via `AssignSupportToEntityList`, which replaces whatever was on the target node — it does not modify an existing spring in place, unlike the real STAAD.Pro `SPRING TENSION`/`COMPRESSION` command it's meant to represent. Any model built with these two functions will fail analysis with `ERROR: SPRING TENSION/COMPRESSION SPECIFIED AT A JOINT DIRECTION THAT DOES [NOT HAVE A SPRING]` (status `4`).
- **Use `SetSupportSpringBehavior(compressionOrTensionFlag, supportNodes, springFlags)` instead** — confirmed live and matches STAAD.Pro's own production import/export code (`StaadWriter.cs`), which calls only this function, never `CreateTensionOnlySpring`/`CreateCompressionOnlySpring`:
  - `compressionOrTensionFlag`: `0` = compression-only, `1` = tension-only — per the openstaadpy source docstring. This is easy to get backwards; `GetSupportInformationEx` does not expose which of the two was actually applied, so double-check against the source rather than assuming.
  - It validates upfront, but only at the node level, not per-direction: raises `[-7504] Spring not defined at node.` only if the node has NO spring in any direction. If the node has a real spring in FY but you flag FX (which has none), it succeeds silently and creates the same broken, unanalyzable state as the two functions above — confirmed live. Always check each flagged direction individually against `GetSupportInformationEx(nodeNo)` before calling.
  - When the flagged direction does have a real spring, it modifies the existing support **in place** — confirmed live: `GetSupportInformationEx(nodeNo)` is unchanged (same support ID, same stiffness) before and after the call, and the resulting model analyzes successfully.
  - Always establish the real spring first via `CreateSupportFixedBut` (`ReleaseSpec=-1`, real `SpringSpec` value), assign it, THEN call `SetSupportSpringBehavior` — see [check-tension-compression-spring.py](./scripts/check-tension-compression-spring.py).
- **Marking a node via `SetSupportSpringBehavior` (or the broken functions above) adds it to a separate, persistent, model-level `SPRING TENSION`/`COMPRESSION` joint list that `RemoveSupportFromNode` does NOT clear** — confirmed live: after marking a node and later calling `RemoveSupportFromNode` on it, analysis fails on the *entire model* with the same `"...DOES [NOT HAVE A SPRING]"` error, even though `GetSupportNodes()` shows the node as unsupported. There is no known function in this API to clear that list once a node has been added to it. If you need to "undo" a tension/compression-only marking, leave a real spring on the node (do not fully remove its support) — removing it entirely leaves the model permanently broken for analysis.
- **Assigning any support to a node that already has one replaces it silently** — confirmed live: assigning a new support to a node with an existing Fixed-But support replaced it with no error, no warning, and no trace of the discarded support. This is general OpenSTAAD behavior — be aware of it whenever reassigning a node that may already be supported.

