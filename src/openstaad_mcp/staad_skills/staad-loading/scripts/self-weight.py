# self-weight.py
# Creates a primary load case and adds self-weight in the gravity direction.
# Always call SetLoadActive before adding load items.
# Use staad.Geometry.IsZUp() to choose the correct gravity direction.

load = staad.Load

# Create load case and activate it before adding items
lc = load.CreateNewPrimaryLoad('Self Weight')
load.SetLoadActive(lc)          # mandatory — must call before adding items

# AddSelfWeightInXYZ(direction, factor)
# direction: 1=X, 2=Y, 3=Z
# factor: -1.0 in the gravity direction (negative)
# Use direction 2 for Y-up models, direction 3 for Z-up models
load.AddSelfWeightInXYZ(2, -1.0)

print(f'Load case {lc} created: self-weight -Y direction')
