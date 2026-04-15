# create-floor-plates.py
# Creates four nodes forming a floor panel, adds a plate element, and assigns thickness.
# Example uses English units (inches). Adjust coordinates for Metric (meters).

geo = staad.Geometry

# Floor panel at elevation Y=118.11 in (~3m), 3m x 5m footprint
n1 = geo.AddNode(0, 118.11, 0)
n2 = geo.AddNode(118.11, 118.11, 0)
n3 = geo.AddNode(118.11, 118.11, 196.85)
n4 = geo.AddNode(0, 118.11, 196.85)

# AddPlate takes 4 separate int args — NOT a list
pid = geo.AddPlate(n1, n2, n3, n4)
print(f'Plate {pid} created with nodes {n1},{n2},{n3},{n4}')

# SaveModel(True) flushes in-memory geometry to disk before property assignment
# Do NOT use UpdateStructure() here — it discards in-memory geometry
staad.SetSilentMode(True)
staad.SaveModel(True)
staad.SetSilentMode(False)

prop = staad.Property

# CreatePlateThicknessProperty takes a list of 4 floats (one per corner)
t = 3.937   # 100 mm in inches
thick_id = prop.CreatePlateThicknessProperty([t, t, t, t])
prop.AssignPlateThickness([pid], thick_id)

print(f'Thickness {t} in (property {thick_id}) assigned to plate {pid}')
