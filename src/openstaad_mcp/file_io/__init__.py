"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Server-side file I/O for the ``execute_code`` tool.

All operations run **outside** the sandbox.  The sandbox never touches the
filesystem -- it receives pre-parsed data via ``__input__`` and returns a
structured value that this module writes to disk.

Sub-modules
-----------
``readers``     -- BaseReader, CSVReader, XLSXReader
``writers``     -- BaseWriter, CSVWriter, XLSXWriter
``models``      -- Pydantic models for return-value validation
``validation``  -- validate_return_value, validate_args_allowed_dirs, deep_freeze
``helpers``     -- get_allowed_dirs, get_input_data, dispatch functions
"""

from openstaad_mcp.file_io.helpers import (
    get_allowed_dirs,
    get_input_data,
    read_input_file,
    write_output_file,
)
from openstaad_mcp.file_io.readers import CSVReader, XLSXReader
from openstaad_mcp.file_io.validation import (
    deep_freeze,
    validate_args_allowed_dirs,
    validate_return_value,
)
from openstaad_mcp.file_io.writers import CSVWriter

__all__ = [
    "CSVReader",
    "CSVWriter",
    "XLSXReader",
    "deep_freeze",
    "get_allowed_dirs",
    "get_input_data",
    "read_input_file",
    "validate_args_allowed_dirs",
    "validate_return_value",
    "write_output_file",
]
