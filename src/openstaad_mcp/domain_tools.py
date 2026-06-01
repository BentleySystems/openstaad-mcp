"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Named domain tools for common structural engineering queries.

Each public ``fetch_*`` function takes a raw OpenSTAAD COM object (or a
duck-typed mock) and returns a JSON-serialisable dict.  These functions are
pure data-extractors — they perform no mutation and require only that analysis
results already exist (checked via ``AreResultsAvailable``).

The response envelope mirrors the PR 1 contract on ``execute_code``:
  - A human-readable summary header (units, counts)
  - A detail array capped at ``_MAX_ITEMS`` before serialisation
  - A pre-cap ``result_count`` so the LLM can report the true total

For ``fetch_design_summary``, **failures are never dropped** when the detail
list is truncated.  Passing members fill any remaining capacity.  This follows
the hallucination-prevention rule in the design guide: silently suppressing a
failing member is a safety regression, not a token saving.
"""

from __future__ import annotations

from typing import Any

# Matches MAX_RESULT_ITEMS in sandbox/const.py so the payload cap is
# consistent across execute_code results and domain tool results.
_MAX_ITEMS = 200


# ── helpers ──────────────────────────────────────────────────────────


def _as_list(value: Any) -> list:
    """Convert a COM tuple or list result to a plain Python list."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _round_forces(raw: Any) -> dict[str, float]:
    """Map a 6-element force/moment vector to a labelled dict."""
    v = _as_list(raw)
    if len(v) < 6:
        v = v + [0.0] * (6 - len(v))
    return {
        "FX": round(float(v[0]), 6),
        "FY": round(float(v[1]), 6),
        "FZ": round(float(v[2]), 6),
        "MX": round(float(v[3]), 6),
        "MY": round(float(v[4]), 6),
        "MZ": round(float(v[5]), 6),
    }


# ── public fetch functions ────────────────────────────────────────────


def fetch_model_summary(staad: Any) -> dict[str, Any]:
    """Return geometry counts, units, and file info for the open model."""
    geo = staad.Geometry
    return {
        "model_path": staad.GetSTAADFile(),
        "staad_version": staad.GetApplicationVersion(),
        "units": staad.GetBaseUnit(),
        "axis_up": "Z" if geo.IsZUp() else "Y",
        "node_count": geo.GetNodeCount(),
        "beam_count": geo.GetMemberCount(),
        "plate_count": geo.GetPlateCount(),
        "solid_count": geo.GetSolidCount(),
    }


def fetch_member_forces(
    staad: Any,
    member_ids: list[int] | None = None,
    load_cases: list[int] | None = None,
) -> dict[str, Any]:
    """Return end-forces for each member × load-case combination.

    Parameters
    ----------
    member_ids:
        Beam IDs to query.  Defaults to all beams in the model.
    load_cases:
        Primary load case numbers to query.  Defaults to all cases.
    """
    out = staad.Output
    load = staad.Load
    geo = staad.Geometry

    if not out.AreResultsAvailable():
        return {"error": "Results not available. Run analysis first (see run_analysis tool)."}

    all_beams = member_ids if member_ids is not None else _as_list(geo.GetBeamList())
    all_lcs = load_cases if load_cases is not None else _as_list(load.GetPrimaryLoadCaseNumbers())

    try:
        force_unit = out.GetOutputUnitForForce()
        moment_unit = out.GetOutputUnitForMoment()
    except Exception:
        force_unit = "unknown"
        moment_unit = "unknown"

    # Compute true total BEFORE the cap — this is the pre-truncation count.
    result_count = len(all_beams) * len(all_lcs)
    items: list[dict[str, Any]] = []

    for bid in all_beams:
        if len(items) >= _MAX_ITEMS:
            break
        for lc in all_lcs:
            if len(items) >= _MAX_ITEMS:
                break
            try:
                start_raw = out.GetMemberEndForces(bid, 0, lc, 0)
                end_raw = out.GetMemberEndForces(bid, 1, lc, 0)
                items.append({
                    "member_id": int(bid),
                    "load_case": int(lc),
                    "start": _round_forces(start_raw),
                    "end": _round_forces(end_raw),
                })
            except Exception as exc:
                items.append({
                    "member_id": int(bid),
                    "load_case": int(lc),
                    "error": str(exc),
                })

    return {
        "force_unit": force_unit,
        "moment_unit": moment_unit,
        "member_count": len(all_beams),
        "load_case_count": len(all_lcs),
        "result_count": result_count,
        "showing": len(items),
        "truncated": len(items) < result_count,
        "forces": items,
    }


def fetch_support_reactions(
    staad: Any,
    node_ids: list[int] | None = None,
    load_cases: list[int] | None = None,
) -> dict[str, Any]:
    """Return support reactions for each support node × load-case combination.

    Parameters
    ----------
    node_ids:
        Support node IDs to query.  Defaults to all supported nodes.
    load_cases:
        Primary load case numbers to query.  Defaults to all cases.
    """
    out = staad.Output
    load = staad.Load
    sup = staad.Support

    if not out.AreResultsAvailable():
        return {"error": "Results not available. Run analysis first (see run_analysis tool)."}

    support_nodes = node_ids if node_ids is not None else _as_list(sup.GetSupportNodes())
    all_lcs = load_cases if load_cases is not None else _as_list(load.GetPrimaryLoadCaseNumbers())

    try:
        force_unit = out.GetOutputUnitForForce()
        moment_unit = out.GetOutputUnitForMoment()
    except Exception:
        force_unit = "unknown"
        moment_unit = "unknown"

    result_count = len(support_nodes) * len(all_lcs)
    items: list[dict[str, Any]] = []

    for nid in support_nodes:
        if len(items) >= _MAX_ITEMS:
            break
        for lc in all_lcs:
            if len(items) >= _MAX_ITEMS:
                break
            try:
                rxn = out.GetSupportReactions(nid, lc)
                forces = _round_forces(rxn)
                items.append({"node_id": int(nid), "load_case": int(lc), **forces})
            except Exception as exc:
                items.append({"node_id": int(nid), "load_case": int(lc), "error": str(exc)})

    return {
        "force_unit": force_unit,
        "moment_unit": moment_unit,
        "support_node_count": len(support_nodes),
        "load_case_count": len(all_lcs),
        "result_count": result_count,
        "showing": len(items),
        "truncated": len(items) < result_count,
        "reactions": items,
    }


def fetch_design_summary(staad: Any) -> dict[str, Any]:
    """Return steel design pass/fail results for all designed members.

    Failures are **never** dropped when truncating — they appear in full in
    ``failed_members``.  Passing members fill the remaining capacity in
    ``passing_sample`` and may be truncated; ``pass_count`` is the true total.

    This structure is the compliance assertion: ``all_pass``, ``fail_count``,
    and ``failed_members`` are authoritative.  Do not recompute from the
    sample arrays.
    """
    out = staad.Output
    geo = staad.Geometry

    if not out.AreResultsAvailable():
        return {"error": "Results not available. Run analysis first (see run_analysis tool)."}

    beam_list = _as_list(geo.GetBeamList())

    failed: list[dict[str, Any]] = []
    passing: list[dict[str, Any]] = []

    for bid in beam_list:
        try:
            ratio = out.GetMemberSteelDesignRatio(bid)
        except Exception:
            continue  # not in design brief — skip silently

        if ratio == -999:
            continue  # member not designed
        if ratio == -1:
            continue  # no analysis results for this member

        if ratio > 1.0:
            # Fetch full detail for every failure — never truncate failures.
            entry: dict[str, Any] = {
                "member_id": int(bid),
                "status": "FAIL",
                "ratio": round(float(ratio), 4),
            }
            try:
                result = out.GetMemberSteelDesignResults(bid)
                result_list = _as_list(result)
                if len(result_list) >= 6:
                    entry["load_case"] = int(result_list[4])
                    entry["location"] = round(float(result_list[5]), 4)
                if len(result_list) >= 7:
                    entry["clause"] = str(result_list[6])
            except Exception:
                pass
            failed.append(entry)
        else:
            passing.append({"member_id": int(bid), "status": "PASS", "ratio": round(float(ratio), 4)})

    total_designed = len(failed) + len(passing)
    controlling = max((f["ratio"] for f in failed), default=None)

    # Fill remaining capacity with passes after all failures are included.
    # Failures are always at full count; passes may be truncated.
    pass_capacity = max(0, _MAX_ITEMS - len(failed))
    passing_sample = passing[:pass_capacity]

    return {
        "all_pass": len(failed) == 0,
        "pass_count": len(passing),
        "fail_count": len(failed),
        "total_designed": total_designed,
        "controlling_ratio": controlling,
        "result_count": total_designed,
        "showing": len(failed) + len(passing_sample),
        "truncated": len(passing_sample) < len(passing),
        "failed_members": failed,
        "passing_sample": passing_sample,
    }
