# OpenSTAADPy Error Codes Reference

All exceptions inherit from `OsErrorBase(Exception)` and expose a `.code` attribute.
The message is formatted `[code] message`.

## Codes That Never Raise

The wrapper dispatches codes through a lookup table. Anything **not** in the tables
below is silently ignored — the function returns normally with unpopulated output
values instead of raising. Notably code `0` is unmapped, so the classes
`OsUnableToCreateProp` (0) and `OsCannotFindMember` (0) exist but are never raised by
the dispatcher; functions that treat `0` as failure raise a generic `[-1]` error
instead. Never treat "no exception" as proof of success — sanity-check the returned
values.

## General / Argument Errors

| Code | Exception Class | Message |
|------|----------------|---------|
| -1 | `OsError` | General error |
| -2 | `OsInvalidModelPath` | Invalid model path |
| -100 | `OsInvalidArgument` | Invalid argument |
| -101 | `OsModelNotOpened` | STAAD model is not opened |
| -106 | `OsMultidimArrayExpected` | Multidimensional array expected |
| -107 | `OsArrayExpected` | Array expected |
| -108 | `OsArraySizeSmall` | Array size too small |
| -109 | `OsArraySizeZero` | Array size is zero |
| -110 | `OsNoBeamPlateSolidSelected` | No beam, plate, or solid selected |
| -112 | `OsDoubleExpected` | Double value expected |
| -113 | `OsIntegerExpected` | Integer value expected |
| -114 | `OsOleException` | OLE exception occurred |
| -115 | `OsLicenseNotSupported` | License lacks OpenSTAAD Professional functions |
| -125 | `OsArraySizeLessThanReqd` | Array size less than required |
| -130 | `OsIndexOutOfRange` | Index out of range |
| -131 | `OsInvalidDirectionCode` | Invalid direction code |

## File Errors

| Code | Exception Class | Message |
|------|----------------|---------|
| -1003 | `OsFileAlreadyExists` | File already exists |

## Node Errors

| Code | Exception Class | Message |
|------|----------------|---------|
| -2001 | `OsNodeNotFound` | Node not found |
| -2004 | `OsErrorAddNode` | Error adding node |
| -2005 | `OsNoNodeSelected` | No node selected |
| -2006 | `OsInvalidNodeNo` | Invalid node number |

## Beam / Member Errors

| Code | Exception Class | Message |
|------|----------------|---------|
| -3001 | `OsBeamNotFound` | Beam not found |
| -3002 | `OsBeamAlreadyExists` | Beam already exists |
| -3003 | `OsIdenticalBeamAlreadyExists` | Identical beam already exists |
| -3004 | `OsErrorAddBeam` | Error adding beam |
| -3005 | `OsNoBeamSelected` | No beam selected |
| -3006 | `OsInvalidMemberNo` | Invalid member number ID(s) |

## Plate Errors

| Code | Exception Class | Message |
|------|----------------|---------|
| -4001 | `OsPlateNotFound` | Plate not found |
| -4004 | `OsErrorAddPlate` | Error adding plate |
| -4005 | `OsNoPlateSelected` | No plate selected |
| -4006 | `OsInvalidPlateNo` | Invalid plate number |
| -4008 | `OsInvalidPlateNoFound` | Invalid plate number found (some invalid) |
| -4009 | `OsNoValidPlateNoFound` | No valid plate number found (all invalid) |

## Solid Errors

| Code | Exception Class | Message |
|------|----------------|---------|
| -5001 | `OsSolidNotFound` | Solid not found |
| -5004 | `OsErrorAddSolid` | Error adding solid |
| -5005 | `OsNoSolidSelected` | No solid selected |
| -5603 | `OsMeshNotFound` | Mesh not found |
| -5701 | `OsPmemberNotFound` | Physical member not found |

## Property Errors

| Code | Exception Class | Message |
|------|----------------|---------|
| -6001 | `OsInvalidPropRef` | Invalid property reference |
| -6002 | `OsLibErrorPropAssign` | Library error: property assign |
| -6003 | `OsLibErrorCreateProp` | Library error creating property |
| -6004 | `OsProfileNotFound` | Profile not found in database |
| -6005 | `OsProfileDataNotFound` | Profile data not found |
| -6006 | `OsInvalidSectionType` | Invalid section type |
| -6008 | `OsInvalidAssignType` | Invalid assign type |
| -6009 | `OsLibErrorBetaAssign` | Library error assigning beta angle |
| -6010 | `OsLibErrorCreateTrussSpec` | Unable to create member truss spec |
| -6011 | `OsLibErrorCreateInactiveSpec` | Unable to create member inactive spec |
| -6012 | `OsLibErrorCreateTensionSpec` | Unable to create member tension spec |
| -6013 | `OsLibErrorCreateCompressionSpec` | Unable to create member compression spec |
| -6014 | `OsLibErrorCreateIgnoreStiffSpec` | Unable to create ignore stiffness spec |
| -6015 | `OsLibErrorCreateCableSpec` | Unable to create member cable spec |
| -6017 | `OsLibErrorAssignSpec` | Unable to assign specification |
| -6018 | `OsLibErrorCreatePlaneStressSpec` | Unable to create element plane stress spec |
| -6019 | `OsLibErrorCreateInplaneRotnSpec` | Unable to create element inplane rotation spec |
| -6020 | `OsLibErrorCreateReleaseSpec` | Unable to create member release spec |
| -6021 | `OsLibErrorCreateElementNodeReleaseSpec` | Unable to create element node release spec |
| -6022 | `OsNoPropAttached` | No property attached to element |
| -6023 | `OsMaterialNotFound` | Material not found |
| -6025 | `OsNoPropDefined` | No property defined |
| -6026 | `OsInvalidMemberElementRef` | Invalid member/element reference |
| -6027 | `OsNoOffsetInfo` | No offset information for the node index |
| -6029 | `OsLibErrorCreateControlDependentSpec` | Unable to create control/dependent spec |
| -6031 | `OsUptCreateFailed` | UPT creation failed |
| -6032 | `OsAddUptSectionFailed` | Add UPT section failed |
| -6036 | `OsUptNotFound` | Cannot find UPT / unknown table type |
| -6045 | `OsUptSectionExists` | UPT section already exists |
| -6049 | `OsInvalidAttrValPair` | Invalid attribute-value pair |

## Spring Errors

| Code | Exception Class | Message |
|------|----------------|---------|
| -7504 | `OsSpringNotDefinedAtNode` | Spring not defined at node |

## Group Errors

| Code | Exception Class | Message |
|------|----------------|---------|
| -7001 | `OsGroupAlreadyExists` | Group already exists |

## Load Errors

| Code | Exception Class | Message |
|------|----------------|---------|
| -8001 | `OsInvalidLoadDirection` | Invalid load direction |
| -8002 | `OsLoadCaseNotFound` | Load case not found |
| -8004 | `OsCreateLoadFailed` | Create load failed |
| -8005 | `OsLibErrorAssignLoad` | Library error: unable to assign load |
| -8029 | `OsLoadExists` | Load already exists |
| -8034 | `OsSeismicCodeNotFound` | Seismic code not found |
| -8038 | `OsInvalidSeismicDirection` | Invalid seismic direction |
| -8039 | `OsInvalidLoadDefId` | Invalid load definition ID |
| -8040 | `OsInvalidLoadCombName` | Invalid load combination name |
| -8041 | `OsInvalidLoadCombCategory` | Invalid load combination category |
| -8043 | `OsEnclosedZoneNotFound` | Enclosed zone not found |
| -8044 | `OsCreateEnclosedZoneFailed` | Failed to create enclosed zone |
| -8045 | `OsAddOpeningFailed` | Failed to add opening to enclosed zone |
| -8046 | `OsIgnoreMemberPanelFailed` | Failed to ignore members for panel formation |
| -8047 | `OsIgnoreMemberLoadFailed` | Failed to ignore members for load transfer |
| -8048 | `OsEnclosedZoneAlreadyExists` | Enclosed zone already exists |
| -8049 | `OsAddEnclosedZoneLoadFailed` | Failed to add load to enclosed zone |
| -8101 | `OsBoundaryNoBeamsFound` | No beams found for the floor boundary |
| -8102 | `OsBoundaryInsufficientNodes` | Insufficient nodes for the floor boundary |
| -8103 | `OsBoundaryInsufficientBeams` | Insufficient beams for the floor boundary |
| -8104 | `OsBoundaryNonCoplanar` | Floor boundary nodes are not coplanar |
| -8105 | `OsBoundaryAllNodesCollinear` | All floor boundary nodes are collinear |
| -8106 | `OsBoundaryMissingNodeReference` | Missing node reference in the floor boundary |

## Results Errors

| Code | Exception Class | Message |
|------|----------------|---------|
| -9004 | `OsBeamForcesNotLoaded` | Beam forces not loaded |
| -9911 | `OsNoGnlResultSet` | No GNL result set found |
| -9915 | `OsResultNotFound` | Result not found or could not be loaded |

## Export Errors

| Code | Exception Class | Message |
|------|----------------|---------|
| -14501 | `OsExportSuccessWithWarnings` | Export succeeded with warnings |
| -14502 | `OsExportFailed` | Export failed |

## Miscellaneous

| Code | Exception Class | Message |
|------|----------------|---------|
| 3007 | `OsMemberUpdated` | Member updated (informational) |
