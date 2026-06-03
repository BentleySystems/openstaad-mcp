"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Pydantic models for file I/O return-value validation.
"""

from __future__ import annotations

import unicodedata
from typing import Annotated, Any

from pydantic import BaseModel, RootModel, field_validator, model_validator

from openstaad_mcp.file_io.const import (
    MAX_CELL_SIZE,
    MAX_OUTPUT_COLUMNS,
    MAX_OUTPUT_ROWS,
    MAX_OUTPUT_SHEETS,
    MAX_SHEET_NAME_LENGTH,
)

# ---------------------------------------------------------------------------
# Cell value type — JSON primitives with max string length
# ---------------------------------------------------------------------------

CellValue = str | int | float | bool | None

# Characters that, when leading a spreadsheet cell, cause the value to be
# interpreted as a formula (CSV/XLSX injection).
_FORMULA_PREFIXES = ("=", "+", "-", "@")

# Line separators that would split a single cell into multiple logical CSV
# rows. A later segment could itself begin with a formula prefix, so any cell
# containing one of these is rejected outright.
_LINE_SEPARATORS = frozenset("\n\r\x0b\x0c\u2028\u2029\u0085")


def _check_formula_injection(v: str) -> None:
    """Reject strings that could be interpreted as a spreadsheet formula.

    Defends against three bypasses of a naive ``v.strip()[0] in (...)`` check:

    1. Fullwidth / lookalike Unicode (e.g. U+FF1D fullwidth equals) that
       NFKC-normalises to a formula character. We normalise first, then inspect.
    2. Zero-width / format characters (Unicode category ``Cf``) that survive
       ``str.strip()`` and hide the real leading formula character.
    3. Embedded newlines that split the cell into extra CSV rows.
    """

    normalized = unicodedata.normalize("NFKC", v)

    if any(ch in _LINE_SEPARATORS for ch in normalized):
        raise ValueError("Cell values cannot contain line separators to prevent CSV row splitting")

    # Drop leading whitespace and zero-width/format characters so the first
    # *visible* character is the one that gets checked.
    idx = 0
    for ch in normalized:
        if ch.isspace() or unicodedata.category(ch) == "Cf":
            idx += 1
        else:
            break

    if normalized[idx : idx + 1] in _FORMULA_PREFIXES:
        raise ValueError("Cell values cannot start with '=', '+', '-', or '@' to prevent formula injection")


def check_cell(v: Any, reject_formula: bool = True) -> CellValue:
    """Validate a single cell value: must be a JSON primitive with bounded string length."""

    if isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, str):
        if len(v) > MAX_CELL_SIZE:
            raise ValueError(f"String too long: {len(v)}; limit {MAX_CELL_SIZE}")
        if reject_formula:
            _check_formula_injection(v)
        return v
    if v is None:
        return v
    msg = f"Cell value must be a JSON primitive, got {type(v).__name__}"
    raise ValueError(msg)


# ---------------------------------------------------------------------------
# Row type — a list (or tuple) of cell values
# ---------------------------------------------------------------------------

Row = Annotated[list[CellValue], "A row of cell values"]


# ---------------------------------------------------------------------------
# Flat output (CSV / single-sheet)
# ---------------------------------------------------------------------------


class FlatOutput(RootModel[list[Row]]):
    """Flat tabular output: list of rows, each row a list of JSON-primitive cells."""

    @model_validator(mode="before")
    @classmethod
    def _coerce_sequences(cls, v: Any) -> Any:
        """Accept tuples (from deep_freeze) as rows."""
        if isinstance(v, (list, tuple)):
            return [list(row) if isinstance(row, (list, tuple)) else row for row in v]
        return v

    @model_validator(mode="after")
    def _check_limits(self) -> FlatOutput:
        rows = self.root
        if len(rows) > MAX_OUTPUT_ROWS + 1:  # +1 header
            msg = f"Too many rows: {len(rows)}; limit {MAX_OUTPUT_ROWS}"
            raise ValueError(msg)
        for row in rows:
            if len(row) > MAX_OUTPUT_COLUMNS:
                msg = f"Too many columns: {len(row)}; limit {MAX_OUTPUT_COLUMNS}"
                raise ValueError(msg)
            for cell in row:
                check_cell(cell)
        return self


# ---------------------------------------------------------------------------
# Multi-sheet output (XLSX)
# ---------------------------------------------------------------------------


class SheetData(BaseModel):
    """A single sheet's data: column headers and rows of cells."""

    columns: list[CellValue]
    rows: list[Row]

    @model_validator(mode="before")
    @classmethod
    def _coerce_sequences(cls, v: Any) -> Any:
        """Accept tuples (from deep_freeze) as columns/rows."""
        if isinstance(v, dict):
            data = dict(v)
            if "columns" in data and isinstance(data["columns"], tuple):
                data["columns"] = list(data["columns"])
            if "rows" in data and isinstance(data["rows"], (list, tuple)):
                data["rows"] = [list(r) if isinstance(r, (list, tuple)) else r for r in data["rows"]]
            return data
        return v

    @model_validator(mode="after")
    def _check_limits(self) -> SheetData:
        all_rows = [self.columns, *self.rows]
        for row in all_rows:
            if len(row) > MAX_OUTPUT_COLUMNS:
                msg = f"Too many columns: {len(row)}; limit {MAX_OUTPUT_COLUMNS}"
                raise ValueError(msg)
            for cell in row:
                check_cell(cell)
        if len(self.rows) > MAX_OUTPUT_ROWS:
            msg = f"Too many rows: {len(self.rows)}; limit {MAX_OUTPUT_ROWS}"
            raise ValueError(msg)
        return self


class MultiSheetOutput(RootModel[dict[str, SheetData]]):
    """Multi-sheet output keyed by sheet name."""

    @field_validator("root", mode="before")
    @classmethod
    def _check_sheet_count(cls, v: Any) -> Any:
        if isinstance(v, dict) and len(v) > MAX_OUTPUT_SHEETS:
            msg = f"Too many sheets: {len(v)}; limit {MAX_OUTPUT_SHEETS}"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def _check_sheet_names(self) -> MultiSheetOutput:
        for name in self.root:
            if len(name) > MAX_SHEET_NAME_LENGTH:
                msg = f"Sheet name '{name}' exceeds {MAX_SHEET_NAME_LENGTH} characters"
                raise ValueError(msg)
        return self
