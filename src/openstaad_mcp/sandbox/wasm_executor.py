"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

WASM sandbox executor for the ``execute_code`` MCP tool.

Runs AI-generated JavaScript inside an Extism plugin (QuickJS-ng on
WebAssembly). User code has no filesystem, network, or host-memory access
— the only I/O is three host functions provided here:

    com_get({handle, prop})             -> {handle} | {error}
    com_invoke({handle, method, args})  -> {result} | {error}
    console_output({stream, text})      -> void

Per-call isolation:
    - A *fresh* ``extism.Plugin`` is instantiated for every ``execute()``
      call. Globals in one call are invisible to the next (Extism does
      not auto-reset globals on ``plugin.call``).
    - Host-function closures are built per call over a private handle
      table, so nothing leaks across calls either.

Per-call limits:
    - ``EXECUTION_TIMEOUT_SECONDS`` — cooperative wall-clock trap enforced
      inside the host functions. Any COM call made after the deadline
      raises inside WASM, which terminates the script.
    - ``WASM_MAX_MEMORY_PAGES`` — WASM linear memory cap, enforced by the
      Extism manifest.
    - ``MAX_STDOUT_BYTES`` — captured stdout/stderr cap, enforced in the
      ``console_output`` host function (silent truncation beyond the cap).

Error sanitisation:
    COM exceptions are caught in the host functions and replaced with a
    generic ``"COM error in 'Method': <msg>"`` string that crosses the
    WASM boundary. Python tracebacks never cross. Full details are logged
    at DEBUG on the Python side.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import extism  # type: ignore[import-untyped]

from openstaad_mcp.sandbox.constants import (
    ALLOWED_ROOT_METHODS,
    ALLOWED_SUB_OBJECT_METHODS,
    ALLOWED_SUB_OBJECTS,
    DENIED_METHODS,
    DESTRUCTIVE_METHODS,
    EXECUTION_TIMEOUT_SECONDS,
    MAX_CODE_BYTES,
    MAX_STDOUT_BYTES,
    WASM_MAX_MEMORY_PAGES,
)

logger = logging.getLogger(__name__)

# Path to the pre-built evaluator module. Loaded once at import time.
_EVALUATOR_PATH = Path(__file__).with_name("evaluator.wasm")
_EVALUATOR_SHA256_PATH = _EVALUATOR_PATH.with_suffix(".wasm.sha256")
try:
    _EVALUATOR_BYTES = _EVALUATOR_PATH.read_bytes()
except OSError as exc:  # pragma: no cover - deployment misconfiguration
    raise RuntimeError(
        f"WASM evaluator not found at {_EVALUATOR_PATH}. "
        "Rebuild with src/openstaad_mcp/sandbox/evaluator_src/build.ps1."
    ) from exc

# Verify WASM binary integrity against the shipped hash file.
if _EVALUATOR_SHA256_PATH.exists():
    import hashlib

    _expected_hash = (
        _EVALUATOR_SHA256_PATH.read_text(encoding="utf-8").split()[0].lower()
    )
    _actual_hash = hashlib.sha256(_EVALUATOR_BYTES).hexdigest().lower()
    if _actual_hash != _expected_hash:
        raise RuntimeError(
            f"WASM evaluator integrity check failed.\n"
            f"  Expected SHA-256: {_expected_hash}\n"
            f"  Actual SHA-256:   {_actual_hash}\n"
            f"  File: {_EVALUATOR_PATH}\n"
            "The evaluator.wasm binary may have been tampered with. "
            "Rebuild with build.ps1 and regenerate the .sha256 file."
        )
else:
    logger.warning(
        "evaluator.wasm.sha256 not found at %s — skipping integrity check. "
        "This is expected during development but not in release builds.",
        _EVALUATOR_SHA256_PATH,
    )


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ExecutionResult:
    """Structured result returned from :meth:`WasmExecutor.execute`."""

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
# Sandbox errors — translated to the sanitised ``error`` field
# ---------------------------------------------------------------------------


class _SandboxError(Exception):
    """Raised on the Python side to terminate execution with a known category."""

    def __init__(self, category: str) -> None:
        super().__init__(category)
        self.category = category


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _serialize_com_return(value: Any) -> Any:
    """Recursively normalise a COM return value into JSON-compatible types.

    The COM surface audit (``docs/plan-research-support/enumerate-com-api.py``)
    confirmed every return value is a scalar (``bool | int | float | str |
    None``) or a container (``list | tuple``) of the same. Anything else is
    a bug to catch in tests.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_serialize_com_return(v) for v in value]
    raise TypeError(f"Unexpected COM return type: {type(value).__name__}")


def _sanitize_com_error(where: str, exc: BaseException) -> str:
    """Produce a short, non-revealing error string for the WASM side.

    The Python traceback is logged at DEBUG server-side.  For
    ``pywintypes.com_error`` the ``args`` tuple contains
    ``(hresult, description, exc_info, argerror)`` where ``exc_info``
    is ``(wcode, source, text, helpFile, helpContext, scode)`` —
    ``helpFile`` and ``source`` can leak DLL paths and module names.
    We extract only the HRESULT and the human-readable description.
    """
    logger.debug("COM error in %s", where, exc_info=True)
    cls = type(exc).__name__

    # pywintypes.com_error: args = (hresult, description, exc_info, argerror)
    if hasattr(exc, "args") and isinstance(exc.args, tuple) and len(exc.args) >= 2:
        hresult, description, *_ = exc.args
        if isinstance(hresult, int):
            desc = str(description) if description else "no description"
            return f"COM error in {where!r}: {cls}: [{hresult:#010x}] {desc}"

    # Non-COM exceptions — return only the class name, not str(exc)
    # which may contain tracebacks or path information.
    return f"COM error in {where!r}: {cls}"


@dataclass
class _CallState:
    """Mutable state shared across host-function calls within one execute()."""

    handle_table: dict[int, Any]
    sub_object_handles: dict[str, int] = field(default_factory=dict)
    next_handle: int = 1
    stdout_buf: bytearray = field(default_factory=bytearray)
    stderr_buf: bytearray = field(default_factory=bytearray)
    deadline: float = 0.0
    allow_destructive: bool = False

    def assert_deadline(self) -> None:
        if time.monotonic() > self.deadline:
            raise _SandboxError("timeout")


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


class WasmExecutor:
    """Run AI-generated JavaScript in the Extism WASM sandbox."""

    def __init__(
        self,
        *,
        timeout_seconds: float = EXECUTION_TIMEOUT_SECONDS,
        max_memory_pages: int = WASM_MAX_MEMORY_PAGES,
        max_stdout_bytes: int = MAX_STDOUT_BYTES,
        max_code_bytes: int = MAX_CODE_BYTES,
    ) -> None:
        self._timeout = timeout_seconds
        self._max_memory_pages = max_memory_pages
        self._max_stdout = max_stdout_bytes
        self._max_code = max_code_bytes

    # -- public API ---------------------------------------------------

    def execute(self, code: str, staad_object: Any, *, allow_destructive: bool = False) -> ExecutionResult:
        """Validate and run *code* against *staad_object*.

        Always returns an :class:`ExecutionResult`; never raises for
        expected failure modes (timeout, trap, memory, user error).

        When *allow_destructive* is ``False`` (the default), COM methods
        classified as filesystem-write or session-destructive are blocked
        inside the sandbox.  The server layer sets this to ``True`` only
        after obtaining explicit human approval via MCP elicitation —
        a host-mediated dialog the LLM cannot self-confirm.
        """
        code_bytes = code.encode("utf-8")
        if len(code_bytes) > self._max_code:
            return ExecutionResult(
                success=False,
                error=f"sandbox error: code exceeds {self._max_code} bytes",
            )

        state = _CallState(
            handle_table={0: staad_object},
            deadline=time.monotonic() + self._timeout,
            allow_destructive=allow_destructive,
        )
        functions = self._build_host_functions(state)
        manifest = {
            "wasm": [{"data": _EVALUATOR_BYTES}],
            "memory": {"max_pages": self._max_memory_pages},
            "timeout_ms": int(self._timeout * 1000),
        }

        start = time.perf_counter()
        error: str | None = None
        result: Any = None
        success = False

        try:
            plugin = extism.Plugin(manifest, wasi=True, functions=functions)
            raw = plugin.call("execute", code_bytes)
        except _SandboxError as exc:
            error = f"sandbox error: {exc.category}"
        except extism.Error as exc:
            error = self._classify_extism_error(exc, state)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("unexpected executor error", exc_info=True)
            error = f"sandbox error: {type(exc).__name__}"
        else:
            payload = self._parse_payload(raw)
            if payload is None:
                error = "sandbox error: invalid output"
            elif payload.get("ok"):
                success = True
                result = payload.get("result")
            else:
                # A plain JavaScript throw from user code — not a sandbox error.
                err_msg = payload.get("error") or "unknown error"
                error = f"user error: {err_msg}"

        duration = round(time.perf_counter() - start, 4)

        return ExecutionResult(
            success=success,
            result=result,
            stdout=_decode_buffer(state.stdout_buf),
            stderr=_decode_buffer(state.stderr_buf),
            error=error,
            duration_seconds=duration,
        )

    # -- internals ----------------------------------------------------

    def _build_host_functions(self, state: _CallState) -> list[Any]:
        """Construct host-function closures bound to *state*."""
        max_stdout = self._max_stdout

        @extism.host_fn()
        def com_get(request: str) -> str:
            try:
                state.assert_deadline()
                parsed = json.loads(request)
                handle = int(parsed.get("handle", -1))
                prop = str(parsed.get("prop", ""))
            except _SandboxError:
                raise
            except Exception:
                return json.dumps({"error": "Invalid com_get request"})

            if handle != 0:
                return json.dumps({"error": "com_get is only valid on the root object"})
            if prop not in ALLOWED_SUB_OBJECTS:
                return json.dumps({"error": f"Sub-object {prop!r} is not allowed"})

            if prop in state.sub_object_handles:
                return json.dumps({"handle": state.sub_object_handles[prop]})

            try:
                sub = getattr(state.handle_table[0], prop)
            except Exception as exc:
                return json.dumps({"error": _sanitize_com_error(f"staad.{prop}", exc)})

            h = state.next_handle
            state.next_handle += 1
            state.handle_table[h] = sub
            state.sub_object_handles[prop] = h
            return json.dumps({"handle": h})

        @extism.host_fn()
        def com_invoke(request: str) -> str:
            try:
                state.assert_deadline()
                parsed = json.loads(request)
                handle = int(parsed.get("handle", -1))
                method = str(parsed.get("method", ""))
                args = parsed.get("args", [])
                if not isinstance(args, list):
                    return json.dumps({"error": "args must be an array"})
            except _SandboxError:
                raise
            except Exception:
                return json.dumps({"error": "Invalid com_invoke request"})

            if handle not in state.handle_table:
                return json.dumps({"error": "Invalid handle"})
            if method in DENIED_METHODS:
                return json.dumps({"error": f"Method {method!r} is not allowed"})

            # Determine the logical object name for allowlist + consent checks.
            if handle == 0:
                obj_name: str | None = "_root"
                if method not in ALLOWED_ROOT_METHODS:
                    return json.dumps({"error": f"Method {method!r} is not allowed on the root object"})
            else:
                # Look up the raw sub-object name (e.g. "Geometry") from the handle.
                obj_name = None
                for name, h in state.sub_object_handles.items():
                    if h == handle:
                        obj_name = name
                        break
                if obj_name is not None:
                    allowed = ALLOWED_SUB_OBJECT_METHODS.get(obj_name, frozenset())
                    if method not in allowed:
                        return json.dumps({"error": f"Method {method!r} is not allowed on {obj_name}"})

            # ── Control 4: Consent gate for destructive / filesystem-write methods ──
            destructive_set = DESTRUCTIVE_METHODS.get(obj_name or "", frozenset())
            if method in destructive_set and not state.allow_destructive:
                return json.dumps(
                    {
                        "error": (
                            f"Method {method!r} is blocked because it can modify "
                            f"the filesystem or STAAD session. The user must "
                            f"approve this operation via the host confirmation "
                            f"dialog before it can proceed."
                        )
                    }
                )

            target = state.handle_table[handle]
            try:
                fn = getattr(target, method)
            except Exception as exc:
                return json.dumps({"error": _sanitize_com_error(f"{_handle_name(state, handle)}.{method}", exc)})
            if not callable(fn):
                return json.dumps({"error": f"Attribute {method!r} is not callable"})

            try:
                raw = fn(*args)
            except Exception as exc:
                return json.dumps({"error": _sanitize_com_error(f"{_handle_name(state, handle)}.{method}", exc)})

            try:
                value = _serialize_com_return(raw)
            except TypeError as exc:
                logger.debug("Non-serialisable COM return from %s: %r", method, raw)
                return json.dumps({"error": f"Unsupported COM return type from {method!r}: {exc}"})

            return json.dumps({"result": value})

        @extism.host_fn()
        def console_output(request: str) -> str:
            try:
                state.assert_deadline()
                parsed = json.loads(request)
                stream = str(parsed.get("stream", "stdout"))
                text = str(parsed.get("text", ""))
            except _SandboxError:
                raise
            except Exception:
                return ""

            buf = state.stderr_buf if stream == "stderr" else state.stdout_buf
            remaining = max_stdout - len(buf)
            if remaining <= 0:
                return ""
            chunk = (text + "\n").encode("utf-8", errors="replace")
            if len(chunk) > remaining:
                chunk = chunk[:remaining]
            buf.extend(chunk)
            return ""

        return [com_get, com_invoke, console_output]

    @staticmethod
    def _parse_payload(raw: Any) -> dict[str, Any] | None:
        if raw is None:
            return None
        if isinstance(raw, (bytes, bytearray)):
            try:
                raw = raw.decode("utf-8")
            except UnicodeDecodeError:
                return None
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _classify_extism_error(exc: extism.Error, state: _CallState) -> str:
        """Map raw Extism/Wasmtime errors to sanitised sandbox categories."""
        msg = str(exc).lower()
        if time.monotonic() > state.deadline or "timeout" in msg or "deadline" in msg:
            return "sandbox error: timeout"
        if "memory" in msg or "oom" in msg or "out of memory" in msg:
            return "sandbox error: memory limit exceeded"
        if "unreachable" in msg or "trap" in msg or "unknown import" in msg:
            return "sandbox error: trap"
        logger.debug("unclassified extism error: %s", exc)
        return "sandbox error: trap"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _decode_buffer(buf: bytearray) -> str:
    try:
        return buf.decode("utf-8")
    except UnicodeDecodeError:
        return buf.decode("utf-8", errors="replace")


def _handle_name(state: _CallState, handle: int) -> str:
    """Return a short label like 'staad' or 'staad.Geometry' for error text."""
    if handle == 0:
        return "staad"
    for name, h in state.sub_object_handles.items():
        if h == handle:
            return f"staad.{name}"
    return f"handle-{handle}"
