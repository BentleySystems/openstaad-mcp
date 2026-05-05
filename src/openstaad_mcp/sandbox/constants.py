"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Sandbox constants: allowlists and limits for the WASM executor.

These values define the *security boundary* between AI-generated user code
and the STAAD COM API. Any change to these sets must be accompanied by a
security review and a test update.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# COM surface allowlists
# ---------------------------------------------------------------------------

#: Root sub-objects that user code is allowed to resolve via ``staad.Foo``.
#: Any other property name on the root handle is rejected *before* getattr
#: runs. Derived from the COM API enumeration in
#: ``docs/plan-research-support/enumerate-com-api.py``.
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
#:
#: Kept deliberately broad — see ``docs/plan.md`` "Root allowlist" for the
#: rationale. The methods here are either:
#:   (a) safe by shape (units, status, info, analysis control), or
#:   (b) required workflow steps in skill scripts (SaveModel, NewSTAADFile), or
#:   (c) gated by the consent gate (DESTRUCTIVE_METHODS) — only callable when
#:       the user approves via host elicitation (Quit, CloseSTAADFile, OpenSTAADFile).
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

#: Methods blocked on *any* handle. These either have no legitimate use
#: in any skill workflow, or their only use is an attack (e.g. NTLM relay).
DENIED_METHODS: Final[frozenset[str]] = frozenset(
    {
        # UNC path redirection / NTLM relay vector — unused in all skills.
        "SetStandardProfileDBFolder",
    }
)

# ---------------------------------------------------------------------------
# Destructive / filesystem-write consent gate  (Control 4 — Explicit Consent)
# ---------------------------------------------------------------------------
#
# Methods in this dict write to the local filesystem, terminate the STAAD
# session, or close unsaved work.  They are allowed by the *allowlist* (the
# method is a legitimate API call) but gated behind a **consent flag** that
# the server sets only after receiving explicit human approval via MCP
# elicitation (a host-mediated dialog the LLM cannot self-confirm).
#
# This implements Control 4 (Explicit Consent for State-Changing Actions)
# from the security architecture: even if prompt injection tricks the LLM
# into calling a write method, the consent gate blocks it because approval
# requires a human to confirm a host-side dialog.
#
# Key: ``"_root"`` for handle-0 methods; otherwise the sub-object name.

DESTRUCTIVE_METHODS: Final[dict[str, frozenset[str]]] = {
    "_root": frozenset(
        {
            "NewSTAADFile",  # Creates new .std file at arbitrary path
            "OpenSTAADFile",  # Opens file (+ UNC/NTLM relay risk)
            "CloseSTAADFile",  # Closes current model (data-loss risk)
            "SaveModel",  # Writes current model to disk
            "Quit",  # Terminates STAAD.Pro process
        }
    ),
    "View": frozenset(
        {
            "ExportView",  # Writes image file to arbitrary path
        }
    ),
    "Table": frozenset(
        {
            "SaveReport",  # Writes report file to disk
            "SaveReportAll",  # Writes all report files to disk
            "SaveTable",  # Writes table file to disk
        }
    ),
}

#: Flattened set of all destructive method names, used by the server layer
#: for pre-flight detection before WASM execution.
ALL_DESTRUCTIVE_METHOD_NAMES: Final[frozenset[str]] = frozenset(
    method for methods in DESTRUCTIVE_METHODS.values() for method in methods
)

# ---------------------------------------------------------------------------
# Sub-object method allowlists
# ---------------------------------------------------------------------------
#
# Generated from openstaadpy wrappers on 2026-04-26 via:
#     .venv/Scripts/python -c "import importlib, inspect, json; ..."
#
# These define the *complete* set of methods allowed on each sub-object
# handle. Any method NOT in this set is rejected before getattr fires.
# This flips the posture from deny-list (only SetStandardProfileDBFolder
# blocked) to deny-by-default (only audited methods allowed).
#
# Re-generate when upgrading STAAD.Pro: run enumerate-com-api.py with
# --generate-allowlist and diff the output.

ALLOWED_SUB_OBJECT_METHODS: Final[dict[str, frozenset[str]]] = {
    "Geometry": frozenset({
        "AddBeam", "AddCircularRegionToSurface", "AddDensityLineToSurface",
        "AddDensityPointToSurface", "AddMultipleBeams", "AddMultipleNodes",
        "AddMultiplePlates", "AddMultipleSolids", "AddNode",
        "AddParametricSurfaceToModel", "AddPlate", "AddPolygonalRegionToSurface",
        "AddSolid", "BreakBeamsAtSpecificNodes", "ClearMemberSelection",
        "ClearNodeSelection", "ClearPhysicalMemberSelection", "ClearPlateSelection",
        "ClearSolidSelection", "CommitParametricSurfaceMesh", "CreateBeam",
        "CreateGroup", "CreateGroupEx", "CreateMultipleBeams", "CreateMultipleNodes",
        "CreateMultiplePlates", "CreateNode", "CreatePhysicalMember", "CreatePlate",
        "CreateSolid", "DefineParametricSurface", "DeleteBeam", "DeleteGroup",
        "DeleteNode", "DeletePhysicalMember", "DeletePlate", "DeleteSolid",
        "DoTranslationalRepeat", "GetAnalyticalMemberCountForPhysicalMember",
        "GetAnalyticalMembersForPhysicalMember", "GetAreaOfPlates", "GetBeamLength",
        "GetBeamList", "GetBeamsConnectedAtNode",
        "GetCountOfBreakableBeamsAtSpecificNodes", "GetFlagForHiddenEntities",
        "GetGeneratedQuadPanelIncidences", "GetGroupCount", "GetGroupCountAll",
        "GetGroupEntities", "GetGroupEntityCount", "GetGroupNames",
        "GetIntersectBeamsCount", "GetLastBeamNo", "GetLastNodeNo",
        "GetLastPhysicalMemberNo", "GetLastPlateNo", "GetLastSolidNo",
        "GetMemberCount", "GetMemberIncidence", "GetMemberIncidence_CIS2",
        "GetMemberUniqueID", "GetNoOfBeamsConnectedAtNode",
        "GetNoOfGeneratedQuadPanels", "GetNoOfSelectedBeams",
        "GetNoOfSelectedNodes", "GetNoOfSelectedPhysicalMembers",
        "GetNoOfSelectedPlates", "GetNoOfSelectedSolids", "GetNodeCoordinates",
        "GetNodeCount", "GetNodeDistance", "GetNodeIncidence",
        "GetNodeIncidence_CIS2", "GetNodeList", "GetNodeNumber", "GetNodeUniqueID",
        "GetPID", "GetPMemberCount", "GetParametricSurfaceCount",
        "GetParametricSurfaceInfo", "GetParametricSurfaceInfoEx",
        "GetParametricSurfaceMeshData", "GetParametricSurfaceMeshInfo",
        "GetParametricSurfaceSubType", "GetParametricSurfaceUniqueID",
        "GetPhysicalMemberCount", "GetPhysicalMemberList",
        "GetPhysicalMemberUniqueID", "GetPlateCount", "GetPlateIncidence",
        "GetPlateIncidence_CIS2", "GetPlateList", "GetPlateNodeCount",
        "GetPlateUniqueID", "GetSelectedBeams", "GetSelectedNodes",
        "GetSelectedPhysicalMembers", "GetSelectedPlates", "GetSelectedSolids",
        "GetSolidCount", "GetSolidIncidence", "GetSolidIncidence_CIS2",
        "GetSolidList", "GetSolidUniqueID", "IntersectBeams", "IsBeam",
        "IsColumn", "IsOrphanNode", "IsZUp", "MergeBeams", "MergeNodes",
        "RemoveParametricSurfaceMesh", "RenumberBeam", "SelectBeam",
        "SelectMultipleBeams", "SelectMultipleNodes",
        "SelectMultiplePhysicalMembers", "SelectMultiplePlates",
        "SelectMultipleSolids", "SelectNode", "SelectPhysicalMember",
        "SelectPlate", "SelectSolid", "SetCheckForIdenticalEntity",
        "SetFlagForHiddenEntities", "SetMemberUniqueID", "SetNodeCoordinate",
        "SetNodeUniqueID", "SetPID", "SetParametricSurfaceSubType",
        "SetParametricSurfaceUniqueID", "SetPhysicalMemberUniqueID",
        "SetPlateUniqueID", "SetSolidUniqueID", "SplitBeam",
        "SplitBeamInEqlParts", "UpdateGroup",
    }),
    "Property": frozenset({
        "AddControlDependentRelation", "AddUPTPropertyANGLE",
        "AddUPTPropertyCHANNEL", "AddUPTPropertyDOUBLEANGLE",
        "AddUPTPropertyGENERAL", "AddUPTPropertyISECTION", "AddUPTPropertyPIPE",
        "AddUPTPropertyPRISMATIC", "AddUPTPropertyTEE", "AddUPTPropertyTUBE",
        "AddUPTPropertyWIDEFLANGE", "AddUPTPropertyWIDEFLANGECOMPOSITE",
        "AddUPTPropertyWIDEFLANGEUNEQUAL", "AssignBeamProperty",
        "AssignBetaAngle", "AssignElementAttribute", "AssignElementSpecToPlate",
        "AssignMaterialToMember", "AssignMaterialToPlate", "AssignMaterialToSolid",
        "AssignMemberAttribute", "AssignMemberSpecToBeam", "AssignPlateThickness",
        "CreateAnglePropertyFromTable", "CreateAssignProfileProperty",
        "CreateBeamPropertyFromTable", "CreateBeamPropertyFromTableComposite",
        "CreateBeamPropertyFromTableEx",
        "CreateBeamPropertyFromTableWithCoverPlates",
        "CreateChannelPropertyFromTable", "CreateElementAttribute",
        "CreateElementIgnoreInplaneRotnSpec", "CreateElementLocalZOffsetSpec",
        "CreateElementNodeReleaseSpec", "CreateElementOffsetSpec",
        "CreateElementPlaneStressSpec", "CreateIsotropicMaterialAluminum",
        "CreateIsotropicMaterialConcrete", "CreateIsotropicMaterialProperties",
        "CreateIsotropicMaterialPropertiesEx", "CreateIsotropicMaterialSteel",
        "CreateIsotropicMaterialTimber", "CreateMemberAttribute",
        "CreateMemberCableSpec", "CreateMemberCableSpecEx",
        "CreateMemberCompressionSpec", "CreateMemberFireProofingSpec",
        "CreateMemberIgnoreStiffSpec", "CreateMemberInactiveSpec",
        "CreateMemberOffsetSpec", "CreateMemberPartialReleaseSpec",
        "CreateMemberReleaseSpec", "CreateMemberTensionSpec",
        "CreateMemberTrussSpec", "CreateParametricSurfaceThicknessProperty",
        "CreatePipePropertyFromTable", "CreatePlateThicknessProperty",
        "CreatePrismaticCircleProperty", "CreatePrismaticGeneralProperty",
        "CreatePrismaticRectangleProperty", "CreatePrismaticTeeProperty",
        "CreatePrismaticTrapezoidalProperty", "CreatePropertyFromUPTTable",
        "CreatePropertyFromUserTable", "CreateTaperedIProperty",
        "CreateTaperedTubeProperty", "CreateTeePropertyFromTable",
        "CreateTubePropertyFromTable", "CreateUPTTable", "CreateUPTTableEx",
        "CreateWideFlangePropertyFromTable", "DeleteAllControlDependentRelations",
        "DeleteElementAttribute", "DeleteMaterial", "DeleteMemberAttribute",
        "DeleteMemberReleaseSpec", "DeleteMemberSpec", "DeleteProperty",
        "GetAlphaAngleForSection", "GetAssignedAttributeByIndex",
        "GetAssignedAttributeCount", "GetBeamConstants", "GetBeamMaterialName",
        "GetBeamProperty", "GetBeamPropertyAll", "GetBeamSectionDisplayName",
        "GetBeamSectionName", "GetBeamSectionPropertyRefNo",
        "GetBeamSectionPropertyTypeNo", "GetBeamSectionPropertyValuesEx",
        "GetBetaAngle", "GetCentroidLocationForSection",
        "GetCountofSectionPropertyValuesEx", "GetCountryTableNo",
        "GetDefaultStandardProfileDBFolder", "GetElementCountByAttribute",
        "GetElementGlobalOffSet", "GetElementListByAttribute",
        "GetElementLocalOffset", "GetElementMaterialName", "GetElementOffSetSpec",
        "GetElementOffsetSpecCount", "GetFireProofDataForBeam",
        "GetFireProofedBeamCount", "GetFireProofedBeamList",
        "GetFireProofingSpecAssignedBeamCount",
        "GetFireProofingSpecAssignedBeamList", "GetFireProofingSpecCount",
        "GetFireProofingSpecDetails", "GetInactiveMemberCount",
        "GetInactiveMemberList", "GetIsotropicMaterialAssignedBeamCount",
        "GetIsotropicMaterialAssignedBeamList",
        "GetIsotropicMaterialAssignedPlateCount",
        "GetIsotropicMaterialAssignedPlateList",
        "GetIsotropicMaterialAssignedSolidCount",
        "GetIsotropicMaterialAssignedSolidList", "GetIsotropicMaterialCount",
        "GetIsotropicMaterialProperties",
        "GetIsotropicMaterialPropertiesAssigned",
        "GetIsotropicMaterialPropertiesEx", "GetMaterialProperty",
        "GetMaterialPropertyEx", "GetMemberAttributeCount",
        "GetMemberAttributeList", "GetMemberCountByAttribute",
        "GetMemberCountByAttributeIndex", "GetMemberGlobalOffSet",
        "GetMemberListByAttribute", "GetMemberListByAttributeIndex",
        "GetMemberLocalOffSet", "GetMemberReleaseSpec", "GetMemberReleaseSpecEx",
        "GetMemberSpecCode", "GetOrthotropic2DMaterialCount",
        "GetOrthotropic2DMaterialProperties", "GetOrthotropic3DMaterialCount",
        "GetOrthotropic3DMaterialProperties", "GetPlateMaterialName",
        "GetPlateSectionPropertyRefNo", "GetPlateThickness",
        "GetPropertyUniqueID", "GetPublishedProfileName", "GetRecordForSection",
        "GetSTAADProfileName", "GetSectionPropertyAssignedBeamCount",
        "GetSectionPropertyAssignedBeamList", "GetSectionPropertyCount",
        "GetSectionPropertyCountry", "GetSectionPropertyList",
        "GetSectionPropertyName", "GetSectionPropertyType",
        "GetSectionPropertyValues", "GetSectionPropertyValuesEx",
        "GetSectionTableNo", "GetShapeCode", "GetSolidMaterialName",
        "GetStandardProfileDBFolder", "GetStandardSectionDatabaseName",
        "GetStandardSectionName", "GetStandardSectionTableName",
        "GetThicknessPropertyAssignedPlateCount",
        "GetThicknessPropertyAssignedPlateList", "GetThicknessPropertyCount",
        "GetThicknessPropertyList", "GetThicknessPropertyValues",
        "GetTypeForIsotropicMaterial", "GetUptGeneralProfileBoundaryPoints",
        "GetUptGeneralProfilePointsCount", "GetUptGeneralStressLocationPoints",
        "GetUserProvidedTableCount", "GetUserProvidedTableList",
        "GetUserProvidedTableNo", "GetUserProvidedTableSectionCount",
        "GetUserProvidedTableSectionList",
        "GetUserProvidedTableSectionProperties",
        "GetUserProvidedTableSectionPropertyCount",
        "GetUserProvidedTableSectionType", "IsStandardDatabaseSection",
        "RemoveAllElementNodeReleaseSpec", "RemoveAllElementOffsetSpec",
        "RemoveAttribute", "RemoveElementIgnoreInplaneRotnSpecFromPlate",
        "RemoveElementNodeReleaseSpecFromPlate",
        "RemoveElementPlaneStressSpecFromPlate", "RemoveMaterialFromBeam",
        "RemoveMaterialFromPlate", "RemoveMaterialFromSolid",
        "RemoveMemberCableSpecFromBeam", "RemoveMemberCompressionSpecFromBeam",
        "RemoveMemberFireProofingSpecFromBeam",
        "RemoveMemberIgnoreStiffSpecFromBeam",
        "RemoveMemberInactiveSpecFromBeam", "RemoveMemberOffsetSpecFromBeam",
        "RemoveMemberReleaseSpecFromBeam", "RemoveMemberTensionSpecFromBeam",
        "RemoveMemberTrussSpecFromBeam", "RemovePropertyFromBeam",
        "RemovePropertyFromPlate", "RemovePropertyFromUPTTable",
        "RemoveUPTTable", "SetMaterialName", "SetPropertyUniqueID",
        # SetStandardProfileDBFolder intentionally excluded (DENIED_METHODS).
        "SetTypeToIsotropicMaterial", "UpdatePropertiesToDesignSection",
    }),
    "Support": frozenset({
        "AssignSupportToEntityList", "AssignSupportToNode",
        "CreateElasticFooting", "CreateElasticMat", "CreateInclinedSupport",
        "CreatePlateMat", "CreateSupportFixed", "CreateSupportFixedBut",
        "CreateSupportPinned", "DeleteSupport", "GetCountOfElasticFooting",
        "GetCountOfElasticMat", "GetCountOfPlateMat",
        "GetElasticFootingAssignmentList", "GetElasticFootingDetail",
        "GetElasticMatAssignmentList", "GetElasticMatDetail",
        "GetPlateMatAssignmentList", "GetPlateMatDetail", "GetPlateMatSupportId",
        "GetSupportCount", "GetSupportInformation", "GetSupportInformationEx",
        "GetSupportName", "GetSupportNodes", "GetSupportType",
        "GetSupportUniqueID", "RemoveElasticFooting",
        "RemoveElasticFootingFromNode", "RemoveElasticMat",
        "RemoveElasticMatFromNode", "RemovePlateMat", "RemovePlateMatFromPlate",
        "RemoveSupportFromNode", "SetSupportUniqueID",
    }),
    "Load": frozenset({
        "AddAutoCombinationRepeat", "AddAutoLoadCombinations",
        "AddDirectAnalysisDefinitionParameter", "AddElementHydrostaticPressure",
        "AddElementPressure", "AddElementTrapPressureEx",
        "AddLoadAndFactorToCombination", "AddLoadCasesToEnvelop",
        "AddMemberAreaLoad", "AddMemberConcForce", "AddMemberConcMoment",
        "AddMemberFixedEnd", "AddMemberFloorLoad", "AddMemberFloorLoadEx",
        "AddMemberLinearVari", "AddMemberTrapezoidal", "AddMemberUniformForce",
        "AddMemberUniformMoment", "AddNodalLoad", "AddNotionalLoad",
        "AddReferenceLoad", "AddRepeatLoad", "AddResponseSpectrumLoad",
        "AddSeismicDefElementWeight", "AddSeismicDefFloorWeight",
        "AddSeismicDefJointWeight", "AddSeismicDefMemberWeight",
        "AddSeismicDefSelfWeight", "AddSeismicDefWallArea",
        "AddSeismicDefinition", "AddSeismicLoad", "AddSelfWeightInXYZ",
        "AddSelfWeightInXYZToGeometry", "AddStrainLoad",
        "AddSupportDisplacement", "AddTemperatureLoad", "AddWindDefinition",
        "AddWindDefinitionASCE7Parameters", "AddWindExposure",
        "AddWindIntensity", "AddWindLoad", "BeginLoadMerging",
        "ClearPrimaryLoadCase", "ClearReferenceLoadCase",
        "ComputeWallWindPressureProfile",
        "ComputeWallWindPressureProfileASCE72016", "CreateLoadEnvelop",
        "CreateLoadList", "CreateNewLoadCombination", "CreateNewPrimaryLoad",
        "CreateNewPrimaryLoadEx", "CreateNewPrimaryLoadEx2",
        "CreateNewReferenceLoad", "DeleteDirectAnalysisDefinition",
        "DeleteDirectAnalysisDefinitionParameter", "DeleteLoadEnvelop",
        "DeleteLoadList", "DeletePrimaryLoadCases", "DeleteReferenceLoadCases",
        "DeleteWindDefinition", "EndLoadMerging", "GetActiveLoad",
        "GetAssignmentListForLoadType", "GetAttribute", "GetBeamCountAtFloor",
        "GetConcForceCount", "GetConcForces", "GetConcMomentCount",
        "GetConcMoments", "GetElementConcLoadCount", "GetElementConcLoads",
        "GetElementLoadInfo", "GetElementPressureLoadCount",
        "GetElementPressureLoads", "GetEnvelopeCount", "GetEnvelopeIDs",
        "GetInfluenceArea", "GetLinearVaryingLoadCount",
        "GetLinearVaryingLoads", "GetListSizeForLoadType",
        "GetLoadAndFactorForCombination", "GetLoadCaseTitle",
        "GetLoadCombinationCaseCount", "GetLoadCombinationCaseNumbers",
        "GetLoadCountInLoadList", "GetLoadEnvelopeDetails", "GetLoadItemType",
        "GetLoadItemsCount", "GetLoadListCount", "GetLoadListfromLoadEnvelope",
        "GetLoadType", "GetLoadTypeCount", "GetLoadsInLoadList",
        "GetMemberLoadInfo", "GetNoLoadFactorDirectionInNotionalLoad",
        "GetNoLoadFactorInRepeatLoad", "GetNoOfLoadAndFactorPairsForCombination",
        "GetNoOfSetsInReferenceLoad", "GetNodalLoadCount", "GetNodalLoadInfo",
        "GetNodalLoads", "GetNotionalLoadByIndex", "GetNotionalLoadCount",
        "GetPrimaryLoadCaseCount", "GetPrimaryLoadCaseNumbers",
        "GetReferenceLoadByIndex", "GetReferenceLoadCaseCount",
        "GetReferenceLoadCaseNumbers", "GetReferenceLoadCaseTitle",
        "GetReferenceLoadCount", "GetReferenceLoadType",
        "GetRepeatLoadByIndex", "GetRepeatLoadCount", "GetTrapLoadCount",
        "GetTrapLoads", "GetUDLLoadCount", "GetUDLLoads", "GetUNIMomentCount",
        "GetUNIMoments", "IsCombinationCase", "IsDynamicLoadIncluded",
        "MergeLoadsOnBeam", "ModifySeismicDefinitionParams", "RemoveAttribute",
        "RemoveLoadCasesFromEnvelop", "SetASDLoadAttribute",
        "SetLSDLoadAttribute", "SetLoadActive", "SetLoadType",
        "SetReferenceLoadActive", "SplitLoadsOnBeam",
    }),
    "Command": frozenset({
        "CreateSteelDesignCommand", "DeleteAllAnalysisCommands",
        "DeleteCheckIrregularitiesCommand", "DeleteCheckSoftStoryCommand",
        "DeleteFloorDiaphragmBaseCommand", "PerformAnalysis",
        "PerformBucklingAnalysis", "PerformBucklingAnalysisEx",
        "PerformCableAnalysis", "PerformCableAnalysisEx",
        "PerformDirectAnalysis", "PerformNonlinearAnalysisEx",
        "PerformPDeltaAnalysisEx", "PerformPDeltaAnalysisNoConverge",
        "SetCheckIrregularitiesCommand", "SetCheckSoftStoryCommand",
        "SetFloorDiaphragmBaseCommand",
    }),
    "Output": frozenset({
        "AreResultsAvailable", "GetAllPlateCenterForces",
        "GetAllPlateCenterMoments",
        "GetAllPlateCenterPrincipalStressesAndAngles",
        "GetAllPlateCenterPrincipalStressesAndAnglesEx",
        "GetAllPlateCenterStressesAndMoments", "GetAllSolidNormalStresses",
        "GetAllSolidPrincipalStresses", "GetAllSolidShearStresses",
        "GetAllSolidVonMisesStresses", "GetBasePressures",
        "GetBucklingFactor", "GetBucklingModeDisplacementAtNode",
        "GetIntermediateDeflectionAtDistance",
        "GetIntermediateMemberAbsTransDisplacements",
        "GetIntermediateMemberForcesAtDistance",
        "GetIntermediateMemberTransDisplacements", "GetMatInfluenceAreas",
        "GetMaxBeamStresses", "GetMaxSectionDisplacement",
        "GetMemberDesignSectionName", "GetMemberEndDisplacements",
        "GetMemberEndForces", "GetMemberSteelDesignMaxFailureRatio",
        "GetMemberSteelDesignMinFailureRatio", "GetMemberSteelDesignRatio",
        "GetMemberSteelDesignResults", "GetMinMaxAxialForce",
        "GetMinMaxBendingMoment", "GetMinMaxShearForce",
        "GetModalDisplacementAtNode", "GetModalMassParticipationFactors",
        "GetModeFrequency", "GetMultipleMemberSteelDesignMaxRatio",
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
        "GetResultantForceAlongLineForPlateList", "GetStaticCheckResult",
        "GetSteelDesignParameterBlockCount",
        "GetSteelDesignParameterBlockNameByIndex", "GetSupportReactions",
        "GetTimeHistoryIntegrationStepInfo", "GetTimeHistoryResponse",
        "GetTimeHistoryResponseAtTime", "GetTimeHistoryResponseMinMax",
        "IsBucklingAnalysisResultsAvailable",
        "IsMultipleMemberSteelDesignResultsAvailable",
    }),
    "Design": frozenset({
        "AssignDesignCommand", "AssignDesignGroup", "AssignDesignParameter",
        "CreateDesignBrief", "GetDesignBriefCode", "GetMemberDesignParameters",
    }),
    "Table": frozenset({
        "AddTable", "CreateReport", "DeleteReport", "DeleteTable",
        "GetCellValue", "GetReportCount", "GetTableCount", "RenameTable",
        "ResizeTable", "SaveReport", "SaveReportAll", "SaveTable",
        "SetCellTextBold", "SetCellTextColor", "SetCellTextHorzAlignment",
        "SetCellTextItalic", "SetCellTextSize", "SetCellTextSizeAll",
        "SetCellTextUnderline", "SetCellTextVertAlignment", "SetCellValue",
        "SetColumnHeader", "SetColumnUnitString", "SetRowHeader",
    }),
    "View": frozenset({
        "CloseActiveWindow", "CopyPicture", "CreateNewViewForSelections",
        "CreateNewViewForSelectionsEx", "DetachView", "ExportView",
        "GetApplicationDesktopSize", "GetBeamsInView", "GetInterfaceMode",
        "GetNoOfBeamsInView", "GetScaleCount", "GetScaleValueByType",
        "GetScaleValues", "GetWindowCount", "GetWindowTitle",
        "HideAllMembers", "HideEntity", "HideMember", "HideMembers",
        "HidePlate", "HideSolid", "HideSurface", "OpenView", "RefreshView",
        "RenameView", "RotateDown", "RotateLeft", "RotateRight", "RotateUp",
        "SaveView", "SelectByItemList", "SelectByMissingAttribute",
        "SelectEntitiesConnectedToMember", "SelectEntitiesConnectedToNode",
        "SelectEntitiesConnectedToPlate", "SelectEntitiesConnectedToSolid",
        "SelectGroup", "SelectInverse", "SelectMembersParallelTo",
        "SetActiveWindow", "SetBeamAnnotationMode", "SetDesignResults",
        "SetDiagramMode", "SetInterfaceMode", "SetLabel", "SetModeSectionPage",
        "SetNodeAnnotationMode", "SetReactionAnnotationMode",
        "SetScaleValueByType", "SetScaleValues", "SetSectionView", "SetUnits",
        "SetWindowPosition", "ShowAllMembers", "ShowBack", "ShowBottom",
        "ShowFront", "ShowIsometric", "ShowLeft", "ShowMember", "ShowMembers",
        "ShowPlan", "ShowRight", "SpinLeft", "SpinRight", "ZoomAll",
        "ZoomExtentsMainView",
    }),
}

# ---------------------------------------------------------------------------
# Executor limits
# ---------------------------------------------------------------------------

#: Wall-clock timeout for a single ``execute_code`` call (seconds).
EXECUTION_TIMEOUT_SECONDS: Final[float] = 30.0

#: Maximum WASM linear memory (in WASM pages of 64 KiB each).
#: 128 MiB = 2048 pages. Enforced by the Extism manifest.
#: Sized to accommodate file-I/O compound tools: __input (up to 100K rows,
#: ~30 MB) + return value (up to 100K rows, ~30 MB) + QuickJS engine (~10 MB).
WASM_MAX_MEMORY_PAGES: Final[int] = 2048

#: Maximum captured stdout/stderr size in bytes. Further output is silently
#: dropped to keep agents running rather than hard-failing mid-script.
MAX_STDOUT_BYTES: Final[int] = 256 * 1024  # 256 KiB

#: Maximum size of the user JavaScript source accepted by ``execute_code``.
#: A generous upper bound; larger scripts should live in a skill file.
MAX_CODE_BYTES: Final[int] = 256 * 1024  # 256 KiB
