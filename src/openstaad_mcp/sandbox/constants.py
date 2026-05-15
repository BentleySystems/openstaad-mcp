"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Sandbox constants: allowlists and limits for the Monty executor.

These values define the *security boundary* between AI-generated user code
and the STAAD COM API.  Any change to these sets must be accompanied by a
security review and a test update.

The allowlists mirror the WASM sandbox (feature/wasm-sandbox-security) to
maintain feature-parity on the security surface.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# COM surface allowlists
# ---------------------------------------------------------------------------

#: Root sub-objects that user code is allowed to resolve via ``staad.Foo``.
ALLOWED_SUB_OBJECTS: Final[frozenset[str]] = frozenset(
    {
        "Geometry",
        "Property",
        "Support",
        "Load",
        "Command",
        "Output",
        "Design",
        "Table",
        "View",
    }
)

#: Methods that may be called on the root ``staad`` handle (handle 0).
ALLOWED_ROOT_METHODS: Final[frozenset[str]] = frozenset(
    {
        # Analysis / solver
        "AnalyzeEx",
        "AnalyzeModel",
        "IsAnalyzing",
        "PerformAnalysis",
        # Units
        "GetBaseUnit",
        "GetInputUnitForForce",
        "GetInputUnitForLength",
        "GetOutputUnitForForce",
        "GetOutputUnitForLength",
        "SetInputUnits",
        # Silent / UI
        "SetSilentMode",
        "ShowApplication",
        # Model file control (consent-gated — see DESTRUCTIVE_METHODS)
        "NewSTAADFile",
        "OpenSTAADFile",
        "CloseSTAADFile",
        "SaveModel",
        "Quit",
        # Info / status
        "GetApplicationVersion",
        "GetProcessId",
        "GetSTAADFile",
        "GetSTAADFileFolder",
        "GetAnalysisStatus",
        # Model state
        "UpdateStructure",
    }
)

#: Methods blocked on *any* handle.
DENIED_METHODS: Final[frozenset[str]] = frozenset(
    {
        # UNC path redirection / NTLM relay vector.
        "SetStandardProfileDBFolder",
    }
)

# ---------------------------------------------------------------------------
# Destructive / filesystem-write consent gate
# ---------------------------------------------------------------------------

DESTRUCTIVE_METHODS: Final[dict[str, frozenset[str]]] = {
    "_root": frozenset(
        {
            "NewSTAADFile",
            "OpenSTAADFile",
            "CloseSTAADFile",
            "SaveModel",
            "Quit",
        }
    ),
    "View": frozenset(
        {
            "ExportView",
        }
    ),
    "Table": frozenset(
        {
            "SaveReport",
            "SaveReportAll",
            "SaveTable",
        }
    ),
}

ALL_DESTRUCTIVE_METHOD_NAMES: Final[frozenset[str]] = frozenset(
    method for methods in DESTRUCTIVE_METHODS.values() for method in methods
)

# ---------------------------------------------------------------------------
# Sub-object method allowlists  (deny-by-default)
# ---------------------------------------------------------------------------

ALLOWED_SUB_OBJECT_METHODS: Final[dict[str, frozenset[str]]] = {
    "Geometry": frozenset({
        "AddBeam", "AddCircularRegionToSurface",
        "AddDensityLineToSurface", "AddDensityPointToSurface",
        "AddMultipleBeams", "AddMultipleNodes", "AddMultiplePlates",
        "AddMultipleSolids", "AddNode", "AddParametricSurfaceToModel",
        "AddPlate", "AddPolygonalRegionToSurface", "AddSolid",
        "BreakBeamsAtSpecificNodes", "ClearMemberSelection",
        "ClearNodeSelection", "ClearPhysicalMemberSelection",
        "ClearPlateSelection", "ClearSolidSelection",
        "CommitParametricSurfaceMesh", "CreateBeam", "CreateGroup",
        "CreateGroupEx", "CreateMultipleBeams", "CreateMultipleNodes",
        "CreateMultiplePlates", "CreateNode", "CreatePhysicalMember",
        "CreatePlate", "CreateSolid", "DefineParametricSurface",
        "DeleteBeam", "DeleteGroup", "DeleteNode", "DeletePhysicalMember",
        "DeletePlate", "DeleteSolid", "DoTranslationalRepeat",
        "GetAnalyticalMemberCountForPhysicalMember",
        "GetAnalyticalMembersForPhysicalMember", "GetAreaOfPlates",
        "GetBeamLength", "GetBeamList", "GetBeamsConnectedAtNode",
        "GetCountOfBreakableBeamsAtSpecificNodes",
        "GetFlagForHiddenEntities", "GetGeneratedQuadPanelIncidences",
        "GetGroupCount", "GetGroupCountAll", "GetGroupEntities",
        "GetGroupEntityCount", "GetGroupNames", "GetIntersectBeamsCount",
        "GetLastBeamNo", "GetLastNodeNo", "GetLastPhysicalMemberNo",
        "GetLastPlateNo", "GetLastSolidNo", "GetMemberCount",
        "GetMemberIncidence", "GetMemberIncidence_CIS2",
        "GetMemberUniqueID", "GetNoOfBeamsConnectedAtNode",
        "GetNoOfGeneratedQuadPanels", "GetNoOfSelectedBeams",
        "GetNoOfSelectedNodes", "GetNoOfSelectedPhysicalMembers",
        "GetNoOfSelectedPlates", "GetNoOfSelectedSolids",
        "GetNodeCoordinates", "GetNodeCount", "GetNodeDistance",
        "GetNodeIncidence", "GetNodeIncidence_CIS2", "GetNodeList",
        "GetNodeNumber", "GetNodeUniqueID", "GetPID", "GetPMemberCount",
        "GetParametricSurfaceCount", "GetParametricSurfaceInfo",
        "GetParametricSurfaceInfoEx", "GetParametricSurfaceMeshData",
        "GetParametricSurfaceMeshInfo", "GetParametricSurfaceSubType",
        "GetParametricSurfaceUniqueID", "GetPhysicalMemberCount",
        "GetPhysicalMemberList", "GetPhysicalMemberUniqueID",
        "GetPlateCount", "GetPlateIncidence", "GetPlateIncidence_CIS2",
        "GetPlateList", "GetPlateNodeCount", "GetPlateUniqueID",
        "GetSelectedBeams", "GetSelectedNodes",
        "GetSelectedPhysicalMembers", "GetSelectedPlates",
        "GetSelectedSolids", "GetSolidCount", "GetSolidIncidence",
        "GetSolidIncidence_CIS2", "GetSolidList", "GetSolidUniqueID",
        "IntersectBeams", "IsBeam", "IsColumn", "IsOrphanNode", "IsZUp",
        "MergeBeams", "MergeNodes", "RemoveParametricSurfaceMesh",
        "RenumberBeam", "SelectBeam", "SelectMultipleBeams",
        "SelectMultipleNodes", "SelectMultiplePhysicalMembers",
        "SelectMultiplePlates", "SelectMultipleSolids", "SelectNode",
        "SelectPhysicalMember", "SelectPlate", "SelectSolid",
        "SetCheckForIdenticalEntity", "SetFlagForHiddenEntities",
        "SetMemberUniqueID", "SetNodeCoordinate", "SetNodeUniqueID",
        "SetPhysicalMemberUniqueID", "SetPlateUniqueID",
        "SetSolidUniqueID",
    }),
    "Property": frozenset({
        "AssignBeamProperty", "AssignCompoundTrapezoidalProperty",
        "AssignGeneralThickness", "AssignMaterialToBeam",
        "AssignMaterialToSurface", "AssignPlateThickness",
        "AssignProfileToBeam", "AssignPropertyToSolid",
        "AssignSelfWeightProperty", "AssignToGroup", "CreateMaterial",
        "CreateMemberPropertyFromTable", "CreatePrismaticPropertyFromTable",
        "GetBeamConstants", "GetBeamMaterialName",
        "GetBeamPropertyName", "GetBeamPropertyType",
        "GetBeamReleaseInfo", "GetBeamSectionPropertyValues",
        "GetIsotropicMaterialProperties", "GetListOfPropertyNames",
        "GetMemberDesignSectionName", "GetMemberMaterialType",
        "GetMemberPropertySpecification", "GetMemberReleaseSpec",
        "GetMemberReleaseSpecEx", "GetOrthotropicMaterialProperties",
        "GetPlatePropertyValue", "GetSectionPropertyCount",
        "SetBeamConstants", "SetBeamRelease", "SetMemberPartialRelease",
        "SetMemberRelease", "SetMemberTruss",
    }),
    "Support": frozenset({
        "AssignSupportToNode", "CreateSupportFixed",
        "CreateSupportFixedBut", "CreateSupportInclined",
        "CreateSupportMultilinearSpring", "CreateSupportPinned",
        "CreateSupportSpring", "GetNoOfSupportedNodes",
        "GetSupportCondition", "GetSupportCount",
        "GetSupportedNodes", "GetSupportType",
    }),
    "Load": frozenset({
        "AddLoadCombination", "AddNodalLoad", "AssignAreaLoad",
        "AssignConcentratedLoad", "AssignElementPressureLoad",
        "AssignFloorLoad", "AssignGravityLoad",
        "AssignMemberConcentratedForce",
        "AssignMemberConcentratedMoment", "AssignMemberPreStress",
        "AssignMemberTemperatureLoad", "AssignMemberTrapezoidal",
        "AssignMemberUniformForce", "AssignMemberUniformMoment",
        "AssignNodeDisplacement", "AssignPlateConcentratedLoad",
        "AssignPlateStrainLoad", "AssignPlateTemperatureLoad",
        "AssignPlateTrapezoidalLoad", "AssignPlateUniformLoad",
        "AssignSolidTemperatureLoad", "AssignSolidUniformPressure",
        "AssignSurfacePressureLoad", "AssignWindLoad",
        "CreateNewPrimaryLoad", "CreateResponseSpectrumLoad",
        "GetActiveLoad", "GetConcentratedForce",
        "GetFloorLoad", "GetGravityLoad", "GetGravityLoadEx",
        "GetLoadCaseTitle", "GetLoadCombinationCaseCount",
        "GetLoadCombinationCases", "GetLoadCombinationFactors",
        "GetLoadList", "GetMemberConcentratedForceList",
        "GetMemberConcentratedMomentList",
        "GetMemberDistributedUniformForceList",
        "GetMemberDistributedUniformMomentList",
        "GetMemberTrapezoidalForceList",
        "GetMemberTrapezoidalMomentList",
        "GetNoOfLoadedNodesForNodeDisplacement",
        "GetNoOfMemberConcentratedForce",
        "GetNoOfMemberConcentratedMoment",
        "GetNoOfMemberDistributedUniformForce",
        "GetNoOfMemberDistributedUniformMoment",
        "GetNoOfMemberTrapezoidalForce",
        "GetNoOfMemberTrapezoidalMoment",
        "GetNoOfNodalLoad", "GetNodalLoad",
        "GetNodeDisplacement", "GetPrimaryLoadCaseCount",
        "GetSelfWeightProperty", "GetTrapezoidal",
        "GetUniformLoad", "SetActiveLoad",
        "SetLoadActive",
    }),
    "Command": frozenset({
        "AddCutOffFrequencyCommand", "AddCutOffModeShapeCommand",
        "AddMissingMassCommand", "AddPerformAnalysisCommand",
        "AddPDeltaAnalysisCommand",
        "AssignCheckIrregularitiesCommand",
        "AssignCheckSoftStoryCommand",
        "CreateAnalysisFlag", "CreateResponseSpectrumDamping",
        "CreateTimeFunctionFromFile",
        "CreateTimeHistoryDefinitionFromFile",
        "CreateTimeHistoryLoadFromTimeFunction",
        "SetCheckIrregularitiesCommand",
        "SetCheckSoftStoryCommand",
        "SetFloorDiaphragmBaseCommand",
    }),
    "Output": frozenset({
        "AreResultsAvailable", "GetAllPlateCenterForces",
        "GetAllPlateCenterMoments",
        "GetAllPlateCenterPrincipalStressesAndAngles",
        "GetAllPlateCenterPrincipalStressesAndAnglesEx",
        "GetAllPlateCenterStressesAndMoments",
        "GetAllSolidNormalStresses", "GetAllSolidPrincipalStresses",
        "GetAllSolidShearStresses", "GetAllSolidVonMisesStresses",
        "GetBasePressures", "GetBucklingFactor",
        "GetBucklingModeDisplacementAtNode",
        "GetIntermediateDeflectionAtDistance",
        "GetIntermediateMemberAbsTransDisplacements",
        "GetIntermediateMemberForcesAtDistance",
        "GetIntermediateMemberTransDisplacements",
        "GetMatInfluenceAreas", "GetMaxBeamStresses",
        "GetMaxSectionDisplacement", "GetMemberDesignSectionName",
        "GetMemberEndDisplacements", "GetMemberEndForces",
        "GetMemberSteelDesignMaxFailureRatio",
        "GetMemberSteelDesignMinFailureRatio",
        "GetMemberSteelDesignRatio", "GetMemberSteelDesignResults",
        "GetMinMaxAxialForce", "GetMinMaxBendingMoment",
        "GetMinMaxShearForce", "GetModalDisplacementAtNode",
        "GetModalMassParticipationFactors", "GetModeFrequency",
        "GetMultipleMemberSteelDesignMaxRatio",
        "GetMultipleMemberSteelDesignRatio",
        "GetMultipleMemberSteelDesignResults", "GetNLLoadStep",
        "GetNLNodeDisplacements", "GetNoOfBucklingFactors",
        "GetNoOfModesExtracted", "GetNodeDisplacements",
        "GetOutputUnitForDensity", "GetOutputUnitForDimension",
        "GetOutputUnitForDisplacement", "GetOutputUnitForDistForce",
        "GetOutputUnitForDistMoment", "GetOutputUnitForForce",
        "GetOutputUnitForMoment", "GetOutputUnitForRotation",
        "GetOutputUnitForSectArea", "GetOutputUnitForSectDimension",
        "GetOutputUnitForSectInertia", "GetOutputUnitForSectModulus",
        "GetOutputUnitForStress", "GetPMemberEndForces",
        "GetPMemberIntermediateForcesAtDistance",
        "GetPlateCenterNormalPrincipalStresses",
        "GetPlateCenterVonMisesStresses", "GetPlateCornerForces",
        "GetPlateStressAtPoint",
        "GetResultantForceAlongLineForParametricSurface",
        "GetResultantForceAlongLineForPlateList",
        "GetStaticCheckResult", "GetSteelDesignParameterBlockCount",
        "GetSteelDesignParameterBlockNameByIndex",
        "GetSupportReactions", "GetTimeHistoryIntegrationStepInfo",
        "GetTimeHistoryResponse", "GetTimeHistoryResponseAtTime",
        "GetTimeHistoryResponseMinMax",
        "IsBucklingAnalysisResultsAvailable",
        "IsMultipleMemberSteelDesignResultsAvailable",
    }),
    "Design": frozenset({
        "AssignDesignCommand", "AssignDesignGroup",
        "AssignDesignParameter", "CreateDesignBrief",
        "GetDesignBriefCode", "GetMemberDesignParameters",
    }),
    "Table": frozenset({
        "AddTable", "CreateReport", "DeleteReport", "DeleteTable",
        "GetCellValue", "GetReportCount", "GetTableCount",
        "RenameTable", "ResizeTable", "SaveReport", "SaveReportAll",
        "SaveTable", "SetCellTextBold", "SetCellTextColor",
        "SetCellTextHorzAlignment", "SetCellTextItalic",
        "SetCellTextSize", "SetCellTextSizeAll",
        "SetCellTextUnderline", "SetCellTextVertAlignment",
        "SetCellValue", "SetColumnHeader", "SetColumnUnitString",
        "SetRowHeader",
    }),
    "View": frozenset({
        "CloseActiveWindow", "CopyPicture",
        "CreateNewViewForSelections", "CreateNewViewForSelectionsEx",
        "DetachView", "ExportView", "GetApplicationDesktopSize",
        "GetBeamsInView", "GetInterfaceMode", "GetNoOfBeamsInView",
        "GetScaleCount", "GetScaleValueByType", "GetScaleValues",
        "GetWindowCount", "GetWindowTitle", "HideAllMembers",
        "HideEntity", "HideMember", "HideMembers", "HidePlate",
        "HideSolid", "HideSurface", "OpenView", "RefreshView",
        "RenameView", "RotateDown", "RotateLeft", "RotateRight",
        "RotateUp", "SaveView", "SelectByItemList",
        "SelectByMissingAttribute",
        "SelectEntitiesConnectedToMember",
        "SelectEntitiesConnectedToNode",
        "SelectEntitiesConnectedToPlate",
        "SelectEntitiesConnectedToSolid", "SelectGroup",
        "SelectInverse", "SelectMembersParallelTo",
        "SetActiveWindow", "SetBeamAnnotationMode",
        "SetDesignResults", "SetDiagramMode", "SetInterfaceMode",
        "SetLabel", "SetModeSectionPage", "SetNodeAnnotationMode",
        "SetReactionAnnotationMode", "SetScaleValueByType",
        "SetScaleValues", "SetSectionView", "SetUnits",
        "SetWindowPosition", "ShowAllMembers", "ShowBack",
        "ShowBottom", "ShowFront", "ShowIsometric", "ShowLeft",
        "ShowMember", "ShowMembers", "ShowPlan", "ShowRight",
        "SpinLeft", "SpinRight", "ZoomAll", "ZoomExtentsMainView",
    }),
}

# ---------------------------------------------------------------------------
# Executor limits
# ---------------------------------------------------------------------------

#: Wall-clock timeout for a single ``execute_code`` call (seconds).
EXECUTION_TIMEOUT_SECONDS: Final[float] = 30.0

#: Maximum heap memory for Monty interpreter (bytes).
#: 64 MiB mirrors the WASM linear memory limit.
MAX_MEMORY_BYTES: Final[int] = 64 * 1024 * 1024

#: Maximum number of heap allocations before Monty aborts execution.
MAX_ALLOCATIONS: Final[int] = 10_000_000

#: Garbage-collection interval (every N allocations).
GC_INTERVAL: Final[int] = 50_000

#: Maximum recursion / call-stack depth.
MAX_RECURSION_DEPTH: Final[int] = 200

#: Maximum captured stdout/stderr size in characters.
MAX_STDOUT_CHARS: Final[int] = 256_000

#: Maximum size of the user source accepted by ``execute_code``.
MAX_CODE_BYTES: Final[int] = 256 * 1024  # 256 KiB

#: Maximum length for a single result value to prevent large payloads.
MAX_RESULT_LENGTH: Final[int] = 100_000
