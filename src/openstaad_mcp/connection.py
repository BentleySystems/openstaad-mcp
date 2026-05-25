"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

OpenSTAAD multi-instance connection support.

Public API
----------
``StaadInstance``
    Frozen dataclass representing a running STAAD.Pro instance with fields
    ``alias``, ``pid``, ``file_path``, ``version``.

``InstanceRegistry``
    Lightweight PID-to-alias map.  Assigns stable, monotonic aliases
    (``staadPro1``, ``staadPro2``, …) to STAAD.Pro processes.  Aliases are
    never reused within a server session.  Call ``get_active_instances()``
    to enumerate running instances via the Windows ROT.

``connect_and_run(fn, file_path, timeout) -> Any``
    Spin a short-lived STA thread, call
    ``os_analytical.connect(file_path)``, execute ``fn(staad)``, and
    return the result.  Raises ``TimeoutError`` if the call exceeds
    *timeout* seconds (the daemon thread is abandoned — COM calls cannot
    be safely interrupted).
"""

from __future__ import annotations

import logging
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from openstaad_mcp.version import check_version_warning

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    import pythoncom  # type: ignore[import-untyped]
    import win32com.client  # type: ignore[import-untyped]


# ---------------------------------------------------------------------------
# StaadInstance — typed result from ROT scan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StaadInstance:
    """A running STAAD.Pro instance discovered via the Windows ROT."""

    alias: str
    pid: int
    file_path: str
    version: str
    warning: str | None = field(default=None)

    def asdict(self) -> dict[str, object]:
        """Return a JSON-serializable dict, omitting ``warning`` when ``None``."""
        d: dict[str, object] = {
            "alias": self.alias,
            "pid": self.pid,
            "file_path": self.file_path,
            "version": self.version,
        }
        if self.warning is not None:
            d["warning"] = self.warning
        return d


# ---------------------------------------------------------------------------
# InstanceRegistry — PID → alias map
# ---------------------------------------------------------------------------


class InstanceRegistry:
    """Lightweight map from process IDs to stable session aliases.

    Aliases are monotonic (``staadPro1``, ``staadPro2``, …) and are never
    reused within a server session, even if the original process closes.
    """

    def __init__(self) -> None:
        self._pid_to_alias: dict[int, str] = {}
        self._next_num = 1
        self._lock = threading.Lock()

    def assign_alias(self, pid: int) -> str:
        """Return the existing alias for *pid*, or assign a new one."""
        with self._lock:
            if pid not in self._pid_to_alias:
                self._pid_to_alias[pid] = f"staadPro{self._next_num}"
                self._next_num += 1
            return self._pid_to_alias[pid]

    def resolve(self, alias: str) -> int | None:
        """Return the PID for *alias*, or ``None`` if unknown."""
        with self._lock:
            for pid, a in self._pid_to_alias.items():
                if a == alias:
                    return pid
            return None

    # ------------------------------------------------------------------
    # ROT scanner
    # ------------------------------------------------------------------

    def get_active_instances(self) -> list[StaadInstance]:
        """Return all running STAAD.Pro instances visible in the Windows ROT.

        File paths are read directly from the FileMoniker display name —
        never cached, so model switches within an instance are always
        reflected.

        Returns ``[]`` on non-Windows platforms.
        """
        if sys.platform != "win32":
            return []

        result: list[StaadInstance] = []
        error: list[Exception] = []

        def _scan() -> None:
            try:
                pythoncom.CoInitialize()
                try:
                    rot = pythoncom.GetRunningObjectTable()
                    enum = rot.EnumRunning()
                    while True:
                        monikers = enum.Next(1)
                        if not monikers:
                            break
                        moniker = monikers[0]  # type: ignore[index]
                        try:
                            ctx = pythoncom.CreateBindCtx(0)  # type: ignore[call-arg]
                            display_name: str = moniker.GetDisplayName(ctx, None)
                        except Exception:
                            logger.debug("Failed to read moniker display name", exc_info=True)
                            continue

                        if not display_name.lower().endswith(".std"):
                            continue

                        try:
                            obj = moniker.BindToObject(ctx, None, pythoncom.IID_IDispatch)
                            staad = win32com.client.Dispatch(obj)
                            pid: int = staad.GetProcessId
                            version: str = staad.GetApplicationVersion
                        except Exception:
                            logger.debug("Failed to bind to STAAD object: %s", display_name, exc_info=True)
                            continue

                        alias = self.assign_alias(pid)
                        result.append(
                            StaadInstance(
                                alias=alias,
                                pid=pid,
                                file_path=display_name,
                                version=version,
                                warning=check_version_warning(version),
                            )
                        )
                finally:
                    pythoncom.CoUninitialize()
            except Exception as exc:
                error.append(exc)

        t = threading.Thread(target=_scan, daemon=True)
        t.start()
        t.join(timeout=30.0)

        if t.is_alive():
            logger.warning("ROT scan timed out after 30s")

        if error:
            raise error[0]
        return result


# ---------------------------------------------------------------------------
# connect_and_run — per-execution STA thread
# ---------------------------------------------------------------------------

T = TypeVar("T")


def connect_and_run(
    fn: Callable[[Any], T],
    file_path: str,
    timeout: float = 120.0,
) -> T:
    """Connect to the STAAD.Pro instance that has *file_path* open and run *fn*.

    Spins a short-lived daemon thread that calls
    ``os_analytical.connect(file_path)``, executes ``fn(staad)``, and
    stores the result.  The calling thread blocks until the result is ready
    or *timeout* seconds have elapsed.

    Raises ``TimeoutError`` on timeout (the daemon thread is abandoned;
    COM calls cannot be safely interrupted).  Raises any exception thrown
    by ``fn``.
    """
    result_box: list[Any] = [None]
    done = threading.Event()

    def _worker() -> None:
        try:
            pythoncom.CoInitialize()
            try:
                from openstaadpy import os_analytical  # type: ignore[import-untyped]

                staad = os_analytical.connect(file_path)
                result_box[0] = fn(staad)
            finally:
                pythoncom.CoUninitialize()
        except Exception as exc:
            result_box[0] = exc
        finally:
            done.set()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    if not done.wait(timeout=timeout):
        raise TimeoutError(f"COM call did not complete within {timeout}s")

    value = result_box[0]
    if isinstance(value, Exception):
        raise value
    return value
