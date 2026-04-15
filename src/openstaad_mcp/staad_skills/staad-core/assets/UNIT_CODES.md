# STAAD.Pro Unit Codes Reference

This file contains the complete unit code mappings for `SetInputUnits()`, `SetInputUnitForLength()`, and `SetInputUnitForForce()` methods.

## Length Units

| Code | Unit       | Abbreviation |
| ---- | ---------- | ------------ |
| 0    | Inch       | in           |
| 1    | Feet       | ft           |
| 2    | Feet       | ft           |
| 3    | CentiMeter | cm           |
| 4    | Meter      | m            |
| 5    | MilliMeter | mm           |
| 6    | DeciMeter  | dm           |
| 7    | KiloMeter  | km           |

## Force Units

| Code | Unit       | Abbreviation |
| ---- | ---------- | ------------ |
| 0    | Kilopound  | kip          |
| 1    | Pound      | lb           |
| 2    | Kilogram   | kg           |
| 3    | Metric Ton | mton         |
| 4    | Newton     | N            |
| 5    | KiloNewton | kN           |
| 6    | MegaNewton | mN           |
| 7    | DecaNewton | dN           |

## Common Combinations

| System      | Length    | Force   | Usage                      |
| ----------- | --------- | ------- | -------------------------- |
| Metric SI   | 4 (Meter) | 5 (kN)  | `SetInputUnits(4, 5)` |
| Metric mm   | 5 (mm)    | 4 (N)   | `SetInputUnits(5, 4)` |
| Imperial    | 1 (Feet)  | 0 (kip) | `SetInputUnits(1, 0)` |
| Imperial in | 0 (Inch)  | 1 (lb)  | `SetInputUnits(0, 1)` |

## Base Unit System

The `GetBaseUnit()` method returns:

- `"English"` - Length values based on inches (in), force values based on kilopounds (kip)
- `"Metric"` - Length values based on meters (m), force values based on kilonewtons (kN)
