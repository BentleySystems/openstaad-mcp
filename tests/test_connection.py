"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Tests for InstanceRegistry, get_active_instances, and connect_and_run.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from openstaad_mcp.connection import InstanceRegistry, StaadInstance, connect_and_run, _com_thread_semaphore, MAX_COM_THREADS

# ---------------------------------------------------------------------------
# get_active_instances — ProgID + ROT enumeration (mocked COM layer)
# ---------------------------------------------------------------------------


def _make_moniker(display_name: str, pid: int = 1234, version: str = "22.12") -> MagicMock:
    """Build a minimal mock IMoniker that behaves like a STAAD FileMoniker."""
    staad_obj = MagicMock()
    staad_obj.GetProcessId = pid
    staad_obj.GetApplicationVersion = version

    moniker = MagicMock()
    moniker.GetDisplayName.return_value = display_name
    moniker.BindToObject.return_value = MagicMock()  # IDispatch
    return moniker, staad_obj


def _make_progid_staad(pid: int = 1234, version: str = "22.12", file_path: str = "") -> MagicMock:
    """Build a mock COM object returned by GetActiveObject("StaadPro.OpenSTAAD")."""
    staad_obj = MagicMock()
    staad_obj.GetProcessId = pid
    staad_obj.GetApplicationVersion = version
    staad_obj.GetSTAADFile.return_value = file_path
    return staad_obj


class TestGetActiveInstances:
    def _patch_com(
        self,
        monikers: list[tuple[str, int, str]],
        progid_staad: MagicMock | None = None,
    ):
        """Return a context-manager that patches the module-level pythoncom/win32com mocks.

        *progid_staad*: if provided, ``GetActiveObject`` returns it.
                        If ``None``, ``GetActiveObject`` raises ``OSError``.
        """
        pythoncom_mock = MagicMock()
        win32com_mock = MagicMock()

        # --- ProgID path ---
        if progid_staad is not None:
            win32com_mock.client.GetActiveObject.return_value = progid_staad
        else:
            win32com_mock.client.GetActiveObject.side_effect = OSError("no instance")

        # --- ROT path ---
        moniker_objs = []
        staad_objs = []
        for display_name, pid, version in monikers:
            m, s = _make_moniker(display_name, pid, version)
            moniker_objs.append(m)
            staad_objs.append(s)

        # IEnumMoniker.Next yields one moniker at a time then []
        calls = iter([[m] for m in moniker_objs] + [[]])
        enum = MagicMock()
        enum.Next.side_effect = lambda n: next(calls)

        rot = MagicMock()
        rot.EnumRunning.return_value = enum

        pythoncom_mock.GetRunningObjectTable.return_value = rot
        pythoncom_mock.CreateBindCtx.return_value = MagicMock()
        pythoncom_mock.IID_IDispatch = object()

        # win32com.client.Dispatch returns the matching staad object per call
        dispatch_calls = iter(staad_objs)
        win32com_mock.client.Dispatch.side_effect = lambda _: next(dispatch_calls)

        return patch.multiple(
            "openstaad_mcp.connection",
            pythoncom=pythoncom_mock,
            win32com=win32com_mock,
        )

    def test_rot_filters_non_std_monikers(self):
        """ROT scan skips non-.std monikers; ProgID disabled for this test."""
        registry = InstanceRegistry()
        with (
            patch("openstaad_mcp.connection.sys") as sys_mock,
            self._patch_com(
                monikers=[
                    ("C:\\Models\\Bridge.std", 1234, "22.12"),
                    ("C:\\Notes\\readme.txt", 9999, ""),
                    ("C:\\Models\\Tower.std", 5678, "22.12"),
                ],
            ),
        ):
            sys_mock.platform = "win32"
            results = registry.get_active_instances()

        assert len(results) == 2
        paths = [r.file_path for r in results]
        assert "C:\\Models\\Bridge.std" in paths
        assert "C:\\Models\\Tower.std" in paths
        assert not any("readme" in p for p in paths)

    def test_rot_assigns_monotonic_aliases(self):
        """ROT-discovered instances get monotonic aliases; ProgID disabled."""
        registry = InstanceRegistry()
        with (
            patch("openstaad_mcp.connection.sys") as sys_mock,
            self._patch_com(
                monikers=[
                    ("C:\\A.std", 100, "22.12"),
                    ("C:\\B.std", 200, "22.12"),
                ],
            ),
        ):
            sys_mock.platform = "win32"
            results = registry.get_active_instances()

        aliases = {r.pid: r.alias for r in results}
        assert aliases[100] == "staadPro1"
        assert aliases[200] == "staadPro2"
        assert registry._next_num == 3

    def test_progid_finds_unsaved_instance(self):
        """ProgID discovers STAAD even when no .std file is open (empty file_path)."""
        registry = InstanceRegistry()
        progid = _make_progid_staad(pid=42, version="23.00", file_path="")
        with (
            patch("openstaad_mcp.connection.sys") as sys_mock,
            self._patch_com(monikers=[], progid_staad=progid),
        ):
            sys_mock.platform = "win32"
            results = registry.get_active_instances()

        assert len(results) == 1
        assert results[0].pid == 42
        assert results[0].file_path == ""
        assert results[0].version == "23.00"

    def test_progid_finds_saved_instance(self):
        """ProgID discovers STAAD that has a saved .std file open."""
        registry = InstanceRegistry()
        progid = _make_progid_staad(pid=100, version="22.12", file_path="C:\\Project\\Model.std")
        with (
            patch("openstaad_mcp.connection.sys") as sys_mock,
            self._patch_com(monikers=[], progid_staad=progid),
        ):
            sys_mock.platform = "win32"
            results = registry.get_active_instances()

        assert len(results) == 1
        assert results[0].file_path == "C:\\Project\\Model.std"

    def test_dedup_progid_and_rot_same_pid(self):
        """When ProgID and ROT find the same PID, it appears only once."""
        registry = InstanceRegistry()
        progid = _make_progid_staad(pid=1234, version="22.12", file_path="C:\\A.std")
        with (
            patch("openstaad_mcp.connection.sys") as sys_mock,
            self._patch_com(
                monikers=[("C:\\A.std", 1234, "22.12")],
                progid_staad=progid,
            ),
        ):
            sys_mock.platform = "win32"
            results = registry.get_active_instances()

        assert len(results) == 1
        assert results[0].pid == 1234

    def test_progid_plus_rot_different_pids(self):
        """ProgID finds one instance, ROT finds a second — both appear."""
        registry = InstanceRegistry()
        progid = _make_progid_staad(pid=100, version="22.12", file_path="C:\\A.std")
        with (
            patch("openstaad_mcp.connection.sys") as sys_mock,
            self._patch_com(
                monikers=[("C:\\B.std", 200, "22.12")],
                progid_staad=progid,
            ),
        ):
            sys_mock.platform = "win32"
            results = registry.get_active_instances()

        assert len(results) == 2
        pids = {r.pid for r in results}
        assert pids == {100, 200}

    def test_progid_fails_falls_back_to_rot(self):
        """When ProgID raises, ROT scan still discovers instances."""
        registry = InstanceRegistry()
        with (
            patch("openstaad_mcp.connection.sys") as sys_mock,
            self._patch_com(
                monikers=[("C:\\Models\\Bridge.std", 5678, "22.12")],
                progid_staad=None,  # ProgID fails
            ),
        ):
            sys_mock.platform = "win32"
            results = registry.get_active_instances()

        assert len(results) == 1
        assert results[0].pid == 5678

    def test_non_windows_returns_empty(self):
        registry = InstanceRegistry()
        with patch("openstaad_mcp.connection.sys") as sys_mock:
            sys_mock.platform = "linux"
            results = registry.get_active_instances()
        assert results == []


# ---------------------------------------------------------------------------
# execute_code / get_status instance selection (mocked get_active_instances)
# ---------------------------------------------------------------------------


def _mock_get_active_instances(instances: list[StaadInstance]):
    """Return a patch that makes InstanceRegistry.get_active_instances return *instances*."""
    return patch.object(InstanceRegistry, "get_active_instances", return_value=instances)


class TestInstanceSelection:
    def test_auto_select_single_instance(self):
        """With one instance and no 'instance' param, it is selected automatically."""
        from openstaad_mcp.server import create_mcp_server

        single = [StaadInstance(alias="staadPro1", pid=1234, file_path="C:\\A.std", version="22.12")]
        expected = {"success": True, "result": 42, "stdout": "", "stderr": "", "error": None, "duration_seconds": 0.1}

        with (
            _mock_get_active_instances(single),
            patch("openstaad_mcp.server.connect_and_run", return_value=expected) as mock_run,
        ):
            mcp = create_mcp_server()
            asyncio.run(mcp.call_tool("execute_code", {"code": "result = 42"}))
            assert mock_run.called
            called_path = mock_run.call_args[0][1]
            assert called_path == "C:\\A.std"

    def test_auto_select_errors_on_zero_instances(self):
        with _mock_get_active_instances([]):
            from openstaad_mcp.server import create_mcp_server

            mcp = create_mcp_server()
            result = asyncio.run(mcp.call_tool("execute_code", {"code": "result = 1"}))
            text = result.content[0].text
            assert "No STAAD.Pro instances found" in text

    def test_auto_select_errors_on_multiple_instances(self):
        two = [
            StaadInstance(alias="staadPro1", pid=1234, file_path="C:\\A.std", version="22.12"),
            StaadInstance(alias="staadPro2", pid=5678, file_path="C:\\B.std", version="22.12"),
        ]
        with _mock_get_active_instances(two):
            from openstaad_mcp.server import create_mcp_server

            mcp = create_mcp_server()
            result = asyncio.run(mcp.call_tool("execute_code", {"code": "result = 1"}))
            text = result.content[0].text
            assert "staadPro1" in text
            assert "staadPro2" in text


# ---------------------------------------------------------------------------
# connect_and_run — timeout
# ---------------------------------------------------------------------------


class TestConnectAndRun:
    def test_timeout_raises_timeout_error(self):
        """connect_and_run raises TimeoutError when the worker doesn't finish in time."""
        barrier = threading.Event()

        def _hang(staad: Any) -> None:
            barrier.wait(timeout=30)

        mock_os = MagicMock()
        mock_os.connect.return_value = MagicMock()

        import sys

        with (
            patch.dict(sys.modules, {"openstaadpy": MagicMock(), "openstaadpy.os_analytical": mock_os}),
            pytest.raises(TimeoutError),
        ):
            connect_and_run(_hang, "C:\\A.std", timeout=0.2)
        barrier.set()

    def test_non_windows_raises_import_error(self):
        """On non-Windows, openstaadpy is unavailable — ImportError propagates as exception."""
        import sys

        def _fn(staad: Any) -> str:
            return "ok"

        with (
            patch.dict(sys.modules, {"openstaadpy": None, "openstaadpy.os_analytical": None}),
            pytest.raises(ImportError),
        ):
            connect_and_run(_fn, "C:\\A.std", timeout=5.0)

    def test_semaphore_released_on_success(self):
        """Semaphore slot is released after a successful call."""
        import sys

        mock_os = MagicMock()
        mock_os.connect.return_value = MagicMock()

        before = _com_thread_semaphore._value  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"openstaadpy": MagicMock(), "openstaadpy.os_analytical": mock_os}):
            result = connect_and_run(lambda staad: 42, "C:\\A.std", timeout=5.0)

        assert result == 42
        after = _com_thread_semaphore._value  # type: ignore[attr-defined]
        assert after == before, "Semaphore should be back to its original count after success"

    def test_semaphore_consumed_during_timeout(self):
        """When a call times out, the semaphore slot stays consumed until the worker finishes."""
        import sys

        barrier = threading.Event()
        worker_done = threading.Event()

        def _hang(staad: Any) -> None:
            barrier.wait(timeout=30)
            worker_done.set()

        mock_os = MagicMock()
        mock_os.connect.return_value = MagicMock()

        before = _com_thread_semaphore._value  # type: ignore[attr-defined]

        with (
            patch.dict(sys.modules, {"openstaadpy": MagicMock(), "openstaadpy.os_analytical": mock_os}),
            pytest.raises(TimeoutError),
        ):
            connect_and_run(_hang, "C:\\A.std", timeout=0.1)

        # Slot should be consumed (worker still running)
        during = _com_thread_semaphore._value  # type: ignore[attr-defined]
        assert during == before - 1, "Semaphore slot should be consumed while worker is abandoned"

        # Let the worker finish and verify slot is returned
        barrier.set()
        worker_done.wait(timeout=5)
        # Give the finally block a moment to release
        import time
        time.sleep(0.1)
        after = _com_thread_semaphore._value  # type: ignore[attr-defined]
        assert after == before, "Semaphore should be restored after abandoned worker finishes"

    def test_semaphore_exhaustion_raises_runtime_error(self):
        """When all semaphore slots are consumed, connect_and_run raises RuntimeError immediately."""
        import sys
        import openstaad_mcp.connection as conn

        original_value = MAX_COM_THREADS
        barriers = []
        threads_started = []

        mock_os = MagicMock()
        mock_os.connect.return_value = MagicMock()

        # Temporarily set a small semaphore for this test
        old_sem = conn._com_thread_semaphore
        conn._com_thread_semaphore = threading.Semaphore(2)

        try:
            # Consume both slots with hanging workers
            for _ in range(2):
                b = threading.Event()
                barriers.append(b)

                def _hang(staad: Any, barrier=b) -> None:
                    barrier.wait(timeout=30)

                with (
                    patch.dict(sys.modules, {"openstaadpy": MagicMock(), "openstaadpy.os_analytical": mock_os}),
                    pytest.raises(TimeoutError),
                ):
                    connect_and_run(_hang, "C:\\A.std", timeout=0.1)

            # Third call should fail immediately with RuntimeError
            with pytest.raises(RuntimeError, match="Too many concurrent COM calls"):
                connect_and_run(lambda s: 1, "C:\\A.std", timeout=5.0)
        finally:
            # Clean up: release workers and restore original semaphore
            for b in barriers:
                b.set()
            import time
            time.sleep(0.2)
            conn._com_thread_semaphore = old_sem
