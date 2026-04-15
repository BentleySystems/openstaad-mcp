from __future__ import annotations

import io
import re as _re
from typing import Any

from openstaad_mcp.sandbox.const import MAX_EXECUTION_STDOUT, MAX_RESULT_LENGTH


class LimitedStringIO(io.StringIO):
    """StringIO wrapper that silently discards writes beyond a size limit."""

    def __init__(self, max_size: int = MAX_EXECUTION_STDOUT) -> None:
        super().__init__()
        self._max_size = max_size
        self._size = 0

    def write(self, s: str) -> int:
        if self._size >= self._max_size:
            return 0
        remaining = self._max_size - self._size
        to_write = s[:remaining]
        written = super().write(to_write)
        self._size += written
        return written


_PATH_RE = _re.compile(r'File "(?!<sandbox>).*?"')


def sanitize_traceback(exc: BaseException) -> str:
    """Format an exception traceback, filtering out non-sandbox frames and paths.

    Only frames from ``<sandbox>`` are shown in detail. External frames are
    summarised to prevent leaking filesystem paths and usernames.
    """
    tb_lines: list[str] = []
    tb_lines.append("Traceback (most recent call last):\n")

    # Walk the traceback chain and only include sandbox frames
    tb = exc.__traceback__
    has_sandbox_frame = False
    while tb is not None:
        frame = tb.tb_frame
        filename = frame.f_code.co_filename
        if filename == "<sandbox>":
            has_sandbox_frame = True
            lineno = tb.tb_lineno
            name = frame.f_code.co_name
            tb_lines.append(f'  File "<sandbox>", line {lineno}, in {name}\n')
        tb = tb.tb_next

    if not has_sandbox_frame:
        tb_lines.append("  (in external code)\n")

    # Add the exception type and message (sanitize any paths in the message)
    exc_str = f"{type(exc).__name__}: {exc}"
    exc_str = _PATH_RE.sub('File "<internal>"', exc_str)
    tb_lines.append(exc_str + "\n")

    return "".join(tb_lines)


def sanitize_output(value: Any) -> Any:
    """Sanitize output values to mitigate indirect prompt injection.

    Truncates large strings and adds a data provenance marker so AI agents
    know the data comes from an external model file.
    """
    if isinstance(value, str):
        if len(value) > MAX_RESULT_LENGTH:
            value = value[:MAX_RESULT_LENGTH] + "... (truncated)"
        return value
    if isinstance(value, list):
        return [sanitize_output(item) for item in value]
    if isinstance(value, dict):
        return {k: sanitize_output(v) for k, v in value.items()}
    return value
