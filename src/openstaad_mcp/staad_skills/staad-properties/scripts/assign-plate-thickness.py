# assign-plate-thickness.py
# Assigns a uniform thickness to all plates in the model.
# Always retrieve actual plate IDs — never assume they start at 1.
# CreatePlateThicknessProperty requires a list of 4 floats (one per corner node).

geo = staad.Geometry
prop = staad.Property

# Get actual plate IDs
plate_ids = list(geo.GetPlateList())
print(f'Plates found: {plate_ids}')

# Create thickness property — 4 floats required, one per corner node
t = 3.937   # 100 mm expressed in inches (English model); use meters for Metric
thick_id = prop.CreatePlateThicknessProperty([t, t, t, t])
print(f'Created thickness property ID: {thick_id} (t={t} in)')

# Assign to all plates
prop.AssignPlateThickness(plate_ids, thick_id)
print(f'Assigned thickness {t} in to {len(plate_ids)} plates')
