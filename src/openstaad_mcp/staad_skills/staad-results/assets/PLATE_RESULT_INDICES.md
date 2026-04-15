# Plate Result Index Reference

## GetAllPlateCenterStressesAndMoments Return Value

Returns a list of 8 values `[SQX, SQY, MX, MY, MXY, SX, SY, SXY]`:

| Index | Symbol | Description |
|-------|--------|-------------|
| 0 | SQX | Shear stress on the local X face in the Z direction |
| 1 | SQY | Shear stress on the local Y face in the Z direction |
| 2 | MX | Moment per unit width about the local X face |
| 3 | MY | Moment per unit width about the local Y face |
| 4 | MXY | Torsional moment per unit width in the local X-Y plane |
| 5 | SX | Axial stress in the local X direction |
| 6 | SY | Axial stress in the local Y direction |
| 7 | SXY | Shear stress in the local XY plane |

See STAAD.Pro Technical Reference Section "Sign Convention of Plate Element Stresses and Moments".

## GetAllPlateCenterForces Return Value

Returns forces in the local plate coordinate system.

## GetAllPlateCenterMoments Return Value

Returns moments in the local plate coordinate system.

## GetPlateCenterNormalPrincipalStresses Return Value

Returns principal stresses at the plate center.

## GetAllPlateCenterPrincipalStressesAndAngles Return Value

Returns principal stresses along with orientation angles.

## GetPlateCenterVonMisesStresses Return Value

Returns Von Mises stress at the plate center.

## GetPlateCornerForces Parameters

- `cornerCode`: Corner node number (actual node number, not index)
- Returns forces at that specific corner of the plate.

## Solid Corner Indices

`nCorner` parameter for solid elements is 1-based (1 to 8).

## Modal Mass Participation Factors

`GetModalMassParticipationFactors(modeNo)` returns participation factors in global X, Y, Z directions.
