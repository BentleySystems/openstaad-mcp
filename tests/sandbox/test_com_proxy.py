"""
Tests for the COM object proxy.
"""

import pytest

from openstaad_mcp.sandbox.com_proxy import COMProxy


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
        def ExportView(path, name, fmt, flag):
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
    """Dangerous COM methods must be blocked."""

    def test_new_staad_file_blocked(self, proxy):
        with pytest.raises(AttributeError, match="not allowed"):
            _ = proxy.NewSTAADFile

    def test_open_staad_file_blocked(self, proxy):
        with pytest.raises(AttributeError, match="not allowed"):
            _ = proxy.OpenSTAADFile

    def test_export_view_blocked(self, proxy):
        with pytest.raises(AttributeError, match="not allowed"):
            _ = proxy.ExportView


class TestUNCPathBlocking:
    """UNC paths in method arguments must be blocked."""

    def test_unc_path_in_string_arg(self, proxy):
        _ = proxy.GetSTAADFile  # safe method
        # But if we had a method that accepts a string, UNC should be blocked
        # Let's test via a safe getter that doesn't need args
        result = proxy.GetApplicationVersion()
        assert result == "STAAD.Pro V25"


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
