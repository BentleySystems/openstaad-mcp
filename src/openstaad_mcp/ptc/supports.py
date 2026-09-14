"""Read-only supports queries over Bentley openstaadpy."""

from typing import Any

from openstaad_mcp.ptc.base import Ids, QueryBase


class SupportTools(QueryBase):
    def get_supports(self, node_ids: Ids | None = None) -> list[dict[str, Any]]:
        """Return {node_id, type, releases, springs}; DOF order FX,FY,FZ,MX,MY,MZ.

        Releases: 0=fixed, 1=released, -1=spring. None selects supported nodes.
        """
        rows = []
        for nid in self._ids(node_ids, "Support", "GetSupportNodes"):
            kind, releases, springs = self._call("Support", "GetSupportInformation", nid)
            rows.append({"node_id": nid, "type": kind, "releases": releases, "springs": springs})
        return rows
