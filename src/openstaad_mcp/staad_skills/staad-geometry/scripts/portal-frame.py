# portal-frame.py
# Creates a simple portal frame: 2 columns + 1 beam, fixed supports at base.
# Adjust coordinates to match the model baseUnit (English=inches, Metric=meters).

geo = staad.Geometry

# Coordinates in base units — English: 10ft cols = 120in, 20ft span = 240in
n1 = geo.AddNode(0, 0, 0)       # base left
n2 = geo.AddNode(0, 120, 0)     # top left
n3 = geo.AddNode(240, 120, 0)   # top right
n4 = geo.AddNode(240, 0, 0)     # base right

b1 = geo.AddBeam(n1, n2)        # left column
b2 = geo.AddBeam(n2, n3)        # horizontal beam
b3 = geo.AddBeam(n3, n4)        # right column

# SaveModel(True) flushes in-memory geometry to disk before assigning supports
# Do NOT use UpdateStructure() here — it discards in-memory geometry
staad.SetSilentMode(True)
staad.SaveModel(True)
staad.SetSilentMode(False)

sup = staad.Support
fix_id = sup.CreateSupportFixed()
sup.AssignSupportToNode(n1, fix_id)  # AssignSupportToNode takes ONE node at a time
sup.AssignSupportToNode(n4, fix_id)

print(f'Portal frame: nodes {n1},{n2},{n3},{n4} beams {b1},{b2},{b3}')
print(f'Fixed supports at nodes {n1} and {n4}')
