# add-plate.py
# Demonstrates creating quad plates and triangular plates.
#
# TRIANGLE SENTINEL: all plate functions take exactly 4 node args.
# Pass 0 as the 4th arg to signal a 3-node (triangular) plate.
#   geo.AddPlate(n1, n2, n3, 0)               <- triangle
#   geo.AddMultiplePlates([[n1,n2,n3,0]])      <- triangle row
#   geo.CreatePlate(id, nA, nB, nC, 0)        <- explicit-ID triangle

geo = staad.Geometry

# ── Quad plate (4 corners in a 1×1 square) ──────────────────────────────────
n1 = geo.AddNode(0, 0, 0)
n2 = geo.AddNode(1, 0, 0)
n3 = geo.AddNode(1, 1, 0)
n4 = geo.AddNode(0, 1, 0)

quad_id = geo.AddPlate(n1, n2, n3, n4)
print(f'Quad plate {quad_id}: nodes {n1},{n2},{n3},{n4}')

# ── Triangular plate (apex above the midpoint) ───────────────────────────────
n5 = geo.AddNode(0.5, 0, 1)   # apex node

# 0 is the sentinel for the missing 4th node
tri_id = geo.AddPlate(n1, n2, n5, 0)
print(f'Triangle plate {tri_id}: nodes {n1},{n2},{n5}  (4th arg = 0 sentinel)')

# ── Bulk creation mixing quads and triangles ─────────────────────────────────
# Each row has exactly 4 ints; 0 is the sentinel for triangle (no 4th node)
plate_data = [
    [n1, n2, n3, n4],   # quad
    [n1, n2, n5,  0],   # triangle (0 = sentinel, no 4th node)
    [n2, n3, n5,  0],   # triangle (0 = sentinel, no 4th node)
]
plate_ids = geo.AddMultiplePlates(plate_data)
print(f'Bulk plates: {plate_ids}')

# ── Explicit-ID creation (triangle) ──────────────────────────────────────────
# geo.CreatePlate(plateNo, nA, nB, nC, nD) — nD=0 is the sentinel for triangle
next_id = max(geo.GetPlateList()) + 1
geo.CreatePlate(next_id, n1, n3, n5, 0)   # nD=0 → triangle sentinel
print(f'Explicit-ID triangle plate {next_id}')
