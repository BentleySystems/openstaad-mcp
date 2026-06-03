"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

File writers: CSV and XLSX.
"""

from __future__ import annotations

import abc
import csv
import os
import time
import uuid
from pathlib import Path
from typing import Any

import openpyxl

from openstaad_mcp.file_io.const import (
    SAMPLE_ROW_COUNT,
    STALE_TEMP_AGE_SECONDS,
    TEMP_FILE_PREFIX,
)
from openstaad_mcp.file_io.path_validator import FileIOError

# ═══════════════════════════════════════════════════════════════════════════
# Base writer
# ═══════════════════════════════════════════════════════════════════════════


class BaseWriter(abc.ABC):
    """Base class for file writers.  Handles atomic writes via temp file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, data: Any, *, overwrite: bool = False) -> dict[str, Any]:
        """Validate, write atomically, and return a summary."""
        if self.path.exists() and not overwrite:
            raise FileIOError("FILE_EXISTS", f"File already exists: {self.path}")
        _clean_stale_temps(self.path.parent)

        tmp = _temp_path(self.path.parent)
        try:
            self._write_to(tmp, data)
            os.replace(tmp, self.path)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        return self.build_summary(data)

    @abc.abstractmethod
    def _write_to(self, tmp: Path, data: Any) -> None:
        """Write *data* to the temporary file *tmp*."""

    @abc.abstractmethod
    def build_summary(self, data: Any) -> dict[str, Any]:
        """Build a lightweight summary for the agent."""


# ═══════════════════════════════════════════════════════════════════════════
# CSV writer
# ═══════════════════════════════════════════════════════════════════════════


class CSVWriter(BaseWriter):
    """Writes ``list[list]`` to a CSV file."""

    def _write_to(self, tmp: Path, data: list[list]) -> None:
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(data)

    def build_summary(self, data: list[list]) -> dict[str, Any]:
        header = data[0] if data else []
        data_rows = data[1:] if len(data) > 1 else []
        return {
            "message": f"The `result` data has been written to `{self.path}`",
            "rows_written": len(data_rows),
            "columns": list(header),
            "sample_rows": [list(r) for r in data_rows[:SAMPLE_ROW_COUNT]],
        }


# ═══════════════════════════════════════════════════════════════════════════
# XLSX writer
# ═══════════════════════════════════════════════════════════════════════════


class XLSXWriter(BaseWriter):
    """Writes flat or multi-sheet data to an XLSX file."""

    def _write_to(self, tmp: Path, data: Any) -> None:
        wb = openpyxl.Workbook()
        if isinstance(data, dict):
            for i, (name, sheet_data) in enumerate(data.items()):
                if i == 0:
                    ws = wb.active
                    assert ws is not None
                    ws.title = name
                else:
                    ws = wb.create_sheet(title=name)
                ws.append(sheet_data["columns"])
                for row in sheet_data["rows"]:
                    ws.append(row)
        else:
            ws = wb.active
            assert ws is not None
            for row in data:
                ws.append(row)
        wb.save(tmp)

    def build_summary(self, data: Any) -> dict[str, Any]:
        if isinstance(data, dict):
            return {
                "message": f"The `result` data has been written to `{self.path}`",
                "sheets": {
                    name: {
                        "columns": sheet["columns"],
                        "rows_written": len(sheet["rows"]),
                        "sample_rows": [list(r) for r in sheet["rows"][:SAMPLE_ROW_COUNT]],
                    }
                    for name, sheet in data.items()
                },
            }
        header = data[0] if data else []
        data_rows = data[1:] if len(data) > 1 else []
        return {
            "message": f"The `result` data has been written to `{self.path}`",
            "rows_written": len(data_rows),
            "columns": list(header),
            "sample_rows": [list(r) for r in data_rows[:SAMPLE_ROW_COUNT]],
        }


# ═══════════════════════════════════════════════════════════════════════════
# Shared utilities
# ═══════════════════════════════════════════════════════════════════════════


def _temp_path(directory: Path) -> Path:
    return directory / f"{TEMP_FILE_PREFIX}{uuid.uuid4().hex}.tmp"


def _clean_stale_temps(directory: Path) -> None:
    """Remove orphaned temp files older than ``STALE_TEMP_AGE_SECONDS``."""
    cutoff = time.time() - STALE_TEMP_AGE_SECONDS
    for p in directory.glob(f"{TEMP_FILE_PREFIX}*.tmp"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
        except OSError:
            pass
