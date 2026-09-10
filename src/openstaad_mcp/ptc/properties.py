"""Read-only properties queries over Bentley openstaadpy."""

from typing import Any

from openstaad_mcp.ptc.base import Ends, Ids, Names, QueryBase, id_list, values_record


class PropertyTools(QueryBase):
    def get_member_properties_full(self, member_ids: Ids | None = None) -> list[dict[str, Any]]:
        """Return id, section, material and GetBeamPropertyAll's ten fields in base units.

        Fields: width, depth, AX, AY, AZ, IZ, IY, IX, flange_thickness, web_thickness.
        This is the fixed ten-field API, not type-dependent 24-slot section data.
        """
        rows = []
        for mid in self._members(member_ids):
            rows.append(
                {
                    "id": mid,
                    "section": self._call("Property", "GetBeamSectionName", mid),
                    "material": self._call("Property", "GetBeamMaterialName", mid),
                    **values_record(
                        ("width", "depth", "AX", "AY", "AZ", "IZ", "IY", "IX", "flange_thickness", "web_thickness"),
                        self._call("Property", "GetBeamPropertyAll", mid),
                    ),
                }
            )
        return rows

    def get_plate_properties(self, plate_ids: Ids | None = None) -> list[dict[str, Any]]:
        """Return id, material and corners [{node_id, thickness}] in A/B/C/D order and base length units.

        Triangle fourth slots are validated but omitted from corners.
        """
        rows = []
        for pid in self._ids(plate_ids, "Geometry", "GetPlateList"):
            a, b, c, d = self._call("Geometry", "GetPlateIncidence", pid)
            nodes = id_list([a, b, c] if d == 0 else [a, b, c, d])
            thickness = values_record(("A", "B", "C", "D"), self._call("Property", "GetPlateThickness", pid))
            rows.append(
                {
                    "id": pid,
                    "material": self._call("Property", "GetPlateMaterialName", pid),
                    "corners": [
                        {"node_id": nid, "thickness": value}
                        for nid, value in zip(nodes, list(thickness.values())[: len(nodes)], strict=True)
                    ],
                }
            )
        return rows

    def get_material_properties(self, material_names: Names) -> list[dict[str, Any]]:
        """Return name, elasticity, poisson_ratio, density, thermal_expansion, damping_ratio.

        Native base-unit values; density is STAAD material weight density, not kg/m3.
        Thermal expansion follows the model's temperature convention. Names are case-sensitive.
        """
        return [
            {
                "name": name,
                **values_record(
                    ("elasticity", "poisson_ratio", "density", "thermal_expansion", "damping_ratio"),
                    self._call("Property", "GetMaterialProperty", name),
                ),
            }
            for name in dict.fromkeys(material_names)
        ]

    def get_member_releases(self, member_ids: Ids, ends: Ends | None = None) -> list[dict[str, Any]]:
        """Return member_id, end, release_codes, spring_constants, mp_factor, mp_factors.

        First two records use local FX,FY,FZ,MX,MY,MZ; mp_factors use MX,MY,MZ.
        Codes: 0=no release/spring, 1=released, -1=spring, -3=MP, -2=MPX/MPY/MPZ.
        Spring values use native base units; partial moment factors are dimensionless.
        None selects both ends (0=start, 1=end). No missing-release defaults are invented.
        """
        rows = []
        for mid in dict.fromkeys(member_ids):
            for end in dict.fromkeys([0, 1] if ends is None else ends):
                codes, springs, mp, factors = self._call("Property", "GetMemberReleaseSpecEx", mid, end)
                rows.append(
                    {
                        "member_id": mid,
                        "end": end,
                        "release_codes": values_record(("FX", "FY", "FZ", "MX", "MY", "MZ"), codes),
                        "spring_constants": values_record(("FX", "FY", "FZ", "MX", "MY", "MZ"), springs),
                        "mp_factor": values_record(("value",), [mp])["value"],
                        "mp_factors": values_record(("MX", "MY", "MZ"), factors),
                    }
                )
        return rows

    def get_member_properties(self, member_ids: Ids | None = None) -> list[dict[str, Any]]:
        """Return id, section, material, width, depth, AX, AY, AZ, IZ, IY, IX in base units.

        Areas use squared length; inertias/torsional constant use fourth power.
        """
        rows = []
        for mid in self._members(member_ids):
            properties = self._call("Property", "GetBeamProperty", mid)
            rows.append(
                {
                    "id": mid,
                    "section": self._call("Property", "GetBeamSectionName", mid),
                    "material": self._call("Property", "GetBeamMaterialName", mid),
                    **dict(zip(("width", "depth", "AX", "AY", "AZ", "IZ", "IY", "IX"), properties, strict=True)),
                }
            )
        return rows
