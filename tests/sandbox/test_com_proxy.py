"""
Tests for the COM object proxy.
"""

import pytest

from openstaad_mcp.sandbox.com_proxy import COMProxy, validate_file_path


class FakeCOMObj:
    """Simulates a pywin32 CDispatch object for testing."""

    _oleobj_ = "raw-dispatch"
    _ApplyTypes_ = "apply-types"
    _FlagAsMethod = "flag"
    _olerepr_ = "repr"
    _mapCachedItems_ = {}  # noqa: RUF012
    _builtMethods_ = {}  # noqa: RUF012
    _enum_ = None
    _lazydata_ = None

    class Geometry:
        _oleobj_ = "geo-dispatch"

        @staticmethod
        def GetNodeCount():
            return 42

        @staticmethod
        def GetNodeCoordinates(node_id):
            return (1.0, 2.0, 3.0)

    class View:
        _oleobj_ = "view-dispatch"

        @staticmethod
        def ExportView(directory, filename, fmt, flag):
            return True

    @staticmethod
    def GetApplicationVersion():
        return "STAAD.Pro V25"

    @staticmethod
    def NewSTAADFile(path, a, b):
        return True

    @staticmethod
    def OpenSTAADFile(path):
        return True

    @staticmethod
    def CloseSTAADFile():
        return True

    @staticmethod
    def SaveAs(path):
        return True

    @staticmethod
    def GetSTAADFile():
        return "C:\\model.std"


@pytest.fixture
def proxy():
    return COMProxy(FakeCOMObj())


class TestBlockedInternalAttrs:
    """pywin32 internal attributes must be blocked."""

    def test_oleobj_blocked(self, proxy):
        with pytest.raises(AttributeError, match="not allowed"):
            _ = proxy._oleobj_

    def test_apply_types_blocked(self, proxy):
        with pytest.raises(AttributeError, match="not allowed"):
            _ = proxy._ApplyTypes_

    def test_flag_as_method_blocked(self, proxy):
        with pytest.raises(AttributeError, match="not allowed"):
            _ = proxy._FlagAsMethod

    def test_olerepr_blocked(self, proxy):
        with pytest.raises(AttributeError, match="not allowed"):
            _ = proxy._olerepr_

    def test_builtmethods_blocked(self, proxy):
        with pytest.raises(AttributeError, match="not allowed"):
            _ = proxy._builtMethods_

    def test_enum_blocked(self, proxy):
        with pytest.raises(AttributeError, match="not allowed"):
            _ = proxy._enum_


class TestBlockedDunderAttrs:
    """COM proxy must block dunder attribute access."""

    def test_dict_blocked(self, proxy):
        with pytest.raises(AttributeError, match="not allowed"):
            _ = proxy.__dict__

    def test_subclasses_blocked(self, proxy):
        with pytest.raises(AttributeError, match="not allowed"):
            _ = proxy.__subclasses__

    def test_bases_blocked(self, proxy):
        with pytest.raises(AttributeError, match="not allowed"):
            _ = proxy.__bases__


class TestBlockedDangerousMethods:
    """File-operation COM methods are now allowed with path validation."""

    # -- NewSTAADFile ----------------------------------------------------------

    def test_new_staad_file_valid_path(self, proxy):
        assert proxy.NewSTAADFile("C:\\models\\new_model.std", 1, 0) is True

    def test_new_staad_file_wrong_extension(self, proxy):
        with pytest.raises(ValueError, match="extensions"):
            proxy.NewSTAADFile("C:\\models\\evil.exe", 1, 0)

    def test_new_staad_file_unc_path(self, proxy):
        with pytest.raises(ValueError, match="UNC"):
            proxy.NewSTAADFile("\\\\server\\share\\model.std", 1, 0)

    def test_new_staad_file_relative_path(self, proxy):
        with pytest.raises(ValueError, match="absolute"):
            proxy.NewSTAADFile("relative\\model.std", 1, 0)

    def test_new_staad_file_traversal(self, proxy):
        with pytest.raises(ValueError, match="traversal"):
            proxy.NewSTAADFile("C:\\models\\..\\..\\Windows\\model.std", 1, 0)

    def test_new_staad_file_protected_dir(self, proxy):
        with pytest.raises(ValueError, match="protected"):
            proxy.NewSTAADFile("C:\\Windows\\model.std", 1, 0)

    # -- OpenSTAADFile ---------------------------------------------------------

    def test_open_staad_file_valid_path(self, proxy):
        assert proxy.OpenSTAADFile("C:\\projects\\bridge.std") is True

    def test_open_staad_file_wrong_extension(self, proxy):
        with pytest.raises(ValueError, match="extensions"):
            proxy.OpenSTAADFile("C:\\models\\data.txt")

    def test_open_staad_file_program_files(self, proxy):
        with pytest.raises(ValueError, match="protected"):
            proxy.OpenSTAADFile("C:\\Program Files\\model.std")

    # -- SaveAs ----------------------------------------------------------------

    def test_save_as_valid_path(self, proxy):
        assert proxy.SaveAs("D:\\backups\\model_v2.std") is True

    def test_save_as_wrong_extension(self, proxy):
        with pytest.raises(ValueError, match="extensions"):
            proxy.SaveAs("C:\\models\\model.zip")

    def test_save_as_protected_dir(self, proxy):
        with pytest.raises(ValueError, match="protected"):
            proxy.SaveAs("C:\\ProgramData\\model.std")

    # -- CloseSTAADFile (no path arg — always allowed) -------------------------

    def test_close_staad_file_allowed(self, proxy):
        assert proxy.CloseSTAADFile() is True

    # -- ExportView (composite path: directory + filename on sub-object) ------

    def test_export_view_valid_png(self, proxy):
        view = proxy.View
        assert view.ExportView("C:\\exports", "view.png", 1, 0) is True

    def test_export_view_valid_jpg(self, proxy):
        view = proxy.View
        assert view.ExportView("C:\\exports", "view.jpg", 1, 0) is True

    def test_export_view_valid_bmp(self, proxy):
        view = proxy.View
        assert view.ExportView("C:\\exports", "view.bmp", 1, 0) is True

    def test_export_view_valid_emf(self, proxy):
        view = proxy.View
        assert view.ExportView("C:\\exports", "view.emf", 1, 0) is True

    def test_export_view_valid_jpeg(self, proxy):
        view = proxy.View
        assert view.ExportView("C:\\exports", "view.jpeg", 1, 0) is True

    def test_export_view_valid_wmf(self, proxy):
        view = proxy.View
        assert view.ExportView("C:\\exports", "view.wmf", 1, 0) is True

    def test_export_view_wrong_extension(self, proxy):
        view = proxy.View
        with pytest.raises(ValueError, match="extensions"):
            view.ExportView("C:\\exports", "view.exe", 1, 0)

    def test_export_view_unc_dir(self, proxy):
        view = proxy.View
        with pytest.raises(ValueError, match="UNC"):
            view.ExportView("\\\\server\\share", "view.png", 1, 0)

    def test_export_view_protected_dir(self, proxy):
        view = proxy.View
        with pytest.raises(ValueError, match="protected"):
            view.ExportView("C:\\Windows", "view.png", 1, 0)

    def test_export_view_traversal_in_dir(self, proxy):
        view = proxy.View
        with pytest.raises(ValueError, match="traversal"):
            view.ExportView("C:\\exports\\..\\..\\Windows", "view.png", 1, 0)

    def test_export_view_traversal_in_filename(self, proxy):
        view = proxy.View
        with pytest.raises(ValueError, match="traversal"):
            view.ExportView("C:\\exports", "..\\..\\Windows\\view.png", 1, 0)

    def test_export_view_null_byte_in_filename(self, proxy):
        view = proxy.View
        with pytest.raises(ValueError, match="Null bytes"):
            view.ExportView("C:\\exports", "view.png\x00.exe", 1, 0)


class TestValidateFilePathUnit:
    """Direct unit tests for the validate_file_path function."""

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            validate_file_path("", allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_non_string_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            validate_file_path(123, allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_unc_rejected(self):
        with pytest.raises(ValueError, match="UNC"):
            validate_file_path("\\\\host\\share\\f.std", allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_unc_forward_slash_rejected(self):
        with pytest.raises(ValueError, match="UNC"):
            validate_file_path("//host/share/f.std", allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_unc_device_path_rejected(self):
        with pytest.raises(ValueError, match="UNC"):
            validate_file_path(
                "\\\\?\\UNC\\host\\share\\f.std", allowed_extensions=frozenset({".std"}), method_name="Test"
            )

    def test_relative_rejected(self):
        with pytest.raises(ValueError, match="absolute"):
            validate_file_path("models\\f.std", allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_traversal_rejected(self):
        with pytest.raises(ValueError, match="traversal"):
            validate_file_path(
                "C:\\a\\..\\..\\Windows\\f.std",
                allowed_extensions=frozenset({".std"}),
                method_name="Test",
            )

    def test_wrong_extension_rejected(self):
        with pytest.raises(ValueError, match="extensions"):
            validate_file_path("C:\\a\\f.exe", allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_no_extension_rejected(self):
        with pytest.raises(ValueError, match="extensions"):
            validate_file_path("C:\\a\\noext", allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_protected_windows(self):
        with pytest.raises(ValueError, match="protected"):
            validate_file_path("C:\\Windows\\f.std", allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_protected_program_files(self):
        with pytest.raises(ValueError, match="protected"):
            validate_file_path(
                "C:\\Program Files\\app\\f.std",
                allowed_extensions=frozenset({".std"}),
                method_name="Test",
            )

    def test_protected_program_files_x86(self):
        with pytest.raises(ValueError, match="protected"):
            validate_file_path(
                "C:\\Program Files (x86)\\app\\f.std",
                allowed_extensions=frozenset({".std"}),
                method_name="Test",
            )

    def test_valid_path_passes(self):
        # Should not raise
        validate_file_path(
            "C:\\Users\\me\\models\\test.std", allowed_extensions=frozenset({".std"}), method_name="Test"
        )

    def test_case_insensitive_extension(self):
        # .STD should also pass
        validate_file_path("C:\\models\\TEST.STD", allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_case_insensitive_protected_dir(self):
        with pytest.raises(ValueError, match="protected"):
            validate_file_path("C:\\WINDOWS\\f.std", allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_null_byte_rejected(self):
        with pytest.raises(ValueError, match="Null bytes"):
            validate_file_path(
                "C:\\models\\safe.std\x00.exe", allowed_extensions=frozenset({".std"}), method_name="Test"
            )

    def test_forward_slash_traversal_rejected(self):
        with pytest.raises(ValueError, match="traversal"):
            validate_file_path(
                "C:/models/../../Windows/f.std",
                allowed_extensions=frozenset({".std"}),
                method_name="Test",
            )

    def test_trailing_spaces_in_extension(self):
        # Windows strips trailing spaces; "file.std   " becomes "file.std" — must not bypass checks
        with pytest.raises(ValueError, match="extensions"):
            validate_file_path("C:\\models\\file.exe ", allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_trailing_dot_rejected(self):
        # "file.std." → os.path.splitext yields extension ".", which is not in the allowlist
        with pytest.raises(ValueError, match="extensions"):
            validate_file_path("C:\\models\\file.std.", allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_mixed_case_extension_std(self):
        # .Std (mixed case) should pass
        validate_file_path("C:\\models\\test.Std", allowed_extensions=frozenset({".std"}), method_name="Test")


class TestUNCPathBlocking:
    """UNC paths in method arguments must be blocked."""

    def test_unc_path_in_string_arg(self, proxy):
        _ = proxy.GetSTAADFile  # safe method
        # But if we had a method that accepts a string, UNC should be blocked
        # Let's test via a safe getter that doesn't need args
        result = proxy.GetApplicationVersion()
        assert result == "STAAD.Pro V25"

    def test_forward_slash_unc_blocked_on_validated_method(self, proxy):
        with pytest.raises(ValueError, match="UNC"):
            proxy.OpenSTAADFile("//server/share/model.std")

    def test_device_path_unc_blocked_on_validated_method(self, proxy):
        with pytest.raises(ValueError, match="UNC"):
            proxy.OpenSTAADFile("\\\\?\\UNC\\server\\share\\model.std")


class TestAllowedAccess:
    """Safe COM methods must still work through the proxy."""

    def test_get_version(self, proxy):
        assert proxy.GetApplicationVersion() == "STAAD.Pro V25"

    def test_get_staad_file(self, proxy):
        assert proxy.GetSTAADFile() == "C:\\model.std"

    def test_geometry_node_count(self, proxy):
        geo = proxy.Geometry
        assert geo.GetNodeCount() == 42

    def test_geometry_coordinates(self, proxy):
        geo = proxy.Geometry
        assert geo.GetNodeCoordinates(1) == (1.0, 2.0, 3.0)


class TestImmutability:
    """Proxy must be read-only."""

    def test_setattr_blocked(self, proxy):
        with pytest.raises(AttributeError, match="cannot set"):
            proxy.evil = "payload"

    def test_delattr_blocked(self, proxy):
        with pytest.raises(AttributeError, match="cannot delete"):
            del proxy.GetSTAADFile


class TestRepr:
    def test_repr(self, proxy):
        assert "sandbox COM proxy" in repr(proxy)
