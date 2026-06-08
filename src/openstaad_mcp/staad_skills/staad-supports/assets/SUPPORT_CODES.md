# STAAD.Pro Support Type Codes Reference

## Inclined Support Types

| Value | Type        | Description                        |
| ----- | ----------- | ---------------------------------- |
| 1     | Pinned      | Free rotations, fixed translations |
| 2     | Fixed       | All DOFs fixed                     |
| 3     | FixedBut    | Partial releases as specified      |
| 4     | Enforced    | Enforced displacement              |
| 5     | EnforcedBut | Enforced with partial releases     |

## Reference Type (for Inclined Supports)

| Value | Description                                                          |
| ----- | -------------------------------------------------------------------- |
| 0     | fRefX, fRefY, fRefZ = global distances from joint to reference point |
| 1     | fRefX, fRefY, fRefZ = global coordinates of reference point          |
| 2     | refNode = joint number whose coordinates define the reference point  |

## Direction Codes

Used in `CreateElasticMat()`, `CreatePlateMat()`, `GetElasticMatDetail()`.

| Value | Direction                                                                              |
| ----- | -------------------------------------------------------------------------------------- |
| 0     | X Direction                                                                            |
| 1     | Y Direction *(typical for soil springs — use for most foundations)*                   |
| 2     | Z Direction                                                                            |
| 3     | X Only — springs act in X only; model needs other supports for Y/Z stability           |
| 4     | Y Only — springs act in Y only; model needs other supports for X/Z stability           |
| 5     | Z Only — springs act in Z only; model needs other supports for X/Y stability           |
| 6     | All Directions (plate mat only)                                                        |

## GetSupportType Return Codes

Returned by `GetSupportType(nodeNo)` and embedded in `GetSupportInformation` / `GetSupportInformationEx`.

| Value | Type                              |
| ----- | --------------------------------- |
| 0     | No support                        |
| 1     | Pinned                            |
| 2     | Fixed                             |
| 3     | Fixed with releases (FixedBut)    |
| 4     | Enforced displacement             |
| 5     | Enforced with releases            |
| 6     | Inclined support                  |
| 7     | Elastic footing                   |
| 8     | Elastic mat                       |
| 9     | Plate mat                         |
| 10    | Multi-linear spring               |
| 11    | Generated pinned                  |
| 12    | Generated fixed                   |
| 13    | Generated fixed with releases     |
| -1    | Error                             |

## Spring Types

| Value | Type             |
| ----- | ---------------- |
| 0     | None (linear)    |
| 1     | Compression only |
| 2     | Multi-linear     |

## Release Specification Array

Array of 6 values: `[FX, FY, FZ, MX, MY, MZ]`

| Value | Meaning                                      |
| ----- | -------------------------------------------- |
| 0     | Fixed (restrained)                           |
| 1     | Released (free)                              |
| -1    | Spring (use spring constant from springSpec) |

## Spring Specification Array

Array of 6 values: `[KFX, KFY, KFZ, KMX, KMY, KMZ]`

- Translation springs: force per unit length (e.g., kN/m)
- Rotational springs: moment per unit rotation (e.g., kN·m/rad)
