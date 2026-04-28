# Function → Skill Map

Use this table to look up which skill governs a given openstaadpy function.
Load the governing skill via `read_skills(["skill-name"])` before writing any script that uses those functions.

---

## openstaadroot → staad-core

| Function                                                                    | Purpose                                                                                                                                    |
| --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `GetSTAADFile` / `GetSTAADFileFolder`                                       | Returns path of open model                                                                                                                 |
| `GetBaseUnit` / `GetInputUnitForLength` / `GetInputUnitForForce`            | Unit queries                                                                                                                               |
| `SetInputUnits` / `SetInputUnitForLength` / `SetInputUnitForForce`          | Unit assignment — see UNIT_CODES.md                                                                                                        |
| `SaveModel`                                                                 | Save current model — use `SaveModel(True)` after adding geometry before assigning properties/supports/loads — REQUIRE EXPLICIT USER INTENT |
| `NewSTAADFile`                                                              | Create new model file (`.std` path required, path-validated) — REQUIRE EXPLICIT USER INTENT                                                |
| `OpenSTAADFile`                                                             | Open existing model file (`.std` path required, path-validated) — REQUIRE EXPLICIT USER INTENT                                             |
| `SaveAs`                                                                    | Save model to new path (`.std` path required, path-validated) — REQUIRE EXPLICIT USER INTENT                                               |
| `CloseSTAADFile`                                                            | Close current model — REQUIRE EXPLICIT USER INTENT                                                                                         |
| `SetSilentMode`                                                             | Suppress UI dialogs before mutating ops                                                                                                    |
| `UpdateStructure`                                                           | **Avoid** — discards unsaved in-memory geometry; use `SaveModel(True)` instead                                                             |
| `AnalyzeModel` / `AnalyzeEx`                                                | Run analysis (`AnalyzeEx` preferred — returns status code)                                                                                 |
| `GetAnalysisStatus` / `IsAnalyzing`                                         | Analysis state queries                                                                                                                     |
| `GetApplicationVersion` / `ShowApplication` / `Quit`                        | Application control                                                                                                                        |
| `IsPhysicalModel`                                                           | Model type query                                                                                                                           |
| `GetFullJobInfo` / `GetShortJobInfo` / `SetFullJobInfo` / `SetShortJobInfo` | Job metadata                                                                                                                               |
| `GetMainWindowHandle` / `GetProcessHandle` / `GetProcessId`                 | Process handles                                                                                                                            |

---

## osgeometry → staad-geometry

| Function                                                                               | Purpose                  |
| -------------------------------------------------------------------------------------- | ------------------------ |
| `AddNode` / `AddBeam` / `AddPlate` / `AddSolid`                                        | Create single elements   |
| `AddMultipleNodes` / `AddMultipleBeams` / `AddMultiplePlates`                          | Bulk element creation    |
| `CreateNode` / `CreateBeam` / `CreatePlate` / `CreateSolid`                            | Create with explicit IDs |
| `GetNodeList` / `GetBeamList` / `GetPlateList` / `GetSolidList`                        | List all IDs             |
| `GetNodeCount` / `GetMemberCount` / `GetPlateCount` / `GetSolidCount`                  | Element counts           |
| `GetNodeCoordinates` / `SetNodeCoordinate`                                             | Node position            |
| `GetMemberIncidence` / `GetPlateIncidence`                                             | Connectivity             |
| `GetBeamLength` / `GetNodeDistance`                                                    | Distance queries         |
| `GetLastNodeNo` / `GetLastBeamNo`                                                      | Highest ID queries       |
| `IsColumn` / `IsBeam` / `IsOrphanNode`                                                 | Geometry tests           |
| `DeleteNode` / `DeleteBeam` / `DeletePlate` / `DeleteSolid`                            | Remove elements          |
| `MergeNodes` / `MergeBeams`                                                            | Merge operations         |
| `SplitBeamInEqlParts` / `SplitBeam`                                                    | Split beam               |
| `IntersectBeams` / `BreakBeamsAtSpecificNodes`                                         | Intersection/break       |
| `RenumberBeam`                                                                         | Renumber                 |
| `SelectBeam` / `SelectMultipleBeams` / `ClearMemberSelection`                          | Beam selection           |
| `SelectNode` / `SelectMultipleNodes` / `ClearNodeSelection`                            | Node selection           |
| `SelectPlate` / `SelectMultiplePlates` / `ClearPlateSelection`                         | Plate selection          |
| `SelectSolid` / `SelectMultipleSolids` / `ClearSolidSelection`                         | Solid selection          |
| `GetSelectedBeams` / `GetSelectedNodes` / `GetSelectedPlates` / `GetNoOfSelectedBeams` | Selection query          |
| `CreateGroup` / `CreateGroupEx` / `UpdateGroup` / `DeleteGroup`                        | Group management         |
| `GetGroupCount` / `GetGroupNames` / `GetGroupEntities`                                 | Group queries            |
| `DoTranslationalRepeat`                                                                | Geometry copy/repeat     |
| `DefineParametricSurface` / `AddParametricSurfaceToModel`                              | Mesh surfaces            |
| `CreatePhysicalMember` / `GetPhysicalMemberCount`                                      | Physical members         |
| `IsZUp`                                                                                | Vertical axis query      |
| `SetNodeUniqueID` / `GetNodeUniqueID` / `SetMemberUniqueID` / `GetMemberUniqueID`      | External IDs             |

---

## osload → staad-loading

| Function                                                                            | Purpose                                  |
| ----------------------------------------------------------------------------------- | ---------------------------------------- |
| `CreateNewPrimaryLoad` / `CreateNewPrimaryLoadEx` / `CreateNewPrimaryLoadEx2`       | Create load cases                        |
| `CreateNewReferenceLoad`                                                            | Create reference load case               |
| `CreateNewLoadCombination`                                                          | Create combination case                  |
| `SetLoadActive` / `SetReferenceLoadActive`                                          | Activate case for editing                |
| `SetLoadType`                                                                       | Assign load category — see LOAD_CODES.md |
| `AddSelfWeightInXYZ` / `AddSelfWeightInXYZToGeometry`                               | Self-weight                              |
| `AddNodalLoad`                                                                      | Joint forces/moments                     |
| `AddSupportDisplacement`                                                            | Prescribed support displacement          |
| `AddMemberUniformForce` / `AddMemberUniformMoment`                                  | UDL                                      |
| `AddMemberConcForce` / `AddMemberConcMoment`                                        | Concentrated loads                       |
| `AddMemberTrapezoidal` / `AddMemberLinearVari`                                      | Variable member loads                    |
| `AddMemberAreaLoad` / `AddMemberFloorLoad` / `AddMemberFloorLoadEx`                 | Floor/area loads                         |
| `AddMemberFixedEnd` / `AddStrainLoad` / `AddTemperatureLoad`                        | Misc member loads                        |
| `AddElementPressure` / `AddElementTrapPressureEx` / `AddElementHydrostaticPressure` | Plate loads                              |
| `AddWindDefinition` / `AddWindIntensity` / `AddWindExposure` / `AddWindLoad`        | Wind loading                             |
| `AddSeismicDefinition` / `AddSeismicDefSelfWeight` / `AddSeismicLoad`               | Seismic loading                          |
| `AddLoadAndFactorToCombination` / `AddAutoLoadCombinations`                         | Combination factors                      |
| `AddRepeatLoad` / `AddReferenceLoad`                                                | Repeat/reference loads                   |
| `CreateLoadEnvelop` / `AddLoadCasesToEnvelop` / `DeleteLoadEnvelop`                 | Load envelopes                           |
| `GetPrimaryLoadCaseNumbers` / `GetPrimaryLoadCaseCount`                             | Load case queries                        |
| `GetLoadCombinationCaseNumbers` / `GetLoadCombinationCaseCount`                     | Combination queries                      |
| `GetLoadCaseTitle` / `GetLoadType` / `GetActiveLoad`                                | Load metadata                            |
| `GetNodalLoads` / `GetUDLLoads` / `GetConcForces` / `GetTrapLoads`                  | Load read queries                        |
| `IsCombinationCase` / `IsDynamicLoadIncluded`                                       | Type checks                              |
| `ClearPrimaryLoadCase` / `DeletePrimaryLoadCases` / `DeleteReferenceLoadCases`      | Delete/clear                             |
| `GetAssignmentListForLoadType` / `GetListSizeForLoadType`                           | Assignment queries                       |

---

## osproperty → staad-properties

| Function                                                                                                 | Purpose                                 |
| -------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| `CreateBeamPropertyFromTable` / `CreateBeamPropertyFromTableEx`                                          | Section from DB — see PROPERTY_CODES.md |
| `CreateAnglePropertyFromTable` / `CreateChannelPropertyFromTable` / `CreateTeePropertyFromTable`         | Shape-specific sections                 |
| `CreateTubePropertyFromTable` / `CreatePipePropertyFromTable`                                            | Hollow sections                         |
| `CreateWideFlangePropertyFromTable`                                                                      | Wide flange                             |
| `CreatePrismaticRectangleProperty` / `CreatePrismaticCircleProperty` / `CreatePrismaticTeeProperty`      | Prismatic shapes                        |
| `CreatePrismaticGeneralProperty` / `CreateTaperedIProperty` / `CreateTaperedTubeProperty`                | Advanced prismatic                      |
| `CreatePlateThicknessProperty`                                                                           | Plate thickness                         |
| `AssignBeamProperty` / `AssignPlateThickness`                                                            | Assign section/thickness                |
| `AssignBetaAngle` / `GetBetaAngle`                                                                       | Beta angle                              |
| `CreateIsotropicMaterialProperties` / `CreateIsotropicMaterialSteel` / `CreateIsotropicMaterialConcrete` | Material creation                       |
| `AssignMaterialToMember` / `AssignMaterialToPlate` / `AssignMaterialToSolid`                             | Material assignment                     |
| `CreateMemberReleaseSpec` / `CreateMemberPartialReleaseSpec` / `DeleteMemberReleaseSpec`                 | Releases                                |
| `CreateMemberTrussSpec` / `CreateMemberTensionSpec` / `CreateMemberCompressionSpec`                      | Member specs                            |
| `CreateMemberCableSpec` / `CreateMemberOffsetSpec` / `CreateMemberFireProofingSpec`                      | More specs                              |
| `AssignMemberSpecToBeam` / `AssignElementSpecToPlate`                                                    | Assign specs                            |
| `GetBeamProperty` / `GetBeamPropertyAll` / `GetBeamSectionName`                                          | Section queries                         |
| `GetSectionPropertyList` / `GetSectionPropertyCount`                                                     | Property inventory                      |
| `GetPlateThickness` / `GetMaterialProperty`                                                              | Read assigned properties                |
| `GetPublishedProfileName` / `GetSTAADProfileName` / `GetRecordForSection` / `GetShapeCode`               | DB lookup                               |

---

## ossupport → staad-supports

| Function                                                                                 | Purpose              |
| ---------------------------------------------------------------------------------------- | -------------------- |
| `CreateSupportFixed` / `CreateSupportPinned` / `CreateSupportFixedBut`                   | Create support types |
| `CreateElasticFooting` / `CreateElasticMat` / `CreatePlateMat` / `CreateInclinedSupport` | Special supports     |
| `AssignSupportToNode` / `AssignSupportToEntityList`                                      | Assign support       |
| `RemoveSupportFromNode` / `DeleteSupport`                                                | Remove support       |
| `GetSupportCount` / `GetSupportNodes` / `GetSupportType`                                 | Support queries      |
| `GetSupportInformation` / `GetSupportInformationEx` / `GetSupportName`                   | Support details      |
| `GetElasticFootingDetail` / `GetElasticMatDetail` / `GetPlateMatDetail`                  | Spring details       |
| `GetCountOfElasticFooting` / `GetCountOfElasticMat` / `GetCountOfPlateMat`               | Spring counts        |

---

## oscommand → staad-analysis

| Function                                                      | Purpose                  |
| ------------------------------------------------------------- | ------------------------ |
| `PerformAnalysis`                                             | Standard linear analysis |
| `PerformPDeltaAnalysisEx` / `PerformPDeltaAnalysisNoConverge` | P-Delta analysis         |
| `PerformBucklingAnalysis` / `PerformBucklingAnalysisEx`       | Buckling                 |
| `PerformCableAnalysis` / `PerformCableAnalysisEx`             | Cable analysis           |
| `PerformNonlinearAnalysisEx`                                  | Nonlinear analysis       |
| `PerformDirectAnalysis`                                       | Direct analysis (AISC)   |
| `DeleteAllAnalysisCommands`                                   | Clear analysis commands  |
| `SetCheckIrregularitiesCommand` / `SetCheckSoftStoryCommand`  | Seismic checks           |
| `SetFloorDiaphragmBaseCommand`                                | Diaphragm base           |
| `CreateSteelDesignCommand`                                    | Steel design command     |

---

## osoutput → staad-results

| Function                                                                                          | Purpose                   |
| ------------------------------------------------------------------------------------------------- | ------------------------- |
| `AreResultsAvailable`                                                                             | Check if analysis has run |
| `GetNodeDisplacements` / `GetSupportReactions`                                                    | Node output               |
| `GetMemberEndForces` / `GetPMemberEndForces`                                                      | Beam forces               |
| `GetMinMaxAxialForce` / `GetMinMaxShearForce` / `GetMinMaxBendingMoment`                          | Min/max forces            |
| `GetIntermediateMemberForcesAtDistance` / `GetMaxBeamStresses`                                    | Intermediate              |
| `GetMemberEndDisplacements` / `GetMaxSectionDisplacement` / `GetIntermediateDeflectionAtDistance` | Deflections               |
| `GetAllPlateCenterStressesAndMoments` / `GetAllPlateCenterForces`                                 | Plate center              |
| `GetPlateCenterVonMisesStresses` / `GetAllPlateCenterPrincipalStressesAndAngles`                  | Plate principal           |
| `GetPlateCornerForces` / `GetPlateStressAtPoint`                                                  | Plate corner/point        |
| `GetAllSolidNormalStresses` / `GetAllSolidShearStresses` / `GetAllSolidVonMisesStresses`          | Solid results             |
| `GetNoOfModesExtracted` / `GetModeFrequency` / `GetModalDisplacementAtNode`                       | Modal results             |
| `GetBucklingFactor` / `GetBucklingModeDisplacementAtNode` / `GetNoOfBucklingFactors`              | Buckling results          |
| `GetTimeHistoryResponse` / `GetTimeHistoryResponseMinMax` / `GetTimeHistoryResponseAtTime`        | Time-history              |
| `GetNLLoadStep` / `GetNLNodeDisplacements`                                                        | Nonlinear results         |
| `GetMemberSteelDesignResults` / `GetMemberSteelDesignRatio`                                       | Steel design output       |
| `GetMultipleMemberSteelDesignResults` / `GetMultipleMemberSteelDesignRatio`                       | Multi-block design        |
| `GetMemberSteelDesignMaxFailureRatio` / `GetMemberSteelDesignMinFailureRatio`                     | Model-wide max/min        |
| `GetSteelDesignParameterBlockCount` / `GetSteelDesignParameterBlockNameByIndex`                   | AISC 360 blocks           |
| `GetStaticCheckResult` / `GetBasePressures` / `GetMatInfluenceAreas`                              | Foundation results        |
| `GetOutputUnitForForce` / `GetOutputUnitForMoment` / `GetOutputUnitForDisplacement`               | Output units              |

---

## osdesign → staad-steel-design

| Function                                                              | Purpose                 |
| --------------------------------------------------------------------- | ----------------------- |
| `CreateDesignBrief`                                                   | Create new design brief |
| `AssignDesignCommand` / `AssignDesignParameter` / `AssignDesignGroup` | Configure design brief  |
| `GetDesignBriefCode` / `GetMemberDesignParameters`                    | Read design settings    |

---

## osview → staad-view

| Function                                                                               | Purpose                                                                        |
| -------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `CopyPicture`                                                                          | Copy view to clipboard                                                         |
| `ExportView`                                                                           | Export view as image file (`.png`/`.jpg`/`.bmp`/`.emf`/`.wmf`, path-validated) |
| `ShowFront` / `ShowBack` / `ShowLeft` / `ShowRight` / `ShowPlan` / `ShowIsometric`     | Standard orientations                                                          |
| `ShowBottom` / `RotateLeft` / `RotateRight` / `RotateUp` / `RotateDown`                | Rotate/orient                                                                  |
| `SpinLeft` / `SpinRight`                                                               | Spin                                                                           |
| `ZoomAll` / `ZoomExtentsMainView`                                                      | Zoom                                                                           |
| `ShowMember` / `ShowMembers` / `ShowAllMembers`                                        | Show members                                                                   |
| `HideMember` / `HideMembers` / `HidePlate` / `HideSolid` / `HideAllMembers`            | Hide elements                                                                  |
| `SaveView` / `OpenView` / `RenameView`                                                 | Saved views                                                                    |
| `RefreshView`                                                                          | Refresh display                                                                |
| `SetInterfaceMode` / `GetInterfaceMode`                                                | Mode (Geometry/Post-processing)                                                |
| `SetLabel` / `SetDiagramMode` / `SetDesignResults`                                     | Diagram settings                                                               |
| `SetScaleValueByType` / `GetScaleValueByType` / `GetScaleValues` / `SetScaleValues`    | Scale settings                                                                 |
| `SetSectionView` / `SetUnits`                                                          | View options                                                                   |
| `GetWindowCount` / `GetWindowTitle` / `SetActiveWindow` / `CloseActiveWindow`          | Window management                                                              |
| `SelectByItemList` / `SelectGroup` / `SelectInverse` / `SelectEntitiesConnectedToNode` | View-based selection                                                           |
| `GetApplicationDesktopSize` / `SetWindowPosition`                                      | Window size/position                                                           |

---

## ostable → staad-reports

| Function                                                                 | Purpose          |
| ------------------------------------------------------------------------ | ---------------- |
| `CreateReport` / `DeleteReport` / `SaveReport` / `SaveReportAll`         | Report lifecycle |
| `AddTable` / `DeleteTable` / `RenameTable` / `ResizeTable` / `SaveTable` | Table management |
| `SetCellValue` / `GetCellValue`                                          | Cell data        |
| `SetColumnHeader` / `SetRowHeader` / `SetColumnUnitString`               | Headers/units    |
| `SetCellTextBold` / `SetCellTextItalic` / `SetCellTextUnderline`         | Formatting       |
| `SetCellTextColor` / `SetCellTextSize` / `SetCellTextSizeAll`            | Font             |
| `SetCellTextHorzAlignment` / `SetCellTextVertAlignment`                  | Alignment        |
| `GetReportCount` / `GetTableCount`                                       | Report queries   |
