# STAAD.Pro Property Codes Reference

## Country Codes (CreateBeamPropertyFromTable)

| Code | Country       |
| ---- | ------------- |
| 1    | American      |
| 2    | Australian    |
| 3    | British       |
| 4    | Canadian      |
| 5    | Chinese       |
| 6    | Dutch         |
| 7    | European      |
| 8    | French        |
| 9    | German        |
| 10   | Indian        |
| 11   | Japanese      |
| 12   | Russian       |
| 13   | South African |
| 14   | Spanish       |
| 15   | Venezuelan    |
| 16   | Korean        |

## Spec Type Codes (CreateBeamPropertyFromTable)

| Value | Spec | Description                 |
| ----- | ---- | --------------------------- |
| 0     | ST   | Single standard section     |
| 2     | D    | Double profile              |
| 5     | T    | Tee cut from I-section      |
| 6     | CM   | Composite                   |
| 7     | TC   | Top cover plate             |
| 8     | BC   | Bottom cover plate          |
| 9     | TB   | Top and bottom cover plates |

## Angle Specification Type Codes (CreateAnglePropertyFromTable)

| Value | Spec Type | Description                                |
| ----- | --------- | ------------------------------------------ |
| 0     | ST        | Single standard section                    |
| 1     | RA        | Reversed Y-Z axes                          |
| 3     | LD        | Long legs back-to-back                     |
| 4     | SD        | Short legs back-to-back                    |
| 12    | SA        | Star arrangement, heel to heel (aluminium) |

## UPT Table Type Codes (CreateUPTTable)

| No. | Table Type   |
| --- | ------------ |
| 1   | Wide Flange  |
| 2   | Channel      |
| 3   | Angle        |
| 4   | Double Angle |
| 5   | Tee          |
| 6   | Pipe         |
| 7   | Tube         |
| 8   | General      |
| 9   | I-Section    |
| 10  | Prismatic    |

## Tapered Tube Type Codes (CreateTaperedTubeProperty)

| Value | Tube Type     |
| ----- | ------------- |
| 0     | Round         |
| 1     | Hexadecagonal |
| 2     | Dodecagonal   |
| 3     | Octagonal     |
| 4     | Hexagonal     |
| 5     | Square        |

## Assign Profile Type Codes (CreateAssignProfileProperty)

| Value | Profile      |
| ----- | ------------ |
| 0     | Angle        |
| 1     | Double Angle |
| 2     | Beam         |
| 3     | Column       |
| 4     | Channel      |

## Offset location and axis codes (CreateMemberOffsetSpec)

| offset_location | Meaning         |
| --------------- | --------------- |
| 0               | Start of member |
| 1               | End of member   |

| offset_with_respect_to | Meaning     |
| ---------------------- | ----------- |
| 0                      | Global axis |
| 1                      | Local axis  |

## Member Release DOF Array (CreateMemberReleaseSpec)

The `dof_values` and `spring_constant_values` lists have 6 elements:

| Index | DOF |
| ----- | --- |
| 0     | FX  |
| 1     | FY  |
| 2     | FZ  |
| 3     | MX  |
| 4     | MY  |
| 5     | MZ  |

`dof_values` values: `0` = fixed, `1` = released, `-1` = spring.  
`spring_constant_values`: stiffness for spring releases (0.0 for released or fixed DOFs).

## CreatePrismaticGeneralProperty Array Layout

| Index | Parameter | Description                                 |
| ----- | --------- | ------------------------------------------- |
| 0     | AX        | Cross-section area                          |
| 1     | AY        | Shear area, local Y                         |
| 2     | AZ        | Shear area, local Z                         |
| 3     | IX        | Torsional constant                          |
| 4     | IY        | Moment of inertia, local Y                  |
| 5     | IZ        | Moment of inertia, local Z                  |
| 6     | YD        | Depth in local Y direction                  |
| 7     | ZD        | Depth in local Z direction                  |
| 8     | YB        | Stem depth (T) / top fiber width (trap.)    |
| 9     | ZB        | Stem width (T) / bottom fiber width (trap.) |

## Material Type Codes (SetTypeToIsotropicMaterial)

| Value | Material Type |
| ----- | ------------- |
| 0     | None          |
| 1     | Steel         |
| 2     | Concrete      |
| 3     | Aluminum      |
| 4     | Timber        |

## Section Property Type Numbers (GetBeamSectionPropertyTypeNo)

| Section Type | Value | Section Type | Value |
| ------------ | ----- | ------------- | ----- |
| BEAM ST | 610 | HSS RECTANGLE | 654 |
| BEAM D | 616 | HSS ROUND | 655 |
| BEAM TC | 613 | CASTEL ST | 656 |
| BEAM BC | 614 | TUBE ST | 650 |
| BEAM TB | 615 | TEE ST | 620 |
| BEAM T | 611 | PLATE STRIP | 666 |
| BEAM CM | 612 | ANGLE COLD ST | 644 |
| CHANNEL ST | 630 | ANGLE COLD ST WITH LIPS | 645 |
| CHANNEL D | 631 | CHANNEL COLD ST | 634 |
| CHANNEL FR | 633 | CHANNEL COLD ST WITH LIPS | 635 |
| ANGLE ST | 640 | ZEE COLD ST | 662 |
| ANGLE LD | 642 | ZEE COLD ST WITH LIPS | 663 |
| ANGLE SD | 643 | HAT COLD ST | 664 |
| ANGLE RA | 641 | TAPER | 680 |
| ANGLE SA | 646 | TAPERED TUBE | 675 |
| PIPE ST | 660 | PRISMATIC CIRCLE | 671 |
| PRISMATIC RECT | 672 | PRISMATIC TRAP | 674 |
| PRISMATIC TEE | 673 | PRISMATIC GENERAL | 676 |
| SOLID ROUND | 668 | UPT PRISMATIC | 699 |
| UPT GENERAL | 697 | UPT WIDE FLANGE | 690 |
| UPT CHANNEL | 691 | UPT ANGLE | 692 |
| UPT DOUBLE ANGLE | 693 | UPT TEE | 694 |
| UPT PIPE | 695 | UPT TUBE | 696 |
| UPT ISECTION | 698 | | |
