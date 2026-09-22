# Use availability to avoid querying design details for undesigned members.
utilization = tools.design.get_utilization()  # noqa: F821
details = tools.design.get_member_results(  # noqa: F821
    [row["member_id"] for row in utilization if row["available"]]
)
result = {
    "failed": [row for row in details if row["status"].strip().upper() == "FAIL"],
    "unavailable": [row["member_id"] for row in utilization if not row["available"]],
    "design_scope": "last parameter block for each member",
}
