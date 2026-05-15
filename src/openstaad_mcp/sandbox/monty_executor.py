"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Monty-based sandboxed executor for the ``execute_code`` MCP tool.

Runs user-authored Python code inside `pydantic_monty.Monty`, a minimal
secure Python interpreter written in Rust.  COM interaction is bridged
via external functions that the host (this module) provides — the sandbox
code never touches pywin32 objects directly.

Security properties
-------------------
* **Process isolation** — Monty is a separate interpreter; user code cannot
  reach CPython internals, the filesystem, the network, or env variables.
* **Resource limits** — execution time, memory, allocations, recursion
  depth are all enforced by Monty's Rust runtime.
* **Positive allowlists** — every COM method must be explicitly enumerated
  in ``constants.py`` before it can be called.
* **Deny list** — dangerous methods (e.g. NTLM-relay vectors) are
  unconditionally blocked.
* **Consent gate** — destructive/file-writing methods require an explicit
  ``allow_destructive`` flag set by host-mediated user approval.
* **Per-call isolation** — each ``execute()`` call creates a fresh Monty
  instance; globals do not leak between calls.
* **Error sanitisation** — Python tracebacks and COM internals are stripped
  before reaching the caller.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import pydantic_monty

from openstaad_mcp.sandbox.constants import (
    ALLOWED_ROOT_METHODS,
    ALLOWED_SUB_OBJECT_METHODS,
    ALLOWED_SUB_OBJECTS,
    ALL_DESTRUCTIVE_METHOD_NAMES,
    DENIED_METHODS,
    DESTRUCTIVE_METHODS,
    EXECUTION_TIMEOUT_SECONDS,
    GC_INTERVAL,
    MAX_ALLOCATIONS,
    MAX_CODE_BYTES,
    MAX_MEMORY_BYTES,
    MAX_RECURSION_DEPTH,
    MAX_RESULT_LENGTH,
    MAX_STDOUT_CHARS,
)
from openstaad_mcp.sandbox.rewriter import rewrite_proxy_calls

logger = logging.getLogger(__name__)

#: Root variable names treated as COM proxies by the AST rewriter.
_PROXY_NAMES: frozenset[str] = frozenset({"staad"})

# ---------------------------------------------------------------------------
# Result dataclass (mirrors v1 Executor output shape)
# ---------------------------------------------------------------------------


@dataclass
class ExecutionResult:
    """Structured result returned from :meth:`MontyExecutor.execute`."""

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


# ---------------------------------------------------------------------------
# Per-call mutable state shared between host functions
# ---------------------------------------------------------------------------


@dataclass
class _CallState:
    """Mutable state scoped to a single ``execute()`` invocation."""

    staad_object: Any
    #: Integer handle → (COM object, sub-object name or "_root").
    handle_table: dict[int, tuple[Any, str]] = field(default_factory=dict)
    next_handle: int = 1
    allow_destructive: bool = False
    stdout_buf: list[str] = field(default_factory=list)
    stderr_buf: list[str] = field(default_factory=list)
    stdout_len: int = 0
    stderr_len: int = 0


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


class MontyExecutor:
    """Execute user Python code inside a Monty sandbox with COM bridging.

    Parameters
    ----------
    timeout_seconds:
        Wall-clock execution budget.
    max_memory_bytes:
        Heap memory cap enforced by Monty's Rust runtime.
    max_allocations:
        Maximum number of heap allocations.
    gc_interval:
        Garbage-collection interval (allocations).
    max_recursion_depth:
        Maximum call-stack depth.
    max_stdout_chars:
        Maximum captured stdout/stderr size (characters).
    max_code_bytes:
        Maximum source size accepted.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = EXECUTION_TIMEOUT_SECONDS,
        max_memory_bytes: int = MAX_MEMORY_BYTES,
        max_allocations: int = MAX_ALLOCATIONS,
        gc_interval: int = GC_INTERVAL,
        max_recursion_depth: int = MAX_RECURSION_DEPTH,
        max_stdout_chars: int = MAX_STDOUT_CHARS,
        max_code_bytes: int = MAX_CODE_BYTES,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_memory_bytes = max_memory_bytes
        self._max_allocations = max_allocations
        self._gc_interval = gc_interval
        self._max_recursion_depth = max_recursion_depth
        self._max_stdout_chars = max_stdout_chars
        self._max_code_bytes = max_code_bytes

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(
        self,
        code: str,
        staad_object: Any,
        *,
        allow_destructive: bool = False,
    ) -> ExecutionResult:
        """Validate and execute *code* in a fresh Monty sandbox.

        Parameters
        ----------
        code:
            Python source code to execute.
        staad_object:
            The connected OpenSTAAD root COM object (or a mock).
        allow_destructive:
            When ``True``, consent-gated methods (file writes, Quit, …)
            are permitted.  The server layer sets this after MCP
            elicitation confirms user approval.

        Returns
        -------
        ExecutionResult
        """
        start = time.perf_counter()

        # ── 0. Pre-flight checks ─────────────────────────────────────
        if len(code.encode("utf-8", errors="replace")) > self._max_code_bytes:
            return ExecutionResult(
                success=False,
                error=f"Source code exceeds maximum size ({self._max_code_bytes} bytes).",
            )

        # ── 0b. AST rewrite: staad.Xyz.Method() → _call("staad.Xyz.Method") ─
        try:
            rewritten_code = rewrite_proxy_calls(code, _PROXY_NAMES)
        except SyntaxError as exc:
            duration = time.perf_counter() - start
            return ExecutionResult(
                success=False,
                error=f"Syntax error: {exc}",
                duration_seconds=round(duration, ndigits=4),
            )

        # ── 1. Build per-call state ──────────────────────────────────
        state = _CallState(
            staad_object=staad_object,
            allow_destructive=allow_destructive,
        )
        # Handle 0 = root STAAD object
        state.handle_table[0] = (staad_object, "_root")

        # ── 2. Build external functions ──────────────────────────────
        external_fns = self._build_external_functions(state)

        # ── 3. Build resource limits ─────────────────────────────────
        limits: pydantic_monty.ResourceLimits = {
            "max_duration_secs": self._timeout_seconds,
            "max_memory": self._max_memory_bytes,
            "max_allocations": self._max_allocations,
            "gc_interval": self._gc_interval,
            "max_recursion_depth": self._max_recursion_depth,
        }

        # ── 4. Build stdout collector ────────────────────────────────
        streams = pydantic_monty.CollectStreams()

        # ── 5. Create fresh Monty instance & run ─────────────────────
        try:
            monty = pydantic_monty.Monty(
                rewritten_code,
                script_name="<sandbox>",
            )
            raw_result = monty.run(
                limits=limits,
                external_functions=external_fns,
                print_callback=streams,
            )
        except pydantic_monty.MontySyntaxError as exc:
            duration = time.perf_counter() - start
            return ExecutionResult(
                success=False,
                error=f"Syntax error: {exc}",
                duration_seconds=round(duration, ndigits=4),
            )
        except pydantic_monty.MontyRuntimeError as exc:
            duration = time.perf_counter() - start
            stdout_text = self._collect_stdout(streams, state)
            stderr_text = self._collect_stderr(streams, state)
            error_msg = _sanitize_error(str(exc))
            return ExecutionResult(
                success=False,
                stdout=stdout_text,
                stderr=stderr_text,
                error=error_msg,
                duration_seconds=round(duration, ndigits=4),
            )
        except pydantic_monty.MontyError as exc:
            duration = time.perf_counter() - start
            stdout_text = self._collect_stdout(streams, state)
            stderr_text = self._collect_stderr(streams, state)
            error_msg = _sanitize_error(str(exc))
            return ExecutionResult(
                success=False,
                stdout=stdout_text,
                stderr=stderr_text,
                error=error_msg,
                duration_seconds=round(duration, ndigits=4),
            )
        except Exception as exc:
            duration = time.perf_counter() - start
            logger.debug("Unexpected Monty error: %s", exc, exc_info=True)
            return ExecutionResult(
                success=False,
                error=_sanitize_error(str(exc)),
                duration_seconds=round(duration, ndigits=4),
            )

        duration = time.perf_counter() - start
        stdout_text = self._collect_stdout(streams, state)
        stderr_text = self._collect_stderr(streams, state)

        # ── 6. Sanitize result ───────────────────────────────────────
        result_value = _sanitize_output(raw_result)

        return ExecutionResult(
            success=True,
            result=result_value,
            stdout=stdout_text,
            stderr=stderr_text,
            duration_seconds=round(duration, ndigits=4),
        )

    # ------------------------------------------------------------------
    # External function builders
    # ------------------------------------------------------------------

    def _build_external_functions(
        self,
        state: _CallState,
    ) -> dict[str, Any]:
        """Create the dict of external functions exposed to the Monty sandbox."""

        def _dispatch(method_path: str, *args: Any) -> Any:
            """Dispatch ``staad.Xyz.Method(...)`` calls from rewritten code."""
            return _host_call(state, method_path, list(args))

        return {
            "_dispatch": _dispatch,
        }

    # ------------------------------------------------------------------
    # Stdout / stderr collection
    # ------------------------------------------------------------------

    def _collect_stdout(
        self,
        streams: pydantic_monty.CollectStreams,
        state: _CallState,
    ) -> str:
        """Merge Monty print output with any host-buffered stdout."""
        parts: list[str] = []
        try:
            for stream_name, text in streams.output:
                if stream_name == "stdout":
                    parts.append(text)
        except Exception:
            pass
        parts.extend(state.stdout_buf)
        text = "".join(parts)
        if len(text) > self._max_stdout_chars:
            text = text[: self._max_stdout_chars] + "\n... (truncated)"
        return text

    def _collect_stderr(
        self,
        streams: pydantic_monty.CollectStreams,
        state: _CallState,
    ) -> str:
        parts: list[str] = []
        try:
            for stream_name, text in streams.output:
                if stream_name == "stderr":
                    parts.append(text)
        except Exception:
            pass
        parts.extend(state.stderr_buf)
        text = "".join(parts)
        if len(text) > self._max_stdout_chars:
            text = text[: self._max_stdout_chars] + "\n... (truncated)"
        return text


# ---------------------------------------------------------------------------
# Host functions (called from inside the Monty sandbox)
# ---------------------------------------------------------------------------


def _host_com_get(state: _CallState, handle: int, prop: str) -> dict:
    """Resolve a sub-object property on a COM handle.

    Only valid on handle 0 (root).  Returns ``{"handle": N}`` on success
    or ``{"error": "..."}`` on failure.
    """
    if handle != 0:
        return {"error": "com_get is only valid on the root handle (0)"}

    if prop not in ALLOWED_SUB_OBJECTS:
        return {"error": f"Access denied: '{prop}' is not an allowed sub-object"}

    # Check if we already resolved this sub-object
    for h, (_, name) in state.handle_table.items():
        if name == prop and h != 0:
            return {"handle": h}

    try:
        sub_obj = getattr(state.staad_object, prop)
    except Exception as exc:
        logger.debug("COM error resolving '%s': %s", prop, exc)
        return {"error": f"COM error resolving '{prop}': {_sanitize_com_error(exc)}"}

    h = state.next_handle
    state.next_handle += 1
    state.handle_table[h] = (sub_obj, prop)
    return {"handle": h}


def _host_com_invoke(
    state: _CallState,
    handle: int,
    method: str,
    args: list[Any],
) -> Any:
    """Call a COM method on a handle, enforcing all security gates.

    Returns the COM result directly (Monty will convert to its internal
    representation).  Raises ``RuntimeError`` for blocked calls so Monty
    surfaces a proper exception to user code.
    """
    # ── Gate 1: Handle valid ─────────────────────────────────────
    if handle not in state.handle_table:
        raise RuntimeError(f"Invalid handle: {handle}")

    target, obj_name = state.handle_table[handle]

    # ── Gate 2: Global deny list ─────────────────────────────────
    if method in DENIED_METHODS:
        raise RuntimeError(f"Method '{method}' is denied")

    # ── Gate 3: Per-object positive allowlist ─────────────────────
    if handle == 0:
        allowed = ALLOWED_ROOT_METHODS
    else:
        allowed = ALLOWED_SUB_OBJECT_METHODS.get(obj_name, frozenset())
    if method not in allowed:
        raise RuntimeError(f"Method '{method}' is not allowed on '{obj_name}'")

    # ── Gate 4: Consent gate for destructive methods ──────────────
    destructive_set = DESTRUCTIVE_METHODS.get(obj_name, frozenset())
    if method in destructive_set and not state.allow_destructive:
        raise RuntimeError(f"Method '{method}' is blocked — requires user approval")

    # ── Gate 5: Validate arguments ────────────────────────────────
    # Only allow JSON-safe scalar types through
    _validate_args(args)

    # ── Execute ──────────────────────────────────────────────────
    try:
        fn = getattr(target, method)
        result = fn(*args)
    except Exception as exc:
        logger.debug("COM error in '%s.%s': %s", obj_name, method, exc, exc_info=True)
        raise RuntimeError(f"COM error in '{method}': {_sanitize_com_error(exc)}") from None

    # Convert result to JSON-safe value
    return _com_result_to_safe(result)


def _host_call(
    state: _CallState,
    method_path: str,
    args: list[Any],
) -> Any:
    """Dispatch a dotted method path produced by the AST rewriter.

    The rewriter expands all aliases to their full ``staad.*`` path, so
    this function only needs to handle three shapes:

    * ``"staad.Geometry"``                → sub-object resolution (no args)
    * ``"staad.GetBaseUnit"``             → root method call
    * ``"staad.Geometry.GetNodeCount"``   → sub-object method call
    """
    parts = method_path.split(".")
    if len(parts) < 2 or parts[0] != "staad":
        raise RuntimeError(f"Invalid method path: '{method_path}'")

    if len(parts) == 2:
        name = parts[1]
        if name in ALLOWED_SUB_OBJECTS and not args:
            # staad.Geometry  →  sub-object resolution (returns opaque token)
            _resolve_sub_object(state, name)
            return None  # Monty stores the alias; calls use expanded paths
        else:
            # staad.Method(...)  →  root method call
            return _host_com_invoke(state, 0, name, args)
    elif len(parts) == 3:
        # staad.SubObject.Method(...)  →  resolve + call
        sub_name, method = parts[1], parts[2]
        handle = _resolve_sub_object(state, sub_name)
        return _host_com_invoke(state, handle, method, args)
    else:
        raise RuntimeError(f"Method path too deep: '{method_path}' (expected staad.Method or staad.SubObject.Method)")


def _resolve_sub_object(state: _CallState, sub_name: str) -> int:
    """Resolve a sub-object by name, returning its handle.

    Re-uses existing handles if the sub-object was already resolved.
    """
    result = _host_com_get(state, 0, sub_name)
    if "error" in result:
        raise RuntimeError(result["error"])
    return result["handle"]


def _validate_args(args: list[Any]) -> None:
    """Ensure all arguments are JSON-safe scalars or flat lists thereof."""
    for i, arg in enumerate(args):
        if arg is None or isinstance(arg, (bool, int, float, str)):
            continue
        if isinstance(arg, (list, tuple)):
            _validate_args(list(arg))
            continue
        raise RuntimeError(f"Argument {i} has unsupported type '{type(arg).__name__}'")


def _com_result_to_safe(value: Any) -> Any:
    """Convert a COM return value to a JSON-safe Python value."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_com_result_to_safe(v) for v in value]
    # COM VARIANTs and other objects → repr string
    try:
        return repr(value)
    except Exception:
        return "<unconvertible COM result>"


def _sanitize_com_error(exc: Exception) -> str:
    """Extract a safe error message from a COM exception.

    Strips file paths, DLL names, and source info that could leak
    system details.
    """
    msg = str(exc)
    # pywintypes.com_error includes (hresult, msg, ..., helpFile)
    # Extract just the human-readable description
    if hasattr(exc, "args") and isinstance(exc.args, tuple) and len(exc.args) >= 2:
        hresult = exc.args[0]
        desc = exc.args[1] if isinstance(exc.args[1], str) else str(exc.args[1])
        if isinstance(hresult, int):
            return f"[0x{hresult & 0xFFFFFFFF:08X}] {desc}"
        return desc
    return msg


def _sanitize_error(msg: str) -> str:
    """Remove filesystem paths and internal details from error messages."""
    import re

    # Strip file paths in traceback-style messages
    msg = re.sub(r'File "(?!<sandbox>)[^"]*"', 'File "<internal>"', msg)
    # Strip Windows paths
    msg = re.sub(r"[A-Za-z]:\\[^\s\"']+", "<path>", msg)
    return msg


def _sanitize_output(value: Any) -> Any:
    """Truncate oversized strings and ensure JSON-safety."""
    if value is None:
        return None
    if isinstance(value, str):
        if len(value) > MAX_RESULT_LENGTH:
            return value[:MAX_RESULT_LENGTH] + "... (truncated)"
        return value
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_sanitize_output(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _sanitize_output(v) for k, v in value.items()}
    # Fallback: try JSON, then repr
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        s = repr(value)
        if len(s) > MAX_RESULT_LENGTH:
            return s[:MAX_RESULT_LENGTH] + "... (truncated)"
        return s
