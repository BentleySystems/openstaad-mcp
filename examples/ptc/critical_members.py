# Paste this program into execute_ptc.code; these are sandbox globals.
members = tools.geometry.get_members(up_axis="Y")  # noqa: F821
horizontal_ids = [member["id"] for member in members if member["is_horizontal"]]
ratios = tools.design.get_utilization(horizontal_ids)  # noqa: F821
result = {
    "horizontal_count": len(horizontal_ids),
    "threshold": 0.9,
    "design_scope": "last steel design parameter block",
    "critical": [row for row in ratios if row["available"] and row["ratio"] > 0.9],
    "unavailable": [row["member_id"] for row in ratios if not row["available"]],
}
