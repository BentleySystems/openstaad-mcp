# File I/O Implementation Plan

**Purpose:** Step-by-step checklist for implementing `read_tabular_data` and `write_tabular_data` as described in [file-io-design.md](file-io-design.md). Each step is a discrete, testable action. Complete them in order.

**Reference files you should read before starting:**

- [file-io-design.md](file-io-design.md) — the full design specification. This is your source of truth.
- `src/openstaad_mcp/server.py` — existing tool registrations, `_register_tools()` pattern, `_resolve_target()` helper, `_safe_error_message()`.
- `src/openstaad_mcp/connection.py` — `connect_and_run()` for COM thread calls, `StaadInstance`, `InstanceRegistry`.
- `src/openstaad_mcp/skills.py` — example of a helper module that `server.py` imports.
- `tests/test_skills.py` — test style reference (pytest, `tmp_path` fixture, `unittest.mock.patch`).
- `pyproject.toml` — dependency declarations, build config, ruff settings.
- `CHANGELOG.md` — format for the changelog entry you will write at the end.

---

## Phase 1: Dependencies

- [ ] **1.1** Add `openpyxl==3.1.5` and `defusedxml==0.7.1` to `[project].dependencies` in `pyproject.toml`. Place them after the existing `extism` line. Use exact pins (`==`).

- [ ] **1.2** Run `uv sync` (or `pip install -e .`) to verify the new deps resolve cleanly.

---

## Phase 2: Path validation module

Create `src/openstaad_mcp/file_io.py`. This module holds all file I/O logic (path validation, read, write). It is imported by `server.py` the same way `skills.py` is.

- [ ] **2.1** Create `src/openstaad_mcp/file_io.py` with the module docstring and imports:

```python
"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

File I/O tools — read_tabular_data and write_tabular_data.

MCP-layer tools for reading/writing CSV and xlsx files in the model directory.
Completely outside the WASM sandbox.
"""

from __future__ import annotations

import csv
import datetime
import logging
import os
import secrets
import time
import zipfile
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl import Workbook
from openpyxl.utils.exceptions import InvalidFileException

logger = logging.getLogger(__name__)
```

- [ ] **2.2** Implement `validate_path(path_str: str, model_file: str, *, require_exists: bool) -> Path`. This is the shared path validation function. It must:

1. Check `model_file` is truthy. If not, return error dict `{"success": False, "error": "NO_MODEL_OPEN", "message": "No model is currently open in STAAD.Pro. Open a model first."}`.
2. Compute `model_dir = Path(model_file).resolve().parent`.
3. `resolved = Path(path_str).resolve()`.
4. If `str(resolved)` starts with `\\\\`, return error dict with `error: "UNC_REJECTED"`, message: `"Network paths (UNC) are not supported. Copy your files to a local drive or map the network location to a drive letter (e.g. Z:\\)."`.
5. If not `resolved.is_relative_to(model_dir)`, return error dict with `error: "PATH_OUTSIDE_MODEL_DIR"`, message: `f"Path must be inside the model directory: {model_dir}"`.
6. If `require_exists` and not `resolved.is_file()`, return error dict with `error: "FILE_NOT_FOUND"`, message: `f"File not found: {resolved.name}"`.
7. If not `require_exists` and not `resolved.parent.is_dir()`, return error dict with `error: "PARENT_DIR_MISSING"`, message: `f"Parent directory does not exist: {resolved.parent}"`.
8. Return the `resolved` Path on success (not a dict).

The function signature should be: `def validate_path(...) -> Path | dict[str, Any]`. Callers check `isinstance(result, dict)` to detect errors.

---

## Phase 3: Read implementation

- [ ] **3.1** Implement `_read_csv(path: Path, max_rows: int, start_row: int, columns: list[str] | None) -> dict[str, Any]`:
  - Open with `encoding="utf-8"`. Wrap the entire read in a `try/except UnicodeDecodeError` block. On failure, re-open the file with `encoding="cp1252"` and restart parsing from the beginning.
  - Use `csv.reader`. First row is headers.
  - If `columns` filter is provided, find the indices of matching column names (string match against header row) and return only those columns. If a column name in the filter does not exist in the headers, silently ignore it (do not error). Return only the columns that matched, in the order specified by the filter.
  - Apply `start_row` (skip that many data rows after the header).
  - Collect up to `max_rows` rows.
  - Return `{"success": True, "columns": [...], "rows": [[...], ...], "truncated": bool, "total_rows": int}`.
  - **`total_rows` calculation:** Continue iterating past `max_rows` (without storing data) to get an accurate total count. Stop counting at 50,001.
  - If total rows exceeds 50,000, set `truncated=True` and stop.
  - If columns exceed 500, return error `TOO_MANY_COLUMNS`.
  - Empty file (0 data rows): return `{"success": True, "columns": [...], "rows": [], "truncated": False, "total_rows": 0}`. If the file has no header row either, return `columns: []`.

- [ ] **3.2** Implement `_read_xlsx(path: Path, max_rows: int, start_row: int, columns: list[str] | None, sheet_name: str | None) -> dict[str, Any]`:
  - `import openpyxl` at module level (guarded: `try: import openpyxl` or just import normally since it is a hard dependency).
  - Open with `openpyxl.load_workbook(path, read_only=True, data_only=True)`.
  - If `sheet_name` is provided, select that sheet. If it does not exist, return error `SHEET_NOT_FOUND`.
  - Otherwise use the active sheet.
  - First row is headers.
  - Same `columns` filter, `start_row`, `max_rows`, `truncated` logic as CSV.
  - **Cell type coercion:** openpyxl returns `datetime`, `None`, `float`, `int`, `str`, `bool`. Convert `datetime` to ISO 8601 string (`value.isoformat()`). Leave `None`, `float`, `int`, `str`, `bool` as-is (all JSON-serializable).
  - **`total_rows` calculation:** In read-only mode, `ws.max_row` is unreliable for total count. Instead, continue iterating rows past `max_rows` with a simple counter (do not store the data). This gives an accurate `total_rows` value.
  - Wrap in `try/except` for `openpyxl.utils.exceptions.InvalidFileException` and `zipfile.BadZipFile` — return `CORRUPTED_WORKBOOK`.
  - Close the workbook in a `finally` block.

- [ ] **3.3** Implement `read_tabular_data_impl(path: str, model_file: str, max_rows: int = 10_000, start_row: int = 0, columns: list[str] | None = None, sheet_name: str | None = None) -> dict[str, Any]`:
  - Call `validate_path(path, model_file, require_exists=True)`. If dict, return it.
  - Check extension (case-insensitive via `resolved.suffix.lower()`): `.csv` or `.xlsx`. Otherwise return `UNSUPPORTED_FORMAT` error with message listing supported formats.
  - Reject `.xlsm` explicitly with `UNSUPPORTED_FORMAT` and message about macro-enabled workbooks not being supported.
  - Check file size: `os.path.getsize(resolved)`. If > 10 MB (10 * 1024 * 1024), return `FILE_TOO_LARGE` with `limit_mb: 10` and `actual_mb: round(size / 1024 / 1024, 1)`.
  - Clamp `max_rows` to ceiling of 50,000.
  - Dispatch to `_read_csv` or `_read_xlsx`.
  - Catch `PermissionError` and return `PERMISSION_DENIED`.
  - Catch `UnicodeDecodeError` and return `ENCODING_ERROR` (this catches the case where BOTH UTF-8 and cp1252 fail, e.g. binary content with a `.csv` extension).

---

## Phase 4: Write implementation

- [ ] **4.1** Implement `_cleanup_stale_temps(directory: Path) -> None`:
  - Use `directory.glob(".~omcp_*.tmp")` to find temp files.
  - Delete any where `time.time() - os.path.getmtime(f) > 3600` (older than 1 hour).
  - Wrap each `os.unlink()` in `try/except OSError: pass` (file may be locked or already removed).

- [ ] **4.2** Implement `_write_csv(path: Path, columns: list[str], rows: list[list[Any]]) -> None`:
  - Write to a temp file `.~omcp_{secrets.token_hex(8)}.tmp` in `path.parent`.
  - Open with `newline=""`, `encoding="utf-8"`.
  - Use `csv.writer` with `quoting=csv.QUOTE_ALL`.
  - Write header row, then data rows.
  - `os.replace(tmp_path, path)`.
  - `try/finally` deletes the temp file on failure.

- [ ] **4.3** Implement `_write_xlsx(path: Path, columns: list[str], rows: list[list[Any]]) -> None`:
  - Write to a temp file `.~omcp_{secrets.token_hex(8)}.tmp` in `path.parent`.
  - `from openpyxl import Workbook`.
  - Create workbook in write-only mode: `Workbook(write_only=True)`.
  - Create a sheet, append header row, append data rows.
  - Save to temp path. `os.replace(tmp_path, path)`.
  - `try/finally` deletes the temp file on failure.

- [ ] **4.4** Implement `write_tabular_data_impl(path: str, model_file: str, columns: list[str], rows: list[list[Any]], overwrite: bool = False) -> dict[str, Any]`:
  - Call `validate_path(path, model_file, require_exists=False)`. If dict, return it.
  - Check extension (case-insensitive via `resolved.suffix.lower()`): `.csv` or `.xlsx`. Otherwise `UNSUPPORTED_FORMAT`. Reject `.xlsm` explicitly.
  - If `resolved.exists()` and not `overwrite`, return `FILE_EXISTS` error with path in the message.
  - Validate limits: rows > 100,000 → `TOO_MANY_ROWS`. `len(columns)` > 500 → `TOO_MANY_COLUMNS`.
  - Call `_cleanup_stale_temps(resolved.parent)`.
  - Dispatch to `_write_csv` or `_write_xlsx`.
  - After write, check output file size. If > 50 MB, delete and return `FILE_TOO_LARGE`.
  - Catch `PermissionError` → `PERMISSION_DENIED` with message "Cannot write to this file because it is open in another program. Close the file and try again."
  - On success: `{"success": True, "path": str(resolved), "rows_written": len(rows)}`.

---

## Phase 5: Register tools in server.py

- [ ] **5.1** In `server.py`, add import: `from openstaad_mcp.file_io import read_tabular_data_impl, write_tabular_data_impl`.

- [ ] **5.2** Inside `_register_tools()`, register `read_tabular_data`. Follow this pattern exactly:

```python
@mcp.tool(
    annotations={
        "title": "Read tabular file",
        "readOnlyHint": True,
        "openWorldHint": False,
    }
)
def read_tabular_data(
    path: str,
    max_rows: int = 10_000,
    start_row: int = 0,
    columns: list[str] | None = None,
    sheet_name: str | None = None,
    instance: str | None = None,
) -> dict[str, Any]:
    """Read a CSV or xlsx file from the model directory as structured JSON rows.

    Returns columns and rows as JSON arrays. Use ``columns`` to filter
    specific columns and ``start_row``/``max_rows`` for pagination.
    Supports ``.csv`` and ``.xlsx`` files only (max 10 MB, 50,000 rows,
    500 columns). Files must be in the same directory as the open STAAD
    model (or a subdirectory of it).
    """
    try:
        target = _resolve_target(instance)
    except ValueError as e:
        return {"success": False, "error": "NO_MODEL_OPEN", "message": str(e)}

    def _read(staad: Any) -> dict[str, Any]:
        model_file = staad.GetSTAADFile()
        return read_tabular_data_impl(
            path, model_file, max_rows=max_rows, start_row=start_row,
            columns=columns, sheet_name=sheet_name,
        )

    try:
        return connect_and_run(_read, target.file_path, timeout=30.0)
    except TimeoutError:
        return {"success": False, "error": "TIMEOUT", "message": "Read timed out"}
    except Exception as e:
        logger.debug("read_tabular_data failed", exc_info=True)
        return {"success": False, "error": "INTERNAL", "message": _safe_error_message(e)}
```

- [ ] **5.3** Register `write_tabular_data`. This one is `destructiveHint=true` so the MCP host handles consent:

```python
@mcp.tool(
    annotations={
        "title": "Write tabular file",
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    }
)
def write_tabular_data(
    path: str,
    columns: list[str],
    rows: list[list[Any]],
    overwrite: bool = False,
    instance: str | None = None,
) -> dict[str, Any]:
    """Write structured data to a CSV or xlsx file in the model directory.

    Provide ``columns`` (header names) and ``rows`` (array of arrays).
    Files are written atomically (max 100,000 rows, 500 columns, 50 MB
    output). The target must be in the same directory as the open STAAD
    model (or a subdirectory of it). Set ``overwrite=true`` to replace
    an existing file.
    """
    try:
        target = _resolve_target(instance)
    except ValueError as e:
        return {"success": False, "error": "NO_MODEL_OPEN", "message": str(e)}

    def _write(staad: Any) -> dict[str, Any]:
        model_file = staad.GetSTAADFile()
        return write_tabular_data_impl(
            path, model_file, columns=columns, rows=rows, overwrite=overwrite,
        )

    try:
        return connect_and_run(_write, target.file_path, timeout=60.0)
    except TimeoutError:
        return {"success": False, "error": "TIMEOUT", "message": "Write timed out"}
    except Exception as e:
        logger.debug("write_tabular_data failed", exc_info=True)
        return {"success": False, "error": "INTERNAL", "message": _safe_error_message(e)}
```

- [ ] **5.4** Update the `instructions` string in `create_mcp_server()` to mention the new tools. Add after the existing instruction text: `"Use `read_tabular_data` to read CSV/xlsx files and `write_tabular_data` to write them — both restricted to the model directory."`.

---

## Phase 6: Tests

Create `tests/test_file_io.py`. No STAAD or COM dependency. Mock `model_file` as a path string.

- [ ] **6.1** Test `validate_path`:
  - No model open (empty string) → `NO_MODEL_OPEN`
  - UNC path → `UNC_REJECTED`
  - Path outside model dir (e.g. `../../etc/passwd`) → `PATH_OUTSIDE_MODEL_DIR`
  - Path traversal with `..` that resolves inside model dir → passes
  - Subdirectory path → passes
  - File not found (require_exists=True) → `FILE_NOT_FOUND`
  - Parent missing (require_exists=False) → `PARENT_DIR_MISSING`
  - Happy path → returns resolved Path

- [ ] **6.2** Test `read_tabular_data_impl`:
  - Read a valid CSV (create a temp CSV with `tmp_path`) → correct columns, rows, total_rows
  - Read with `max_rows` smaller than file → `truncated=True`, `total_rows` reflects full file
  - Read with `start_row` → skips rows
  - Read with `columns` filter → only returns those columns
  - File too large (mock `os.path.getsize` to return > 10 MB) → `FILE_TOO_LARGE`
  - Unsupported extension (.xls) → `UNSUPPORTED_FORMAT`
  - .xlsm → `UNSUPPORTED_FORMAT`
  - Read valid xlsx (create a small xlsx with openpyxl in the test) → correct output
  - xlsx with specific sheet_name → reads that sheet
  - xlsx with nonexistent sheet_name → `SHEET_NOT_FOUND`
  - CSV with cp1252 encoding → falls back and reads correctly
  - Empty CSV (header only, no data rows) → `total_rows: 0`, `rows: []`
  - Corrupted xlsx (write garbage bytes to a .xlsx file) → `CORRUPTED_WORKBOOK`
  - xlsx with datetime cells → returned as ISO 8601 strings
  - CSV with > 500 columns → `TOO_MANY_COLUMNS`
  - PermissionError on read (mock `open` to raise) → `PERMISSION_DENIED`
  - CSV with binary/non-text content that fails both UTF-8 and cp1252 → `ENCODING_ERROR`
  - `sheet_name` parameter passed for a CSV file → ignored, reads normally
  - File with uppercase extension `.CSV` or `.XLSX` → reads correctly (case-insensitive extension check)

- [ ] **6.3** Test `write_tabular_data_impl`:
  - Write CSV happy path → file exists on disk, content matches, all values quoted
  - Write xlsx happy path → file exists, readable by openpyxl, headers and data correct
  - Write to existing file with overwrite=False → `FILE_EXISTS`
  - Write to existing file with overwrite=True → file replaced
  - Too many rows (> 100,000) → `TOO_MANY_ROWS`
  - Too many columns (> 500) → `TOO_MANY_COLUMNS`
  - Atomic write: simulate write failure (mock csv.writer.writerow to raise) → no partial file left behind, no temp file remains
  - Stale temp cleanup: create an old `.~omcp_*.tmp` file, call write → old temp is deleted
  - Fresh temp not deleted: create a `.~omcp_*.tmp` file modified <1 hour ago, call write → fresh temp is left alone
  - PermissionError on write (mock `os.replace` to raise PermissionError) → `PERMISSION_DENIED` with correct message
  - Output file too large (mock `os.path.getsize` on result to return > 50 MB) → `FILE_TOO_LARGE`, file deleted
  - .xlsm extension on write → `UNSUPPORTED_FORMAT`
  - .xls extension on write → `UNSUPPORTED_FORMAT`

- [ ] **6.4** Test path validation adversarial cases:
  - Symlink escape (create a symlink inside model dir pointing outside, then try to read through it) → `PATH_OUTSIDE_MODEL_DIR` (because `Path.resolve()` follows the symlink)
  - Mixed separators (`/` and `\`) → normalizes correctly
  - Relative path input → resolves against cwd, likely fails containment (this is fine)

- [ ] **6.5** Run the full test suite: `pytest tests/test_file_io.py -v`. All tests must pass.

---

## Phase 7: Integration wiring check

- [ ] **7.1** Run `pytest tests/ -v --ignore=tests/test_mcp_live.py --ignore=tests/test_integration.py` to verify no existing tests broke.

- [ ] **7.2** Run `ruff check src/openstaad_mcp/file_io.py` and `ruff format --check src/openstaad_mcp/file_io.py`. Fix any issues. The project uses `line-length = 120` and targets Python 3.11.

- [ ] **7.3** Run `ruff check tests/test_file_io.py` and `ruff format --check tests/test_file_io.py`. Fix any issues.

---

## Phase 8: Update CHANGELOG and version

- [ ] **8.1** Add a new section at the top of `CHANGELOG.md`:

```markdown
## 2.2.0 (YYYY-MM-DD)

### Added

- `read_tabular_data` tool: read CSV and xlsx files from the model directory as structured JSON. Supports column filtering, pagination, and sheet selection. Read-only, auto-approved by MCP hosts.
- `write_tabular_data` tool: write structured data to CSV or xlsx files in the model directory. Atomic writes via temp file + `os.replace()`. Destructive, requires host confirmation before invocation.
- Path validation shared between both tools: model directory containment, UNC rejection, symlink-safe resolution.
- `openpyxl==3.1.5` and `defusedxml==0.7.1` dependencies for xlsx support.
```

- [ ] **8.2** Bump version to `"2.2.0"` in `pyproject.toml` (`[project].version`) and `src/openstaad_mcp/__init__.py` (`__version__`).

---

## Phase 9: PyInstaller bundling

The project ships as a PyInstaller-bundled `.mcpb` extension. New pure-Python dependencies need to be discoverable by PyInstaller.

- [ ] **9.1** Both `openstaad-mcp-dir.spec` (root) and `mcpb/openstaad-mcp.spec` have explicit `hiddenimports` lists. Add these entries to both:
  - `"openstaad_mcp.file_io"`
  - `"openpyxl"`
  - `"defusedxml"`
  - `"et_xmlfile"`

  openpyxl is pure Python and does not need `collect_all`. A simple `hiddenimports` entry is sufficient. Place them after the existing `"openstaad_mcp.server"` or `"openstaad_mcp.sandbox"` entries.

- [ ] **9.2** Run the PyInstaller build (if feasible in your environment) to confirm the bundled binary can `import openpyxl` without error. If not feasible, note it as a manual verification step.

---

## Implementation notes for the LLM

**Error response pattern.** Every error return from `file_io.py` must be a dict with exactly `{"success": False, "error": "<CODE>", "message": "<human-readable>"}`. Additional fields (like `limit_mb`) are allowed but optional.

**Copyright header.** Every new `.py` file must start with:
```python
"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------
"""
```

**Import style.** The project uses `from __future__ import annotations` at the top of every module. Type annotations use `|` union syntax (e.g. `Path | dict[str, Any]`).

**Test style.** Tests use plain pytest classes (no unittest.TestCase). Use `tmp_path` fixture for filesystem tests. Use `unittest.mock.patch` for mocking. No pytest markers needed unless async.

**No over-engineering.** Do not add logging beyond `logger.debug` for unexpected exceptions. Do not add retry logic. Do not add caching. Do not add async (the COM thread pattern is already synchronous via `connect_and_run`).

**The openpyxl import.** Import at module top level. It is a hard dependency, not optional.

**ruff.** Run `ruff check` and `ruff format` before considering the implementation complete. The project config is in `pyproject.toml` under `[tool.ruff]`.

**`_write_csv` and `_write_xlsx` raise on failure.** These internal helpers do NOT return error dicts. They raise exceptions (e.g. `PermissionError`, `OSError`). The caller `write_tabular_data_impl` catches exceptions and converts them to error dicts. This keeps the helpers simple and the error-handling centralized.

**`datetime` import.** The xlsx reader needs `import datetime` (or `from datetime import datetime`) for the `isinstance(value, datetime.datetime)` check when coercing cell values. Add it to the imports block.

**`from pathlib import Path` in both modules.** The test file also needs this for `tmp_path` type annotations and for creating test fixtures.

**The `Workbook` import is used only in `_write_xlsx`.** You can import it at module level (already shown in the imports block) or inline. Module-level is fine for a hard dependency.
