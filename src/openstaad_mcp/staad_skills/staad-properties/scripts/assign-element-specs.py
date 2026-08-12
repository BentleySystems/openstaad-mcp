# assign-element-specs.py
# Demonstrates creating and assigning element (plate) specs: plane stress and offset.

prop = staad.Property
geo = staad.Geometry

plate_ids = list(geo.GetPlateList())
print(f'Plates: {len(plate_ids)}')

# Plane stress spec — spec_id can legitimately be 0, don't treat that as failure
plane_stress_id = prop.CreateElementPlaneStressSpec()
print(f'CreateElementPlaneStressSpec -> spec_id: {plane_stress_id}')
result = prop.AssignElementSpecToPlate(plate_ids[:2], plane_stress_id)
print(f'Assigned to first 2 plates: {result}')

# Offset spec — direction: 0=Local, 1=Global; nodeIndex: 1-4
offset_id = prop.CreateElementOffsetSpec(0, 1, 0.1, 0.0, 0.0)
print(f'CreateElementOffsetSpec -> spec_id: {offset_id}')
prop.AssignElementSpecToPlate(plate_ids[0], offset_id)

# Verify via count, not the per-node getters (see Gotchas — they may not reflect immediately)
count = prop.GetElementOffsetSpecCount()
print(f'Element offset spec count: {count}')
