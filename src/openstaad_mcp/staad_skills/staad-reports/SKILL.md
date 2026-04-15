---
name: staad-reports
description: 'Use when creating custom reports and tables in STAAD.Pro for output documentation, result summaries, or formatted data export. Covers: CreateReport, AddTable, SetCellValue, GetCellValue, SetColumnHeader, SetColumnUnitString, SetCellTextBold/Italic/Underline, SetCellTextColor, SetCellTextSize, SetCellTextHorzAlignment, SaveReport, SaveTable, DeleteReport, ResizeTable. Requires staad-core.'
---

# STAAD.Pro Reports & Tables

All report operations go through `table = staad.Table`.

## Workflow
1. Create a report
2. Add tables to the report
3. Set headers and populate cells
4. Format cells (optional)
5. Save the report

## Creating Reports
```python
report_no = table.CreateReport("Analysis Results")
count = table.GetReportCount()
table.DeleteReport(report_no)
```

## Creating Tables
```python
table_no = table.AddTable(report_no, "Node Displacements", row_count, col_count)
table.RenameTable(report_no, table_no, "New Name")
table.ResizeTable(report_no, table_no, new_rows, new_cols)
table.DeleteTable(report_no, table_no)
```

## Cell Values
Row and column indices start from **1**.
```python
table.SetCellValue(report_no, table_no, row, col, "value")
value = table.GetCellValue(report_no, table_no, row, col)
```

## Headers
```python
table.SetColumnHeader(report_no, table_no, col, "Header")
table.SetColumnUnitString(report_no, table_no, col, "mm")
table.SetRowHeader(report_no, table_no, row, "Row Label")
```

## Formatting
```python
# Text style
table.SetCellTextBold(report_no, table_no, row, col)
table.SetCellTextItalic(report_no, table_no, row, col)
table.SetCellTextUnderline(report_no, table_no, row, col)

# Color (RGB 0-255)
table.SetCellTextColor(report_no, table_no, row, col, red, green, blue)

# Size
table.SetCellTextSize(report_no, table_no, row, col, size)
table.SetCellTextSizeAll(report_no, table_no, size)   # entire table

# Alignment
table.SetCellTextHorzAlignment(report_no, table_no, row, col, align)  # 0=left, 1=center, 2=right
table.SetCellTextVertAlignment(report_no, table_no, row, col, align)  # 0=top, 4=center, 8=bottom
```

## Saving
```python
table.SaveTable(report_no, table_no)   # save one table
table.SaveReport(report_no)             # save entire report
table.SaveReportAll()                   # save all reports
```

## Example
See [create-force-report.py](./scripts/create-force-report.py)

## Gotchas
- Row and column indices start from 1, not 0
- Cell values are always strings — convert numbers with `str()` or `f"{value:.3f}"`
- Create the report before adding tables; create tables before setting cells
