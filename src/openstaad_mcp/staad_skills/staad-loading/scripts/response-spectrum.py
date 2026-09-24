# response-spectrum.py
# Demonstrates adding a response spectrum load: rsaCode and rsaCombination are ints, not strings
# (a string raises a COM Type mismatch) — see LOAD_CODES.md "Response Spectrum Codes" for the full tables.

load = staad.Load

lc_id = load.CreateNewPrimaryLoadEx2('RS_CQC_X', 4, 2)  # loadType 4 = Seismic-H
load.SetLoadActive(lc_id)

# rsaCode 6 = IBC 2006, rsaCombination 2 = CQC (Complete Quadratic Combination).
# set1Names/set1Vals: direction + scale (X, ACC).
# set2Names/set2Vals: site seismic hazard parameters (SS, S1, FA, FV) — required for AnalyzeEx to
# actually solve the case; without them it fails with "SUFFICIENT DATA HAS NOT BEEN PROVIDED FOR
# IBC 2006" even though AddResponseSpectrumLoad itself reports success. Putting SS/S1/FA/FV in
# set1Names instead of set2Names silently does not store them (confirmed live via GetResponseSpectrumLoad
# read-back) — this split (direction/scale in set1, hazard params in set2) mirrors STAAD.Pro's own
# native IBC 2015 export path. set2Names/set2Vals and dataPairs are mutually exclusive — pass [] for
# whichever is unused. Use ZIP or LAT+LON in set2Names instead of SS/S1 if the site is defined by
# location rather than by mapped values directly.
load.AddResponseSpectrumLoad(6, 2, ['X', 'ACC'], [1.0, 1.0], ['SS', 'S1', 'FA', 'FV'], [1.5, 0.6, 1.0, 1.0], [])

rs_ids = list(load.GetResponseSpectrumLoadList(lc_id))
print(f'Response spectrum load IDs in case {lc_id}: {rs_ids}')

vals, spectral = load.GetResponseSpectrumLoad(lc_id, rs_ids[0], [])
print(f'vals[0]=rsaCode: {vals[0]}, vals[1]=rsaCombination: {vals[1]}')
