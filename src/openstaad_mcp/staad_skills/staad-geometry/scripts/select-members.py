# select-members.py
# Demonstrates selecting beams in the model — single and multiple.
# Selections are additive: always clear before starting a new selection.

geo = staad.Geometry


def reset_member_selection():
    # Clear only undoes the last Select call, not the whole selection — re-select
    # whatever is currently selected first so Clear actually empties it.
    current = list(geo.GetSelectedBeams())
    if current:
        geo.SelectMultipleBeams(current)
    try:
        geo.ClearMemberSelection()
    except Exception:
        pass  # was already empty


# Get actual beam IDs first — never assume they start at 1
beam_ids = list(geo.GetBeamList())
print(f'All beams: {beam_ids}')

# Select a single beam
reset_member_selection()
result = geo.SelectBeam(beam_ids[0])
print(f'SelectBeam({beam_ids[0]}) result: {result}')  # bool, True = OK
print(f'Selected: {geo.GetSelectedBeams()}')

# Select multiple beams at once
reset_member_selection()
result = geo.SelectMultipleBeams(beam_ids[:3])  # first 3 beams
print(f'SelectMultipleBeams result: {result}')  # None on success
print(f'Selected: {geo.GetSelectedBeams()}')

# Same pattern works for nodes, plates, solids:
# geo.ClearNodeSelection() / SelectNode(id) / SelectMultipleNodes(ids) / GetSelectedNodes()
# geo.ClearPlateSelection() / SelectPlate(id) / SelectMultiplePlates(ids) / GetSelectedPlates()
