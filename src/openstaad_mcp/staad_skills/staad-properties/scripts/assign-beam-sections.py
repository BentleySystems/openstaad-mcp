# assign-beam-sections.py
# Assigns a W-section to all beams in the model.
# Always retrieve actual beam IDs — never assume they start at 1.

geo = staad.Geometry
prop = staad.Property

# Get actual beam IDs
beam_ids = list(geo.GetBeamList())
print(f'Beams found: {beam_ids}')

# Create section property from the American steel table (countryCode=1)
# typeSpec=0 means standard (ST) section
prop_id = prop.CreateBeamPropertyFromTable(1, 'W14X120', 0, 0.0, 0.0)
print(f'Created section property ID: {prop_id}')

# Assign to all beams
prop.AssignBeamProperty(beam_ids, prop_id)
print(f'Assigned W14X120 to {len(beam_ids)} beams')

# countryCode reference:
# 1=American, 2=Australian, 3=British, 4=Canadian, 5=Chinese, 6=Dutch
# 7=European, 8=French, 9=German, 10=Indian, 11=Japanese, 12=Russian
# 13=SouthAfrican, 14=Spanish, 15=Venezuelan, 16=Korean
# typeSpec: 0=ST, 2=D (double), 5=T (tee), 6=CM, 7=TC, 8=BC, 9=TB
