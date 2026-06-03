"""
Tests for the file I/O path validator.

RED phase — these tests define the expected behavior of
``validate_io_path`` before the implementation exists.
"""

from pathlib import Path

import pytest

from openstaad_mcp.file_io.path_validator import FileIOError, validate_io_path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def model_dir(tmp_path: Path) -> Path:
    """Create a temporary 'model directory' with a sample CSV."""
    csv = tmp_path / "data.csv"
    csv.write_text("a,b\n1,2\n", encoding="utf-8")
    xlsx = tmp_path / "data.xlsx"
    xlsx.write_bytes(b"fake-xlsx")  # existence check only
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.csv").write_text("x\n1\n", encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Roots guard
# ---------------------------------------------------------------------------


class TestRootsGuard:
    """Rejects when no allowed directories are provided."""

    def test_empty_allowed_dirs_read(self):
        with pytest.raises(FileIOError) as exc_info:
            validate_io_path("anything.csv", [], mode="read")
        assert exc_info.value.code == "NO_ROOTS"

    def test_empty_allowed_dirs_write(self):
        with pytest.raises(FileIOError) as exc_info:
            validate_io_path("anything.csv", [], mode="write")
        assert exc_info.value.code == "NO_ROOTS"


# ---------------------------------------------------------------------------
# Resolution & containment
# ---------------------------------------------------------------------------


class TestResolutionAndContainment:
    """Resolve before containment check — critical ordering."""

    def test_path_traversal_rejected(self, model_dir: Path):
        """Path that starts with model_dir but resolves outside it."""
        evil = str(model_dir / ".." / ".." / "Windows" / "evil.csv")
        with pytest.raises(FileIOError) as exc_info:
            validate_io_path(evil, [model_dir], mode="read")
        assert exc_info.value.code == "PATH_OUTSIDE_ROOTS"

    def test_path_inside_root_accepted(self, model_dir: Path):
        path = str(model_dir / "data.csv")
        result = validate_io_path(path, [model_dir], mode="read")
        assert result == (model_dir / "data.csv").resolve()

    def test_subdirectory_accepted(self, model_dir: Path):
        path = str(model_dir / "sub" / "nested.csv")
        result = validate_io_path(path, [model_dir], mode="read")
        assert result == (model_dir / "sub" / "nested.csv").resolve()

    def test_multiple_roots_any_match(self, model_dir: Path, tmp_path: Path):
        """Path inside any of the provided roots passes."""
        other_root = tmp_path / "other"
        other_root.mkdir()
        (other_root / "file.csv").write_text("x\n", encoding="utf-8")

        result = validate_io_path(
            str(other_root / "file.csv"),
            [model_dir, other_root],
            mode="read",
        )
        assert result == (other_root / "file.csv").resolve()

    def test_outside_all_roots_rejected(self, model_dir: Path):
        outside = model_dir.parent / "outside_root"
        outside.mkdir(exist_ok=True)
        (outside / "bad.csv").write_text("x\n", encoding="utf-8")

        with pytest.raises(FileIOError) as exc_info:
            validate_io_path(str(outside / "bad.csv"), [model_dir], mode="read")
        assert exc_info.value.code == "PATH_OUTSIDE_ROOTS"


# ---------------------------------------------------------------------------
# UNC rejection
# ---------------------------------------------------------------------------


class TestUNCRejection:
    """Blocks network paths (UNC) to prevent NTLM relay."""

    def test_backslash_unc(self, model_dir: Path):
        with pytest.raises(FileIOError) as exc_info:
            validate_io_path("\\\\server\\share\\file.csv", [model_dir], mode="read")
        assert exc_info.value.code == "UNC_REJECTED"

    def test_forward_slash_unc(self, model_dir: Path):
        with pytest.raises(FileIOError) as exc_info:
            validate_io_path("//server/share/file.csv", [model_dir], mode="read")
        assert exc_info.value.code == "UNC_REJECTED"


# ---------------------------------------------------------------------------
# Extension check
# ---------------------------------------------------------------------------


class TestExtensionCheck:
    """Only .csv and .xlsx are allowed."""

    @pytest.mark.parametrize("ext", [".xls", ".xlsm", ".tsv", ".txt", ".exe", ".py"])
    def test_unsupported_extension_rejected(self, model_dir: Path, ext: str):
        path = str(model_dir / f"file{ext}")
        with pytest.raises(FileIOError) as exc_info:
            validate_io_path(path, [model_dir], mode="read")
        assert exc_info.value.code == "UNSUPPORTED_FORMAT"

    def test_csv_allowed(self, model_dir: Path):
        result = validate_io_path(str(model_dir / "data.csv"), [model_dir], mode="read")
        assert result.suffix == ".csv"

    def test_xlsx_allowed(self, model_dir: Path):
        result = validate_io_path(str(model_dir / "data.xlsx"), [model_dir], mode="read")
        assert result.suffix == ".xlsx"

    def test_case_insensitive(self, model_dir: Path):
        upper = model_dir / "DATA.CSV"
        upper.write_text("a\n", encoding="utf-8")
        result = validate_io_path(str(upper), [model_dir], mode="read")
        assert result.suffix.lower() == ".csv"


# ---------------------------------------------------------------------------
# Existence checks
# ---------------------------------------------------------------------------


class TestExistenceChecks:
    """Read mode: file must exist.  Write mode: parent must exist."""

    def test_read_nonexistent_file(self, model_dir: Path):
        with pytest.raises(FileIOError) as exc_info:
            validate_io_path(str(model_dir / "missing.csv"), [model_dir], mode="read")
        assert exc_info.value.code == "FILE_NOT_FOUND"

    def test_write_nonexistent_parent(self, model_dir: Path):
        with pytest.raises(FileIOError) as exc_info:
            validate_io_path(
                str(model_dir / "no_such_dir" / "out.csv"),
                [model_dir],
                mode="write",
            )
        assert exc_info.value.code == "PARENT_DIR_MISSING"

    def test_write_existing_parent_ok(self, model_dir: Path):
        """Write to a file whose parent exists — should succeed."""
        result = validate_io_path(
            str(model_dir / "new_output.csv"),
            [model_dir],
            mode="write",
        )
        assert result.parent == model_dir.resolve()

    def test_write_to_subdirectory(self, model_dir: Path):
        result = validate_io_path(
            str(model_dir / "sub" / "new.xlsx"),
            [model_dir],
            mode="write",
        )
        assert result.parent == (model_dir / "sub").resolve()


# ---------------------------------------------------------------------------
# Null bytes
# ---------------------------------------------------------------------------


class TestNullBytes:
    def test_null_byte_rejected(self, model_dir: Path):
        with pytest.raises(FileIOError):
            validate_io_path(
                str(model_dir / "file\x00.csv"),
                [model_dir],
                mode="read",
            )


# ---------------------------------------------------------------------------
# FileIOError structure
# ---------------------------------------------------------------------------


class TestFileIOError:
    def test_has_code_and_message(self):
        err = FileIOError("TEST_CODE", "some detail")
        assert err.code == "TEST_CODE"
        assert err.message == "some detail"
        assert "TEST_CODE" in str(err)
