# seismic-definition.py
# Defines a UBC 1997 static seismic load and applies it in the X direction.
# `type` codes are function-specific and NOT interchangeable — see LOAD_CODES.md
# "Seismic Definition Type Codes (AddSeismicDefinition)" for the full verified table.
# There is no getter to read a seismic definition back — only use documented type codes,
# never guess one, and treat AddSeismicDefinition's True return as "call succeeded",
# not "type was valid" (it returns True for any type 0-49, valid or not).
# Live-verified requirement: this load case must be created BEFORE any non-seismic load
# case in the model (UBC/IBC engine error otherwise: "UBC LOAD CASES MUST BE DEFINED
# BEFORE ANY OTHER LOAD CASE") — build seismic cases first if the model will have others.

load = staad.Load

lc = load.CreateNewPrimaryLoadEx('UBC 1997 Seismic X', 4)  # loadType 4 = Seismic-H
load.SetLoadActive(lc)                                     # mandatory — must call before adding items

load.AddSeismicDefinition(2, 0)              # type 2 = UBC 1997; accidental: 0/1 flag, not a scale factor
# UBC 1997 requires ALL of these set (only CT/PX/PZ are optional) — leaving any unset
# produces a generic "ABOVE LINE CONTAINS ERRONEOUS DATA" analysis error, live-verified.
ubc_1997_params = {'ZONE': 0.2, 'I': 1.0, 'RWX': 5.6, 'RWZ': 5.6, 'STYPE': 2, 'NA': 1.0, 'NV': 1.0}
for name, value in ubc_1997_params.items():
    load.ModifySeismicDefinitionParams(name, value)

load.AddSeismicDefSelfWeight(1.0)            # factor applied to structure self-weight as seismic mass
load.AddSeismicLoad(0, 1.0)                  # direction: 0=X, 1=Y, 2=Z (zero-indexed global axis, live-verified)

print(f'Load case {lc}: UBC 1997 seismic definition (ZONE=0.2) applied in X')
