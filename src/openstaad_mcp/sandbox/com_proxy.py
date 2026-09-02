"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

COM object proxy for the sandbox.

Wraps pywin32 CDispatch objects to block access to internal attributes
(_oleobj_, _ApplyTypes_, etc.) and validates the arguments of every COM call.

Validation is deny-by-default: a per-method rule in :data:`COM_METHOD_RULES` gives the
strict treatment (argument position, extension allowlist, or an outright deny), and
*every* string argument of *every* call additionally goes through
:func:`_scan_string_args`.  An earlier version validated only the handful of methods
named in the registry, which let unlisted path-taking COM methods through unchecked.
"""

from __future__ import annotations

import ntpath
import re
from dataclasses import dataclass
from typing import Any

# UNC path patterns for detecting NTLM relay attempts in any string argument.
# Covers: \\server\share  //server/share  \\?\UNC\server\share
_UNC_RE = re.compile(r"^(?:\\\\|//|\\\\\?\\UNC\\)", re.ASCII | re.IGNORECASE)

# Strings shaped like a filesystem root: "C:\...", "C:/...", "\..." or "/...".
# Deliberately narrow, so ordinary STAAD arguments (unit strings such as "kN/m2",
# section names, free-text job info) are not mistaken for paths.
_PATH_SHAPE_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/])", re.ASCII)

# Windows expands %VAR% when opening a file, which can hide a protected directory.
_ENV_VAR_RE = re.compile(r"%[A-Za-z_][A-Za-z0-9_()]*%", re.ASCII)

# 8.3 short names ("PROGRA~1") alias long directory names past the protected-prefix check.
_SHORT_NAME_RE = re.compile(r"~\d", re.ASCII)

_SEPARATOR_RE = re.compile(r"[\\/]")


# ---------------------------------------------------------------------------
# Path-validation infrastructure
# ---------------------------------------------------------------------------


_MISSING = object()


@dataclass(frozen=True)
class _Arg:
    """One COM method argument, addressable either positionally or by keyword."""

    index: int
    name: str

    def resolve(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any:
        """Return the supplied value, or :data:`_MISSING` if the caller omitted it."""
        if self.index < len(args):
            return args[self.index]
        return kwargs.get(self.name, _MISSING)


class _NullRule:
    """Rule for methods with no declared path argument; the generic scan still applies."""

    def validate(self, args: tuple[Any, ...], kwargs: dict[str, Any], method_name: str) -> None:
        """Accept any arguments."""


@dataclass(frozen=True)
class _DenyRule:
    """Rule for COM methods that have no legitimate use inside the sandbox."""

    reason: str

    def validate(self, args: tuple[Any, ...], kwargs: dict[str, Any], method_name: str) -> None:
        """Always raise :class:`ValueError`."""
        raise ValueError(f"'{method_name}' is not available in the sandbox: {self.reason}")


@dataclass(frozen=True)
class _PathRule:
    """Declares which argument carries a file path and what extensions are legal."""

    arg: _Arg
    allowed_extensions: frozenset[str]
    optional: bool = False

    def validate(self, args: tuple[Any, ...], kwargs: dict[str, Any], method_name: str) -> None:
        """Extract the path argument and run :func:`validate_file_path`."""
        path = self.arg.resolve(args, kwargs)
        if self.optional and (path is _MISSING or path is None):
            return
        if path is _MISSING:
            raise ValueError(f"'{method_name}' requires a file path argument '{self.arg.name}'")
        validate_file_path(path, allowed_extensions=self.allowed_extensions, method_name=method_name)


@dataclass(frozen=True)
class _CompositePathRule:
    """Rule for methods where the path is split across two arguments (directory + filename).

    The validator joins *directory* and *filename* into a single path before running
    :func:`validate_file_path`. An extension present in the filename must match the
    extension(s) implied by *format_arg* — catching a caller passing e.g. a ".jpg" filename
    with a TIF format code. A bare filename (no extension at all) is always allowed, since the
    extension is only used to catch a *mismatch*, never to require one.
    """

    directory: _Arg
    filename: _Arg
    allowed_extensions: frozenset[str]
    format_arg: _Arg
    format_extension_map: dict[int, frozenset[str]]

    def validate(self, args: tuple[Any, ...], kwargs: dict[str, Any], method_name: str) -> None:
        """Join directory + filename and run :func:`validate_file_path`."""
        dir_part = self.directory.resolve(args, kwargs)
        name_part = self.filename.resolve(args, kwargs)
        if not isinstance(dir_part, str) or not isinstance(name_part, str):
            raise ValueError(
                f"'{method_name}' requires string arguments for '{self.directory.name}' and '{self.filename.name}'"
            )

        validate_file_path(
            ntpath.join(dir_part, name_part),
            allowed_extensions=self._expected_extensions(args, kwargs),
            method_name=method_name,
            extension_optional=True,
        )

    def _expected_extensions(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> frozenset[str]:
        """Narrow the allowlist to the format the caller asked for, if it is a known code."""
        return self.format_extension_map.get(self.format_arg.resolve(args, kwargs), self.allowed_extensions)


_MethodRule = _PathRule | _CompositePathRule | _DenyRule | _NullRule
_NULL_RULE = _NullRule()


# Defaults to the currently open model when omitted; STAAD derives the .anl log from the .std.
_ANALYSIS_MODEL_PATH_RULE = _PathRule(_Arg(0, "modelPath"), frozenset({".std"}), optional=True)

# Per-method rules applied before a COM call is forwarded.  Methods absent from this mapping
# are NOT unvalidated: they fall back to _NULL_RULE and still go through _scan_string_args.
COM_METHOD_RULES: dict[str, _MethodRule] = {
    "NewSTAADFile": _PathRule(_Arg(0, "fileName"), frozenset({".std"})),
    "OpenSTAADFile": _PathRule(_Arg(0, "file"), frozenset({".std"})),
    "GetAnalysisStatus": _ANALYSIS_MODEL_PATH_RULE,
    "GetAnalysisErrorMessages": _ANALYSIS_MODEL_PATH_RULE,
    "GetAnalysisWarningMessages": _ANALYSIS_MODEL_PATH_RULE,
    "ExportView": _CompositePathRule(
        directory=_Arg(0, "FileLocation"),
        filename=_Arg(1, "FileName"),
        # Real supported formats per openstaadpy's ExportView FileFormat codes: 0=bmp, 1=jpg, 2=tga, 3=tif.
        # STAAD.Pro always appends its own extension for FileFormat on top of whatever FileName is given,
        # so a caller-supplied extension ends up doubled on disk (e.g. "foo.tif" -> "foo.tif.tif") -- this
        # is expected/harmless. A bare filename (no extension) is also accepted here since COM itself does
        # not require one, but has been observed to behave unreliably; recommend always supplying the
        # extension matching FileFormat (arg 2) -- validated here to catch a mismatch (e.g. a ".jpg"
        # filename passed with FileFormat=3/tif) before it silently produces a confusing result.
        allowed_extensions=frozenset({".bmp", ".jpg", ".jpeg", ".tga", ".tif", ".tiff"}),
        format_arg=_Arg(2, "FileFormat"),
        format_extension_map={
            0: frozenset({".bmp"}),
            1: frozenset({".jpg", ".jpeg"}),
            2: frozenset({".tga"}),
            3: frozenset({".tif", ".tiff"}),
        },
    ),
    "SetStandardProfileDBFolder": _DenyRule(
        "it repoints the STAAD.Pro profile database at another folder, which configures the "
        "application rather than the model; change it in the STAAD.Pro UI instead"
    ),
}

# Normalised directory prefixes (after ntpath.splitdrive, lower-cased) that
# must never be written to or read from.
_PROTECTED_DIR_PREFIXES: tuple[str, ...] = (
    "\\windows\\",
    "\\program files\\",
    "\\program files (x86)\\",
    "\\programdata\\",
    "\\system volume information\\",
    "\\$recycle.bin\\",
)


def _reject_escape_primitives(value: str, method_name: str) -> None:
    """Reject the sequences that let a string escape its intended directory.

    Applied to *every* string argument of *every* COM call, because none of these is ever
    legitimate content in a STAAD.Pro argument.
    """
    if "\x00" in value:
        raise ValueError(f"Null bytes are not allowed (blocked in '{method_name}')")

    if _UNC_RE.match(value):
        raise ValueError(f"UNC paths are not allowed (blocked in '{method_name}')")

    segments = _SEPARATOR_RE.split(value)
    if ".." in segments:
        raise ValueError(f"Path traversal ('..') is not allowed in '{method_name}'")

    # The remaining checks only make sense once a string spans directories — a lone "50%"
    # or a section name like "W14~1" is not a path.
    if len(segments) == 1:
        return

    if _ENV_VAR_RE.search(value):
        raise ValueError(f"Environment variables are not allowed in paths (blocked in '{method_name}')")

    if any(_SHORT_NAME_RE.search(segment) for segment in segments):
        raise ValueError(f"8.3 short names are not allowed in paths (blocked in '{method_name}')")


def _reject_protected_directory(tail: str, method_name: str) -> None:
    # Windows trims trailing dots and spaces from each path segment, so "C:\Windows.\x" lands
    # in the real Windows directory and would otherwise slip past the prefix comparison.
    trimmed = ntpath.sep.join(segment.rstrip(". ") for segment in tail.lower().split(ntpath.sep))
    if not trimmed.endswith(ntpath.sep):
        trimmed += ntpath.sep
    if trimmed.startswith(_PROTECTED_DIR_PREFIXES):
        raise ValueError(f"'{method_name}' cannot access files in a protected system directory")


def _validate_path_core(path: str, method_name: str) -> str:
    """Validate the shape of *path* and return it normalised.

    Uses ``ntpath`` rather than ``os.path`` so the rules stay identical on the Windows target
    and on whichever platform the unit tests happen to run on.

    Checks performed (in order):
    1. Must be a non-empty string.
    2. Must contain no escape primitives (null byte, UNC, ``..``, ``%VAR%``, 8.3 short name).
    3. Must be absolute, with a drive letter.
    4. Must not target a protected OS directory.
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError(f"'{method_name}' requires a non-empty file path string")

    _reject_escape_primitives(path, method_name)

    try:
        normalized = ntpath.normpath(path)
    except (ValueError, OSError) as exc:
        raise ValueError(f"Invalid path passed to '{method_name}': {exc}") from None

    # A drive letter alone is not enough: "C:models\f.std" is relative to the drive's CWD.
    drive, tail = ntpath.splitdrive(normalized)
    if not drive or not tail.startswith(ntpath.sep):
        raise ValueError(f"'{method_name}' requires an absolute file path, got relative path")

    _reject_protected_directory(tail, method_name)
    return normalized


def validate_file_path(
    path: str,
    *,
    allowed_extensions: frozenset[str],
    method_name: str,
    extension_optional: bool = False,
) -> None:
    """Raise :class:`ValueError` if *path* is unsafe, or does not carry an allowed extension.

    *extension_optional* permits a path with no extension at all, for COM methods that append
    their own.
    """
    normalized = _validate_path_core(path, method_name)

    _, ext = ntpath.splitext(normalized)
    if not (extension_optional and ext == "") and ext.lower() not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValueError(f"'{method_name}' only allows files with extensions: {allowed}; got '{ext}'")


def _validate_untyped_arg(value: str, method_name: str) -> None:
    """Deny-by-default check for a string argument that no explicit rule covers.

    The full path validation only runs on strings shaped like a filesystem root; the extension
    allowlist cannot be applied because the method's intent is unknown.
    """
    _reject_escape_primitives(value, method_name)
    if _PATH_SHAPE_RE.match(value):
        _validate_path_core(value, method_name)


def _scan_string_args(args: tuple[Any, ...], kwargs: dict[str, Any], method_name: str) -> None:
    """Run :func:`_validate_untyped_arg` over every string argument of a COM call."""
    for value in (*args, *kwargs.values()):
        if isinstance(value, str):
            _validate_untyped_arg(value, method_name)


class COMProxy:
    """Runtime proxy that restricts attribute access on COM dispatch objects.

    Blocks:
    - Single-underscore pywin32 internals (_oleobj_, _ApplyTypes_, etc.)
    - Dunder attributes (__class__, __init__, etc.)
    - Unsafe arguments on every COM method call (see :func:`_scan_string_args`)

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
            return _MethodWrapper(value, name, COM_METHOD_RULES.get(name, _NULL_RULE))

        return value

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("cannot set attributes on COM objects in the sandbox")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("cannot delete attributes on COM objects in the sandbox")

    def __repr__(self) -> str:
        return "<sandbox COM proxy>"


class _MethodWrapper:
    """Wraps a COM method so its arguments are validated before the call is forwarded.

    The method's :data:`COM_METHOD_RULES` entry runs first (it produces the most specific
    error), followed by the deny-by-default scan of every string argument.
    """

    __slots__ = ("_method", "_name", "_rule")

    def __init__(self, method: Any, name: str, rule: _MethodRule) -> None:
        object.__setattr__(self, "_method", method)
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_rule", rule)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        name = object.__getattribute__(self, "_name")
        rule: _MethodRule = object.__getattribute__(self, "_rule")

        rule.validate(args, kwargs, name)
        _scan_string_args(args, kwargs, name)

        method = object.__getattribute__(self, "_method")
        result = method(*args, **kwargs)
        return _maybe_wrap(result)

    def __repr__(self) -> str:
        name = object.__getattribute__(self, "_name")
        return f"<sandbox COM method '{name}'>"


# Types returned as-is by COM/openstaadpy calls that never need (and cannot usefully be)
# wrapped in a COMProxy — everything else (raw COM dispatch objects, and openstaadpy's
# own Python sub-API wrapper instances such as OSGeometry/OSView/OSLoad, which are plain
# Python objects with NO `_oleobj_`) gets wrapped so their methods stay subject to the same
# argument validation and internal-attribute blocking as the root object.
_PASSTHROUGH_TYPES = (str, bytes, int, float, bool, complex, type(None))
_PASSTHROUGH_CONTAINER_TYPES = (list, tuple, dict, set, frozenset)


def _maybe_wrap(value: Any) -> Any:
    """Wrap any non-primitive, non-callable object so nested method calls stay validated.

    Classes are wrapped even though they are technically callable (constructing them), since
    they're used here as plain namespace containers, never instantiated. Other callables (bound
    methods, raw COM method wrappers) are left untouched — they are wrapped separately by the
    caller via ``_MethodWrapper``.
    """
    if isinstance(value, type):
        return COMProxy(value)
    if callable(value):
        return value
    if isinstance(value, _PASSTHROUGH_TYPES + _PASSTHROUGH_CONTAINER_TYPES):
        return value
    return COMProxy(value)
