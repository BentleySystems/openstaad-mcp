# hydrostatic-tank.py
# Assigns hydrostatic water pressure to walls and base of a plate tank.
# Reads baseUnit from staad.GetBaseUnit() and vertical axis from staad.Geometry.IsZUp().
# Uses AddElementTrapPressureEx for wall plates (variable pressure with depth)
# and AddElementPressure for the base plate (uniform full-head pressure).

geo = staad.Geometry
load = staad.Load

# Read units and axis from model — never hardcode
baseUnit = staad.GetBaseUnit()          # 'English' or 'Metric'
verticalAxis = 'Z' if geo.IsZUp() else 'Y'

# Water unit weight in model units
if baseUnit == 'English':
    gamma_water = 62.4 / 1728000.0   # kip/in^3
elif baseUnit == 'Metric':
    gamma_water = 9.81               # kN/m^3
else:
    raise ValueError(f'Unsupported baseUnit: {baseUnit}')

axis_index = 1 if verticalAxis == 'Y' else 2

# Build node elevation map; find water surface (max) and tank base (min)
node_coords = {}
max_elev = -1e30
min_elev = 1e30

for nid in geo.GetNodeList():
    x, y, z = geo.GetNodeCoordinates(nid)
    node_coords[nid] = (x, y, z)
    elev = node_coords[nid][axis_index]
    if elev > max_elev:
        max_elev = elev
    if elev < min_elev:
        min_elev = elev

# Classify plates: horizontal (same elevation all nodes) = base, else = wall
wall_groups = {}   # signature (corner elevations) → [plate_ids]
base_plates = []

for pid in geo.GetPlateList():
    nodes = [n for n in geo.GetPlateIncidence(pid) if n != 0]
    elevations = [node_coords[n][axis_index] for n in nodes]
    if (max(elevations) - min(elevations)) < 0.001:
        base_plates.append(pid)
    else:
        signature = tuple(round(e, 6) for e in elevations)
        wall_groups.setdefault(signature, []).append(pid)

# Create load case (type 7 = fluid/hydrostatic)
lc = load.CreateNewPrimaryLoadEx('Hydrostatic Water Pressure', 7)
load.SetLoadActive(lc)

# Wall loads — group plates with identical corner elevation signature together
# loadDir=3 (LocalZ normal), varyDir=1 (LocalX varies with depth)
for signature, plate_ids in sorted(wall_groups.items()):
    p1 = gamma_water * (max_elev - signature[0])
    p2 = gamma_water * (max_elev - signature[1])
    p3 = gamma_water * (max_elev - signature[2])
    p4 = gamma_water * (max_elev - signature[3])
    load.AddElementTrapPressureEx(plate_ids, 3, 1, p1, p2, p3, p4)

# Base load — uniform full-head pressure
full_head = gamma_water * (max_elev - min_elev)
load.AddElementPressure(base_plates, 3, full_head, 0.0, 0.0, 0.0, 0.0)

print(f'Load case {lc}: {len(wall_groups)} wall groups, {len(base_plates)} base plates')
print(f'Water surface elevation: {max_elev:.3f}, base: {min_elev:.3f}')
print(f'Full head pressure: {full_head:.6f}')
