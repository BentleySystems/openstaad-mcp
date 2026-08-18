# enclosed-zone.py
# Defines an enclosed zone over a floor panel and applies a zone load.
# Enclosed zone boundary nodes MUST be in polygon traversal order, not sorted-by-ID
# order — get the correct order from Geometry.IdentifyFloorBoundariesFromNodes()
# + GetFloorBoundaryNodesByIndex(), not from GetFloorNodesAtLevel() directly.

geo = staad.Geometry
load = staad.Load

# 1. Pick a floor level and get all nodes at that level (sorted by ID — NOT boundary order)
levels = geo.GetFloorLevels()
level = levels[1]  # e.g. the first upper floor level
raw_nodes = geo.GetFloorNodesAtLevel(level)

# 2. Compute the floor boundary(ies) from those nodes, then fetch the
#    correctly-ordered boundary node list for boundary index 0
boundary_count = geo.IdentifyFloorBoundariesFromNodes(raw_nodes)
ordered_boundary = geo.GetFloorBoundaryNodesByIndex(0)

# 3. Define the enclosed zone using the ORDERED boundary (not raw_nodes)
load.DefineEnclosedZone('ZONE1', ordered_boundary)

# 4. Apply a load to the zone in the active load case
lc = load.CreateNewPrimaryLoadEx('Zone Load', 0)  # loadType 0 = Dead
load.SetLoadActive(lc)
# loadDirection: 3=Local Z, 4=Global X, 5=Global Y, 6=Global Z
load.AddEnclosedZoneLoad('ZONE1', 5, -10.0)

print(f'Enclosed zone ZONE1 defined on boundary {ordered_boundary}, load case {lc}')
