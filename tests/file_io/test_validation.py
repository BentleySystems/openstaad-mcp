"""Tests for return-value validation (Pydantic models), deep freeze, and allowed dirs."""

import os
from pathlib import Path
from types import MappingProxyType

import pytest

from openstaad_mcp.file_io import deep_freeze, validate_args_allowed_dirs, validate_return_value
from openstaad_mcp.file_io.path_validator import FileIOError

# ═══════════════════════════════════════════════════════════════════════════
# Return value validation
# ═══════════════════════════════════════════════════════════════════════════


class TestValidateReturnValue:
    def test_valid_flat(self):
        validate_return_value(Path("test.csv"), [["a", "b"], [1, 2]])

    def test_valid_multi_sheet(self):
        validate_return_value(
            Path("test.xlsx"),
            {
                "S1": {"columns": ["a"], "rows": [[1]]},
            },
        )

    def test_rejects_non_primitive_leaf(self):
        with pytest.raises(FileIOError) as exc_info:
            validate_return_value(Path("test.csv"), [["a"], [object()]])
        assert exc_info.value.code == "INVALID_RETURN_SHAPE"

    def test_rejects_too_many_sheets(self):
        data = {f"S{i}": {"columns": ["a"], "rows": [[1]]} for i in range(51)}
        with pytest.raises(FileIOError) as exc_info:
            validate_return_value(Path("test.xlsx"), data)
        assert exc_info.value.code == "INVALID_RETURN_SHAPE"

    def test_rejects_too_many_rows(self):
        data = [["a"]] + [[i] for i in range(100_001)]
        with pytest.raises(FileIOError) as exc_info:
            validate_return_value(Path("test.csv"), data)
        assert exc_info.value.code == "INVALID_RETURN_SHAPE"

    def test_rejects_too_many_columns(self):
        data = [[i for i in range(501)]]
        with pytest.raises(FileIOError) as exc_info:
            validate_return_value(Path("test.csv"), data)
        assert exc_info.value.code == "INVALID_RETURN_SHAPE"

    def test_rejects_long_sheet_name(self):
        data = {"A" * 32: {"columns": ["a"], "rows": [[1]]}}
        with pytest.raises(FileIOError) as exc_info:
            validate_return_value(Path("test.xlsx"), data)
        assert exc_info.value.code == "INVALID_RETURN_SHAPE"

    def test_rejects_non_list_non_dict(self):
        with pytest.raises(FileIOError) as exc_info:
            validate_return_value(Path("test.csv"), "not valid")
        assert exc_info.value.code == "INVALID_RETURN_SHAPE"

    def test_rejects_oversized_cell_in_flat(self):
        """String cell exceeding MAX_CELL_SIZE is rejected."""
        data = [["a"], ["x" * 32_769]]
        with pytest.raises(FileIOError) as exc_info:
            validate_return_value(Path("test.csv"), data)
        assert exc_info.value.code == "INVALID_RETURN_SHAPE"

    def test_rejects_oversized_cell_in_multi_sheet(self):
        """Oversized cell in multi-sheet output is rejected."""
        data = {"S1": {"columns": ["a"], "rows": [["x" * 32_769]]}}
        with pytest.raises(FileIOError) as exc_info:
            validate_return_value(Path("test.xlsx"), data)
        assert exc_info.value.code == "INVALID_RETURN_SHAPE"

    def test_accepts_tuples_as_rows(self):
        """Tuples (from deep_freeze) should be accepted as rows."""
        validate_return_value(Path("test.csv"), (("a", "b"), (1, 2)))

    @pytest.mark.parametrize("cell", ["=SUM(A1)", "+cmd|'/C calc'!A0", "-2+3", "@SUM(1,2)"])
    def test_rejects_formula_injection_in_flat(self, cell: str):
        """Cell values starting with formula-injection characters are rejected."""
        with pytest.raises(FileIOError) as exc_info:
            validate_return_value(Path("test.csv"), [["header"], [cell]])
        assert exc_info.value.code == "INVALID_RETURN_SHAPE"

    @pytest.mark.parametrize("cell", ["=A1", "+1", "-1", "@test"])
    def test_rejects_formula_injection_in_multi_sheet(self, cell: str):
        """Formula injection is rejected in multi-sheet output cells."""
        with pytest.raises(FileIOError) as exc_info:
            validate_return_value(Path("test.xlsx"), {"S1": {"columns": ["a"], "rows": [[cell]]}})
        assert exc_info.value.code == "INVALID_RETURN_SHAPE"

    @pytest.mark.parametrize("cell", ["=SUM(A1)", "+cmd", "-2", "@foo"])
    def test_rejects_formula_injection_in_column_headers(self, cell: str):
        """Formula injection is also rejected in column header cells."""
        with pytest.raises(FileIOError) as exc_info:
            validate_return_value(Path("test.xlsx"), {"S1": {"columns": [cell], "rows": []}})
        assert exc_info.value.code == "INVALID_RETURN_SHAPE"

    @pytest.mark.parametrize("cell", [" =not-injected", "\t+ok"])
    def test_rejects_formula_injection_after_stripping_whitespace(self, cell: str):
        """Leading whitespace is stripped before the formula-char check, so these are also rejected."""
        with pytest.raises(FileIOError) as exc_info:
            validate_return_value(Path("test.csv"), [["header"], [cell]])
        assert exc_info.value.code == "INVALID_RETURN_SHAPE"

    @pytest.mark.parametrize("cell", ["hello=world", "1+1", "text-here", "price: -5", "note@domain.com"])
    def test_accepts_strings_not_starting_with_formula_chars(self, cell: str):
        """Strings where formula chars appear only in the middle are accepted."""
        validate_return_value(Path("test.csv"), [["header"], [cell]])

    # -----------------------------------------------------------------------
    # Formula-injection bypass tests — prove the intern's check is incomplete
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize(
        "cell",
        [
            "＝SUM(A1)",  # U+FF1D FULLWIDTH EQUALS SIGN — NFKC-normalises to '='
            "＋1+2",  # U+FF0B FULLWIDTH PLUS SIGN
            "－1+2",  # U+FF0D FULLWIDTH HYPHEN-MINUS
            "＠SUM(1)",  # U+FF20 FULLWIDTH COMMERCIAL AT
        ],
    )
    def test_bypass_fullwidth_unicode_lookalikes(self, cell: str):
        """Fullwidth Unicode lookalikes bypass the ASCII-only set check.

        The guard checks against the ASCII characters '=', '+', '-', '@'.
        Fullwidth variants (U+FF0B, U+FF0D, U+FF1D, U+FF20) are distinct
        code points and are not in that set, so the check silently passes them
        through.  Yet many spreadsheet applications apply NFKC Unicode
        normalisation when loading a CSV/XLSX file, which maps every fullwidth
        character back to its ASCII equivalent and then evaluates the result as
        a formula.
        """
        # Should raise ValueError / INVALID_RETURN_SHAPE — currently does NOT.
        with pytest.raises(FileIOError) as exc_info:
            validate_return_value(Path("test.csv"), [["header"], [cell]])
        assert exc_info.value.code == "INVALID_RETURN_SHAPE"

    @pytest.mark.parametrize(
        "cell",
        [
            "\u200b=SUM(1)",  # U+200B ZERO WIDTH SPACE (category Cf, not stripped by str.strip())
            "\u200c+cmd",  # U+200C ZERO WIDTH NON-JOINER
            "\u200d-1",  # U+200D ZERO WIDTH JOINER
            "\u2060=A1",  # U+2060 WORD JOINER
        ],
    )
    def test_bypass_zero_width_character_prefix(self, cell: str):
        """Zero-width characters prefix the injection character and evade the guard.

        Python's str.strip() only removes characters where str.isspace() is
        True.  Zero-width format characters (Unicode category Cf) do *not*
        satisfy isspace(), so they survive the strip() call.  After stripping,
        the first character is the zero-width character, which is not in
        ('=', '+', '-', '@'), and the check silently passes.

        Some spreadsheet applications ignore invisible characters when parsing
        cell content, effectively treating '\\u200b=SUM(1)' as '=SUM(1)'.
        """
        # Should raise ValueError / INVALID_RETURN_SHAPE — currently does NOT.
        with pytest.raises(FileIOError) as exc_info:
            validate_return_value(Path("test.csv"), [["header"], [cell]])
        assert exc_info.value.code == "INVALID_RETURN_SHAPE"

    @pytest.mark.parametrize(
        "cell",
        [
            'safe text\n=HYPERLINK("http://evil.com","click")',
            "normal value\r\n=cmd|'/c calc'!A0",
            "header\r=SUM(1+1)",
        ],
    )
    def test_bypass_embedded_newline_row_splitting(self, cell: str):
        """Embedded newlines bypass the first-character check and split CSV rows.

        The guard inspects v.strip()[0:1] of the *entire* cell value.  A cell
        whose content begins with benign text but contains an embedded newline
        starts with a safe character and is accepted.  When this value is then
        written to a CSV file, the newline breaks the logical row: the text
        after '\\n' becomes the first token of a new CSV row.  If that token
        starts with '=' the spreadsheet application evaluates it as a formula.
        """
        # Should raise ValueError / INVALID_RETURN_SHAPE — currently does NOT.
        with pytest.raises(FileIOError) as exc_info:
            validate_return_value(Path("test.csv"), [["header"], [cell]])
        assert exc_info.value.code == "INVALID_RETURN_SHAPE"

    def test_accepts_tuples_in_multi_sheet(self):
        """Frozen multi-sheet data should be accepted."""
        validate_return_value(
            Path("test.xlsx"),
            {
                "S1": {"columns": ("a",), "rows": ((1,),)},
            },
        )


# ═══════════════════════════════════════════════════════════════════════════
# Deep freeze
# ═══════════════════════════════════════════════════════════════════════════


class TestDeepFreeze:
    def test_lists_become_tuples(self):
        data = [[1, 2], [3, 4]]
        frozen = deep_freeze(data)
        assert isinstance(frozen, tuple)
        assert isinstance(frozen[0], tuple)

    def test_dict_values_frozen(self):
        data = {"S": {"columns": ["a"], "rows": [[1]]}}
        frozen = deep_freeze(data)
        assert isinstance(frozen, MappingProxyType)
        assert isinstance(frozen["S"], MappingProxyType)
        assert isinstance(frozen["S"]["rows"], tuple)

    def test_dict_is_immutable(self):
        frozen = deep_freeze({"a": 1})
        with pytest.raises(TypeError):
            frozen["a"] = 2
        with pytest.raises(TypeError):
            frozen["b"] = 3

    def test_none_passthrough(self):
        assert deep_freeze(None) is None

    def test_primitives_unchanged(self):
        assert deep_freeze(42) == 42
        assert deep_freeze("hello") == "hello"
        assert deep_freeze(True) is True


# ═══════════════════════════════════════════════════════════════════════════
# validate_args_allowed_dirs
# ═══════════════════════════════════════════════════════════════════════════


class TestValidateArgsAllowedDirs:
    def test_none_returns_empty(self):
        assert validate_args_allowed_dirs(None) == []

    def test_empty_list_returns_empty(self):
        assert validate_args_allowed_dirs([]) == []

    def test_existing_dir_resolved(self, tmp_path: Path):
        result = validate_args_allowed_dirs([str(tmp_path)])
        assert len(result) == 1
        assert result[0] == Path(os.path.normpath(tmp_path.resolve(strict=True)))

    def test_nonexistent_dir_still_accepted(self, tmp_path: Path):
        fake = tmp_path / "does_not_exist"
        result = validate_args_allowed_dirs([str(fake)])
        assert len(result) == 1
        assert result[0] == Path(os.path.normpath(fake.resolve(strict=False)))

    def test_multiple_dirs(self, tmp_path: Path):
        d1 = tmp_path / "a"
        d1.mkdir()
        d2 = tmp_path / "b"
        d2.mkdir()
        result = validate_args_allowed_dirs([str(d1), str(d2)])
        assert len(result) == 2

    def test_tilde_expanded(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv("HOME", str(tmp_path))
        result = validate_args_allowed_dirs(["~/mydir"])
        assert len(result) == 1
        assert "~" not in str(result[0])

    def test_returns_path_objects(self, tmp_path: Path):
        result = validate_args_allowed_dirs([str(tmp_path)])
        assert all(isinstance(p, Path) for p in result)
