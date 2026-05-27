"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Sandboxed code executor for the ``execute_code`` MCP tool.

Runs validated Python code in a restricted globals dict, captures stdout,
and returns structured results. Timeout enforcement is handled by the
connection/dispatch layer rather than by this executor itself. All COM
calls are dispatched to a dedicated COM thread via a queue (see
``connection.py``).
"""

from __future__ import annotations

import builtins
import importlib
import json
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any

from openstaad_mcp.sandbox.ast import capture_last_expr, validate_code
from openstaad_mcp.sandbox.com_proxy import COMProxy
from openstaad_mcp.sandbox.const import ALLOWED_BUILTINS, ALLOWED_MODULE_ATTRS
from openstaad_mcp.sandbox.module_proxy import ModuleProxy
from openstaad_mcp.sandbox.stdio_helpers import LimitedStringIO, sanitize_output, sanitize_traceback


@dataclass
class ExecutionResult:
    """Structured result returned from :func:`execute`."""

    success: bool
    result: Any = None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "result": self.result,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
        }


class Executor:
    def __init__(
        self,
        allowed_builtins: frozenset[str] | None = None,
        allowed_module_attrs: dict[str, frozenset[str]] | None = None,
    ) -> None:
        if allowed_builtins is None:
            allowed_builtins = ALLOWED_BUILTINS
        if allowed_module_attrs is None:
            allowed_module_attrs = ALLOWED_MODULE_ATTRS

        # Pre-approved modules injected into the sandbox globals, each wrapped in a
        # read-only proxy so only the whitelisted public API is reachable.  This
        # prevents module-graph traversal attacks (e.g. json.codecs.builtins.exec).
        self.injected_modules: dict[str, Any] = {
            name: ModuleProxy(importlib.import_module(name), allowed) for name, allowed in allowed_module_attrs.items()
        }

        # A restricted __builtins__ dict to prevent access to dangerous functions.
        self.safe_builtins = {name: getattr(builtins, name) for name in allowed_builtins}

        # Serialise execute() calls so concurrent requests don't race on
        # sys.stdout / sys.stderr reassignment.
        self._exec_lock = threading.Lock()

    def execute(
        self,
        code: str,
        staad_object: Any,
        *,
        input_data: Any = None,
    ) -> ExecutionResult:
        """Validate and execute *code* in the sandbox.

        Parameters
        ----------
        code:
            Python source code to execute.
        staad_object:
            The connected OpenSTAAD root object (or a mock for testing).
        input_data:
            Optional pre-parsed, deep-frozen data injected as ``input_data``
            in the sandbox globals.  ``None`` when no input file is provided.

        Returns
        -------
        ExecutionResult
        """
        # ── 1. Validate ──────────────────────────────────────────────
        validation = validate_code(code)
        if not validation.is_valid:
            return ExecutionResult(
                success=False,
                error=validation.summary(),
            )

        # ── 2. Rewrite last expression for result capture ────────────
        rewritten, has_result_expr = capture_last_expr(code)

        # ── 3. Build restricted globals ──────────────────────────────
        sandbox_globals: dict[str, Any] = {"__builtins__": self.safe_builtins.copy()}
        sandbox_globals.update(self.injected_modules)
        sandbox_globals["staad"] = COMProxy(staad_object)
        sandbox_globals["input_data"] = input_data

        # ── 4. Execute with stdout/stderr capture ───────────────────
        captured_out, captured_err = LimitedStringIO(), LimitedStringIO()
        exec_error: BaseException | None = None
        duration = 0.0

        if not self._exec_lock.acquire(timeout=5.0):
            return ExecutionResult(
                success=False,
                error="Executor busy — a previous operation may have timed out. Restart the server.",
            )
        try:
            old_stdout, old_stderr = sys.stdout, sys.stderr
            start = time.perf_counter()
            try:
                sys.stdout, sys.stderr = captured_out, captured_err  # type: ignore[assignment]
                exec(compile(rewritten, "<sandbox>", "exec"), sandbox_globals)
            except Exception as exc:
                exec_error = exc
            finally:
                duration = time.perf_counter() - start
                sys.stdout, sys.stderr = old_stdout, old_stderr
        finally:
            self._exec_lock.release()

        stdout_text = captured_out.getvalue()
        stderr_text = captured_err.getvalue()

        if exec_error is not None:
            return ExecutionResult(
                success=False,
                stdout=stdout_text,
                stderr=stderr_text,
                error=sanitize_traceback(exec_error),
                duration_seconds=round(duration, ndigits=4),
            )

        # ── 5. Collect result ────────────────────────────────────────
        if "result" in sandbox_globals:  # explicit `result = ...`
            result_value = sandbox_globals["result"]
        elif has_result_expr:
            result_value = sandbox_globals.get("__result__")
        else:
            result_value = None

        result_value = sanitize_output(result_value)

        # Attempt JSON-safe serialisation; fall back to repr.
        try:
            json.dumps(result_value)
        except (TypeError, ValueError):
            result_value = repr(result_value)

        return ExecutionResult(
            success=True,
            result=result_value,
            stdout=stdout_text,
            stderr=stderr_text,
            duration_seconds=duration,
        )
