# load-lists-and-reference-loads.py
# Demonstrates load lists, and the correct reference-load workflow:
# a reference load is a reusable container of real load items, applied to a primary case with a factor.
# Also shows the CreateLoadList false-negative gotcha:
# CreateLoadList can return False even when it succeeds — verify via GetLoadListCount/GetLoadsInLoadList.

load = staad.Load
geo = staad.Geometry

primary_cases = load.GetPrimaryLoadCaseNumbers()
print(f'Primary load cases: {list(primary_cases)}')

# Group existing primary load cases into a load list (listType 0 = plain load list)
result = load.CreateLoadList(0, list(primary_cases))
print(f'CreateLoadList returned: {result} (may be False even on success)')

list_index = load.GetLoadListCount()
case_count = load.GetLoadCountInLoadList(list_index)
case_ids = load.GetLoadsInLoadList(list_index)
print(f'Load list {list_index}: {case_count} cases -> {list(case_ids)}')

# Reference load — Step 1: define the container and populate it with real load items.
# refId must not collide with an existing REFERENCE load ID (separate namespace from primary cases).
existing_ref_ids = list(load.GetReferenceLoadCaseNumbers())
safe_ref_id = max(existing_ref_ids, default=0) + 1

ref_id = load.CreateNewReferenceLoad(safe_ref_id, 'Wind Pattern', 3)  # loadType 3 = Wind
load.SetReferenceLoadActive(ref_id)  # mandatory — AddReferenceLoad silently no-ops without this
node_ids = list(geo.GetNodeList())[:2]
load.AddNodalLoad(node_ids, 10.0, 0.0, 0.0, 0.0, 0.0, 0.0)

# Reference load — Step 2: apply it to a primary case with a factor.
# AddReferenceLoad must be called while a PRIMARY case is active — calling it while the reference
# load itself is active nests it into its own definition (verified live to produce a circular
# REFERENCE LOAD block in the generated STD file).
target_case = primary_cases[0]
load.SetLoadActive(target_case)
load.AddReferenceLoad([ref_id], [0.75])
print(f'Applied reference load {ref_id} to primary case {target_case} with factor 0.75')

ref_case_count = load.GetReferenceLoadCaseCount()
print(f'GetReferenceLoadCaseCount: {ref_case_count}')
