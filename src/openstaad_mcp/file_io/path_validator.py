"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Shared path validator for file I/O operations.

Validates that a file path is safe to read from or write to, using
MCP roots as the containment boundary.  Both ``input_path`` and
``output_path`` go through :func:`validate_io_path` — one function,
not duplicated logic.

Validation order (do **not** reorder — see Research-file-io.md §5.2):
1. Roots guard   — at least one allowed directory must be provided.
2. Resolve       — canonicalise the path (collapse ``..``, follow symlinks).
3. UNC reject    — resolved path must not be a network path.
4. Containment   — resolved path must be inside at least one allowed dir.
5. Extension     — must be ``.csv`` or ``.xlsx``.
6. Existence     — read: file must exist; write: parent dir must exist.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlparse

from openstaad_mcp.file_io.const import ALLOWED_FILE_EXTENSIONS

_UNC_RE = re.compile(r"^(?:\\\\|//)", re.ASCII)


class FileIOError(Exception):
    """Structured error with a machine-readable ``code`` and human-readable ``message``."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def parse_roots_to_dirs(roots: list) -> list[Path]:
    """Convert MCP ``Root`` objects (with ``file://`` URIs) to local ``Path`` instances.

    Non-``file://`` URIs are silently skipped.
    """
    dirs: list[Path] = []
    for root in roots:
        uri: str = root.uri if hasattr(root, "uri") else str(root)
        parsed = urlparse(uri)
        if parsed.scheme != "file":
            continue
        # RFC 8089: file:///C:/path → parsed.path = "/C:/path"
        # The leading "/" is an artifact of the URI authority; strip it
        # before the Windows drive letter so Path() resolves correctly.
        local = unquote(parsed.path)
        if local.startswith("/") and len(local) > 2 and local[2] == ":":
            local = local[1:]  # /C:/foo → C:/foo
        dirs.append(Path(local))
    return dirs


def validate_io_path(
    raw_path: str,
    allowed_dirs: list[Path],
    *,
    mode: Literal["read", "write"],
) -> Path:
    """Validate *raw_path* for a file I/O operation and return the resolved path.

    Parameters
    ----------
    raw_path:
        The user-supplied file path (may be relative or contain ``..``).
    allowed_dirs:
        Directories the server is allowed to access (from MCP roots).
    mode:
        ``"read"`` requires the file to exist; ``"write"`` requires the
        parent directory to exist.

    Returns
    -------
    Path
        The resolved, canonical path.

    Raises
    ------
    FileIOError
        With a machine-readable ``code`` describing the failure.
    """
    # ── 1. Roots guard ───────────────────────────────────────────────
    if not allowed_dirs:
        raise FileIOError(
            "NO_ROOTS",
            "No allowed directories configured. Please instruct your user to go update their settings for that extension",
        )

    # Reject null bytes early (before Path() which may raise on some OSes).
    if "\x00" in raw_path:
        raise FileIOError("UNSUPPORTED_FORMAT", "Null bytes are not allowed in file paths")

    # ── 2. Resolve ───────────────────────────────────────────────────
    try:
        resolved = Path(raw_path).resolve()
    except (OSError, ValueError) as exc:
        raise FileIOError("UNSUPPORTED_FORMAT", f"Invalid path: {exc}") from None

    # ── 3. UNC reject ────────────────────────────────────────────────
    resolved_str = str(resolved)
    if _UNC_RE.match(resolved_str):
        raise FileIOError("UNC_REJECTED", "Network paths (UNC) are not allowed")

    # ── 4. Containment ───────────────────────────────────────────────
    inside_any = False
    for root_dir in allowed_dirs:
        try:
            resolved.relative_to(root_dir.resolve())
            inside_any = True
            break
        except ValueError:
            continue
    if not inside_any:
        raise FileIOError(
            "PATH_OUTSIDE_ROOTS",
            f"Path is outside all allowed directories: {resolved}",
        )

    # ── 5. Extension ─────────────────────────────────────────────────
    ext = resolved.suffix.lower()
    if ext not in ALLOWED_FILE_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_FILE_EXTENSIONS))
        raise FileIOError(
            "UNSUPPORTED_FORMAT",
            f"Extension '{ext}' is not supported. Allowed: {allowed}",
        )

    # ── 6. Existence ─────────────────────────────────────────────────
    if mode == "read":
        if not resolved.is_file():
            raise FileIOError("FILE_NOT_FOUND", f"File does not exist: {resolved}")
    else:  # write
        if not resolved.parent.is_dir():
            raise FileIOError(
                "PARENT_DIR_MISSING",
                f"Parent directory does not exist: {resolved.parent}",
            )

    return resolved
