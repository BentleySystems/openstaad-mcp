---
name: staad-supports
description: "Use when creating or assigning supports, boundary conditions, restraints, pins, fixed bases, springs, inclined supports, elastic mat, plate mat, or elastic footing. Covers: CreateSupportFixed (all 6 DOF), CreateSupportPinned, CreateSupportFixedBut (selective releases/springs), CreateInclinedSupport, CreateElasticMat (subgrade modulus), CreatePlateMat, CreateElasticFooting, AssignSupportToNode (single node — loop for multiple), GetSupportCount, GetSupportNodes, GetSupportInformation, RemoveSupportFromNode, DeleteSupport. Requires staad-core."
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
mat_id = sup.CreateElasticMat(
    direction=5,     # Y Only — compression only in Y
    subgrade=20.0,   # kN/m^3 or equivalent
    printFlag=0,
    springType=1     # 1=Compression only
)
sup.AssignSupportToEntityList(mat_id, [41, 42, 43])
```

### Plate Mat Support

```python
pm_id = sup.CreatePlateMat(direction, subgrades, printFlag, springType)
```

### Elastic Footing

```python
foot_id = sup.CreateElasticFooting(length, width, direction, subgrade)
```

### Assigning Supports

- `sup.AssignSupportToNode(nodeID, supportID)` — assigns to a **SINGLE node**
- Use a `for` loop to assign to multiple nodes

### Workflow

1. Call `openstaad_execute_code` with code that calls `staad.Geometry.GetNodeCount()` — then check the result via `openstaad_get_job_status` / `openstaad_get_job_result` to confirm nodes exist
2. After adding geometry in the same script, call `SaveModel(True)` before assigning supports (see staad-core for SaveModel vs UpdateStructure)
3. Create support type once → assign to base nodes in a loop

### Querying

| Function                          | Returns                                           |
| --------------------------------- | ------------------------------------------------- |
| `GetSupportCount()`               | total supports                                    |
| `GetSupportNodes()`               | list of supported node IDs                        |
| `GetSupportType(nodeNo)`          | support type code                                 |
| `GetSupportInformation(nodeNo)`   | `(type, releases, springs)`                       |
| `GetSupportInformationEx(nodeNo)` | `(supportNo, type, releases, springs)`            |
| `GetSupportName(supportNo)`       | support name                                      |
| `GetCountOfElasticMat()`          | elastic mat count                                 |
| `GetElasticMatDetail(matId)`      | `(direction, subgrade, print, spring, nodeCount)` |

### Removing

```python
sup.RemoveSupportFromNode([1, 2, 3])   # remove from nodes
sup.DeleteSupport(supportNo)            # delete definition
sup.RemoveElasticMatFromNode(nodeNo)     # remove elastic mat from node
sup.RemoveElasticMat(matId)              # delete elastic mat definition
```

## Example

See [assign-fixed-supports.py](./scripts/assign-fixed-supports.py) for a complete working example.

## Gotchas

- `AssignSupportToNode` takes a SINGLE node ID — it does NOT accept a list; iterate with a loop
- When nodes were added in-memory in the same script, call `SaveModel(True)` before assigning supports — do NOT use `UpdateStructure()` (it discards unsaved geometry)
- For `CreateSupportFixedBut`: use `-1` for spring DOFs (not `1`); `1` = released, `0` = fixed, `-1` = spring
