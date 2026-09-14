# Example: summarize local end forces for horizontal members in the first primary case.
members = tools.geometry.get_members(up_axis="Y")  # noqa: F821
member_ids = [member["id"] for member in members if member["is_horizontal"]]
cases = tools.loads.get_load_cases(include_combinations=False)  # noqa: F821
if not cases:
    raise ValueError("No primary load cases found")
case_id = cases[0]["id"]
forces = tools.analysis.get_member_forces(member_ids, [case_id])  # noqa: F821
units = tools.analysis.get_units()  # noqa: F821
result = {
    "load_case": case_id,
    "member_count": len(member_ids),
    "units": units,
    "max_absolute_local_end_MY": max([abs(row["MY"]) for row in forces], default=0),
    "note": "End moments only; this is not an internal member envelope or a design ratio.",
}
