"""Shared helpers and fixtures for file I/O tests."""

import csv
from pathlib import Path

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _write_csv(path: Path, rows: list[list], encoding: str = "utf-8") -> None:
    with open(path, "w", newline="", encoding=encoding) as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def _write_xlsx(path: Path, sheets: dict[str, list[list]]) -> None:
    wb = openpyxl.Workbook()
    first = True
    for name, rows in sheets.items():
        ws = wb.active if first else wb.create_sheet(title=name)
        if not isinstance(ws, Worksheet):
            raise ValueError("Expected openpyxl Worksheet")
        if first:
            ws.title = name
            first = False
        for row in rows:
            ws.append(row)
    wb.save(path)
