"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------
"""
# ── File I/O limits ──────────────────────────────────────────────────────

# Maximum file size on disk (bytes) for read operations.
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB

# Row / column / sheet caps for input files.
MAX_INPUT_ROWS = 100_000
MAX_INPUT_COLUMNS = 500
MAX_INPUT_SHEETS = 50

# Row / column / sheet caps for output (return value → file).
MAX_OUTPUT_ROWS = 100_000
MAX_OUTPUT_COLUMNS = 500
MAX_OUTPUT_SHEETS = 20

# Excel's own limit on sheet-tab names.
MAX_SHEET_NAME_LENGTH = 31

# Allowed file extensions for file I/O paths.
ALLOWED_FILE_EXTENSIONS: frozenset[str] = frozenset({".csv", ".xlsx"})

# Temp-file naming for atomic writes.
TEMP_FILE_PREFIX = ".~omcp_"

# Orphan temp files older than this (seconds) are cleaned up.
STALE_TEMP_AGE_SECONDS = 3600

# Number of sample rows included in summaries returned to the agent.
SAMPLE_ROW_COUNT = 5

# Maximum character length for a single cell value (Excel limit: 32,767 characters).
MAX_CELL_SIZE = 32_767
