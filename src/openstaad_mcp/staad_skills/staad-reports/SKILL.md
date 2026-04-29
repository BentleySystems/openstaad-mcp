---
name: staad-reports
description: 'Use when creating custom reports and tables in STAAD.Pro for output documentation, result summaries, or formatted data export. Covers: CreateReport, AddTable, SetCellValue, GetCellValue, SetColumnHeader, SetColumnUnitString, SetCellTextBold/Italic/Underline, SetCellTextColor, SetCellTextSize, SetCellTextHorzAlignment, SaveReport, SaveTable, DeleteReport, ResizeTable. Requires staad-core.'
---

# STAAD.Pro Reports & Tables

All report operations go through `const table = staad.Table;`.

## Workflow
1. Create a report
2. Add tables to the report
3. Set headers and populate cells
4. Format cells (optional)
5. Save the report

## Creating Reports
```javascript
const reportNo = table.CreateReport("Analysis Results");
const count = table.GetReportCount();
table.DeleteReport(reportNo);
```

## Creating Tables
```javascript
const tableNo = table.AddTable(reportNo, "Node Displacements", rowCount, colCount);
table.RenameTable(reportNo, tableNo, "New Name");
table.ResizeTable(reportNo, tableNo, newRows, newCols);
table.DeleteTable(reportNo, tableNo);
```

## Cell Values
Row and column indices start from **1**.
```javascript
table.SetCellValue(reportNo, tableNo, row, col, "value");
const value = table.GetCellValue(reportNo, tableNo, row, col);
```

## Headers
```javascript
table.SetColumnHeader(reportNo, tableNo, col, "Header");
table.SetColumnUnitString(reportNo, tableNo, col, "mm");
table.SetRowHeader(reportNo, tableNo, row, "Row Label");
```

## Formatting
```javascript
// Text style
table.SetCellTextBold(reportNo, tableNo, row, col);
table.SetCellTextItalic(reportNo, tableNo, row, col);
table.SetCellTextUnderline(reportNo, tableNo, row, col);

// Color (RGB 0-255)
table.SetCellTextColor(reportNo, tableNo, row, col, red, green, blue);

// Size
table.SetCellTextSize(reportNo, tableNo, row, col, size);
table.SetCellTextSizeAll(reportNo, tableNo, size);   // entire table

// Alignment
table.SetCellTextHorzAlignment(reportNo, tableNo, row, col, align);  // 0=left, 1=center, 2=right
table.SetCellTextVertAlignment(reportNo, tableNo, row, col, align);  // 0=top, 4=center, 8=bottom
```

## Saving
```javascript
table.SaveTable(reportNo, tableNo);   // save one table
table.SaveReport(reportNo);           // save entire report
table.SaveReportAll();                // save all reports
```

## Example
See [create-force-report.js](./scripts/create-force-report.js)

## Gotchas
- Row and column indices start from 1, not 0
- Cell values are always strings — convert numbers with `String(value)` or `value.toFixed(3)`
- Create the report before adding tables; create tables before setting cells
