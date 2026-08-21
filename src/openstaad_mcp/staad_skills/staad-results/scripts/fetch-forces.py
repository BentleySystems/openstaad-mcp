# fetch-forces.py
# Fetches member end forces, bending moments, and support reactions for the first load case.
# Always call AreResultsAvailable() before reading any output.
# GetPrimaryLoadCaseNumbers returns a tuple — wrap in list() before indexing.
# All getters return BASE units; GetOutputUnitFor* is the UI display unit to convert to.

out = staad.Output

# Guard: check results exist before querying
if not out.AreResultsAvailable():
    print('No results available — run analysis first')
else:
    load = staad.Load
    geo = staad.Geometry

    base = staad.GetBaseUnit()                      # 'English' or 'Metric'
    force_unit = out.GetOutputUnitForForce()        # UI display unit, e.g. 'kN'
    disp_unit = out.GetOutputUnitForDisplacement()  # UI display unit, e.g. 'mm'

    # Factors FROM the base unit (Metric: m/kN, English: in/kip) TO the UI unit
    length_factors = {'Metric': {'m': 1.0, 'cm': 100.0, 'mm': 1000.0},
                      'English': {'in': 1.0, 'ft': 1.0 / 12.0}}
    force_factors = {'Metric': {'kN': 1.0, 'N': 1000.0, 'MN': 0.001},
                     'English': {'kip': 1.0, 'lb': 1000.0}}
    disp_f = length_factors[base][disp_unit]
    force_f = force_factors[base][force_unit]

    # Always fetch load case numbers dynamically — never hardcode
    lc_numbers = list(load.GetPrimaryLoadCaseNumbers())
    print(f'Load cases: {lc_numbers}')
    lc = lc_numbers[0]

    beam_list = list(geo.GetBeamList())
    node_list = list(geo.GetNodeList())

    # Member end forces — local axis, start end (0=StartA, 1=EndB; 0=Local, 1=Global)
    bid = beam_list[0]
    f = out.GetMemberEndForces(bid, 0, lc, 0)
    print(f'Member {bid} (StartA, Local): FX={f[0] * force_f:.3f} FY={f[1] * force_f:.3f} FZ={f[2] * force_f:.3f} {force_unit}')

    # Min/max bending moment — dir is a string ('MY' or 'MZ'), not an integer
    mz_min, mz_min_pos, mz_max, mz_max_pos = out.GetMinMaxBendingMoment(bid, 'MZ', lc)
    print(f'Member {bid} MZ range (base units): [{mz_min:.3f}, {mz_max:.3f}]')

    # Min/max shear force
    fy_min, fy_min_pos, fy_max, fy_max_pos = out.GetMinMaxShearForce(bid, 'FY', lc)
    print(f'Member {bid} FY range: [{fy_min * force_f:.3f}, {fy_max * force_f:.3f}] {force_unit}')

    # Support reactions — returns [FX, FY, FZ, MX, MY, MZ]
    nid = node_list[0]
    r = out.GetSupportReactions(nid, lc)
    print(f'Node {nid} reactions: FX={r[0] * force_f:.3f} FY={r[1] * force_f:.3f} FZ={r[2] * force_f:.3f} {force_unit}')

    # Displacements: raw value is in base length units (Metric = m), UI shows mm
    d = out.GetNodeDisplacements(node_list[-1], lc)
    print(f'Node {node_list[-1]} UX={d[0] * disp_f:.3f} UY={d[1] * disp_f:.3f} {disp_unit}')
