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
        def ExportView(FileLocation, FileName, FileFormat, Overwrite):
            return True

    class Property:
        _oleobj_ = "property-dispatch"

        @staticmethod
        def SetStandardProfileDBFolder(folder_path):
            return True

        @staticmethod
        def GetStandardProfileDBFolder():
            return "C:\\Sections"

        @staticmethod
        def GetStandardSectionName(section_property_id):
            return "W14X90"

    class _PlainSubObjectImpl:
        """Mimics openstaadpy's real sub-API shape: a plain Python instance with NO
        `_oleobj_` (e.g. `OSView`/`OSGeometry`), unlike the `View`/`Geometry` fakes above.
        """

        @staticmethod
        def ExportView(FileLocation, FileName, FileFormat, Overwrite):
            return True

        @staticmethod
        def _internal():
            return "secret"

    PlainSubObject = _PlainSubObjectImpl()

    @staticmethod
    def GetApplicationVersion():
        return "STAAD.Pro V25"

    @staticmethod
    def NewSTAADFile(fileName, lengthUnit, forceUnit):
        return True

    @staticmethod
    def OpenSTAADFile(file):
        return True

    @staticmethod
    def GetAnalysisStatus(modelPath=None):
        return {"ReturnValue": 0}

    @staticmethod
    def CloseSTAADFile():
        return True

    @staticmethod
    def SaveAs(path):
        return True

    @staticmethod
    def SetShortJobInfo(text):
        return True

    @staticmethod
    def SetInputUnits(unit):
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

    # -- CloseSTAADFile (no path arg — always allowed) -------------------------

    def test_close_staad_file_allowed(self, proxy):
        assert proxy.CloseSTAADFile() is True

    # -- Optional path argument (GetAnalysisStatus) ----------------------------

    def test_analysis_status_without_path_allowed(self, proxy):
        assert proxy.GetAnalysisStatus() == {"ReturnValue": 0}

    def test_analysis_status_explicit_none_allowed(self, proxy):
        assert proxy.GetAnalysisStatus(None) == {"ReturnValue": 0}

    def test_analysis_status_valid_path_allowed(self, proxy):
        assert proxy.GetAnalysisStatus("C:\\models\\bridge.std") == {"ReturnValue": 0}

    def test_analysis_status_keyword_path_validated(self, proxy):
        with pytest.raises(ValueError, match="extensions"):
            proxy.GetAnalysisStatus(modelPath="C:\\models\\bridge.txt")

    def test_analysis_status_protected_dir(self, proxy):
        with pytest.raises(ValueError, match="protected"):
            proxy.GetAnalysisStatus("C:\\Windows\\bridge.std")

    # -- Missing / malformed rule arguments fail closed ------------------------

    def test_open_staad_file_missing_path_argument(self, proxy):
        with pytest.raises(ValueError, match="requires a file path argument"):
            proxy.OpenSTAADFile()

    def test_open_staad_file_keyword_path_validated(self, proxy):
        with pytest.raises(ValueError, match="traversal"):
            proxy.OpenSTAADFile(file="C:\\models\\..\\..\\Windows\\model.std")

    def test_export_view_non_string_path_arguments(self, proxy):
        view = proxy.View
        with pytest.raises(ValueError, match="requires string arguments"):
            view.ExportView(1, 2, 0, 0)

    # -- ExportView (composite path: directory + filename on sub-object) ------

    def test_export_view_valid_bmp(self, proxy):
        view = proxy.View
        assert view.ExportView("C:\\exports", "view.bmp", 0, 0) is True

    def test_export_view_valid_jpg(self, proxy):
        view = proxy.View
        assert view.ExportView("C:\\exports", "view.jpg", 1, 0) is True

    def test_export_view_valid_jpeg(self, proxy):
        view = proxy.View
        assert view.ExportView("C:\\exports", "view.jpeg", 1, 0) is True

    def test_export_view_valid_tga(self, proxy):
        view = proxy.View
        assert view.ExportView("C:\\exports", "view.tga", 2, 0) is True

    def test_export_view_valid_tif(self, proxy):
        view = proxy.View
        assert view.ExportView("C:\\exports", "view.tif", 3, 0) is True

    def test_export_view_valid_tiff(self, proxy):
        view = proxy.View
        assert view.ExportView("C:\\exports", "view.tiff", 3, 0) is True

    def test_export_view_bare_filename_allowed(self, proxy):
        # A bare filename (no extension) is the normal, correct usage — openstaadpy's
        # ExportView strips any caller-supplied extension anyway before calling COM.
        view = proxy.View
        assert view.ExportView("C:\\exports", "view", 1, 0) is True

    def test_export_view_extension_mismatches_format(self, proxy):
        # A .jpg filename with FileFormat=3 (tif) must be rejected as a mismatch, not
        # silently accepted just because .jpg is a generally-valid ExportView extension.
        view = proxy.View
        with pytest.raises(ValueError, match="extensions"):
            view.ExportView("C:\\exports", "view.jpg", 3, 0)

    def test_export_view_unknown_format_falls_back_to_any_allowed_extension(self, proxy):
        # An unrecognised FileFormat code falls back to the general allowed-extensions set.
        view = proxy.View
        assert view.ExportView("C:\\exports", "view.tga", 99, 0) is True

    def test_export_view_png_now_rejected(self, proxy):
        """PNG was never a real ExportView format — must be rejected, not accepted."""
        view = proxy.View
        with pytest.raises(ValueError, match="extensions"):
            view.ExportView("C:\\exports", "view.png", 1, 0)

    def test_export_view_emf_now_rejected(self, proxy):
        view = proxy.View
        with pytest.raises(ValueError, match="extensions"):
            view.ExportView("C:\\exports", "view.emf", 1, 0)

    def test_export_view_wmf_now_rejected(self, proxy):
        view = proxy.View
        with pytest.raises(ValueError, match="extensions"):
            view.ExportView("C:\\exports", "view.wmf", 1, 0)

    def test_export_view_wrong_extension(self, proxy):
        view = proxy.View
        with pytest.raises(ValueError, match="extensions"):
            view.ExportView("C:\\exports", "view.exe", 1, 0)

    def test_export_view_unc_dir(self, proxy):
        view = proxy.View
        with pytest.raises(ValueError, match="UNC"):
            view.ExportView("\\\\server\\share", "view.bmp", 0, 0)

    def test_export_view_protected_dir(self, proxy):
        view = proxy.View
        with pytest.raises(ValueError, match="protected"):
            view.ExportView("C:\\Windows", "view.bmp", 0, 0)

    def test_export_view_traversal_in_dir(self, proxy):
        view = proxy.View
        with pytest.raises(ValueError, match="traversal"):
            view.ExportView("C:\\exports\\..\\..\\Windows", "view.bmp", 0, 0)

    def test_export_view_traversal_in_filename(self, proxy):
        view = proxy.View
        with pytest.raises(ValueError, match="traversal"):
            view.ExportView("C:\\exports", "..\\..\\Windows\\view.bmp", 0, 0)

    def test_export_view_null_byte_in_filename(self, proxy):
        view = proxy.View
        with pytest.raises(ValueError, match="Null bytes"):
            view.ExportView("C:\\exports", "view.bmp\x00.exe", 1, 0)

    # -- Regression: plain (non-COM) sub-objects must ALSO be validated -------

    def test_plain_sub_object_export_view_still_validated(self, proxy):
        """openstaadpy sub-API objects (OSView, OSGeometry, ...) are plain Python
        instances with no `_oleobj_` — they must still be wrapped and validated,
        not bypass the sandbox entirely.
        """
        plain = proxy.PlainSubObject
        with pytest.raises(ValueError, match="extensions"):
            plain.ExportView("C:\\exports", "view.exe", 0, 0)
        assert plain.ExportView("C:\\exports", "view.bmp", 0, 0) is True

    def test_plain_sub_object_internal_attr_blocked(self, proxy):
        plain = proxy.PlainSubObject
        with pytest.raises(AttributeError, match="not allowed"):
            _ = plain._internal


class TestDenyByDefaultScan:
    """Security Report 2121043: methods with no explicit rule were forwarded unvalidated.

    `SaveAs` is deliberately absent from COM_METHOD_RULES here — it stands in for any
    path-accepting COM method that has not been enumerated yet.
    """

    def test_unlisted_method_rejects_traversal(self, proxy):
        with pytest.raises(ValueError, match="traversal"):
            proxy.SaveAs("C:\\Users\\victim\\models\\..\\..\\..\\Windows\\System32\\drivers\\etc")

    def test_unlisted_method_rejects_protected_dir(self, proxy):
        with pytest.raises(ValueError, match="protected"):
            proxy.SaveAs("C:\\Windows\\System32\\payload.std")

    def test_unlisted_method_rejects_unc(self, proxy):
        with pytest.raises(ValueError, match="UNC"):
            proxy.SaveAs("\\\\attacker\\share\\payload.std")

    def test_unlisted_method_rejects_env_var(self, proxy):
        with pytest.raises(ValueError, match="Environment variables"):
            proxy.SaveAs("%WINDIR%\\System32\\payload.std")

    def test_unlisted_method_rejects_short_name(self, proxy):
        with pytest.raises(ValueError, match="short names"):
            proxy.SaveAs("C:\\PROGRA~1\\payload.std")

    def test_unlisted_method_rejects_rooted_path_without_drive(self, proxy):
        with pytest.raises(ValueError, match="absolute"):
            proxy.SaveAs("\\models\\payload.std")

    def test_unlisted_method_rejects_null_byte(self, proxy):
        with pytest.raises(ValueError, match="Null bytes"):
            proxy.SaveAs("C:\\models\\payload.std\x00.exe")

    def test_unlisted_method_rejects_traversal_in_keyword_arg(self, proxy):
        with pytest.raises(ValueError, match="traversal"):
            proxy.SaveAs(path="C:\\models\\..\\..\\Windows\\payload.std")

    def test_unlisted_method_allows_ordinary_path(self, proxy):
        assert proxy.SaveAs("C:\\models\\report.pdf") is True

    def test_unlisted_method_allows_drive_root(self, proxy):
        assert proxy.SaveAs("C:\\") is True


class TestNonPathArgumentsAllowed:
    """The scan must not reject ordinary STAAD strings that merely resemble paths."""

    def test_unit_string_with_slash_allowed(self, proxy):
        assert proxy.SetInputUnits("kN/m2") is True

    def test_free_text_with_backslash_allowed(self, proxy):
        assert proxy.SetShortJobInfo("ACME\\Engineering") is True

    def test_free_text_with_percent_allowed(self, proxy):
        assert proxy.SetShortJobInfo("50% design capacity") is True

    def test_free_text_with_ellipsis_allowed(self, proxy):
        assert proxy.SetShortJobInfo("Phase 2... pending review") is True

    def test_section_name_with_tilde_digit_allowed(self, proxy):
        assert proxy.SetShortJobInfo("W14~1") is True

    def test_colon_prefixed_text_allowed(self, proxy):
        assert proxy.SetShortJobInfo("E: 29000 ksi") is True

    def test_integer_args_ignored(self, proxy):
        assert proxy.NewSTAADFile("C:\\models\\new_model.std", 1, 0) is True


class TestDeniedMethods:
    """Config-mutating COM methods with no sandbox use case are denied outright."""

    def test_set_standard_profile_db_folder_denied(self, proxy):
        prop = proxy.Property
        with pytest.raises(ValueError, match="not available in the sandbox"):
            prop.SetStandardProfileDBFolder("C:\\Sections")

    def test_set_standard_profile_db_folder_denied_for_valid_looking_path(self, proxy):
        prop = proxy.Property
        with pytest.raises(ValueError, match="not available in the sandbox"):
            prop.SetStandardProfileDBFolder("C:\\Users\\me\\Sections")

    def test_profile_db_getter_still_allowed(self, proxy):
        prop = proxy.Property
        assert prop.GetStandardProfileDBFolder() == "C:\\Sections"

    def test_other_property_methods_still_allowed(self, proxy):
        prop = proxy.Property
        assert prop.GetStandardSectionName(1) == "W14X90"


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

    def test_trailing_dot_directory_does_not_bypass_protected_dir(self):
        # Windows trims the trailing dot, so this resolves into the real C:\Windows.
        with pytest.raises(ValueError, match="protected"):
            validate_file_path("C:\\Windows.\\f.std", allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_trailing_space_directory_does_not_bypass_protected_dir(self):
        with pytest.raises(ValueError, match="protected"):
            validate_file_path("C:\\Windows \\f.std", allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_short_name_rejected(self):
        with pytest.raises(ValueError, match="short names"):
            validate_file_path("C:\\PROGRA~1\\f.std", allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_environment_variable_rejected(self):
        with pytest.raises(ValueError, match="Environment variables"):
            validate_file_path("%WINDIR%\\f.std", allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_drive_relative_path_rejected(self):
        # "C:models\f.std" is relative to the drive's current directory, not absolute.
        with pytest.raises(ValueError, match="absolute"):
            validate_file_path("C:models\\f.std", allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_rooted_path_without_drive_rejected(self):
        with pytest.raises(ValueError, match="absolute"):
            validate_file_path("\\models\\f.std", allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_forward_slash_absolute_path_passes(self):
        validate_file_path("C:/models/test.std", allowed_extensions=frozenset({".std"}), method_name="Test")

    def test_extension_optional_allows_bare_name(self):
        validate_file_path(
            "C:\\exports\\view",
            allowed_extensions=frozenset({".bmp"}),
            method_name="Test",
            extension_optional=True,
        )

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValueError, match="non-empty"):
            validate_file_path("   ", allowed_extensions=frozenset({".std"}), method_name="Test")


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
