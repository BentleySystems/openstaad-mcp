"""Tests for CSV and XLSX readers: encoding, dialect, limits, header detection, summaries."""

import csv
from pathlib import Path

import pytest

from openstaad_mcp.file_io import CSVReader, XLSXReader, read_input_file
from openstaad_mcp.file_io.path_validator import FileIOError
from openstaad_mcp.file_io.readers import _detect_header

from .conftest import FIXTURES_DIR, _write_csv, _write_xlsx

# ═══════════════════════════════════════════════════════════════════════════
# _detect_header unit tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectHeader:
    """Direct tests for the header-detection heuristic."""

    def test_explicit_true_overrides(self):
        assert _detect_header([[1, 2], [3, 4]], has_header=True) is True

    def test_explicit_false_overrides(self):
        assert _detect_header([["a", "b"], [1, 2]], has_header=False) is False

    def test_single_row_defaults_to_header(self):
        assert _detect_header([["a", "b"]], has_header=None) is True

    def test_empty_rows_defaults_to_header(self):
        assert _detect_header([], has_header=None) is True

    def test_string_header_numeric_data(self):
        rows = [["name", "value"], [1, 2], [3, 4]]
        assert _detect_header(rows, has_header=None) is True

    def test_all_numeric_no_header(self):
        rows = [[1, 2], [3, 4], [5, 6]]
        assert _detect_header(rows, has_header=None) is False

    def test_all_string_no_header(self):
        rows = [["a", "b"], ["c", "d"], ["e", "f"]]
        assert _detect_header(rows, has_header=None) is False

    def test_matching_mixed_types_no_header(self):
        """When header types match data types per-column, heuristic says no header."""
        rows = [["Name", 0, "Type"], ["Alice", 1, "A"], ["Bob", 2, "B"]]
        assert _detect_header(rows, has_header=None) is False

    def test_null_values_ignored(self):
        rows = [[None, "b"], [None, 1], [None, 2]]
        assert _detect_header(rows, has_header=None) is True

    def test_all_null_column_skipped(self):
        rows = [[None, 1], [None, 2], [None, 3]]
        assert _detect_header(rows, has_header=None) is False

    def test_bool_vs_string_is_header(self):
        rows = [["flag", "val"], [True, 1], [False, 2]]
        assert _detect_header(rows, has_header=None) is True

    def test_uses_up_to_4_data_rows(self):
        rows = [["h"], [1], [2], [3], [4], ["outlier"]]
        assert _detect_header(rows, has_header=None) is True


# ═══════════════════════════════════════════════════════════════════════════
# CSV Read
# ═══════════════════════════════════════════════════════════════════════════


class TestCSVRead:
    def test_basic_csv(self):
        data, _summary = read_input_file(FIXTURES_DIR / "basic.csv")
        assert data == [["name", "value"], ["A", 1], ["B", 2.5]]

    def test_utf8_encoding(self):
        data, _ = read_input_file(FIXTURES_DIR / "utf8.csv")
        assert data[1][0] == "café"

    def test_cp1252_fallback(self):
        data, _ = read_input_file(FIXTURES_DIR / "cp1252.csv")
        assert data[1][0] == "naïve"

    def test_semicolon_dialect(self):
        data, _ = read_input_file(FIXTURES_DIR / "semicolon.csv")
        assert data == [["x", "y"], [1, 2], [3, 4]]

    def test_single_row_csv_as_header_only(self):
        data, summary = read_input_file(FIXTURES_DIR / "header_only.csv")
        assert data == [["a", "b", "c"]]
        assert summary["total_rows"] == 0
        assert summary["columns"] == ["a", "b", "c"]

    def test_empty_csv(self):
        data, summary = read_input_file(FIXTURES_DIR / "empty.csv")
        assert data == []
        assert summary["total_rows"] == 0
        assert summary["columns"] == []

    def test_start_row_and_max_rows(self, tmp_path: Path):
        rows = [["h"]] + [[i] for i in range(100)]
        p = tmp_path / "big.csv"
        _write_csv(p, rows)
        data, _ = read_input_file(p, start_row=10, max_rows=5)
        assert len(data) == 5
        assert data[0] == [10]

    def test_too_large_file(self, tmp_path: Path):
        p = tmp_path / "huge.csv"
        p.write_bytes(b"a\n" + b"x" * (50 * 1024 * 1024 + 1))
        with pytest.raises(FileIOError) as exc_info:
            read_input_file(p)
        assert exc_info.value.code == "FILE_TOO_LARGE"

    def test_too_many_columns(self, tmp_path: Path):
        p = tmp_path / "wide.csv"
        _write_csv(p, [[f"c{i}" for i in range(501)]])
        with pytest.raises(FileIOError) as exc_info:
            read_input_file(p)
        assert exc_info.value.code == "TOO_MANY_COLUMNS"

    def test_oversized_cell_csv(self, tmp_path: Path):
        """CSV cell exceeding MAX_CELL_SIZE is rejected on read."""
        p = tmp_path / "big_cell.csv"
        _write_csv(p, [["header"], ["x" * 32_769]])
        with pytest.raises(FileIOError) as exc_info:
            read_input_file(p)
        assert exc_info.value.code == "INVALID_CELL"

    def test_malformed_csv_raises_file_io_error(self, tmp_path: Path):
        """CSV field exceeding csv.field_size_limit raises CSV_PARSE_ERROR."""
        p = tmp_path / "big_field.csv"
        p.write_text("a,b\n" + "x" * 200 + ",c\n", encoding="utf-8")
        old_limit = csv.field_size_limit(10)
        try:
            with pytest.raises(FileIOError) as exc_info:
                read_input_file(p)
            assert exc_info.value.code == "CSV_PARSE_ERROR"
        finally:
            csv.field_size_limit(old_limit)

    def test_no_header_csv(self):
        """CSV with all-numeric rows: auto-detect no header."""
        data, summary = read_input_file(FIXTURES_DIR / "no_header.csv")
        assert data == [[1, 2, 3], [4, 5, 6]]
        assert summary["total_rows"] == 2
        assert summary["columns"] == ["col_1", "col_2", "col_3"]

    def test_mixed_first_row_still_header(self, tmp_path: Path):
        """First row with different types from data rows is detected as header."""
        p = tmp_path / "mixed.csv"
        _write_csv(p, [["Name", "X", "Y"], ["Alice", 3, 4], ["Bob", 5, 6]])
        data, summary = read_input_file(p)
        assert data[0] == ["Name", "X", "Y"]
        assert summary["total_rows"] == 2
        assert summary["columns"] == ["Name", "X", "Y"]

    def test_has_header_true_override(self):
        """Force has_header=True on all-numeric data."""
        data, summary = read_input_file(FIXTURES_DIR / "no_header.csv", has_header=True)
        assert data == [[1, 2, 3], [4, 5, 6]]
        assert summary["total_rows"] == 1
        assert summary["columns"] == [1, 2, 3]

    def test_has_header_false_override(self, tmp_path: Path):
        """Force has_header=False on data with string header."""
        p = tmp_path / "with_header.csv"
        _write_csv(p, [["Name", "Value"], ["A", 1], ["B", 2]])
        data, summary = read_input_file(p, has_header=False)
        assert data == [["Name", "Value"], ["A", 1], ["B", 2]]
        assert summary["total_rows"] == 3
        assert summary["columns"] == ["col_1", "col_2"]

    def test_all_string_data_no_header(self, tmp_path: Path):
        """All-string rows with uniform types -- auto-detect no header."""
        p = tmp_path / "strings.csv"
        _write_csv(p, [["A", "B"], ["C", "D"], ["E", "F"]])
        data, summary = read_input_file(p)
        assert data == [["A", "B"], ["C", "D"], ["E", "F"]]
        assert summary["total_rows"] == 3
        assert summary["columns"] == ["col_1", "col_2"]


# ═══════════════════════════════════════════════════════════════════════════
# XLSX Read
# ═══════════════════════════════════════════════════════════════════════════


class TestXLSXRead:
    def test_single_sheet(self):
        data, _summary = read_input_file(FIXTURES_DIR / "single_sheet.xlsx")
        assert isinstance(data, dict)
        assert "Sheet1" in data
        assert data["Sheet1"]["columns"] == ["a", "b"]
        assert data["Sheet1"]["rows"] == [[1, 2], [3, 4]]

    def test_multi_sheet(self):
        data, _ = read_input_file(FIXTURES_DIR / "multi_sheet.xlsx")
        assert set(data.keys()) == {"Beams", "Loads"}

    def test_select_sheet(self):
        data, _ = read_input_file(FIXTURES_DIR / "multi_sheet.xlsx", sheet="Loads")
        assert "Loads" in data
        assert len(data) == 1

    def test_sheet_not_found(self):
        with pytest.raises(FileIOError) as exc_info:
            read_input_file(FIXTURES_DIR / "single_sheet.xlsx", sheet="Missing")
        assert exc_info.value.code == "SHEET_NOT_FOUND"

    def test_datetime_to_iso(self):
        data, _ = read_input_file(FIXTURES_DIR / "dates.xlsx")
        assert data["Dates"]["rows"][0][0] == "2026-05-01T00:00:00"

    def test_header_only_xlsx(self):
        data, summary = read_input_file(FIXTURES_DIR / "header_only.xlsx")
        assert data["Data"]["columns"] == ["x", "y"]
        assert data["Data"]["rows"] == []
        assert summary["total_rows"] == 0

    def test_empty_sheet_xlsx(self):
        data, summary = read_input_file(FIXTURES_DIR / "empty_sheet.xlsx")
        assert data["Empty"]["columns"] == []
        assert data["Empty"]["rows"] == []
        assert summary["total_rows"] == 0

    def test_corrupted_xlsx(self, tmp_path: Path):
        p = tmp_path / "bad.xlsx"
        p.write_bytes(b"not a zip file")
        with pytest.raises(FileIOError) as exc_info:
            read_input_file(p)
        assert exc_info.value.code == "CORRUPTED_WORKBOOK"

    def test_oversized_cell_xlsx(self, tmp_path: Path, monkeypatch):
        """XLSX cell exceeding MAX_CELL_SIZE is rejected on read."""

        # openpyxl truncates strings to 32767 chars, so lower the limit
        def check_cell_override(cell, reject_formula: bool = True) -> None:
            if isinstance(cell, str) and len(cell) > 100:
                raise ValueError("Cell too large")

        monkeypatch.setattr("openstaad_mcp.file_io.readers.check_cell", check_cell_override)
        _write_xlsx(tmp_path / "big_cell.xlsx", {"Sheet1": [["h"], ["x" * 200]]})
        with pytest.raises(FileIOError) as exc_info:
            read_input_file(tmp_path / "big_cell.xlsx")
        assert exc_info.value.code == "INVALID_CELL"

    def test_no_header_xlsx(self):
        """XLSX with all-numeric rows: auto-detect no header."""
        data, summary = read_input_file(FIXTURES_DIR / "no_header.xlsx")
        assert data["Data"]["columns"] == ["col_1", "col_2", "col_3"]
        assert data["Data"]["rows"] == [[1, 2, 3], [4, 5, 6]]
        assert summary["total_rows"] == 2

    def test_has_header_true_override_xlsx(self, tmp_path: Path):
        """Force has_header=True on all-numeric XLSX."""
        _write_xlsx(tmp_path / "num.xlsx", {"Sheet1": [[1, 2], [3, 4]]})
        data, summary = read_input_file(tmp_path / "num.xlsx", has_header=True)
        assert data["Sheet1"]["columns"] == [1, 2]
        assert data["Sheet1"]["rows"] == [[3, 4]]
        assert summary["total_rows"] == 1

    def test_has_header_false_override_xlsx(self, tmp_path: Path):
        """Force has_header=False on XLSX with string header."""
        _write_xlsx(tmp_path / "hdr.xlsx", {"Sheet1": [["Name", "Val"], ["A", 1]]})
        data, summary = read_input_file(tmp_path / "hdr.xlsx", has_header=False)
        assert data["Sheet1"]["columns"] == ["col_1", "col_2"]
        assert data["Sheet1"]["rows"] == [["Name", "Val"], ["A", 1]]
        assert summary["total_rows"] == 2


# ═══════════════════════════════════════════════════════════════════════════
# Summary generation
# ═══════════════════════════════════════════════════════════════════════════


class TestSummaries:
    def test_input_summary_csv(self):
        data, _ = read_input_file(FIXTURES_DIR / "basic.csv")
        summary = CSVReader(FIXTURES_DIR / "basic.csv").build_summary(data)
        assert summary["total_rows"] == 2
        assert summary["columns"] == ["name", "value"]

    def test_input_summary_xlsx(self):
        data, _ = read_input_file(FIXTURES_DIR / "multi_sheet.xlsx")
        summary = XLSXReader(FIXTURES_DIR / "multi_sheet.xlsx").build_summary(data)
        assert set(summary["sheets"]) == {"Beams", "Loads"}
        assert summary["total_rows"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# defusedxml verification
# ═══════════════════════════════════════════════════════════════════════════


class TestDefusedXML:
    """Verify that defusedxml is active alongside openpyxl."""

    def test_defusedxml_installed(self):
        import defusedxml

        assert defusedxml is not None

    def test_corrupted_xml_rejected(self, tmp_path: Path):
        """An xlsx with invalid/malicious XML content is rejected."""
        import zipfile

        p = tmp_path / "bomb.xlsx"
        with zipfile.ZipFile(p, "w") as zf:
            zf.writestr("[Content_Types].xml", "<?xml version='1.0'?><bad/>")
        with pytest.raises(FileIOError) as exc_info:
            read_input_file(p)
        assert exc_info.value.code == "CORRUPTED_WORKBOOK"
