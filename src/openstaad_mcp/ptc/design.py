"""Read-only design queries over Bentley openstaadpy."""

import math
from typing import Any

from openstaad_mcp.ptc.base import Ids, QueryBase, values_record


class DesignTools(QueryBase):
    def get_member_results(self, member_ids: Ids | None = None) -> list[dict[str, Any]]:
        """Return details from each member's LAST steel design parameter block.

        Fields: member_id, design_code, status (raw API PASS/FAIL), ratio, allowable_ratio,
        critical_load_case, position, clause, section, forces {FX,MY,MZ}, slenderness.
        Position and critical forces use current BASE units. API failures (including
        not-designed members) fail the request; use get_utilization to identify unavailable IDs first.
        No status is inferred from ratio=1 or from a selected analysis case.
        """
        self._require_results()
        rows = []
        for mid in self._members(member_ids):
            code, status, ratio, allowable, case, position, clause, section, forces, slenderness = self._call(
                "Output", "GetMemberSteelDesignResults", mid
            )
            numbers = values_record(
                ("ratio", "allowable_ratio", "position", "slenderness"), (ratio, allowable, position, slenderness)
            )
            if numbers["ratio"] < 0 or numbers["allowable_ratio"] < 0:
                raise ValueError("Steel design details are unavailable; check get_utilization first")
            rows.append(
                {
                    "member_id": mid,
                    "design_code": code,
                    "status": status,
                    **numbers,
                    "critical_load_case": case,
                    "clause": clause,
                    "section": section,
                    "forces": values_record(("FX", "MY", "MZ"), forces),
                }
            )
        return rows

    def get_utilization(self, member_ids: Ids | None = None) -> list[dict[str, Any]]:
        """Return member_id, ratio, available and source_code for the LAST steel design parameter block.

        Ratio is dimensionless, NOT an analysis load-case result. Negative API
        sentinels become ratio=null and available=false, never passing ratios.
        This endpoint does not infer PASS/FAIL (the design allowable may differ).
        """
        self._require_results()
        rows = []
        for mid in self._members(member_ids):
            ratio = self._call("Output", "GetMemberSteelDesignRatio", mid)
            if not isinstance(ratio, (int, float)) or isinstance(ratio, bool) or not math.isfinite(ratio):
                raise ValueError("OpenSTAAD returned an invalid steel design ratio")
            available = ratio >= 0
            rows.append(
                {
                    "member_id": mid,
                    "ratio": ratio if available else None,
                    "available": available,
                    "source_code": None if available else ratio,
                }
            )
        return rows
