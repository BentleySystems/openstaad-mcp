"""Strict fake of the pinned wrapper; no COM or STAAD writes."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def staad():
    coordinates = {1: (0, 0, 0), 2: (4, 0, 0), 3: (4, 3, 0), 4: (4, 3, 2)}
    incidence = {10: (1, 2), 30: (2, 3), 50: (3, 4), 90: (1, 1)}
    output = SimpleNamespace(
        AreResultsAvailable=Mock(return_value=True),
        GetMemberEndForces=Mock(side_effect=lambda mid, end, lc, system: [mid, end, lc, system, 5, 6]),
        GetNodeDisplacements=Mock(return_value=[1, 2, 3, 4, 5, 6]),
        GetSupportReactions=Mock(return_value=[6, 5, 4, 3, 2, 1]),
        GetMemberSteelDesignRatio=Mock(side_effect=lambda mid: {10: 1.1, 30: 0.7, 50: -999, 90: -1}[mid]),
    )
    for field, unit in zip(
        ("Force", "Moment", "Displacement", "Stress", "Dimension", "Rotation"),
        ("kN", "kN-m", "m", "kN/m2", "m", "rad"),
        strict=True,
    ):
        setattr(output, f"GetOutputUnitFor{field}", Mock(return_value=unit))
    return SimpleNamespace(
        GetBaseUnit=Mock(return_value="Metric"),
        Geometry=SimpleNamespace(
            GetNodeCount=Mock(return_value=4),
            GetMemberCount=Mock(return_value=4),
            GetNodeList=Mock(return_value=tuple(coordinates)),
            GetBeamList=Mock(return_value=tuple(incidence)),
            GetNodeCoordinates=Mock(side_effect=coordinates.__getitem__),
            GetMemberIncidence=Mock(side_effect=incidence.__getitem__),
        ),
        Property=SimpleNamespace(
            GetBeamProperty=Mock(return_value=(1, 2, 3, 4, 5, 6, 7, 8)),
            GetBeamSectionName=Mock(return_value="W12"),
            GetBeamMaterialName=Mock(return_value="STEEL"),
        ),
        Load=SimpleNamespace(
            GetPrimaryLoadCaseNumbers=Mock(return_value=(201, 203)),
            GetLoadCombinationCaseNumbers=Mock(return_value=(301,)),
            GetLoadCaseTitle=Mock(side_effect=lambda lc: f"Load {lc}"),
        ),
        Support=SimpleNamespace(
            GetSupportNodes=Mock(return_value=(1,)),
            GetSupportInformation=Mock(return_value=(1, [0] * 6, [0.0] * 6)),
        ),
        Output=output,
    )
