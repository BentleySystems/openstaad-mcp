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
| 18 | Hide Piping |
| 19 | Sort Geometry |
| 20 | Sort Nodes |
| 21 | Plate Stress |
| 22 | Solid Stress |
| 23 | Mode Shape |
| 24 | Stress Animation |
| 25 | Plate reinforcement |

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

## Entity Type Codes (SelectInverse, SelectByItemList, etc.)

| ID | Entity |
|----|--------|
| 0 | Node |
| 1 | Beam/Member |
| 2 | Plate |
| 3 | Solid |
