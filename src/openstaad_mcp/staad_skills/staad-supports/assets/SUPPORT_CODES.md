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

| Value | Direction                                |
| ----- | ---------------------------------------- |
| 0     | X Direction                              |
| 1     | Y Direction                              |
| 2     | Z Direction                              |
| 3     | X Only Direction (compression only in X) |
| 4     | Y Only Direction (compression only in Y) |
| 5     | Z Only Direction (compression only in Z) |
| 6     | All Directions (plate mat only)          |

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
