---
name: staad-supports
description: 'Use when creating or assigning supports, boundary conditions, restraints, pins, fixed bases, springs, inclined supports, elastic mat, plate mat, or elastic footing. Covers: CreateSupportFixed (all 6 DOF), CreateSupportPinned, CreateSupportFixedBut (selective releases/springs), CreateInclinedSupport, CreateElasticMat (subgrade modulus), CreatePlateMat, CreateElasticFooting, AssignSupportToNode (single node — loop for multiple), GetSupportCount, GetSupportNodes, GetSupportInformation, RemoveSupportFromNode, DeleteSupport. Requires staad-core.'
---

# STAAD.Pro Supports

## Instructions

### Basic Supports

**Fixed** — restrains all 6 DOF:
```javascript
const fixId = sup.CreateSupportFixed();
```

**Pinned** — translations restrained, rotations free:
```javascript
const pinId = sup.CreateSupportPinned();
```

**Fixed-But** — selective releases or springs:
```javascript
// releaseSpec: [FX,FY,FZ,MX,MY,MZ] → 0=fixed, 1=released, -1=spring
// springSpec:  [KFX,KFY,KFZ,KMX,KMY,KMZ] → spring stiffness
const supId = sup.CreateSupportFixedBut(
    [0, -1, 0, 0, 0, 1],   // ReleaseSpec: FY=spring, MZ=released
    [0, 100.0, 0, 0, 0, 0]  // SpringSpec: KFY=100
);
```

### Inclined Supports
```javascript
const supId = sup.CreateInclinedSupport(
    2,             // inclinedType: 1=Pinned, 2=Fixed, 3=FixedBut
    2,             // refType: 0=distances, 1=coordinates, 2=node reference
    1,             // refNode
    [0, 0, 0],     // coord
    [0,0,0,0,0,0], // releaseSpec
    [0,0,0,0,0,0]  // springSpec
);
```

### Elastic Mat Support (Soil Springs)
Spring support distributed over tributary area:
```javascript
const matId = sup.CreateElasticMat(
    5,      // direction (see codes below)
    20.0,   // subgrade (kN/m^3 or equivalent)
    0,      // printFlag
    1       // springType: 0=None, 1=Compression only, 2=Multi-linear
);
sup.AssignSupportToEntityList(matId, [41, 42, 43]);
```

### Plate Mat Support
```javascript
const pmId = sup.CreatePlateMat(direction, subgrades, printFlag, springType);
```

### Elastic Footing
```javascript
const footId = sup.CreateElasticFooting(length, width, direction, subgrade);
```

### Assigning Supports
- `sup.AssignSupportToNode(nodeID, supportID)` — assigns to a **SINGLE node**
- Use a `for` loop to assign to multiple nodes

### Workflow
1. Use `execute_code` to call `staad.Geometry.GetNodeCount()` and confirm the model has nodes
2. After adding geometry in the same script, call `staad.SaveModel(true)` before assigning supports — do NOT use `UpdateStructure()` (it discards unsaved geometry)
3. Create support type once → assign to base nodes in a loop

### Querying

| Function | Returns |
|----------|---------|
| `GetSupportCount()` | total supports |
| `GetSupportNodes()` | array of supported node IDs |
| `GetSupportType(nodeNo)` | support type code |
| `GetSupportInformation(nodeNo)` | `[type, releases, springs]` |
| `GetSupportInformationEx(nodeNo)` | `[supportNo, type, releases, springs]` |
| `GetSupportName(supportNo)` | support name |
| `GetCountOfElasticMat()` | elastic mat count |
| `GetElasticMatDetail(matId)` | `[direction, subgrade, print, spring, nodeCount]` |

### Removing
```javascript
sup.RemoveSupportFromNode([1, 2, 3]);   // remove from nodes
sup.DeleteSupport(supportNo);            // delete definition
sup.RemoveElasticMatFromNode(nodeNo);    // remove elastic mat from node
sup.RemoveElasticMat(matId);             // delete elastic mat definition
```

## Example
See [assign-fixed-supports.js](./scripts/assign-fixed-supports.js) for a complete working example.

## Gotchas
- `AssignSupportToNode` takes a SINGLE node ID — it does NOT accept an array; iterate with a loop
- When nodes were added in-memory in the same script, call `SaveModel(true)` before assigning supports — do NOT use `UpdateStructure()` (it discards unsaved geometry)
- For `CreateSupportFixedBut`: use `-1` for spring DOFs (not `1`); `1` = released, `0` = fixed, `-1` = spring
