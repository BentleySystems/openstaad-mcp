---
name: staad-geometry
description: 'Use when creating, querying, modifying, or selecting structure geometry: nodes, beams, plates, solids, groups. Covers: AddNode, AddBeam, AddPlate (4 int args not a list), AddSolid, AddMultipleNodes/Beams/Plates, CreateNode/CreateBeam with explicit IDs, shared element ID sequence (beams+plates+solids share one counter — never assume IDs start at 1), GetBeamList, GetNodeList, GetPlateList, GetNodeCoordinates, GetMemberIncidence, SelectBeam, SelectMultipleBeams, ClearMemberSelection, groups (CreateGroupEx, UpdateGroup), SplitBeam, MergeBeams, IntersectBeams, DeleteBeam/Node/Plate, translational repeat, parametric surfaces, physical members. Requires staad-core.'
---

# STAAD.Pro Geometry Modeling

## Instructions

- Define the shorthand once per script: `geo = staad.Geometry`

### Creating Elements
- `geo.AddNode(x, y, z)` → node ID (coordinates in base unit)
- `geo.AddBeam(startNode, endNode)` → beam ID
- `geo.AddPlate(n1, n2, n3, n4)` → plate ID — pass **4 separate int args**, NOT a list
- `geo.AddSolid(n1, n2, n3, n4, n5, n6, n7, n8)` → solid ID

### Bulk Creation (more efficient than loops)
- `geo.AddMultipleNodes([[x,y,z], ...])` → list of node IDs
- `geo.AddMultipleBeams([[start,end], ...])` → list of beam IDs
- `geo.AddMultiplePlates([[n1,n2,n3,n4], ...])` → list of plate IDs

### Explicit ID Creation
- `geo.CreateNode(nodeNo, x, y, z)` — creates node with a specific ID
- `geo.CreateBeam(beamNo, startNode, endNode)` — beam with specific ID
- `geo.CreatePlate(plateNo, nA, nB, nC, nD)` — plate with specific ID (nD=0 for triangle)
- `geo.CreateSolid(solidNo, nA, nB, nC, nD, nE, nF, nG, nH)` — solid with specific ID

### Shared Element ID Sequence
**IMPORTANT:** Beams, plates, and solids share a SINGLE continuous ID counter.
- If you create 10 beams (IDs 1–10) then 4 plates, plates get IDs 11–14, NOT 1–4
- NEVER assume element IDs start at 1 for each type
- Always retrieve actual IDs: `geo.GetBeamList()`, `geo.GetPlateList()`, `geo.GetSolidList()`

### Quick Reference

| Function | Returns | Notes |
|----------|---------|-------|
| `GetNodeCount()` | `int` | total nodes |
| `GetMemberCount()` | `int` | total beams |
| `GetPlateCount()` | `int` | total plates |
| `GetSolidCount()` | `int` | total solids |
| `GetNodeList()` | `list` | all node IDs |
| `GetBeamList()` | `list` | all beam IDs |
| `GetPlateList()` | `list` | all plate IDs |
| `GetSolidList()` | `list` | all solid IDs |
| `GetLastNodeNo()` | `int` | highest node ID |
| `GetLastBeamNo()` | `int` | highest beam ID |
| `GetNodeCoordinates(nid)` | `(x,y,z)` | |
| `GetMemberIncidence(bid)` | `(start,end)` | start/end node IDs |
| `GetPlateIncidence(pid)` | `(n1,n2,n3,n4)` | 0 if triangle |
| `GetBeamLength(bid)` | `float` | in base units |
| `GetNodeDistance(nA, nB)` | `float` | distance between two nodes |
| `IsColumn(bid, tol)` | `bool` | True if near-vertical (tol in degrees) |
| `IsBeam(bid, tol)` | `bool` | True if near-horizontal |
| `IsOrphanNode(nid)` | `bool` | True if not connected |

### Modifying Elements
- `geo.SetNodeCoordinate(nodeNo, x, y, z)` — move a node
- `geo.DeleteNode(nodeNo)` / `geo.DeleteBeam(beamNo)` / `geo.DeletePlate(plateNo)` / `geo.DeleteSolid(solidNo)`
- `geo.MergeNodes(newId, nodeList)` — merge coincident nodes
- `geo.SplitBeamInEqlParts(beamNo, nParts)` — split beam into equal segments
- `geo.SplitBeam(beamNo, nodes, distToNodes)` — split at specific distances
- `geo.IntersectBeams(method, beamList, tolerance)` — split beams at intersections
- `geo.MergeBeams(beamList, newId, propId, betaAngle, material)` — merge collinear beams
- `geo.RenumberBeam(oldNo, newNo)` — renumber a beam
- `geo.BreakBeamsAtSpecificNodes(nodeList)` — break beams at nodes

### Selection
Selections are additive — **always clear before starting a new selection**.

| Operation | Beams | Nodes | Plates | Solids |
|-----------|-------|-------|--------|--------|
| Clear | `ClearMemberSelection()` | `ClearNodeSelection()` | `ClearPlateSelection()` | `ClearSolidSelection()` |
| Single | `SelectBeam(id)` | `SelectNode(id)` | `SelectPlate(id)` | `SelectSolid(id)` |
| Multiple | `SelectMultipleBeams(ids)` | `SelectMultipleNodes(ids)` | `SelectMultiplePlates(ids)` | `SelectMultipleSolids(ids)` |
| Query | `GetSelectedBeams()` | `GetSelectedNodes()` | `GetSelectedPlates()` | `GetSelectedSolids()` |
| Count | `GetNoOfSelectedBeams()` | `GetNoOfSelectedNodes()` | `GetNoOfSelectedPlates()` | `GetNoOfSelectedSolids()` |

All select/clear functions return `0` on success.

### Groups

| Function | Description |
|----------|-------------|
| `CreateGroup(type, name)` | create empty group |
| `CreateGroupEx(type, name, entityList)` | create with entities |
| `UpdateGroup(name, option, entityList)` | modify: 0=Replace, 1=Remove, 2=Add |
| `DeleteGroup(name)` | delete group |
| `GetGroupCount(type)` | count by type |
| `GetGroupNames(type)` | list names |
| `GetGroupEntityCount(name)` | entity count |
| `GetGroupEntities(name)` | entity ID list |

Group types: 1=Nodes, 2=Members, 3=Plates, 4=Solids, 5=Geometry, 6=FloorBeam

### Translational Repeat
Duplicate selected geometry along an axis:
```python
geo.DoTranslationalRepeat(
    link_bays=True, open_base=False,
    axis_dir=0,  # 0=GX, 1=GY, 2=GZ
    spacing_list=[5.0, 5.0], no_of_bays=2,
    renumber_bays=False, renumber_list=[],
    geometry_only_flag=False
)
```

### Parametric Surfaces (Mesh Generation)
```python
surf_id = geo.DefineParametricSurface(name, type, origin_Node, x_vertex_node, y_vertex_node, vertices_list, auto_generate)
geo.AddParametricSurfaceToModel(surf_id)
geo.CommitParametricSurfaceMesh(surf_id)
```
Types: 1=Wall, 2=Slab

### Physical Members
```python
geo.CreatePhysicalMember(memberList)
pm_count = geo.GetPhysicalMemberCount()
```

### Unique IDs (External Reference Strings)
- `geo.SetNodeUniqueID(nodeNo, uniqueID)` / `geo.GetNodeUniqueID(nodeNo)`
- `geo.SetMemberUniqueID(beamNo, uniqueID)` / `geo.GetMemberUniqueID(beamNo)`
- `geo.SetPlateUniqueID(plateNo, uniqueID)` / `geo.GetPlateUniqueID(plateNo)`

## Examples
- [portal-frame.py](./scripts/portal-frame.py) — create a simple portal frame with supports
- [add-beam.py](./scripts/add-beam.py) — add a single beam between two new nodes
- [select-members.py](./scripts/select-members.py) — select single and multiple beams
- [plate-max-area.py](./scripts/plate-max-area.py) — find plate with maximum area (uses `GetPlateIncidence`, cross-product)

## Gotchas
- `AddPlate` takes 4 separate int arguments, NOT a list — `geo.AddPlate(n1, n2, n3, n4)` not `geo.AddPlate([n1,n2,n3,n4])`
- After adding geometry in the same script, call `staad.SetSilentMode(True)` → `staad.SaveModel(True)` → `staad.SetSilentMode(False)` before assigning properties, supports, or loads — do NOT use `UpdateStructure()` (it discards unsaved in-memory geometry)
- Always use `geo` (OSGeometry) for selections — do NOT use `OSView.SelectByItemList`
- Beams, plates, and solids share one ID counter — never assume IDs start at 1 per type
