"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Tests for the ModuleProxy sandbox wrapper.
"""

import json
import math

import pytest

from openstaad_mcp.sandbox.module_proxy import ModuleProxy


@pytest.fixture
def json_proxy():
    return ModuleProxy(json, frozenset({"dumps", "loads"}))


@pytest.fixture
def math_proxy():
    return ModuleProxy(math, frozenset({"sqrt", "pi", "ceil"}))


class TestAllowedAccess:
    """Whitelisted attributes are accessible."""

    def test_call_allowed_function(self, json_proxy):
        assert json_proxy.dumps({"a": 1}) == '{"a": 1}'

    def test_call_second_allowed_function(self, json_proxy):
        assert json_proxy.loads('{"b": 2}') == {"b": 2}

    def test_access_allowed_constant(self, math_proxy):
        assert math_proxy.pi == math.pi

    def test_call_allowed_math_function(self, math_proxy):
        assert math_proxy.sqrt(144) == 12.0

    def test_call_ceil(self, math_proxy):
        assert math_proxy.ceil(1.2) == 2


class TestBlockedAccess:
    """Non-whitelisted attributes raise AttributeError."""

    def test_blocked_attribute(self, json_proxy):
        with pytest.raises(AttributeError, match=r"not available.*sandbox"):
            _ = json_proxy.encoder

    def test_blocked_dunder(self, json_proxy):
        with pytest.raises(AttributeError, match=r"not available.*sandbox"):
            _ = json_proxy.__file__

    def test_blocked_math_attribute(self, math_proxy):
        with pytest.raises(AttributeError, match=r"not available.*sandbox"):
            _ = math_proxy.log  # not in the allowed set

    def test_error_message_includes_module_name(self, json_proxy):
        with pytest.raises(AttributeError, match="'json'"):
            _ = json_proxy.encoder

    def test_error_message_includes_attr_name(self, json_proxy):
        with pytest.raises(AttributeError, match="'encoder'"):
            _ = json_proxy.encoder

    def test_internal_module_reference_blocked(self, json_proxy):
        with pytest.raises(AttributeError, match=r"not available.*sandbox"):
            _ = json_proxy._proxy_module

    def test_internal_allowed_set_blocked(self, json_proxy):
        with pytest.raises(AttributeError, match=r"not available.*sandbox"):
            _ = json_proxy._proxy_allowed


class TestImmutability:
    """Proxy is read-only: setattr and delattr are blocked."""

    def test_setattr_blocked(self, json_proxy):
        with pytest.raises(AttributeError, match="cannot set"):
            json_proxy.dumps = lambda x: x

    def test_delattr_blocked(self, json_proxy):
        with pytest.raises(AttributeError, match="cannot delete"):
            del json_proxy.dumps

    def test_setattr_new_attr_blocked(self, json_proxy):
        with pytest.raises(AttributeError, match="cannot set"):
            json_proxy.evil = "payload"


class TestRepr:
    """repr() shows a clear sandbox label."""

    def test_repr_json(self, json_proxy):
        assert repr(json_proxy) == "<sandbox module 'json'>"

    def test_repr_math(self, math_proxy):
        assert repr(math_proxy) == "<sandbox module 'math'>"


class TestEmptyAllowedSet:
    """Proxy with no allowed attributes blocks everything."""

    def test_all_access_blocked(self):
        proxy = ModuleProxy(json, frozenset())
        with pytest.raises(AttributeError, match="not available"):
            _ = proxy.dumps


class TestModuleGraphTraversal:
    """Ensure module-graph traversal attacks are blocked."""

    def test_codecs_not_reachable_via_json(self, json_proxy):
        with pytest.raises(AttributeError, match="not available"):
            _ = json_proxy.codecs

    def test_builtins_not_reachable(self, json_proxy):
        with pytest.raises(AttributeError, match="not available"):
            _ = json_proxy.__builtins__

    def test_submodule_not_reachable(self, json_proxy):
        with pytest.raises(AttributeError, match="not available"):
            _ = json_proxy.decoder
