"""Read-only loads queries over Bentley openstaadpy."""

from typing import Any

from openstaad_mcp.ptc.base import Ids, QueryBase, _check_rows, id_list, values_record


class LoadTools(QueryBase):
    def get_combinations(self, combination_ids: Ids | None = None) -> list[dict[str, Any]]:
        """Return id, title, terms [{load_case, factor}], trailing_factor.

        Bentley allocates one extra factor slot. Preserve it as trailing_factor:
        for SRSS it is the overall multiplier; its presence alone does NOT identify SRSS.
        No active-load selection is changed and nested combinations are not expanded.
        """
        rows = []
        total = 0
        for cid in self._ids(combination_ids, "Load", "GetLoadCombinationCaseNumbers"):
            raw_ids, raw_factors = self._call("Load", "GetLoadAndFactorForCombination", cid)
            ids = id_list(raw_ids)
            factors = list(raw_factors)
            if len(factors) not in (len(ids), len(ids) + 1):
                raise ValueError("Invalid combination factor array returned by OpenSTAAD")
            total += len(ids)
            _check_rows(total)
            numeric = list(values_record(tuple(str(i) for i in range(len(factors))), factors).values())
            rows.append(
                {
                    "id": cid,
                    "title": self._call("Load", "GetLoadCaseTitle", cid),
                    "terms": [
                        {"load_case": lc, "factor": factor} for lc, factor in zip(ids, numeric[: len(ids)], strict=True)
                    ],
                    "trailing_factor": numeric[-1] if len(numeric) > len(ids) else None,
                }
            )
        return rows

    def get_reference_load_cases(self) -> list[dict[str, Any]]:
        """Return reference-load {id, title, load_type}; these definitions are not analysis result cases."""
        return [
            {
                "id": rid,
                "title": self._call("Load", "GetReferenceLoadCaseTitle", rid),
                "load_type": self._call("Load", "GetReferenceLoadType", rid),
            }
            for rid in self._ids(None, "Load", "GetReferenceLoadCaseNumbers")
        ]

    def get_load_cases(self, include_combinations: bool = True) -> list[dict[str, Any]]:
        """Return {id, title, is_combination} for primary cases and optionally load combinations."""
        cases = self._ids(None, "Load", "GetPrimaryLoadCaseNumbers")
        combinations = []
        if include_combinations:
            combinations = self._ids(None, "Load", "GetLoadCombinationCaseNumbers")
        return [
            {"id": lc, "title": self._call("Load", "GetLoadCaseTitle", lc), "is_combination": combined}
            for numbers, combined in ((cases, False), (combinations, True))
            for lc in numbers
        ]
