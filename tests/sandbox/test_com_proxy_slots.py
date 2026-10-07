"""Regression tests for private slot access through sandbox COM proxies."""

import pytest

from openstaad_mcp.sandbox.ast import validate_code
from openstaad_mcp.sandbox.com_proxy import COMProxy
from openstaad_mcp.sandbox.executor import Executor


class SlottedStaad:
    __slots__ = ("Property", "View", "calls", "returned")

    def __init__(self):
        self.calls = []
        self.Property = self
        self.View = self
        self.returned = None

    def OpenSTAADFile(self, file):
        self.calls.append(("OpenSTAADFile", file))
        return True

    def SetStandardProfileDBFolder(self, folder):
        self.calls.append(("SetStandardProfileDBFolder", folder))
        return True

    def ExportView(self, directory, filename, file_format, overwrite=True):
        self.calls.append(("ExportView", directory, filename, file_format, overwrite))
        return True

    def GetReturnedObject(self):
        return self.returned


@pytest.fixture
def raw_staad():
    return SlottedStaad()


@pytest.mark.parametrize("target", ["root", "sub_api", "method"])
@pytest.mark.parametrize(
    "name",
    ["_com_obj", "_method", "_name", "_rule", "_oleobj_", "_unknown", "__class__", "__init__", "__slots__"],
)
def test_private_attributes_are_blocked_before_slot_lookup(raw_staad, target, name):
    proxy = COMProxy(raw_staad)
    targets = {"root": proxy, "sub_api": proxy.Property, "method": proxy.OpenSTAADFile}

    with pytest.raises(AttributeError, match="not allowed"):
        getattr(targets[target], name)

    assert raw_staad.calls == []


@pytest.mark.parametrize("target", ["root", "method"])
@pytest.mark.parametrize("name", ["_com_obj", "_method", "_name", "_rule", "public"])
@pytest.mark.parametrize("operation", ["set", "delete"])
def test_proxy_and_method_attributes_are_read_only(raw_staad, target, name, operation):
    proxy = COMProxy(raw_staad)
    wrapped = proxy if target == "root" else proxy.OpenSTAADFile

    with pytest.raises(AttributeError, match=f"cannot {operation}"):
        if operation == "set":
            setattr(wrapped, name, None)
        else:
            delattr(wrapped, name)

    assert proxy.OpenSTAADFile(r"C:\models\bridge.std") is True
    assert raw_staad.calls == [("OpenSTAADFile", r"C:\models\bridge.std")]


@pytest.mark.parametrize(
    "code",
    [
        r"leak = staad._com_obj; leak.SetStandardProfileDBFolder(r'C:\profiles')",
        r"staad._com_obj.OpenSTAADFile(r'\\server\share\evil.std')",
        r"staad.OpenSTAADFile._method(r'\\server\share\evil.std')",
        r"staad.OpenSTAADFile._method(r'C:\Windows\System32\payload.exe')",
        r"staad.ExportView._method(r'C:\Windows\Temp', 'shot', 0)",
        r"staad.Property._com_obj.SetStandardProfileDBFolder(r'C:\profiles')",
        r"staad.View.ExportView._method(r'C:\exports\..\..\Windows\System32', 'x.scr', 0, True)",
        "staad.OpenSTAADFile._method = staad.SetStandardProfileDBFolder",
        "staad.OpenSTAADFile._rule = None",
        "staad.OpenSTAADFile._name = 'UnlistedMethod'",
        "del staad.OpenSTAADFile._rule",
        "staad.OpenSTAADFile._rule.validate = staad.OpenSTAADFile",
    ],
)
def test_executor_blocks_slot_bypasses_without_calling_raw_api(raw_staad, code):
    # These payloads reach the runtime guard rather than relying on an AST name blocklist.
    assert validate_code(code).is_valid

    result = Executor().execute(code, raw_staad)

    assert result.success is False
    assert "AttributeError" in result.error
    assert raw_staad.calls == []


@pytest.mark.parametrize(
    ("code", "error"),
    [
        (r"staad.OpenSTAADFile(r'\\server\share\evil.std')", "UNC"),
        (r"staad.OpenSTAADFile(r'C:\Windows\evil.std')", "protected"),
        (r"staad.OpenSTAADFile(r'C:\models\payload.exe')", "extensions"),
        (r"staad.Property.SetStandardProfileDBFolder(r'C:\profiles')", "not allowed"),
        (r"staad.View.ExportView(r'C:\exports\..\..\Windows\System32', 'x.scr', 0, True)", "traversal"),
    ],
)
def test_executor_keeps_existing_com_policies(raw_staad, code, error):
    result = Executor().execute(code, raw_staad)

    assert result.success is False
    assert error in result.error
    assert raw_staad.calls == []


@pytest.mark.parametrize(
    ("value", "expression"),
    [
        ("scalar", "staad.GetReturnedObject()"),
        ("list", "staad.GetReturnedObject()[0]"),
        ("tuple", "staad.GetReturnedObject()[0]"),
        ("nested", "staad.GetReturnedObject()['items'][0][0]"),
        ("keys", "next(iter(staad.GetReturnedObject()))"),
        ("set", "next(iter(staad.GetReturnedObject()))"),
        ("frozenset", "next(iter(staad.GetReturnedObject()))"),
    ],
)
def test_returned_slotted_objects_keep_runtime_guards(raw_staad, value, expression):
    child = SlottedStaad()
    raw_staad.returned = {
        "scalar": child,
        "list": [child],
        "tuple": (child,),
        "nested": {"items": ([child],)},
        "keys": {child: "value"},
        "set": {child},
        "frozenset": frozenset({child}),
    }[value]
    executor = Executor()

    for suffix in ("._com_obj", ".OpenSTAADFile._method", r".SetStandardProfileDBFolder(r'C:\profiles')"):
        result = executor.execute(expression + suffix, raw_staad)
        assert result.success is False
        assert "not allowed" in result.error
        assert child.calls == []

    allowed = executor.execute(expression + r".OpenSTAADFile(r'C:\models\bridge.std')", raw_staad)
    assert allowed.success is True
    assert allowed.result is True
    assert child.calls == [("OpenSTAADFile", r"C:\models\bridge.std")]


def test_proxy_special_methods_still_work_implicitly(raw_staad):
    proxy = COMProxy(raw_staad)
    method = proxy.OpenSTAADFile

    assert callable(method)
    assert repr(proxy) == "<sandbox COM proxy>"
    assert repr(method) == "<sandbox COM method 'OpenSTAADFile'>"
    assert isinstance(proxy, COMProxy)
    with pytest.raises(AttributeError):
        _ = proxy.MissingPublicMember
    with pytest.raises(AttributeError):
        _ = method.MissingPublicMember


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("staad", "<sandbox COM proxy>"),
        ("staad.OpenSTAADFile", "<sandbox COM method 'OpenSTAADFile'>"),
        ("[staad]", "[<sandbox COM proxy>]"),
        ("{'method': staad.OpenSTAADFile}", "{'method': <sandbox COM method 'OpenSTAADFile'>}"),
    ],
)
def test_executor_preserves_repr_fallback_for_proxy_results(raw_staad, code, expected):
    result = Executor().execute(code, raw_staad)

    assert result.success is True
    assert result.result == expected
