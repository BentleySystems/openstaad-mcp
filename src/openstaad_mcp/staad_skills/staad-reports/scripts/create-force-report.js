// create-force-report.js
// Creates a report table summarizing member end forces.

const geo = staad.Geometry;
const out = staad.Output;
const tbl = staad.Table;
const load = staad.Load;

if (!out.AreResultsAvailable()) {
    console.log('No results available - run analysis first');
} else {
    const beamList = geo.GetBeamList();
    const lcNumbers = load.GetPrimaryLoadCaseNumbers();
    const lc = lcNumbers[0];

    const reportNo = tbl.CreateReport('Member Forces Summary');
    const tableNo = tbl.AddTable(reportNo, `End Forces LC ${lc}`, beamList.length, 4);

    // Headers
    const headers = ['Member', 'FX', 'FY', 'MZ'];
    headers.forEach((h, i) => {
        const col = i + 1;
        tbl.SetColumnHeader(reportNo, tableNo, col, h);
        tbl.SetCellTextBold(reportNo, tableNo, 1, col);
    });

    // Data
    beamList.forEach((bid, idx) => {
        const row = idx + 1;
        const f = out.GetMemberEndForces(bid, 0, lc, 0);
        tbl.SetCellValue(reportNo, tableNo, row, 1, String(bid));
        tbl.SetCellValue(reportNo, tableNo, row, 2, f[0].toFixed(3));
        tbl.SetCellValue(reportNo, tableNo, row, 3, f[1].toFixed(3));
        tbl.SetCellValue(reportNo, tableNo, row, 4, f[5].toFixed(3));
    });

    tbl.SetCellTextSizeAll(reportNo, tableNo, 10.0);
    tbl.SaveReport(reportNo);
    console.log(`Report created with ${beamList.length} rows`);
}
