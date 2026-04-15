# select-members.py
# Demonstrates selecting beams in the model — single and multiple.
# Selections are additive: always clear before starting a new selection.

geo = staad.Geometry

# Get actual beam IDs first — never assume they start at 1
beam_ids = list(geo.GetBeamList())
print(f'All beams: {beam_ids}')

# Select a single beam
geo.ClearMemberSelection()          # always clear first
result = geo.SelectBeam(beam_ids[0])
print(f'SelectBeam({beam_ids[0]}) result: {result}')  # 0 = OK
print(f'Selected: {geo.GetSelectedBeams()}')

# Select multiple beams at once
geo.ClearMemberSelection()
result = geo.SelectMultipleBeams(beam_ids[:3])  # first 3 beams
print(f'SelectMultipleBeams result: {result}')  # 0 = OK
print(f'Selected: {geo.GetSelectedBeams()}')

# Same pattern works for nodes, plates, solids:
# geo.ClearNodeSelection() / SelectNode(id) / SelectMultipleNodes(ids) / GetSelectedNodes()
# geo.ClearPlateSelection() / SelectPlate(id) / SelectMultiplePlates(ids) / GetSelectedPlates()
