"""
COM object proxy for the sandbox.

Wraps pywin32 CDispatch objects to block access to internal attributes
(_oleobj_, _ApplyTypes_, etc.) and dangerous methods that accept file paths.
"""

from __future__ import annotations

import re
from typing import Any

# COM methods that accept filesystem paths and must be blocked.
# These can write files, open UNC paths (NTLM relay), or modify the model file.
BLOCKED_COM_METHODS: frozenset[str] = frozenset(
    {
        "NewSTAADFile",
        "OpenSTAADFile",
        "SaveAs",
        "CloseSTAADFile",
        "ExportView",
    }
)

# UNC path pattern for detecting NTLM relay attempts in any string argument
_UNC_RE = re.compile(r"^\\\\", re.ASCII)


class COMProxy:
    """Runtime proxy that restricts attribute access on COM dispatch objects.

    Blocks:
    - Single-underscore pywin32 internals (_oleobj_, _ApplyTypes_, etc.)
    - Dunder attributes (__class__, __init__, etc.)
    - Dangerous COM methods that accept filesystem paths

    Recursively wraps returned COM sub-objects so that sub-APIs
    (e.g. staad.Geometry, staad.View) are also protected.
    """

    __slots__ = ("_com_obj",)

    def __init__(self, com_obj: Any) -> None:
        object.__setattr__(self, "_com_obj", com_obj)

    def __getattr__(self, name: str) -> Any:
        # Block dunder attributes
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(f"access to '{name}' is not allowed on COM objects in the sandbox")
        # Block pywin32 internal attributes (single underscore prefix)
        if name.startswith("_"):
            raise AttributeError(f"access to '{name}' is not allowed on COM objects in the sandbox")
        # Block dangerous COM methods
        if name in BLOCKED_COM_METHODS:
            raise AttributeError(f"'{name}' is not allowed in the sandbox (filesystem operation)")

        obj = object.__getattribute__(self, "_com_obj")
        value = getattr(obj, name)

        # Wrap returned COM sub-objects first (they may also be callable)
        wrapped = _maybe_wrap(value)
        if wrapped is not value:
            return wrapped

        # Wrap callable results to intercept path arguments
        if callable(value):
            return _SafeMethodWrapper(value, name)

        return value

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("cannot set attributes on COM objects in the sandbox")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("cannot delete attributes on COM objects in the sandbox")

    def __repr__(self) -> str:
        return "<sandbox COM proxy>"


class _SafeMethodWrapper:
    """Wraps a COM method to validate arguments before calling."""

    __slots__ = ("_method", "_name")

    def __init__(self, method: Any, name: str) -> None:
        object.__setattr__(self, "_method", method)
        object.__setattr__(self, "_name", name)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        # Check all string arguments for UNC paths
        for arg in args:
            if isinstance(arg, str) and _UNC_RE.match(arg):
                name = object.__getattribute__(self, "_name")
                raise ValueError(f"UNC paths are not allowed in COM method calls (blocked in '{name}')")
        for val in kwargs.values():
            if isinstance(val, str) and _UNC_RE.match(val):
                name = object.__getattribute__(self, "_name")
                raise ValueError(f"UNC paths are not allowed in COM method calls (blocked in '{name}')")
        method = object.__getattribute__(self, "_method")
        result = method(*args, **kwargs)
        return _maybe_wrap(result)

    def __repr__(self) -> str:
        name = object.__getattribute__(self, "_name")
        return f"<sandbox COM method '{name}'>"


def _maybe_wrap(value: Any) -> Any:
    """Wrap COM dispatch objects recursively; pass through primitives."""
    # Check if it looks like a COM dispatch wrapper.
    # For instances: check the type.  For classes used as sub-objects
    # (e.g. staad.Geometry returning a class), check the value directly.
    if hasattr(type(value), "_oleobj_") or (isinstance(value, type) and hasattr(value, "_oleobj_")):
        return COMProxy(value)
    # Also wrap plain class objects used as namespace containers (e.g. in tests
    # or non-COM sub-objects).  This ensures recursive protection even when the
    # underlying object is not a true COM dispatch.
    if isinstance(value, type):
        return COMProxy(value)
    return value
