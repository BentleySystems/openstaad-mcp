# Cross-case MY envelope retaining the controlling case, position and sign.
members = tools.geometry.get_members()  # noqa: F821
cases = tools.loads.get_load_cases()  # noqa: F821
extrema = tools.analysis.get_member_force_extrema(  # noqa: F821
    [m["id"] for m in members], [c["id"] for c in cases], components=["MY"]
)
envelope = {}
for row in extrema:
    for side in ["min", "max"]:
        candidate = {
            "member_id": row["member_id"],
            "load_case": row["load_case"],
            "MY": row[side],
            "position": row[side + "_position"],
        }
        previous = envelope.get(row["member_id"])
        if previous is None or abs(candidate["MY"]) > abs(previous["MY"]):
            envelope[row["member_id"]] = candidate
result = list(envelope.values())
