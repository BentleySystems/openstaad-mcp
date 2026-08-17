---
name: staad-geometry
description: 'Use when creating, querying, modifying, or selecting structure geometry: nodes, beams, plates, solids, groups. Covers: AddNode, AddBeam, AddPlate (4 int args not a list), AddSolid, AddMultipleNodes/Beams/Plates, CreateNode/CreateBeam with explicit IDs, shared element ID sequence (beams+plates+solids share one counter — never assume IDs start at 1), GetBeamList, GetNodeList, GetPlateList, GetNodeCoordinates, GetMemberIncidence, SelectBeam, SelectMultipleBeams, ClearMemberSelection, groups (CreateGroupEx, UpdateGroup), SplitBeam, MergeBeams, IntersectBeams, GetIntersectBeamsCount, BreakBeamsAtSpecificNodes, GetCountOfBreakableBeamsAtSpecificNodes, SetPID, GetPID, SetFlagForHiddenEntities, GetFlagForHiddenEntities, SetCheckForIdenticalEntity, DeleteBeam/Node/Plate/Solid, DeleteGroup, DeletePhysicalMember, RemoveParametricSurfaceMesh, translational repeat, parametric surfaces, physical members, unique IDs. Requires staad-core.'
---

# STAAD.Pro Geometry Modeling

## Instructions

- Define the shorthand once per script: `geo = staad.Geometry`

### Creating Elements
- `geo.AddNode(x, y, z)` → node ID (coordinates in base unit)
- `geo.AddBeam(startNode, endNode)` → beam ID
- `geo.AddPlate(n1, n2, n3, n4)` → plate ID — pass **4 separate int args**, NOT a list
  - **Triangle:** the API always takes 4 args; pass `0` as a sentinel for the missing 4th node → `geo.AddPlate(n1, n2, n3, 0)`
- `geo.AddSolid(n1, n2, n3, n4, n5, n6, n7, n8)` → solid ID

### Bulk Creation (more efficient than loops)
- `geo.AddMultipleNodes([[x,y,z], ...])` → list of node IDs
- `geo.AddMultipleBeams([[start,end], ...])` → list of beam IDs
- `geo.AddMultiplePlates([[n1,n2,n3,n4], ...])` → list of plate IDs
  - **Triangle rows:** each row must have exactly 4 ints; use `0` as the sentinel 4th element → `[n1, n2, n3, 0]`
- `geo.AddMultipleSolids([[n1..n8], ...])` → list of solid IDs (rows of 6/7/8 nodes are auto-padded with `0`)

### Explicit-ID Bulk Creation
Same as the `Add*` bulk functions above but with caller-chosen IDs (thin Python-side loops around `CreateNode`/`CreateBeam`/`CreatePlate` — not raw COM batch calls):
```python
geo.CreateMultipleNodes(node_ids, [[x1,y1,z1], [x2,y2,z2], ...])   # node_ids and coordinate rows must be same length
geo.CreateMultipleBeams(beam_ids, [[start1,end1], [start2,end2], ...])
geo.CreateMultiplePlates(plate_ids, [[n1,n2,n3,n4], ...])          # triangle rows: 0 as 4th node
```

### Explicit ID Creation
- `geo.CreateNode(nodeNo, x, y, z)` — creates node with a specific ID
- `geo.CreateBeam(beamNo, startNode, endNode)` — beam with specific ID
- `geo.CreatePlate(plateNo, nA, nB, nC, nD)` — plate with specific ID
  - **Triangle:** pass `0` for `nD` (the sentinel for a missing 4th node) → `geo.CreatePlate(id, nA, nB, nC, 0)`
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
| `GetPlateNodeCount(pid)` | `int` | 3 or 4 |
| `GetBeamLength(bid)` | `float` | in base units |
| `GetNodeDistance(nA, nB)` | `float` | distance between two nodes |
| `IsColumn(bid, tol)` | `bool` | True if near-vertical (tol in degrees) |
| `IsBeam(bid, tol)` | `bool` | True if near-horizontal |
| `IsOrphanNode(nid)` | `bool` | True if not connected |
| `IsZUp()` | `bool` | True if model uses Z-up convention |
| `GetNodeNumber(x_y_z_coordinates)` | `int` | look up node ID from a `(x,y,z)` tuple |
| `GetLastPlateNo()` | `int` | highest plate ID |
| `GetLastSolidNo()` | `int` | highest solid ID |
| `GetSolidIncidence(sid)` | `(n1..n8)` | 8 corner node IDs |
| `GetNodeIncidence(nid)` | `(x,y,z)` | same data as `GetNodeCoordinates` |
| `GetAreaOfPlates(plateIds)` | `list[float]` | one area value per plate in the input list |
| `GetBeamsConnectedAtNode(nid)` | `list[int]` | beam IDs connected at a node |
| `GetNoOfBeamsConnectedAtNode(nid)` | `int` | count before calling the getter above |

### Modifying Elements
- `geo.SetNodeCoordinate(nodeNo, x, y, z)` — move a node
- `geo.DeleteNode(nodeNo)` / `geo.DeleteBeam(beamNo)` / `geo.DeletePlate(plateNo)` / `geo.DeleteSolid(solidNo)`
- `geo.MergeNodes(newId, nodeList)` — merge coincident nodes
- `geo.SplitBeamInEqlParts(beamNo, nParts)` — split beam into equal segments
- `geo.SplitBeam(beamNo, nodes, distToNodes)` — split at specific distances
- `geo.GetIntersectBeamsCount(beamList, tolerance)` — count before calling `IntersectBeams` (empty `beamList` = all beams; tolerance in base units)
- `geo.IntersectBeams(method, beamList, tolerance)` — split beams at intersections
- `geo.GetCountOfBreakableBeamsAtSpecificNodes(nodeList)` — count before calling `BreakBeamsAtSpecificNodes`
- `geo.BreakBeamsAtSpecificNodes(nodeList)` → `(brokenBeamIds, newBeamIds)` tuple — break beams passing through the given nodes, copying attributes to the new segments
- `geo.MergeBeams(beamList, newId, propId, betaAngle, material)` — merge collinear beams
- `geo.RenumberBeam(oldNo, newNo)` — renumber a beam

### Property IDs (PID)
A separate ID system from element numbers, shared across entity types via `EntityType` (1=Node, 2=Beam, 3=Plate, 4=Solid, 5=Surface — same convention as `view.SelectByItemList`):
```python
geo.SetPID(entityNo, entityType, propertyID)
pid = geo.GetPID(entityNo, entityType)
```

### Hidden Entities & Performance Flags
```python
# Controls whether hidden nodes/plates are included in count/list queries
geo.SetFlagForHiddenEntities(flag)   # 0=All (default), 1=Ignore hidden, 2=Only hidden
flag = geo.GetFlagForHiddenEntities()

# Disable identical-entity checking to speed up bulk Add*/Create* calls
geo.SetCheckForIdenticalEntity(entityType, checkFlag)  # entityType: 1-5 as above
```

### Selection
Selections are additive — **always clear before starting a new selection**.

| Operation | Beams | Nodes | Plates | Solids |
|-----------|-------|-------|--------|--------|
| Clear | `ClearMemberSelection()` | `ClearNodeSelection()` | `ClearPlateSelection()` | `ClearSolidSelection()` |
| Single | `SelectBeam(id)` | `SelectNode(id)` | `SelectPlate(id)` | `SelectSolid(id)` |
| Multiple | `SelectMultipleBeams(ids)` | `SelectMultipleNodes(ids)` | `SelectMultiplePlates(ids)` | `SelectMultipleSolids(ids)` |
| Query | `GetSelectedBeams()` | `GetSelectedNodes()` | `GetSelectedPlates()` | `GetSelectedSolids()` |
| Count | `GetNoOfSelectedBeams()` | `GetNoOfSelectedNodes()` | `GetNoOfSelectedPlates()` | `GetNoOfSelectedSolids()` |

`Select*` returns `bool` (`True` = OK), `SelectMultiple*`/`Clear*` return `None` on success. Query functions return a `tuple` of IDs (empty `()` when nothing is selected).

`Clear*Selection()` empties the entire accumulated selection (verified live across multiple `SelectBeam`/`SelectMultipleBeams` calls) — but it raises (e.g. `OsNoBeamSelected`) if the selection is already empty, so guard the call. See [select-members.py](./scripts/select-members.py) for a `reset_member_selection()` helper.

### Groups

| Function | Description |
|----------|-------------|
| `CreateGroup(type, name)` | create an empty group |
| `CreateGroupEx(type, name, entityList)` | create with entities — raises if `entityList` is empty (verified live); use `CreateGroup` for an empty group |
| `UpdateGroup(name, option, entityList)` | modify: 0=Replace, 1=Remove, 2=Add |
| `DeleteGroup(name)` | delete group |
| `GetGroupCount(type)` | count by type |
| `GetGroupCountAll()` | count across all types |
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

# After committing, query the generated mesh panels
count = geo.GetNoOfGeneratedQuadPanels()
nodeAs, nodeBs, nodeCs, nodeDs = geo.GetGeneratedQuadPanelIncidences()  # empty lists if count == 0
```
Types: 1=Wall, 2=Slab

**Mesh introspection & lifecycle:**
```python
count = geo.GetParametricSurfaceCount()
node_count, element_count = geo.GetParametricSurfaceMeshInfo(surfaceNo)
node_ids, element_ids = geo.GetParametricSurfaceMeshData(surfaceNo)   # actual generated node/plate IDs
geo.RemoveParametricSurfaceMesh(surfaceNo)   # bool; removes the mesh but keeps the surface definition

# Extended info (preferred) — name, type, sub-type, vertex count, mesh size, divisions, meshing method,
# isQuad, origin/axis nodes, opening/region counts, density point/line counts (17 fields total)
info_ex = geo.GetParametricSurfaceInfoEx(surfaceNo)
# GetParametricSurfaceInfo(surfaceNo) also available — simpler 6-field subset (name, type, boundary/density counts, opening/region counts)
surface_name, surface_type, boundary_count, density_count, opening_count, region_count = geo.GetParametricSurfaceInfo(surfaceNo)

geo.SetParametricSurfaceSubType(surfaceName, subType)   # e.g. "FLOOR"
sub_type = geo.GetParametricSurfaceSubType(surfaceName)
geo.SetParametricSurfaceUniqueID(surfaceName, uniqueId)
uid = geo.GetParametricSurfaceUniqueID(surfaceName)
```

**Mesh refinement — density points/lines and openings/regions:**
```python
geo.AddDensityPointToSurface(surfaceNo, pointData)
line_index = geo.AddDensityLineToSurface(surfaceNo, x1, y1, z1, density1, x2, y2, z2, density2, divisions)
ok = geo.AddCircularRegionToSurface(surfaceNo, x, y, z, radius, divisions, density, is_opening=False)
geo.AddPolygonalRegionToSurface(surfaceNo, regionData)
```

### Physical Members
```python
geo.CreatePhysicalMember(memberList)
pm_count = geo.GetPhysicalMemberCount()

# Selection (separate from beam selection)
geo.SelectPhysicalMember(physicalMemberId)
geo.SelectMultiplePhysicalMembers(physicalMemberList)
geo.ClearPhysicalMemberSelection()
geo.SetPhysicalMemberUniqueID(physicalMemberId, uniqueId)
```

**Physical member introspection:**
```python
count = geo.GetPMemberCount()                         # total physical members (distinct from GetPhysicalMemberCount)
ids = geo.GetPhysicalMemberList()
last_id = geo.GetLastPhysicalMemberNo()
uid = geo.GetPhysicalMemberUniqueID(physicalMemberId)

sel_count = geo.GetNoOfSelectedPhysicalMembers()
selected_ids = geo.GetSelectedPhysicalMembers()

# Each physical member maps to 1+ underlying analytical (beam) members
analytical_count = geo.GetAnalyticalMemberCountForPhysicalMember(physicalMemberId)
analytical_ids = geo.GetAnalyticalMembersForPhysicalMember(physicalMemberId)

geo.DeletePhysicalMember(physicalMemberId)
```

### Unique IDs (External Reference Strings)
- `geo.SetNodeUniqueID(nodeNo, uniqueID)` / `geo.GetNodeUniqueID(nodeNo)`
- `geo.SetMemberUniqueID(beamNo, uniqueID)` / `geo.GetMemberUniqueID(beamNo)`
- `geo.SetPlateUniqueID(plateNo, uniqueID)` / `geo.GetPlateUniqueID(plateNo)`
- `geo.SetSolidUniqueID(solidNo, uniqueID)` / `geo.GetSolidUniqueID(solidNo)`
- `geo.SetPhysicalMemberUniqueID(physicalMemberId, uniqueId)`

### CIS/2 Format Incidence (Interop)
Same incidence data as the standard `Get*Incidence` functions above, but each also returns a CIS/2 unique string ID as the first tuple element — used for CIS/2 (CIMsteel) interoperability exports:
```python
unique_str_id, x, y, z = geo.GetNodeIncidence_CIS2(nodeId)
unique_str_id, start_node, end_node = geo.GetMemberIncidence_CIS2(memberId)
unique_str_id, n1, n2, n3, n4 = geo.GetPlateIncidence_CIS2(plateId)
unique_str_id, n1, n2, n3, n4, n5, n6, n7, n8 = geo.GetSolidIncidence_CIS2(solidId)
```

## Examples
- [portal-frame.py](./scripts/portal-frame.py) — create a simple portal frame with supports
- [add-beam.py](./scripts/add-beam.py) — add a single beam between two new nodes
- [add-plate.py](./scripts/add-plate.py) — create quad and triangular plates (shows the `0` triangle convention)
- [select-members.py](./scripts/select-members.py) — select single and multiple beams

## Gotchas
- **Triangle plates use `0` as a sentinel:** all plate functions always take exactly 4 node arguments; `0` tells STAAD the slot is empty (i.e., this is a 3-node element). See [add-plate.py](./scripts/add-plate.py) for a full example.
- `AddPlate` takes 4 separate int arguments, NOT a list — `geo.AddPlate(n1, n2, n3, n4)` not `geo.AddPlate([n1,n2,n3,n4])`
- After adding geometry in the same script, call `staad.SetSilentMode(True)` → `staad.SaveModel(True)` → `staad.SetSilentMode(False)` before assigning properties, supports, or loads — do NOT use `UpdateStructure()` (it discards unsaved in-memory geometry)
- Always use `geo` (OSGeometry) for selections — do NOT use `OSView.SelectByItemList`
- Beams, plates, and solids share one ID counter — never assume IDs start at 1 per type
- `ClearMemberSelection()` (and the node/plate/solid equivalents) empties the whole accumulated selection in one call, but raises `OsNoBeamSelected`/equivalent if the selection is already empty — never call it unconditionally; wrap it in `try: geo.ClearMemberSelection() except Exception: pass`, or check `GetSelectedBeams()` first. See [select-members.py](./scripts/select-members.py)'s `reset_member_selection()` for the reliable pattern
