"""Read-only geometry queries over Bentley openstaadpy."""

import math
from typing import Any, Literal

from openstaad_mcp.ptc.base import Ids, QueryBase, Tolerance, _check_rows, id_list


class GeometryTools(QueryBase):
    def get_plates(self, plate_ids: Ids | None = None) -> list[dict[str, Any]]:
        """Return {id, node_ids, node_count}; preserve A/B/C/D order, omit the triangle D=0 sentinel."""
        rows = []
        for pid in self._ids(plate_ids, "Geometry", "GetPlateList"):
            a, b, c, d = self._call("Geometry", "GetPlateIncidence", pid)
            nodes = id_list([a, b, c] if d == 0 else [a, b, c, d])
            rows.append({"id": pid, "node_ids": nodes, "node_count": len(nodes)})
        return rows

    def get_solids(self, solid_ids: Ids | None = None) -> list[dict[str, Any]]:
        """Return {id, node_slots}; all eight A..H slots, including zero/repeated slots, are preserved."""
        rows = []
        for sid in self._ids(solid_ids, "Geometry", "GetSolidList"):
            slots = list(self._call("Geometry", "GetSolidIncidence", sid))
            if len(slots) != 8 or any(type(n) is not int or n < 0 for n in slots):
                raise ValueError("Invalid solid incidence returned by OpenSTAAD")
            rows.append({"id": sid, "node_slots": slots})
        return rows

    def get_groups(
        self, entity_type: Literal["nodes", "members", "plates", "solids", "geometry", "floor"] = "members"
    ) -> list[dict[str, Any]]:
        """Return {name, entity_type, entity_ids}; geometry groups contain mixed element types."""
        code = {"nodes": 1, "members": 2, "plates": 3, "solids": 4, "geometry": 5, "floor": 6}[entity_type]
        names = list(self._call("Geometry", "GetGroupNames", code))
        _check_rows(len(names))
        rows = []
        count = 0
        for name in names:
            ids = id_list(self._call("Geometry", "GetGroupEntities", name))
            count += len(ids)
            _check_rows(count)
            rows.append({"name": name, "entity_type": entity_type, "entity_ids": ids})
        return rows

    def get_connected_members(self, node_ids: Ids) -> list[dict[str, Any]]:
        """Return {node_id, member_ids} for each requested node; isolated nodes have an empty list."""
        rows = []
        count = 0
        for nid in dict.fromkeys(node_ids):
            ids = id_list(self._call("Geometry", "GetBeamsConnectedAtNode", nid))
            count += len(ids)
            _check_rows(count)
            rows.append({"node_id": nid, "member_ids": ids})
        return rows

    def get_node_count(self) -> int:
        """Return the model node count."""
        return self._call("Geometry", "GetNodeCount")

    def get_base_units(self) -> dict[str, str]:
        """Return geometry/property base units: Metric=m,kN; English=in,kip. No conversion is applied."""
        system = self._call(None, "GetBaseUnit")
        units = {"Metric": ("m", "kN"), "English": ("in", "kip")}
        if system not in units:
            raise ValueError("OpenSTAAD returned an unknown base unit system")
        length, force = units[system]
        return {"system": system, "length": length, "force": force}

    def get_member_count(self) -> int:
        """Return the analytical beam/member count (not plates or solids)."""
        return self._call("Geometry", "GetMemberCount")

    def get_nodes(self, node_ids: Ids | None = None) -> list[dict[str, Any]]:
        """Return {id, x, y, z} records in model base length units. None selects all; [] selects none."""
        return [
            {"id": nid, **dict(zip(("x", "y", "z"), self._call("Geometry", "GetNodeCoordinates", nid), strict=True))}
            for nid in self._ids(node_ids, "Geometry", "GetNodeList")
        ]

    def get_members(
        self,
        member_ids: Ids | None = None,
        up_axis: Literal["Y", "Z"] = "Y",
        tolerance: Tolerance = 1e-6,
    ) -> list[dict[str, Any]]:
        """Return {id, start_node, end_node, dx, dy, dz, length, is_horizontal} in base units.

        Set up_axis='Z' for a SET Z UP model. tolerance is an absolute length;
        zero-length members are never horizontal. None selects all; [] none.
        """
        rows = []
        coordinates: dict[int, Any] = {}
        for mid in self._members(member_ids):
            start, end = self._call("Geometry", "GetMemberIncidence", mid)
            for nid in (start, end):
                if nid not in coordinates:
                    coordinates[nid] = self._call("Geometry", "GetNodeCoordinates", nid)
            delta = [b - a for a, b in zip(coordinates[start], coordinates[end], strict=True)]
            dx, dy, dz = delta
            length = math.hypot(dx, dy, dz)
            vertical = {"Y": dy, "Z": dz}[up_axis]
            rows.append(
                {
                    "id": mid,
                    "start_node": start,
                    "end_node": end,
                    "dx": dx,
                    "dy": dy,
                    "dz": dz,
                    "length": length,
                    "is_horizontal": length > tolerance and abs(vertical) <= tolerance,
                }
            )
        return rows
