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
