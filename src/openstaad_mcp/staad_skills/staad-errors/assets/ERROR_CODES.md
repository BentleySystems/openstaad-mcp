# OpenSTAADPy Error Codes Reference

All exceptions inherit from `OsErrorBase(Exception)` and expose a `.code` attribute.

## General / Argument Errors

| Code | Exception Class | Message |
|------|----------------|---------|
| -1 | `OsError` | General error |
| 0 | `OsUnableToCreateProp` | Unable to create property |
| -100 | `OsInvalidArgument` | Invalid argument |
| -106 | `OsMultidimArrayExpected` | Multidimensional array expected |
| -107 | `OsArrayExpected` | Array expected |
| -108 | `OsArraySizeSmall` | Array size too small |
| -109 | `OsArraySizeZero` | Array size is zero |
| -110 | `OsNoBeamPlateSolidSelected` | No beam, plate, or solid selected |
| -112 | `OsDoubleExpected` | Double value expected |
| -113 | `OsIntegerExpected` | Integer value expected |
| -125 | `OsArraySizeLessThanReqd` | Array size less than required |

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
| -6003 | `OsLibErrorCreateProp` | Library error creating property |
| -6004 | `OsProfileNotFound` | Profile not found in database |
| -6005 | `OsProfileDataNotFound` | Profile data not found |
| -6006 | `OsInvalidSectionType` | Invalid section type |
| -6008 | `OsInvalidAssignType` | Invalid assign type |
| -6009 | `OsLibErrorBetaAssign` | Library error assigning beta angle |
| -6017 | *(raw int)* | Library error: unable to assign specification |
| -6020 | *(raw int)* | Library error: unable to create member release spec |
| -6022 | `OsNoPropAttached` | No property attached to element |
| -6023 | `OsMaterialNotFound` | Material not found |
| -6025 | `OsNoPropDefined` | No property defined |
| -6031 | `OsUptCreateFailed` | UPT creation failed |
| -6032 | `OsAddUptSectionFailed` | Add UPT section failed |
| -6045 | `OsUptSectionExists` | UPT section already exists |

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
| -8029 | `OsLoadExists` | Load already exists |
| -8034 | `OsSeismicCodeNotFound` | Seismic code not found |
| -8039 | `OsInvalidLoadDefId` | Invalid load definition ID |
| -8040 | `OsInvalidLoadCombName` | Invalid load combination name |
| -8041 | `OsInvalidLoadCombCategory` | Invalid load combination category |

## Results Errors

| Code | Exception Class | Message |
|------|----------------|---------|
| -9004 | `OsBeamForcesNotLoaded` | Beam forces not loaded |
| -9911 | `OsNoGnlResultSet` | No GNL result set found |

## Miscellaneous

| Code | Exception Class | Message |
|------|----------------|---------|
| 3007 | `OsMemberUpdated` | Member updated (informational) |
