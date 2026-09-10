# Table result: pass an allowed output_data_path to export CSV or XLSX.
plates = tools.geometry.get_plates()  # noqa: F821
cases = tools.loads.get_load_cases(include_combinations=False)  # noqa: F821
stresses = tools.analysis.get_plate_von_mises_stresses(  # noqa: F821
    [p["id"] for p in plates], [c["id"] for c in cases]
)
result = [["plate_id", "load_case", "top_von_mises", "bottom_von_mises"]] + [
    [row["plate_id"], row["load_case"], row["top"], row["bottom"]] for row in stresses
]
