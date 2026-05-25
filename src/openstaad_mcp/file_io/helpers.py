"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Server-level helpers and public dispatch functions for file I/O."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastmcp.server.context import Context
from mcp.shared.exceptions import McpError

from openstaad_mcp.file_io.path_validator import FileIOError, parse_roots_to_dirs, validate_io_path
from openstaad_mcp.file_io.readers import BaseReader, CSVReader, XLSXReader
from openstaad_mcp.file_io.validation import deep_freeze, validate_return_value
from openstaad_mcp.file_io.writers import BaseWriter, CSVWriter, XLSXWriter

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Reader/writer factory helpers
# ═══════════════════════════════════════════════════════════════════════════

_READERS: dict[str, type[BaseReader]] = {".csv": CSVReader, ".xlsx": XLSXReader}
_WRITERS: dict[str, type[BaseWriter]] = {".csv": CSVWriter, ".xlsx": XLSXWriter}


def _get_reader(path: Path) -> BaseReader:
    ext = path.suffix.lower()
    cls = _READERS.get(ext)
    if cls is None:
        raise FileIOError("UNSUPPORTED_FORMAT", f"Cannot read '{ext}' files")
    return cls(path)


def _get_writer(path: Path) -> BaseWriter:
    ext = path.suffix.lower()
    cls = _WRITERS.get(ext)
    if cls is None:
        raise FileIOError("UNSUPPORTED_FORMAT", f"Cannot write '{ext}' files")
    return cls(path)


# ═══════════════════════════════════════════════════════════════════════════
# Public dispatch functions
# ═══════════════════════════════════════════════════════════════════════════


def read_input_file(
    path: Path,
    *,
    sheet: str | None = None,
    start_row: int = 0,
    max_rows: int | None = None,
    has_header: bool | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Read a CSV or XLSX file and return ``(data, summary)``."""
    reader = _get_reader(path)
    data = reader.read(start_row=start_row, max_rows=max_rows, sheet=sheet, has_header=has_header)
    summary = reader.build_summary(data)
    return data, summary


def write_output_file(path: str, data: Any, allowed_dirs: list[Path], *, overwrite: bool = False) -> dict[str, Any]:
    """Validate path, validate return value, write atomically, return summary."""
    resolved = validate_io_path(path, allowed_dirs, mode="write")
    validate_return_value(data)
    writer = _get_writer(resolved)
    return writer.write(data, overwrite=overwrite)


# ═══════════════════════════════════════════════════════════════════════════
# Server-level helpers (called from server.py)
# ═══════════════════════════════════════════════════════════════════════════


async def get_allowed_dirs(
    ctx: Context, args_allowed_dirs: list[Path], input_path: str | None, output_path: str | None
) -> list[Path]:
    """Resolve MCP roots into a list of allowed directories."""
    logger.debug("Args allowed dirs: %s", args_allowed_dirs)
    allowed_dirs: list[Path] = [Path(el) for el in args_allowed_dirs]
    if input_path is not None or output_path is not None:
        try:
            roots = await ctx.list_roots()
            logger.debug(f"Received MCP roots: {roots}")
        except McpError as exc:
            logger.error(f"Error listing MCP roots: {exc}")
            roots = []
        allowed_dirs += parse_roots_to_dirs(roots)
    logger.debug(f"Allowed directories for file I/O: {allowed_dirs}")
    return allowed_dirs


async def get_input_data(input_path: str | None, allowed_dirs: list[Path]) -> tuple[Any, dict[str, Any] | None]:
    """Validate path, read file, freeze data.  Returns ``(data, summary)``."""
    if input_path is None:
        return None, None
    resolved_input = validate_io_path(input_path, allowed_dirs, mode="read")
    data, input_summary = read_input_file(resolved_input)
    return deep_freeze(data), input_summary
