"""Guards ``COM_METHOD_RULES`` against drift from the real OpenSTAAD API surface.

openstaadpy imports ``comtypes`` at module load, so it cannot be imported on a
non-Windows CI runner — the package is parsed with ``ast`` instead.
"""

import ast
import importlib.util
import re
from pathlib import Path

import pytest

from openstaad_mcp.sandbox.com_proxy import (
    COM_METHOD_RULES,
    _CompositePathRule,
    _DenyRule,
    _PathRule,
)

# Matched against whole tokens of a parameter name, so "loadDirection" and "profile_spec_list"
# are not mistaken for paths. Bare "dir" is excluded on purpose: in OpenSTAAD it always means
# "direction" (as in `forceInXDir`), never a directory. The runtime deny-by-default scan in
# com_proxy covers whatever this naming heuristic misses.
_PATH_TOKENS = frozenset({"path", "file", "filename", "fname", "folder", "directory", "location"})

# Splits both snake_case and camelCase: "FileLocation" -> File, Location; "bFullPath" -> b, Full, Path.
_TOKEN_SPLIT_RE = re.compile(r"[^A-Za-z]+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

# Parameters whose *name* looks path-like but which are not filesystem paths.
# Every entry has been read against the openstaadpy source; adding one is a deliberate
# security review decision, not a way to silence this test.
REVIEWED_NON_PATH_PARAMS: frozenset[tuple[str, str]] = frozenset(
    {
        ("ExportView", "FileFormat"),  # int code: 0=bmp, 1=jpg, 2=tga, 3=tif
        ("GetSTAADFile", "bFullPath"),  # bool: return the full path or just the file name
        # "location" here is a position along a member (start/end), not a filesystem location.
        ("CreateMemberOffsetSpec", "offset_location"),
        ("CreateMemberPartialReleaseSpec", "location"),
        ("CreateMemberReleaseSpec", "offset_location"),
        ("DeleteMemberReleaseSpec", "release_location"),
        ("RemoveMemberOffsetSpecFromBeam", "release_location"),
        ("RemoveMemberReleaseSpecFromBeam", "release_location"),
    }
)


def _is_path_like(param_name: str) -> bool:
    return any(token.lower() in _PATH_TOKENS for token in _TOKEN_SPLIT_RE.split(param_name) if token)


def _openstaadpy_root() -> Path | None:
    """Locate the installed openstaadpy package without importing it."""
    spec = importlib.util.find_spec("openstaadpy")
    if spec is None or spec.origin is None:
        return None
    return Path(spec.origin).parent


def _declared_path_params(method_name: str) -> dict[str, int]:
    """Return the ``{parameter name: index}`` pairs a rule claims are paths."""
    rule = COM_METHOD_RULES.get(method_name)
    if isinstance(rule, _PathRule):
        return {rule.arg.name: rule.arg.index}
    if isinstance(rule, _CompositePathRule):
        return {rule.directory.name: rule.directory.index, rule.filename.name: rule.filename.index}
    return {}


def _iter_public_methods(root: Path):
    """Yield ``(method_name, param_index, param_name)`` for every public method parameter."""
    for source_file in sorted(root.rglob("*.py")):
        tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
        for class_node in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
            if class_node.name.startswith("_"):
                continue
            for method in (n for n in class_node.body if isinstance(n, ast.FunctionDef)):
                if method.name.startswith("_"):
                    continue
                # Drop ``self`` so indices line up with the arguments a caller passes.
                params = [arg.arg for arg in method.args.args if arg.arg != "self"]
                for index, param in enumerate(params):
                    yield method.name, index, param


@pytest.fixture(scope="module")
def openstaadpy_root() -> Path:
    root = _openstaadpy_root()
    if root is None:
        pytest.skip("openstaadpy is not installed")
    return root


def test_every_path_like_parameter_is_covered(openstaadpy_root):
    """Any openstaadpy parameter that looks like a path must be ruled on or explicitly cleared."""
    uncovered = set()
    for method_name, _index, param in _iter_public_methods(openstaadpy_root):
        if not _is_path_like(param):
            continue
        if isinstance(COM_METHOD_RULES.get(method_name), _DenyRule):
            continue
        if param in _declared_path_params(method_name):
            continue
        if (method_name, param) in REVIEWED_NON_PATH_PARAMS:
            continue
        uncovered.add((method_name, param))

    assert not uncovered, (
        "Path-like OpenSTAAD parameters are not covered by COM_METHOD_RULES. Add a rule "
        "(or a _DenyRule), or record the parameter in REVIEWED_NON_PATH_PARAMS after "
        f"confirming it is not a filesystem path: {sorted(uncovered)}"
    )


def test_declared_path_argument_indices_match_the_api(openstaadpy_root):
    """A rule's argument index must match the real openstaadpy signature."""
    actual = {(method_name, param): index for method_name, index, param in _iter_public_methods(openstaadpy_root)}
    mismatches = {
        (method_name, param, declared_index, actual[(method_name, param)])
        for method_name in COM_METHOD_RULES
        for param, declared_index in _declared_path_params(method_name).items()
        if (method_name, param) in actual and actual[(method_name, param)] != declared_index
    }
    assert not mismatches, f"COM_METHOD_RULES argument indices are out of date: {sorted(mismatches)}"


def test_declared_path_arguments_exist_in_the_api(openstaadpy_root):
    """A rule must not reference a parameter openstaadpy does not have."""
    known = {(method_name, param) for method_name, _index, param in _iter_public_methods(openstaadpy_root)}
    missing = {
        (method_name, param)
        for method_name in COM_METHOD_RULES
        for param in _declared_path_params(method_name)
        if (method_name, param) not in known
    }
    assert not missing, f"COM_METHOD_RULES references unknown OpenSTAAD parameters: {sorted(missing)}"
