"""
---------------------------------------------------------------------------------------------
Copyright (c) Bentley Systems, Incorporated. All rights reserved.
See LICENSE.md in the project root for license terms and full copyright notice.
---------------------------------------------------------------------------------------------

Tests for InstanceRegistry, get_active_instances, and connect_and_run.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
from pathlib import Path
from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

import pytest

from openstaad_mcp.connection import InstanceRegistry, StaadInstance, connect_and_run
from openstaad_mcp.server import create_mcp_server

# ---------------------------------------------------------------------------
# get_active_instances — ROT enumeration (mocked COM layer)
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


class TestGetActiveInstances:
    def _patch_pythoncom(self, monikers: list[tuple[str, int, str]]):
        """Return a context-manager that patches the module-level pythoncom/win32com mocks."""
        pythoncom_mock = MagicMock()
        win32com_mock = MagicMock()

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

    def test_filters_non_std_monikers(self):
        registry = InstanceRegistry()
        with (
            patch("openstaad_mcp.connection.sys") as sys_mock,
            self._patch_pythoncom(
                [
                    ("C:\\Models\\Bridge.std", 1234, "22.12"),
                    ("C:\\Notes\\readme.txt", 9999, ""),
                    ("C:\\Models\\Tower.std", 5678, "22.12"),
                ]
            ),
        ):
            sys_mock.platform = "win32"
            results = registry.get_active_instances()

        assert len(results) == 2
        paths = [r.file_path for r in results]
        assert "C:\\Models\\Bridge.std" in paths
        assert "C:\\Models\\Tower.std" in paths
        assert not any("readme" in p for p in paths)

    def test_assigns_monotonic_aliases(self):
        registry = InstanceRegistry()
        with (
            patch("openstaad_mcp.connection.sys") as sys_mock,
            self._patch_pythoncom(
                [
                    ("C:\\A.std", 100, "22.12"),
                    ("C:\\B.std", 200, "22.12"),
                ]
            ),
        ):
            sys_mock.platform = "win32"
            results = registry.get_active_instances()

        aliases = {r.pid: r.alias for r in results}
        assert aliases[100] == "staadPro1"
        assert aliases[200] == "staadPro2"
        assert registry._next_num == 3

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

        single = [StaadInstance(alias="staadPro1", pid=1234, file_path="C:\\A.std", version="22.12")]
        expected = {"success": True, "result": 42, "stdout": "", "stderr": "", "error": None, "duration_seconds": 0.1}

        with (
            _mock_get_active_instances(single),
            patch("openstaad_mcp.server.connect_and_run", return_value=expected) as mock_run,
        ):
            mcp = create_mcp_server(allowed_dirs=[])
            asyncio.run(mcp.call_tool("execute_code", {"code": "result = 42"}))
            assert mock_run.called
            called_path = mock_run.call_args[0][1]
            assert called_path == "C:\\A.std"

    def test_auto_select_errors_on_zero_instances(self):
        with _mock_get_active_instances([]):
            mcp = create_mcp_server(allowed_dirs=[])
            result = asyncio.run(mcp.call_tool("execute_code", {"code": "result = 1"}))
            text = result.content[0].text
            assert "No STAAD.Pro instances found" in text

    def test_auto_select_errors_on_multiple_instances(self):
        two = [
            StaadInstance(alias="staadPro1", pid=1234, file_path="C:\\A.std", version="22.12"),
            StaadInstance(alias="staadPro2", pid=5678, file_path="C:\\B.std", version="22.12"),
        ]
        with _mock_get_active_instances(two):
            mcp = create_mcp_server(allowed_dirs=[])
            result = asyncio.run(mcp.call_tool("execute_code", {"code": "result = 1"}))
            text = result.content[0].text
            assert "staadPro1" in text
            assert "staadPro2" in text


class TestTruncatedCodeDiagnostics:
    """A truncated `code` argument must be attributed to the caller, not to the sandbox."""

    _INSTANCE: ClassVar = [StaadInstance(alias="staadPro1", pid=1234, file_path="C:\\A.std", version="22.12")]

    @staticmethod
    def _failure(error: str) -> dict:
        return {
            "success": False,
            "result": None,
            "stdout": "",
            "stderr": "",
            "error": error,
            "duration_seconds": 0.0,
        }

    def _call(self, code: str, error: str):
        with (
            _mock_get_active_instances(self._INSTANCE),
            patch("openstaad_mcp.server.connect_and_run", return_value=self._failure(error)),
        ):
            mcp = create_mcp_server(allowed_dirs=[])
            return asyncio.run(mcp.call_tool("execute_code", {"code": code}))

    def test_reports_received_size_and_tail(self, caplog):
        code = "staad.Geometry.AddNode(1, 0.0, 0.0,"
        error = "Validation failed:\n  line 1:23 — syntax error: '(' was never closed — truncated in transit"

        with caplog.at_level(logging.WARNING, logger="openstaad_mcp.server"):
            result = self._call(code, error)

        text = result.content[0].text
        assert f"received {len(code)} bytes" in text
        assert "ending with" in text
        assert "execute_code received 35 bytes of code" in caplog.text

    def test_ordinary_failure_is_not_annotated(self, caplog):
        error = "Validation failed:\n  line 1:0 — 'import' is not allowed"

        with caplog.at_level(logging.WARNING, logger="openstaad_mcp.server"):
            result = self._call("import os", error)

        assert "received" not in result.content[0].text
        assert "execute_code received" not in caplog.text


class TestGetStatusAllowedDirs:
    """`get_status` must report the directories currently in effect, not a stale copy."""

    _INSTANCE: ClassVar = [StaadInstance(alias="staadPro1", pid=1234, file_path="C:\\A.std", version="22.12")]
    _CONNECTED: ClassVar = {
        "connected": True,
        "staad_version": "25.0.1.293",
        "model_path": "C:\\A.std",
        "alias": "staadPro1",
        "analyzing": False,
    }

    def test_reports_configured_allowed_dirs_on_success(self):
        with (
            _mock_get_active_instances(self._INSTANCE),
            patch("openstaad_mcp.server.connect_and_run", return_value=self._CONNECTED),
        ):
            mcp = create_mcp_server(allowed_dirs=[Path("C:\\Models"), Path("C:\\Exports")])
            result = asyncio.run(mcp.call_tool("get_status", {}))

        text = result.content[0].text
        assert "Models" in text
        assert "Exports" in text

    def test_reports_no_allowed_dirs_when_none_configured(self):
        with (
            _mock_get_active_instances(self._INSTANCE),
            patch("openstaad_mcp.server.connect_and_run", return_value=self._CONNECTED),
        ):
            mcp = create_mcp_server(allowed_dirs=[])
            result = asyncio.run(mcp.call_tool("get_status", {}))

        assert '"allowed_dirs":[]' in result.content[0].text

    def test_reports_allowed_dirs_even_when_no_instance_found(self):
        with _mock_get_active_instances([]):
            mcp = create_mcp_server(allowed_dirs=[Path("C:\\Models")])
            result = asyncio.run(mcp.call_tool("get_status", {}))

        text = result.content[0].text
        assert "No STAAD.Pro instances found" in text
        assert "Models" in text


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

        with (
            patch.dict(sys.modules, {"openstaadpy": MagicMock(), "openstaadpy.os_analytical": mock_os}),
            pytest.raises(TimeoutError),
        ):
            connect_and_run(_hang, "C:\\A.std", timeout=0.2)
        barrier.set()

    def test_non_windows_raises_import_error(self):
        """On non-Windows, openstaadpy is unavailable — ImportError propagates as exception."""

        def _fn(staad: Any) -> str:
            return "ok"

        with (
            patch.dict(sys.modules, {"openstaadpy": None, "openstaadpy.os_analytical": None}),
            pytest.raises(ImportError),
        ):
            connect_and_run(_fn, "C:\\A.std", timeout=5.0)
