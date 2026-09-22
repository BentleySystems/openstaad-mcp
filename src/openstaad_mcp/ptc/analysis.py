"""Read-only analysis queries over Bentley openstaadpy."""

from typing import Annotated, Any, Literal

from pydantic import Field

from openstaad_mcp.ptc.base import Distances, Ids, QueryBase, _check_rows, values_record

Components = Annotated[list[Literal["FX", "FY", "FZ", "MY", "MZ"]], Field(min_length=1, max_length=5)]
Directions = Annotated[list[Literal["X", "Y", "Z"]], Field(min_length=1, max_length=3)]


class AnalysisTools(QueryBase):
    def get_member_forces_at_distance(
        self, member_ids: Ids, load_cases: Ids, distances: Distances
    ) -> list[dict[str, Any]]:
        """Return member_id, load_case, distance, local FX,FY,FZ,MX,MY,MZ at each distance.

        Distances are measured from the starting node in model base length units;
        every distance must fit every selected member. Values use native output
        force/moment units. No interpolation or cross-case envelope is computed.
        """
        _check_rows(len(member_ids) * len(load_cases) * len(distances))
        self._require_results()
        mids, cases, stations = map(lambda xs: list(dict.fromkeys(xs)), (member_ids, load_cases, distances))
        if not mids or not cases or not stations:
            return []
        for mid in mids:
            length = values_record(("length",), [self._call("Geometry", "GetBeamLength", mid)])["length"]
            if max(stations) > length:
                raise ValueError("A requested distance exceeds a selected member length")
        return [
            {
                "member_id": mid,
                "load_case": lc,
                "distance": distance,
                "coordinate_system": "local",
                **values_record(
                    ("FX", "FY", "FZ", "MX", "MY", "MZ"),
                    self._call("Output", "GetIntermediateMemberForcesAtDistance", mid, distance, lc),
                ),
            }
            for mid in mids
            for lc in cases
            for distance in stations
        ]

    def get_member_force_extrema(
        self, member_ids: Ids, load_cases: Ids, components: Components | None = None
    ) -> list[dict[str, Any]]:
        """Return per-member/per-case/per-component min, min_position, max, max_position (local).

        Default components FX,FY,FZ,MY,MZ; torsion MX is not supported by these APIs.
        Preserve signed extrema and positions along the member, not absolute-only
        values. Native API output units, no conversion; this is not a cross-case envelope.
        """
        components = ["FX", "FY", "FZ", "MY", "MZ"] if components is None else components
        _check_rows(len(member_ids) * len(load_cases) * len(components))
        self._require_results()
        methods = {
            "FX": "GetMinMaxAxialForce",
            "FY": "GetMinMaxShearForce",
            "FZ": "GetMinMaxShearForce",
            "MY": "GetMinMaxBendingMoment",
            "MZ": "GetMinMaxBendingMoment",
        }
        rows = []
        for mid in dict.fromkeys(member_ids):
            for lc in dict.fromkeys(load_cases):
                for component in dict.fromkeys(components):
                    args = (mid, lc) if component == "FX" else (mid, component, lc)
                    rows.append(
                        {
                            "member_id": mid,
                            "load_case": lc,
                            "component": component,
                            "coordinate_system": "local",
                            **values_record(
                                ("min", "min_position", "max", "max_position"),
                                self._call("Output", methods[component], *args),
                            ),
                        }
                    )
        return rows

    def get_max_section_displacements(
        self, member_ids: Ids, load_cases: Ids, directions: Directions | None = None
    ) -> list[dict[str, Any]]:
        """Return member_id, load_case, direction, displacement, position using GLOBAL X/Y/Z.

        Preserve the API's maximum and sign without taking abs(). Default all directions;
        native API units, no conversion. position is along the member from its start.
        """
        directions = ["X", "Y", "Z"] if directions is None else directions
        _check_rows(len(member_ids) * len(load_cases) * len(directions))
        self._require_results()
        return [
            {
                "member_id": mid,
                "load_case": lc,
                "direction": direction,
                "coordinate_system": "global",
                **values_record(
                    ("displacement", "position"), self._call("Output", "GetMaxSectionDisplacement", mid, direction, lc)
                ),
            }
            for mid in dict.fromkeys(member_ids)
            for lc in dict.fromkeys(load_cases)
            for direction in dict.fromkeys(directions)
        ]

    def get_plate_center_results(self, plate_ids: Ids, load_cases: Ids) -> list[dict[str, Any]]:
        """Return plate_id, load_case, SQX,SQY,MX,MY,MXY,SX,SY,SXY in plate-local axes.

        SQX/SQY and SX/SY/SXY are stresses; MX/MY/MXY are moments PER UNIT WIDTH,
        not beam moments. Native output units; no conversion. See STAAD plate sign conventions.
        """
        return self._plate_results(
            "GetAllPlateCenterStressesAndMoments",
            ("SQX", "SQY", "MX", "MY", "MXY", "SX", "SY", "SXY"),
            plate_ids,
            load_cases,
        )

    def get_plate_principal_stresses(self, plate_ids: Ids, load_cases: Ids) -> list[dict[str, Any]]:
        """Return plate_id, load_case, top_max, top_min, bottom_max, bottom_min at plate center.

        In-plane principal stresses on the local top/bottom surfaces; native stress units.
        """
        return self._plate_results(
            "GetPlateCenterNormalPrincipalStresses",
            ("top_max", "top_min", "bottom_max", "bottom_min"),
            plate_ids,
            load_cases,
        )

    def get_plate_von_mises_stresses(self, plate_ids: Ids, load_cases: Ids) -> list[dict[str, Any]]:
        """Return plate_id, load_case, top, bottom Von Mises stresses at plate center in native stress units."""
        return self._plate_results("GetPlateCenterVonMisesStresses", ("top", "bottom"), plate_ids, load_cases)

    def _plate_results(self, method: str, fields: tuple[str, ...], plate_ids: Ids, load_cases: Ids) -> list[dict]:
        _check_rows(len(plate_ids) * len(load_cases))
        self._require_results()
        return [
            {"plate_id": pid, "load_case": lc, **values_record(fields, self._call("Output", method, pid, lc))}
            for pid in dict.fromkeys(plate_ids)
            for lc in dict.fromkeys(load_cases)
        ]

    def are_results_available(self) -> bool:
        """Check whether analysis results exist; does not guarantee they reflect unsaved edits."""
        return bool(self._call("Output", "AreResultsAvailable"))

    def get_units(self) -> dict[str, str]:
        """Return output units for force, moment, displacement, stress, dimension and rotation."""
        self._require_results()
        return {
            name.lower(): self._call("Output", f"GetOutputUnitFor{name}")
            for name in ("Force", "Moment", "Displacement", "Stress", "Dimension", "Rotation")
        }

    def get_member_forces(
        self,
        member_ids: Ids,
        load_cases: Ids,
        ends: Annotated[list[Annotated[int, Field(strict=True, ge=0, le=1)]], Field(min_length=1, max_length=2)]
        | None = None,
        coordinate_system: Literal["local", "global"] = "local",
    ) -> list[dict[str, Any]]:
        """Return member_id, load_case, end, coordinate_system and FX,FY,FZ,MX,MY,MZ.

        End 0=start, 1=end. Force and moment use get_units(); no design ratio is
        computed from these forces. At most 100000 rows per call.
        """
        self._require_results()
        ends = [0, 1] if ends is None else ends
        _check_rows(len(member_ids) * len(load_cases) * len(ends))
        return [
            {
                "member_id": mid,
                "load_case": lc,
                "end": end,
                "coordinate_system": coordinate_system,
                **dict(
                    zip(
                        ("FX", "FY", "FZ", "MX", "MY", "MZ"),
                        self._call("Output", "GetMemberEndForces", mid, end, lc, int(coordinate_system == "global")),
                        strict=True,
                    )
                ),
            }
            for mid in dict.fromkeys(member_ids)
            for lc in dict.fromkeys(load_cases)
            for end in dict.fromkeys(ends)
        ]

    def _node_results(self, method: str, names: tuple[str, ...], node_ids: Ids, load_cases: Ids) -> list[dict]:
        self._require_results()
        _check_rows(len(node_ids) * len(load_cases))
        return [
            {"node_id": nid, "load_case": lc, **dict(zip(names, self._call("Output", method, nid, lc), strict=True))}
            for nid in dict.fromkeys(node_ids)
            for lc in dict.fromkeys(load_cases)
        ]

    def get_node_displacements(self, node_ids: Ids, load_cases: Ids) -> list[dict[str, Any]]:
        """Return node_id, load_case, UX,UY,UZ,RX,RY,RZ (global); see get_units()."""
        return self._node_results("GetNodeDisplacements", ("UX", "UY", "UZ", "RX", "RY", "RZ"), node_ids, load_cases)

    def get_support_reactions(self, node_ids: Ids, load_cases: Ids) -> list[dict[str, Any]]:
        """Return node_id, load_case, FX,FY,FZ,MX,MY,MZ (global); see get_units()."""
        return self._node_results("GetSupportReactions", ("FX", "FY", "FZ", "MX", "MY", "MZ"), node_ids, load_cases)
