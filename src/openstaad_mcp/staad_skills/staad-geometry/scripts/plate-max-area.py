# plate-max-area.py
# Finds the plate with the maximum area in a large model (100k+ plates).
# Optimized: fetches all node coordinates once into a dict, then iterates plates.
# Uses progress() for real-time feedback on large models.
# GetPlateIncidence(pid) returns (n1, n2, n3, n4) — n4 is 0 for triangles.

geo = staad.Geometry

# ── 1. Area calculation helpers (defined before use) ─────────────

def tri_area(p0, p1, p2):
    """Area of a 3D triangle via cross product of edge vectors."""
    v1x, v1y, v1z = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    v2x, v2y, v2z = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
    cx = v1y*v2z - v1z*v2y
    cy = v1z*v2x - v1x*v2z
    cz = v1x*v2y - v1y*v2x
    return 0.5 * math.sqrt(cx*cx + cy*cy + cz*cz)

def plate_area(pts):
    """Area of a plate (3 or 4 coordinate tuples)."""
    if len(pts) == 3:
        return tri_area(pts[0], pts[1], pts[2])
    if len(pts) == 4:
        return (tri_area(pts[0], pts[1], pts[2])
              + tri_area(pts[0], pts[2], pts[3]))
    return 0.0

# ── 2. Pre-fetch all node coordinates into a dict (single pass) ──
node_ids = geo.GetNodeList()
total_nodes = len(node_ids)
coords = {}
for i, nid in enumerate(node_ids):
    if i % 500 == 0:
        progress(f"Reading nodes {i}/{total_nodes}")
    coords[nid] = geo.GetNodeCoordinates(nid)

progress(f"Loaded {total_nodes} nodes. Scanning plates...")

# ── 3. Iterate plates and find maximum area ──────────────────────
plates = geo.GetPlateList()
total_plates = len(plates)

max_area = 0.0
max_plate = None

for i, pid in enumerate(plates):
    if i % 500 == 0:
        progress(f"Plate {i}/{total_plates}")

    incidence = geo.GetPlateIncidence(pid)
    pts = [coords[nid] for nid in incidence if nid != 0]

    area = plate_area(pts)
    if area > max_area:
        max_area = area
        max_plate = pid

# Include incidence nodes of the winner for context
winner_nodes = [nid for nid in geo.GetPlateIncidence(max_plate) if nid != 0]
result = {
    "plate": max_plate,
    "area": round(max_area, 4),
    "nodes": winner_nodes,
    "total_plates": total_plates,
}
