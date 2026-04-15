# fetch-forces.py
# Fetches member end forces, bending moments, and support reactions for the first load case.
# Always call AreResultsAvailable() before reading any output.
# GetPrimaryLoadCaseNumbers returns a tuple — wrap in list() before indexing.

out = staad.Output

# Guard: check results exist before querying
if not out.AreResultsAvailable():
    print('No results available — run analysis first')
else:
    load = staad.Load
    geo = staad.Geometry

    # Always fetch load case numbers dynamically — never hardcode
    lc_numbers = list(load.GetPrimaryLoadCaseNumbers())
    print(f'Load cases: {lc_numbers}')
    lc = lc_numbers[0]

    beam_list = list(geo.GetBeamList())
    node_list = list(geo.GetNodeList())

    # Member end forces — local axis, start end (0=StartA, 1=EndB; 0=Local, 1=Global)
    bid = beam_list[0]
    f = out.GetMemberEndForces(bid, 0, lc, 0)
    print(f'Member {bid} (StartA, Local): FX={f[0]:.3f} FY={f[1]:.3f} FZ={f[2]:.3f}  MX={f[3]:.3f} MY={f[4]:.3f} MZ={f[5]:.3f}')

    # Min/max bending moment — dir is a string ('MY' or 'MZ'), not an integer
    mz_min, mz_min_pos, mz_max, mz_max_pos = out.GetMinMaxBendingMoment(bid, 'MZ', lc)
    print(f'Member {bid} MZ range: [{mz_min:.3f}, {mz_max:.3f}]')

    # Min/max shear force
    fy_min, fy_min_pos, fy_max, fy_max_pos = out.GetMinMaxShearForce(bid, 'FY', lc)
    print(f'Member {bid} FY range: [{fy_min:.3f}, {fy_max:.3f}]')

    # Support reactions — returns [FX, FY, FZ, MX, MY, MZ]
    nid = node_list[0]
    r = out.GetSupportReactions(nid, lc)
    print(f'Node {nid} reactions: FX={r[0]:.3f} FY={r[1]:.3f} FZ={r[2]:.3f}')

    # Output units
    force_unit = out.GetOutputUnitForForce()
    moment_unit = out.GetOutputUnitForMoment()
    print(f'Units: Force={force_unit}, Moment={moment_unit}')
