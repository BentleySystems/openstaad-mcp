# STAAD.Pro Load Codes Reference

## Load Type Codes (CreateNewPrimaryLoadEx / SetLoadType)

| Value | Load Type | Value | Load Type |
|-------|-----------|-------|-----------|
| 0 | Dead | 12 | Traffic |
| 1 | Live | 13 | Temperature |
| 2 | Roof Live | 14 | Imperfection |
| 3 | Wind | 15 | Accidental |
| 4 | Seismic-H | 16 | Flood |
| 5 | Seismic-V | 17 | Ice |
| 6 | Snow | 18 | Wind Ice |
| 7 | Fluids | 19 | Crane Hook |
| 8 | Soil | 20 | Mass |
| 9 | Rain | 21 | Gravity |
| 10 | Ponding | 22 | Push |
| 11 | Dust | 23 | None |

## Load Direction Codes

### Member uniform/trapezoidal force (9-way)

| Value | Direction |
|-------|-----------|
| 1 | Local X |
| 2 | Local Y |
| 3 | Local Z |
| 4 | Global X |
| 5 | Global Y |
| 6 | Global Z |
| 7 | Projected X |
| 8 | Projected Y |
| 9 | Projected Z |

### Concentrated force (6-way)

| Value | Direction |
|-------|-----------|
| 1 | Local X |
| 2 | Local Y |
| 3 | Local Z |
| 4 | Global X |
| 5 | Global Y |
| 6 | Global Z |

### Self weight / support displacement direction

| Value | Axis |
|-------|------|
| 1 | X |
| 2 | Y |
| 3 | Z |

## ASD Strength Type Codes (SetASDLoadAttribute)

| Value | Strength Type |
|-------|---------------|
| 0 | None |
| 1 | Normal ASD working stress, no P-Delta |
| 2 | Normal ASD working stress, with P-Delta |
| 3 | Strength type forces, no P-Delta |
| 4 | Strength type forces, with P-Delta |
| 5 | Column only strength, no P-Delta |
| 6 | Column only strength, with P-Delta |

## Load Envelope Type Codes (CreateLoadEnvelop)

| Value | Envelope Type |
|-------|---------------|
| 0 | None |
| 1 | Stress |
| 2 | Serviceability |
| 3 | Column |
| 4 | Connection |
| 5 | Strength |
| 6 | Temporary |

## Floor Load Range Type Codes (AddMemberFloorLoadEx)

| Value | Range Type |
|-------|------------|
| 0 | Y Range |
| 1 | X Range |
| 2 | Z Range |

## Seismic Load Direction Codes (AddSeismicLoad)

| Value | Direction |
|-------|-----------|
| 1 | X |
| 2 | Y |
| 3 | Z |

## Response Spectrum Codes (AddResponseSpectrumLoad)

### rsaCode (seismic code)

| Value | Seismic Code | Value | Seismic Code |
|-------|--------------|-------|---------------|
| 0 | Generic or Custom | 8 | IBC 2015 |
| 1 | IS:1893 Part 1 2002 | 10 | SNiP II-7-81 |
| 2 | IS:1893 2016 | 11 | SP 14.13330.2011 |
| 4 | ENV 1998-1:1994 | 12 | Canadian NRC-2005 |
| 5 | EN 1998-1:2004 | 13 | Canadian NRC-2010 |
| 6 | IBC 2006 | 14 | GB 50011 2010 |
| 7 | IBC 2012 | | |

### rsaCombination (modal combination rule)

| Value | Rule |
|-------|------|
| 0 | SRSS |
| 1 | ABS |
| 2 | CQC |
| 3 | ASCE |
| 4 | TEN |
| 5 | CSM |
| 6 | GRP |

### set1Names / set1Vals keywords by rsaCode

| rsaCode | Seismic Code | Keywords |
|---------|--------------|----------|
| 0 | Generic or Custom | DEC, ECC, X, Y, Z, ACC, DIS, SCA, DAM, CDA, MDA, LIN, LOG, MIS, ZPA, FF1, FF2, DOM, SIG, SAV, IMR, STA |
| 1 | IS:1893 Part 1 2002 | TOR, DEC, ECC, X, Y, Z, ACC, DIS, SCA, DAM, CDA, MDA, MIS, ZPA, IGN, DOM, SIG, SAV, IMR, STA, SOI, CHE, RF |
| 2 | IS:1893 2016 | TOR, DEC, ECC, X, Y, Z, ACC, DIS, SCA, DAM, CDA, MDA, LIN, LOG, MIS, ZPA, IGN, DOM, SIG, SAV, IMR, STA, SOI, CHE, RF |
| 4 | ENV 1998-1:1994 | ELA, DES, X, Y, Z, ACC, DAM, CDA, MDA, LIN, LOG, MIS, ZPA, DOM, SIG, SAV, IMR, STA, SOI, ALP, Q |
| 5 | EN 1998-1:2004 | ELA, DES, RS1, RS2, X, Y, Z, ACC, DAM, CDA, MDA, LIN, LOG, MIS, ZPA, DOM, SIG, SAV, IMR, STA, SOI, ALP, Q |
| 6 | IBC 2006 | X, Y, Z, ACC, DAM, CDA, MDA, LIN, LOG, MISC, ZPA, DOM, SIG, SAV, IMR, STA, ZIP, LAT, LON, SS, S1, SCA, FA, FV, TL |
| 7 | IBC 2012 | X, Y, Z, ACC, DAM, CDA, MDA, LIN, LOG, MISC, ZPA, DOM, SIG, SAV, IMR, STA, ZIP, LAT, LON, SS, S1, SCA, FA, FV, TL |
| 8 | IBC 2015 | X, Y, Z, ACC, DAM, CDA, MDA, LIN, LOG, MISC, ZPA, DOM, SIG, SAV, IMR, STA, ZIP, LAT, LON, SS, S1, SCA, FA, FV, TL |
| 10 | SNiP II-7-81 | A, X, KWX, KX1, Y, KWY, KY1, Z, KWZ, KZ1, ACC, SCA, DAM, CDA, MDA, LIN, LOG, MIS, ZPA, DOM, SIG, SOI, SAV |
| 11 | SP 14.13330.2011 | ECC, A, X, Y, Z, ACC, SCA, DAM, LOG, MIS, ZPA, DOM, SIG, SOI |
| 12 | Canadian NRC-2005 | TOR, DEC, ECC, X, Y, Z, ACC, DIS, SCA, DAM, CDA, MDA, LIN, LOG, MIS, ZPA, DOM, SIG, SAV, IMR, STA |
| 13 | Canadian NRC-2010 | TOR, DEC, ECC, X, Y, Z, ACC, DIS, SCA, DAM, CDA, MDA, LIN, LOG, MIS, ZPA, DOM, SIG, SAV, IMR, STA |
| 14 | GB 50011 2010 | X, Y, Z, ALP, DAM, CDA, MDA, LIN, LOG, MISS, ZPA, DOM, SIG, INT, FRE, FOR, RAR, GRO, SCL |

For rsaCode 14 (GB 50011 2010), the `INT` (fortification intensity) parameter takes: 0=Intensity 6, 1=Intensity 7, 2=Intensity 7A, 3=Intensity 8, 4=Intensity 8A, 5=Intensity 9.

## Seismic Definition Parameter Keywords (ModifySeismicDefinitionParams)

`varParamName` is code-specific — the active seismic definition's code determines which keywords apply:

| Seismic Code | Parameters |
|--------------|------------|
| Algerian: RPA | A, Q, RX, RZ, STYPE, CT, CRDAMP, PX, PZ |
| Canadian: NRC-1995 | V, ZA, ZV, RX, RZ, I, F, CT, PX, PZ |
| Canadian: NRC-2005 | SA1, SA2, SA3, SA4, IE, SCLASS, MVX, MVZ, JX, JZ, RDX, RDZ, ROX, ROZ, CT, PX, PZ, FA, FV |
| Canadian: NRC-2010 | SA1, SA2, SA3, SA4, I, SCLASS, MVX, MVZ, RDX, RDZ, ROX, ROZ, CTX, CTZ, PX, PZ, FA, FV, STX, STZ, MD |
| Chinese: GB50011-2001 | INTENSITY, FREQUENT, RARE, GROUP, SCLASS, DAMP, DELN, SF, PX, PZ, GFACTOR (FREQUENT/RARE: 0/1) |
| Chinese: GB50011-2010 | INTENSITY, FREQUENT, FORTIFIED, RARE, GROUP, SCLASS, DAMP, GFACTOR, DELN, SF, PX, PZ (FREQUENT/FORTIFIED/RARE: 0/1/2) |
| Colombian: NSR 98 | ZONE, I, S |
| Colombian: NSR 2010 | AA, AV, FA, FV, I, CT, PX, PZ, ALPHA |
| IBC 2000 / 2003 | SDS, SD1, S1, I, RX, RZ, SCLASS, CT, PX, PZ |
| IBC 2006 / 2012 / 2015 / 2018 | SS, S1, ZIP, I, RX, RZ, SCLASS, CTX, CTZ, PX, PZ, LAT, LONG, TL, FA, FV, XX, XZ (provide one of ZIP, or LAT+LONG, or SS+S1) |
| Indian: IS 1893-1984 | ZONE, K, I, B, PX, PZ |
| Indian: IS 1893-2002/2005 | ZONE, RF, I, SS, ST, DM, PX, PZ, DT, GL, SA, DF, CS, AX, ES, CV, DV |
| Indian: IS 1893-2016 | ZONE, RF, I, SS, ST, DM, PX, PZ, DT, GL, SA, DF, HT, DX, DZ |
| Indian: IS 1893(Part4) 2015 | ZONE, RF, I, SS, ST, DM, PX, PZ, SA, DF |
| Japanese (AIJ) | ZONE, CO, TC, ALPHA |
| Mex: CFE-1993 | ZONE, QX, QZ, GROUP, STYPE, REGULAR, TS, PX, PZ |
| Mex: NTC-1987 | ZONE, QX, QZ, GROUP, SHADOWED, REGULAR, REDUCE, PX, PZ (SHADOWED/REGULAR/REDUCE: 0/1) |
| Turkish | A, TA, TB, I, RX, RZ, CT, PX, PZ |
| UBC 1985 | ZONE, I, K, TS |
| UBC 1994 | ZONE, I, RWX, RWZ, S, CT, PX, PZ |
| UBC 1997 | ZONE, I, RWX, RWZ, STYPE, CT, PX, PZ, NA, NV |

Example: `load.ModifySeismicDefinitionParams("ZONE", 0.2)`

## Wind ASCE 7 Parameters (AddWindDefinitionASCE7Parameters)

### code

| Value | ASCE Code |
|-------|-----------|
| 0 | ASCE 7-1995 |
| 1 | ASCE 7-2002 |
| 2 | ASCE 7-2010 |
| 3 | ASCE 7-2016 |

### bldgClass (Building Classification Category)

| Value | Category |
|-------|----------|
| 0 | Category I |
| 1 | Category II |
| 2 | Category III |
| 3 | Category IV |

### bldgType

| Value | Building Type |
|-------|----------------|
| 0 | Building Structures |
| 1 | Chimney, Tank and similar structures |
| 2 | Solid Signs |
| 3 | Open Signs |
| 4 | Lattice Framework |
| 5 | Trussed Tower |

### expCat (Exposure Category)

| Value | Category |
|-------|----------|
| 0 | Exposure A |
| 1 | Exposure B |
| 2 | Exposure C |
| 3 | Exposure D |

### wallType

| Value | Wall Type |
|-------|-----------|
| 0 | WindWard |
| 1 | Leeward |
| 2 | SideWall |

### escarpmentData (float list, size 4 — always this shape)

| Index | Data |
|-------|------|
| 0 | Type: 2D Ridge (0) / 2D Escarpment (1) / 3D Escarpment (2) |
| 1 | Height (H) |
| 2 | Distance upwind of crest (Lh) |
| 3 | Distance from the crest to the building (x) |

### bldgData (float list — shape depends on `bldgType`)

| bldgType | Index 0 | Index 1 | Index 2 | Index 3 | Index 4 | Index 5 |
|----------|---------|---------|---------|---------|---------|---------|
| 0 Building | Enclosure class (0-2, or 0-3 for 2016: Open/Partially Open/Partially Enclosed/Enclosed) | Height | Length along wind (L) | Length normal to wind (B) | Natural frequency | Damping ratio |
| 1 Chimney/Tank | Cross-section (0=Square,1=Square Diagonal,2=Hexagonal,3=Octagonal Non-axisym,4=Octagonal Axisym,5=Round Non-axisym,6=Round Axisym — pre-2016: 0=Square,1=Square Diagonal,2=Hex/Oct,3=Round) | Height | Least horizontal dimension (W) | Depth of spoilers/ribs (D') | Natural frequency | Damping ratio |
| 2 Solid Sign | Height (H) | M dimension | N dimension | Natural frequency | Damping ratio | — |
| 3 Open Sign / 4 Lattice | Orientation: Flat (0)/Rounded (1) | Height (H) | Width | Diameter of typical round member | Ratio of solid area to gross area | Natural frequency | Damping ratio |
| 5 Trussed Tower | Cross-section: Triangle (0)/Square (1) | Height (H) | Width | Ratio of solid area to gross area (%) | Natural frequency | Damping ratio |

### unitsData (float list, size 8 — length/velocity unit codes)

Length unit codes (indices 1-7): 0=in, 1=ft, 2=foot, 3=cm, 4=m, 5=mm, 6=dm, 7=km, 8=yard, 9=mile.

| Index | Meaning |
|-------|---------|
| 0 | Wind speed unit: 0=mph, 1=m/sec, 2=cm/sec, 3=mm/sec, 4=kmph, 5=in/sec, 6=ft/sec, 7=yd/sec |
| 1 | Height above sea level unit (length code; ASCE7-2016 only, else any) |
| 2 | Escarpment Height (H) unit (length code) |
| 3 | Escarpment distance upwind of crest (Lh) unit (length code) |
| 4 | Escarpment distance crest-to-building (x) unit (length code) |
| 5 | Height unit (building/tank/sign/lattice/tower, per bldgType — length code) |
| 6 | Length/Width/M-dimension unit (per bldgType — length code) |
| 7 | Width/Depth/N-dimension/Diameter unit (per bldgType, N/A for Trussed Tower — length code) |

### factorsUserInput / factors (float lists, size 8 — 1=user input, 0=calculated for factorsUserInput)

| Index | Factor |
|-------|--------|
| 0 | Kz |
| 1 | Kzt |
| 2 | I |
| 3 | Kd |
| 4 | Ke (ASCE7-2016 only) |
| 5 | G |
| 6 | Cp |
| 7 | Gcpi |

## Notional Load Direction Codes (AddNotionalLoad)

Applies to both `varPLDirectionList` (primary) and `varRLDirectionList` (reference):

| Value | Direction |
|-------|-----------|
| 1 or 4 | X (Local or Global) |
| 2 or 5 | Y (Local or Global) |
| 3 or 6 | Z (Local or Global) |

## Load Item Type Codes (GetLoadTypeCount / GetLoadItemType)

| Value | Load Type | Value | Load Type |
|-------|-----------|-------|-----------|
| 4000 | SelfWeight | 3275 | Uniform Force (Physical) |
| 3110 | Nodal Load (Node) | 3280 | Uniform Moment (Physical) |
| 3120 | Nodal Load (Inclined) | 3285 | Concentrated Force (Physical) |
| 3910 | Nodal Load (Support Displacement) | 3290 | Concentrated Moment (Physical) |
| 3210 | Uniform Force | 3295 | Trapezoidal (Physical) |
| 3220 | Uniform Moment | 3310 | Pressure on full plate |
| 3230 | Concentrated Force | 3310 | Concentrated Load (Plate) |
| 3240 | Concentrated Moment | 3310 | Partial plate pressure load |
| 3250 | Linear Varying | 3320 | Trapezoidal (Plate) |
| 3260 | Trapezoidal | 3322 | Solid |
| 3260 | Hydrostatic | 3710 | Temperature |
| 3620 | Pre/Post Stress | 3720 | Strain |
| 3810 | Fixed End | 3721 | Strain Rate |
| 3530 | FloorLoadGroup | 3410 | Area |
| 3554 | OneWayFloorLoadGroup | | |
