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
        data = {f"S{i}": {"columns": ["a"], "rows": [[1]]} for i in range(21)}
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
