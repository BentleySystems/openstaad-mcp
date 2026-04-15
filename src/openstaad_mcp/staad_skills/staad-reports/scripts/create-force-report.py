"""Create a report table summarizing member end forces."""
geo = staad.Geometry
out = staad.Output
tbl = staad.Table
load = staad.Load

if not out.AreResultsAvailable():
    print("No results available - run analysis first")
else:
    beam_list = list(geo.GetBeamList())
    lc_numbers = list(load.GetPrimaryLoadCaseNumbers())
    lc = lc_numbers[0]

    report_no = tbl.CreateReport("Member Forces Summary")
    table_no = tbl.AddTable(report_no, "End Forces LC " + str(lc), len(beam_list), 4)

    # Headers
    headers = ["Member", "FX", "FY", "MZ"]
    for i, h in enumerate(headers, 1):
        tbl.SetColumnHeader(report_no, table_no, i, h)
        tbl.SetCellTextBold(report_no, table_no, 1, i)

    # Data
    for row, bid in enumerate(beam_list, 1):
        f = out.GetMemberEndForces(bid, 0, lc, 0)
        tbl.SetCellValue(report_no, table_no, row, 1, str(bid))
        tbl.SetCellValue(report_no, table_no, row, 2, f"{f[0]:.3f}")
        tbl.SetCellValue(report_no, table_no, row, 3, f"{f[1]:.3f}")
        tbl.SetCellValue(report_no, table_no, row, 4, f"{f[5]:.3f}")

    tbl.SetCellTextSizeAll(report_no, table_no, 10.0)
    tbl.SaveReport(report_no)
    print(f"Report created with {len(beam_list)} rows")
