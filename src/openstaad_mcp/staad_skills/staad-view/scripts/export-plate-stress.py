# export-plate-stress.py
# Exports an isometric plate-stress (Von Mises) contour screenshot per load case.
# Requires analysis results already available (out.AreResultsAvailable()).
#
# Notes:
# - Load.SetLoadActive(loadCaseNo) switches which load case's results are shown for post-processing
#   display -- View.SetModeSectionPage's 3rd arg is a PAGE number, not a load case.
# - View.SetInterfaceMode(...) is not required.
# - SetDiagramMode(15, ...) (Fill Plates & Solids) is not required -- SetDiagramMode(20, ...) alone
#   produces a fully-filled color gradient contour with a correct legend and units.
# - If no plate/solid stress type has been picked yet (via the Diagrams > Plate/Solid Stress dialog),
#   STAAD.Pro defaults to Max Von Mises; any type already picked manually is left untouched.
# - SetDiagramMode(20, ...) is Plate Stress; SetDiagramMode(21, ...) is Solid Stress (see VIEW_CODES.md
#   for the full Diagram Mode Codes table).
# - ExportView's return code and file size alone don't guarantee a real (non-blank) capture -- if a
#   result looks suspicious, view the exported file to confirm.

out = staad.Output
load = staad.Load
view = staad.View

if not out.AreResultsAvailable():
    result = {"ok": False, "message": "No analysis results available. Run analysis first."}
else:
    load_cases = list(load.GetPrimaryLoadCaseNumbers())
    export_dir = r"C:\Temp\plate_stress_exports"
    exported = []

    for lc in load_cases:
        load.SetLoadActive(lc)
        view.SetActiveWindow(1)
        view.ShowIsometric()
        view.SetDiagramMode(20, True, True)  # Plate Stress (Von Mises, STAAD.Pro's default plate stress display)
        view.ZoomExtentsMainView()
        view.RefreshView()

        filename = f"LC{lc}_plate_stress.jpg"
        export_result = view.ExportView(export_dir, filename, 1, True)  # 1=jpg
        exported.append({"load_case": lc, "file": f"{export_dir}\\{filename}", "export_result": export_result})

    result = {"ok": True, "exported": exported, "stress_unit": out.GetOutputUnitForStress()}
