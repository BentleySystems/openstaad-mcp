"""
COM object proxy for the sandbox.

Wraps pywin32 CDispatch objects to block access to internal attributes
(_oleobj_, _ApplyTypes_, etc.) and validates file-path arguments on
methods that interact with the filesystem.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

# UNC path patterns for detecting NTLM relay attempts in any string argument.
# Covers: \\server\share  //server/share  \\?\UNC\server\share
_UNC_RE = re.compile(r"^(?:\\\\|//|\\\\\?\\UNC\\)", re.ASCII | re.IGNORECASE)


# ---------------------------------------------------------------------------
# Path-validation infrastructure
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _PathRule:
    """Declares which positional arg carries a file path and what extensions are legal."""

    arg_index: int
    allowed_extensions: frozenset[str]

    def validate(self, args: tuple[Any, ...], method_name: str) -> None:
        """Extract the path from *args* and run :func:`validate_file_path`."""
        if self.arg_index >= len(args):
            raise ValueError(f"'{method_name}' requires a file path as positional argument {self.arg_index}")
        validate_file_path(args[self.arg_index], allowed_extensions=self.allowed_extensions, method_name=method_name)


@dataclass(frozen=True)
class _CompositePathRule:
    """Rule for methods where the path is split across two arguments (directory + filename).

    The validator joins ``args[dir_arg_index] / args[name_arg_index]`` into a
    single path before running :func:`validate_file_path`.
    """

    dir_arg_index: int
    name_arg_index: int
    allowed_extensions: frozenset[str]

    def validate(self, args: tuple[Any, ...], method_name: str) -> None:
        """Join directory + filename from *args* and run :func:`validate_file_path`."""
        if self.dir_arg_index >= len(args) or self.name_arg_index >= len(args):
            raise ValueError(
                f"'{method_name}' requires a directory (arg {self.dir_arg_index}) "
                f"and a filename (arg {self.name_arg_index})"
            )
        dir_part = args[self.dir_arg_index]
        name_part = args[self.name_arg_index]
        if not isinstance(dir_part, str) or not isinstance(name_part, str):
            raise ValueError(f"'{method_name}' requires string arguments for directory and filename")
        validate_file_path(
            os.path.join(dir_part, name_part),
            allowed_extensions=self.allowed_extensions,
            method_name=method_name,
        )


# COM methods that accept a filesystem path and must be validated before the
# call is forwarded.  Each entry maps the method name to a rule that describes
# where the path lives and which file extensions are acceptable.
VALIDATED_COM_METHODS: dict[str, _PathRule | _CompositePathRule] = {
    "NewSTAADFile": _PathRule(arg_index=0, allowed_extensions=frozenset({".std"})),
    "OpenSTAADFile": _PathRule(arg_index=0, allowed_extensions=frozenset({".std"})),
    "SaveAs": _PathRule(arg_index=0, allowed_extensions=frozenset({".std"})),
    "ExportView": _CompositePathRule(
        dir_arg_index=0,
        name_arg_index=1,
        allowed_extensions=frozenset({".png", ".jpg", ".jpeg", ".bmp", ".emf", ".wmf"}),
    ),
}

# Normalised directory prefixes (after os.path.splitdrive, lower-cased) that
# must never be written to or read from.
_PROTECTED_DIR_PREFIXES: tuple[str, ...] = (
    os.sep + "windows" + os.sep,
    os.sep + "program files" + os.sep,
    os.sep + "program files (x86)" + os.sep,
    os.sep + "programdata" + os.sep,
    os.sep + "system volume information" + os.sep,
    os.sep + "$recycle.bin" + os.sep,
)


def validate_file_path(
    path: str,
    *,
    allowed_extensions: frozenset[str],
    method_name: str,
) -> None:
    """Raise :class:`ValueError` if *path* is unsafe for a COM file operation.

    Checks performed (in order):
    1. Must be a non-empty string.
    2. Must not be a UNC path (``\\\\...``).
    3. Must be absolute (has a drive letter on Windows).
    4. Must not contain ``..`` segments (path traversal).
    5. Must end with one of the *allowed_extensions*.
    6. Must not target a protected OS directory.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError(f"'{method_name}' requires a non-empty file path string")

    if "\x00" in path:
        raise ValueError(f"Null bytes are not allowed in file paths (blocked in '{method_name}')")

    if _UNC_RE.match(path):
        raise ValueError(f"UNC paths are not allowed (blocked in '{method_name}')")

    # Reject path-traversal sequences in the raw input *before* normalisation,
    # so tricks like "C:\models\..\..\Windows\file.std" are caught immediately.
    if ".." in path.replace("/", os.sep).split(os.sep):
        raise ValueError(f"Path traversal ('..') is not allowed in '{method_name}'")

    # Normalise early so we can reliably check extension and directory.
    try:
        normalized = os.path.normpath(path)
    except (ValueError, OSError) as exc:
        raise ValueError(f"Invalid path passed to '{method_name}': {exc}") from None

    # Must be absolute (drive letter on Windows).
    if not os.path.isabs(normalized):
        raise ValueError(f"'{method_name}' requires an absolute file path, got relative path")

    # Extension check.
    _, ext = os.path.splitext(normalized)
    if ext.lower() not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValueError(f"'{method_name}' only allows files with extensions: {allowed}; got '{ext}'")

    # Protected-directory check.
    _, tail = os.path.splitdrive(normalized.lower())
    tail_with_sep = tail if tail.endswith(os.sep) else tail + os.sep
    for prefix in _PROTECTED_DIR_PREFIXES:
        if tail_with_sep.startswith(prefix):
            raise ValueError(f"'{method_name}' cannot access files in a protected system directory")


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

        obj = object.__getattribute__(self, "_com_obj")
        value = getattr(obj, name)

        # Wrap returned COM sub-objects first (they may also be callable)
        wrapped = _maybe_wrap(value)
        if wrapped is not value:
            return wrapped

        # Wrap callable results to intercept path arguments
        if callable(value):
            rule = VALIDATED_COM_METHODS.get(name)
            if rule is not None:
                return _ValidatedFileMethodWrapper(value, name, rule)
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


class _ValidatedFileMethodWrapper:
    """Wraps a COM method that accepts a filesystem path.

    Runs :func:`validate_file_path` on the designated positional argument
    before forwarding the call, in addition to the standard UNC-path check
    on all string arguments.
    """

    __slots__ = ("_method", "_name", "_rule")

    def __init__(self, method: Any, name: str, rule: _PathRule | _CompositePathRule) -> None:
        object.__setattr__(self, "_method", method)
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_rule", rule)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        name = object.__getattribute__(self, "_name")
        rule: _PathRule | _CompositePathRule = object.__getattribute__(self, "_rule")

        # --- UNC check on every string argument (same as _SafeMethodWrapper) ---
        for arg in args:
            if isinstance(arg, str) and _UNC_RE.match(arg):
                raise ValueError(f"UNC paths are not allowed in COM method calls (blocked in '{name}')")
        for val in kwargs.values():
            if isinstance(val, str) and _UNC_RE.match(val):
                raise ValueError(f"UNC paths are not allowed in COM method calls (blocked in '{name}')")

        # --- Validate the designated path argument(s) ---
        rule.validate(args, name)

        method = object.__getattribute__(self, "_method")
        result = method(*args, **kwargs)
        return _maybe_wrap(result)

    def __repr__(self) -> str:
        name = object.__getattribute__(self, "_name")
        return f"<sandbox validated COM method '{name}'>"


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
