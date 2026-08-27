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

Standalone spring supports (not tied to a mat/footing) that only resist compression or only resist tension. `kFX`/`kFY`/`kFZ` are direction flags — pass a value greater than 0 to enable the spring in that translational direction:

```python
comp_id = sup.CreateCompressionOnlySpring(kFX=1, kFY=0, kFZ=1)   # spring active in X and Z
tens_id = sup.CreateTensionOnlySpring(kFX=0, kFY=1, kFZ=0)       # spring active in Y
```
Both return a support reference number ID — assign with `AssignSupportToEntityList(supportId, [nodeId, ...])`, which reports `type` 14 for compression-only and 15 for tension-only springs. Inspect an assigned spring with `GetSupportInformationEx(nodeNo)`.

### Assigning Supports

- `sup.AssignSupportToNode(nodeID, supportID)` — assigns to a **SINGLE node**
- Use a `for` loop to assign to multiple nodes

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

## Gotchas

- `AssignSupportToNode` takes a SINGLE node ID — it does NOT accept a list; iterate with a loop
- Support methods (`CreateSupportFixed`, `CreateSupportPinned`, `CreateSupportFixedBut`, `AssignSupportToNode`, `GetSupportNodes`, `GetSupportType`, `GetSupportInformation`, `DeleteSupport`) **raise on failure** instead of returning a negative code — call them directly; `execute_code` reports any uncaught error
- When nodes were added in-memory in the same script, call `SaveModel(True)` before assigning supports — do NOT use `UpdateStructure()` (it discards unsaved geometry)
- For `CreateSupportFixedBut`: use `-1` for spring DOFs (not `1`); `1` = released, `0` = fixed, `-1` = spring
- **Compression-only supports (`springType=1`) are only compatible with plain linear static analysis** — using them with P-Delta, Nonlinear, Buckling, or Cable analysis causes an engine error. The engine uses spring deactivation iterations that cannot coexist with those solver modes.
- The same tension/compression-only incompatibility applies to `CreateCompressionOnlySpring`/`CreateTensionOnlySpring` — use plain linear static analysis only.
- `CreateCompressionOnlySpring`/`CreateTensionOnlySpring` supports must be assigned with `AssignSupportToEntityList` — confirmed live: `AssignSupportToNode` fails with `"Unable to assign support to node(s)"` for these two support types even on a node with no existing support, while `AssignSupportToEntityList(supportId, [nodeId])` succeeds.
