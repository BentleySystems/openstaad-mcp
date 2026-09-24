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
# - SetStressType(entityType, stressType, refreshFlag) picks which stress component the contour
#   shows and recomputes its legend range for the currently active load case. Call it BEFORE
#   SetDiagramMode(20, ...) -- a stress type must already be set for the diagram to turn on at all
#   (matches the Diagrams>Plate/Solid Stress dialog). entityType=20 Plate, 21 Solid; stressType=8
#   is Max Von Mises for plates (see VIEW_CODES.md for the full tables).
# - SetDiagramMode(20, ...) is Plate Stress; SetDiagramMode(21, ...) is Solid Stress (see VIEW_CODES.md
#   for the full Diagram Mode Codes table).
# - ExportView's return code and file size alone don't guarantee a real (non-blank) capture -- if a
#   result looks suspicious, view the exported file to confirm.
# - SetActiveWindow(1) targets the main view of THIS freshly-connected model -- use the real window id
#   instead of 1 if the script created/opened a different window (CreateNewViewForSelectionsEx, OpenView).

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
        view.SetStressType(20, 8, False)      # Max Von Mises; skip refresh, SetDiagramMode refreshes next
        view.SetDiagramMode(20, True, True)    # enable Plate Stress diagram now that a type is set
        view.ZoomExtentsMainView()
        view.RefreshView()

        filename = f"LC{lc}_plate_stress.jpg"
        export_result = view.ExportView(export_dir, filename, 1, True)  # 1=jpg
        exported.append({"load_case": lc, "file": f"{export_dir}\\{filename}", "export_result": export_result})

    result = {"ok": True, "exported": exported, "stress_unit": out.GetOutputUnitForStress()}
