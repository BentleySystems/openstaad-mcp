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
    to discover running instances (COM ProgID first, ROT scan fallback).

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
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Maximum number of concurrent (or abandoned) COM worker threads.  Each
# connect_and_run call spins a daemon thread; if it times out the thread is
# abandoned (COM calls cannot be safely interrupted).  The semaphore ensures
# abandoned threads don't accumulate without bound.  20 is generous for any
# real workflow (typically 1-2 concurrent calls) but still caps a runaway.
MAX_COM_THREADS = 20
_com_thread_semaphore = threading.Semaphore(MAX_COM_THREADS)

if sys.platform == "win32":
    import pythoncom  # type: ignore[import-untyped]
    import win32com.client  # type: ignore[import-untyped]


# ---------------------------------------------------------------------------
# StaadInstance — typed result from instance discovery
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StaadInstance:
    """A running STAAD.Pro instance discovered via COM ProgID or ROT scan."""

    alias: str
    pid: int
    file_path: str
    version: str


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
    # Instance discovery (ProgID first, ROT fallback)
    # ------------------------------------------------------------------

    def get_active_instances(self) -> list[StaadInstance]:
        """Return all running STAAD.Pro instances.

        Discovery order (most reliable first):

        1. **COM ProgID** — ``GetActiveObject("StaadPro.OpenSTAAD")`` finds
           any running STAAD.Pro, even if no ``.std`` file is saved yet.
        2. **ROT scan** — enumerates ``.std`` file monikers in the Windows
           Running Object Table.  May discover additional instances that
           the ProgID shortcut misses (e.g. secondary instances).

        Results are deduplicated by PID so each physical process appears
        only once.  Returns ``[]`` on non-Windows platforms.
        """
        if sys.platform != "win32":
            return []

        result: list[StaadInstance] = []
        seen_pids: set[int] = set()
        error: list[Exception] = []

        def _scan() -> None:
            try:
                pythoncom.CoInitialize()
                try:
                    # --- Strategy 1: COM ProgID (most reliable) --------
                    self._discover_via_progid(result, seen_pids)

                    # --- Strategy 2: ROT file-moniker scan -------------
                    self._discover_via_rot(result, seen_pids)
                finally:
                    pythoncom.CoUninitialize()
            except Exception as exc:
                error.append(exc)

        t = threading.Thread(target=_scan, daemon=True)
        t.start()
        t.join(timeout=30.0)

        if t.is_alive():
            logger.warning("Instance discovery timed out after 30s")

        if error:
            raise error[0]
        return result

    # ------------------------------------------------------------------
    # Strategy 1: COM ProgID
    # ------------------------------------------------------------------

    def _discover_via_progid(
        self,
        result: list[StaadInstance],
        seen_pids: set[int],
    ) -> None:
        """Try ``GetActiveObject("StaadPro.OpenSTAAD")``.

        This is the fastest and most reliable path — it works even when
        the user has just launched STAAD.Pro without saving a file yet.
        It only returns one instance (the most recently activated one).
        """
        try:
            staad = win32com.client.GetActiveObject("StaadPro.OpenSTAAD")
            pid: int = staad.GetProcessId
            version: str = staad.GetApplicationVersion
            try:
                file_path: str = staad.GetSTAADFile() or ""
            except Exception:
                file_path = ""

            seen_pids.add(pid)
            alias = self.assign_alias(pid)
            result.append(
                StaadInstance(
                    alias=alias,
                    pid=pid,
                    file_path=file_path,
                    version=version,
                )
            )
            logger.debug("ProgID discovery found PID %d (%s)", pid, file_path or "<unsaved>")
        except Exception:
            logger.debug("ProgID discovery did not find a STAAD instance", exc_info=True)

    # ------------------------------------------------------------------
    # Strategy 2: ROT file-moniker scan
    # ------------------------------------------------------------------

    def _discover_via_rot(
        self,
        result: list[StaadInstance],
        seen_pids: set[int],
    ) -> None:
        """Scan the Windows Running Object Table for ``.std`` file monikers.

        This may find additional instances not returned by the ProgID
        shortcut (e.g. a second STAAD.Pro process).  Instances already
        discovered (by PID) are skipped.
        """
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

                if pid in seen_pids:
                    logger.debug("ROT: skipping PID %d (already discovered)", pid)
                    continue

                seen_pids.add(pid)
                alias = self.assign_alias(pid)
                result.append(
                    StaadInstance(
                        alias=alias,
                        pid=pid,
                        file_path=display_name,
                        version=version,
                    )
                )
        except Exception:
            logger.debug("ROT scan failed", exc_info=True)


# ---------------------------------------------------------------------------
# connect_and_run — per-execution STA thread
# ---------------------------------------------------------------------------


def connect_and_run(
    fn: Callable[[Any], Any],
    file_path: str,
    timeout: float = 120.0,
) -> Any:
    """Connect to the STAAD.Pro instance that has *file_path* open and run *fn*.

    Spins a short-lived daemon thread that calls
    ``os_analytical.connect(file_path)``, executes ``fn(staad)``, and
    stores the result.  The calling thread blocks until the result is ready
    or *timeout* seconds have elapsed.

    A process-wide semaphore (``MAX_COM_THREADS``) limits the number of
    concurrent or abandoned worker threads.  If the limit is reached, the
    call fails fast rather than leaking another thread.

    Raises ``TimeoutError`` on timeout (the daemon thread is abandoned;
    COM calls cannot be safely interrupted).  Raises ``RuntimeError`` if
    too many threads are already active.  Raises any exception thrown
    by ``fn``.
    """
    if not _com_thread_semaphore.acquire(timeout=0):
        raise RuntimeError(
            f"Too many concurrent COM calls ({MAX_COM_THREADS} threads active or abandoned). "
            "This usually means previous calls timed out and their threads are still running."
        )

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
            # Release the semaphore slot only when the thread actually finishes,
            # including CoUninitialize.  If the thread was abandoned (timeout),
            # the slot stays consumed until it eventually completes.
            _com_thread_semaphore.release()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    if not done.wait(timeout=timeout):
        # Don't release the semaphore here — the thread is still running.
        # The slot stays consumed until _worker finishes on its own.
        raise TimeoutError(f"COM call did not complete within {timeout}s")

    value = result_box[0]
    if isinstance(value, Exception):
        raise value
    return value
