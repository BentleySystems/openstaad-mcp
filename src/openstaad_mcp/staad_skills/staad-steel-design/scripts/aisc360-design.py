# aisc360-design.py
# Performs AISC 360-16 steel design on all members and reports utilization ratios.
# Uses AnalyzeEx (not AnalyzeModel) — only AnalyzeEx triggers design.
# GetMemberSteelDesignResults raises an error for members not in the design brief.

geo = staad.Geometry
prop = staad.Property
design = staad.Design
out = staad.Output

beam_list = list(geo.GetBeamList())
print(f'Members to design: {len(beam_list)}')

# Map beam IDs to section names before design runs
beam_to_section = {}
for sid in list(prop.GetSectionPropertyList()):
    name = prop.GetSectionPropertyName(sid)
    for bid in list(prop.GetSectionPropertyAssignedBeamList(sid)):
        beam_to_section[bid] = name

# Step 1: Create AISC 360-16 design brief (code 1067)
# 1045 = AISC 360-05, 1067 = AISC 360-16
brief_ref = design.CreateDesignBrief(1067)
print(f'Design brief ref: {brief_ref}')

# Step 2: Assign CHECK CODE to all members — returns 0 on success
result = design.AssignDesignCommand(brief_ref, 'CHECK CODE', '', beam_list)
print(f'AssignDesignCommand result: {result}')  # non-zero = failure

# Step 3: Save to persist design commands
staad.SaveModel(True)

# Step 4: Run analysis + design (silentMode=1, hiddenMode=0, waitTillComplete=1)
staad.SetSilentMode(True)
status = staad.AnalyzeEx(1, 0, 1)
staad.SetSilentMode(False)
print(f'AnalyzeEx status: {status}')  # 2 = success

# Verify design completed
blk_count = out.GetSteelDesignParameterBlockCount()
print(f'Design parameter blocks: {blk_count}')  # must be > 0

# Step 5: Per-member results
# r = (codeName, status, ratio, allowable, critLC, critPos, clause, section, forces[FX,MY,MZ], klr)
print(f'\n{"Member":<8} {"Section":<12} {"Status":<6} {"Ratio":>7}  {"Clause":<20} {"Des.Section"}')
print('-' * 70)
for bid in beam_list:
    r = out.GetMemberSteelDesignResults(bid)
    section = beam_to_section.get(bid, '?')
    print(f'{bid:<8} {section:<12} {r[1]:<6} {r[2]:>7.4f}  {r[6]:<20} {r[7]}')

# Model-wide extremes
max_r = out.GetMemberSteelDesignMaxFailureRatio()
min_r = out.GetMemberSteelDesignMinFailureRatio()
print(f'\nModel max utilization: {max_r:.4f}')
print(f'Model min utilization: {min_r:.4f}')
