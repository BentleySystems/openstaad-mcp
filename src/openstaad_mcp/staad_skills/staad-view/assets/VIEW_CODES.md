# STAAD.Pro View Codes Reference

## Interface Mode Codes (SetInterfaceMode)

| ID | Mode |
|----|------|
| 0 | Pre-processor / Modeling |
| 1 | Physical modeling |
| 2 | Building planner |
| 3 | Piping |
| 5 | Post-processing |
| 6 | Foundation Design |
| 7 | Connection Design |
| 9 | Advanced Concrete Design |
| 10 | Advanced Slab Design |
| 11 | Earthquake |
| 12 | Steel Auto Drafter |
| 13 | Chinese Steel Design |

## Section Number Codes (SetModeSectionPage)

| ID | Main Page |
|----|-----------|
| 1 | Setup page |
| 2 | Geometry page |
| 3 | General page |
| 5 | Node Results page |
| 6 | Beam Result page |
| 7 | Plate Results page |
| 8 | Solid Results page |

## Page Number Codes (SetModeSectionPage)

| ID | Sub Page |
|----|----------|
| 0 | Job Info |
| 1 | Beam |
| 4 | Plate |
| 5 | Solid |
| 6 | Property |
| 7 | Constant |
| 8 | Material |
| 9 | Support |
| 10 | Member Specifications |
| 11 | Load |
| 17 | Reaction |

## Label Codes (SetLabel)

| ID | Label Type |
|----|------------|
| 0 | Node number |
| 1 | Member number |
| 2 | Member property reference |
| 3 | Material property reference |
| 4 | Support |
| 5 | Member release |
| 6 | Member orientation |
| 7 | Member section |
| 8 | Load value |
| 9 | Axes |
| 10 | Node position |
| 11 | Member specification |
| 12 | Member ends |
| 13 | Plate element number |
| 14 | Plate element orientation |
| 15 | Solid element number |
| 16 | Dimension |
| 17 | Floor load |
| 18 | Floor load distribution diagram |
| 19 | Wind load |
| 20 | Wind load influence area diagram |
| 21 | Diagram Info |

## Diagram Mode Codes (SetDiagramMode)

| ID | Diagram Type |
|----|--------------|
| 0 | Load |
| 1 | Displacement |
| 2 | MY |
| 3 | MZ |
| 4 | FY |
| 5 | FZ |
| 6 | AX (Axial) |
| 7 | TR (Torsion) |
| 8 | Structure |
| 9 | Full Section |
| 10 | Section Outline |
| 11 | Stress |
| 12 | Shrink |
| 13 | Perspective |
| 14 | Hide Structure |
| 15 | Fill Plates & Solids |
| 16 | Hide Plates & Solids |
| 17 | Hide Piping |
| 18 | Sort Geometry |
| 19 | Sort Nodes |
| 20 | Plate Stress |
| 21 | Solid Stress |
| 22 | Mode Shape |
| 23 | Stress Animation |
| 24 | Plate reinforcement |

## Stress Entity Type Codes (SetStressType)

| ID | Entity |
|----|--------|
| 20 | Plate Stress |
| 21 | Solid Stress |

## Plate Stress Type Codes (SetStressType, entityType=20)

`UI Label` is the exact text shown in the Diagrams > Plate Stress dialog's Type combo box — match
user requests against this column, not just the `Stress Type` name (several differ, e.g. FX/FY/FXY
show as "SX (local)"/"SY (local)"/"SXY (local)"; stressType 19 shows "MXY (local)", not "MZ";
Max Von Mises is truncated to "Max Von Mis" with no "es").

| ID | Stress Type | UI Label |
|----|-------------|----------|
| 1 | Max Absolute | Max Absolute |
| 2 | Top Max | Max Top (Principal Major Stress) |
| 3 | Top Min | Min Top (Principal Minor Stress) |
| 4 | Top Max Shear | Tau Max Top |
| 5 | Bottom Max | Max Bottom (Principal Major Stress) |
| 6 | Bottom Min | Min Bottom (Principal Minor Stress) |
| 7 | Bottom Max Shear | Tau Max Bottom |
| 8 | Max Von Mises | Max Von Mis |
| 9 | Von Mises Top Max | Von Mis Top |
| 10 | Von Mises Bottom Max | Von Mis Bottom |
| 11 | Max Tresca | Max Tresca |
| 12 | Top Tresca | Tresca Top |
| 13 | Bottom Tresca | Tresca Bottom |
| 14 | FX | SX (local) |
| 15 | FY | SY (local) |
| 16 | FXY | SXY (local) |
| 17 | MX | MX (local) |
| 18 | MY | MY (local) |
| 19 | MZ | MXY (local) |
| 20 | QX | SQX (local) |
| 21 | QY | SQY (local) |
| 22 | Global | Global Moment |
| 23 | Global Membrane Stresses | Global Direct Stress |
| 24 | Global Shear Stresses | Global Shear Stress |
| 25 | Base Pressure | Base Pressure |
| 26 | Combined X Top | Top Combined SX (local) |
| 27 | Combined Y Top | Top Combined SY (local) |
| 28 | Combined XY Top | Top Combined SXY (local) |
| 29 | Combined X Bottom | Bottom Combined SX (local) |
| 30 | Combined Y Bottom | Bottom Combined SY (local) |
| 31 | Combined XY Bottom | Bottom Combined SXY (local) |

## Solid Stress Type Codes (SetStressType, entityType=21)

`UI Label` is the exact text shown in the Diagrams > Solid Stress dialog's Type combo box.

| ID | Stress Type | UI Label |
|----|-------------|----------|
| 1 | SXX | SXX |
| 2 | SYY | SYY |
| 3 | SZZ | SZZ |
| 4 | SXY | SXY |
| 5 | SYZ | SYZ |
| 6 | SXZ | SZX |
| 7 | S11 | S1 |
| 8 | S22 | S2 |
| 9 | S33 | S3 |
| 10 | Sigma Effective (Von Mises) | Sige/Von Mises |

## Unit Type Codes (SetUnits)

| ID | Unit Category |
|----|---------------|
| -1 | No Unit |
| 0 | Dimension |
| 1 | Displacement |
| 2 | Section Dimension |
| 3 | Section Area |
| 4 | Inertia |
| 5 | Force |
| 6 | Moment |
| 7 | Distributed Force |
| 8 | Distributed Moment |
| 9 | Density |
| 10 | Acceleration |
| 11 | Spring |
| 12 | Rotational Spring |
| 13 | Material Modulus |
| 14 | Stress |
| 15 | Alpha |
| 16 | Temperature |
| 17 | Mass |
| 18 | Section Modulus |
| 19 | Rotational Displacement |
| 20 | Subgrade Modulus |

## Scale Type IDs (GetScaleValueByType / SetScaleValueByType)

| ID | Category | Item | Unit |
|----|----------|------|------|
| 0 | Loads | Point Force | Force |
| 1 | Loads | Dist. Force | Force/length |
| 2 | Loads | Point Moment | Force×length |
| 3 | Loads | Dist. Moment | Force×length/length |
| 4 | Loads | Pressure | Force/length² |
| 5 | Results | Bending Y | Force×length |
| 6 | Results | Bending Z | Force×length |
| 7 | Results | Shear Y | Force |
| 8 | Results | Shear Z | Force |
| 9 | Results | Axial | Force |
| 10 | Results | Torsion | Force×length |
| 11 | Results | Displacement | Length |
| 12 | Results | Beam Stress | Force/length² |
| 13 | Results | Mode Shape | (none) |

## Entity Type Codes (SelectInverse, SelectByItemList)

| ID | Entity |
|----|--------|
| 1 | Node |
| 2 | Beam/Member |
| 3 | Plate |
| 4 | Solid |
| 5 | Surface |

## Entity Type Codes (SelectEntitiesConnectedToNode/Member/Plate/Solid)

Different convention from the table above — no dedicated Node code.

| ID | Entity |
|----|--------|
| 0 | Geometry |
| 1 | Beam/Member |
| 2 | Plate |
| 3 | Solid |
