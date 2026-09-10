"""Installer failures must stop before pip can alter a working environment."""

import ctypes
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell installer")


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "checkout with spaces"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    shutil.copyfile(Path(__file__).parents[1] / "scripts/install-codex.ps1", scripts / "install-codex.ps1")
    return root


def add_ptc_source(root):
    source = root / "src/openstaad_mcp/ptc/adapter.py"
    source.parent.mkdir(parents=True)
    source.touch()


def run_installer(root, *arguments):
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(root / "scripts/install-codex.ps1"),
            *map(str, arguments),
        ],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
        check=False,
    )


def test_checkout_without_ptc_does_not_create_environment(checkout):
    result = run_installer(checkout)
    assert result.returncode == 1
    assert "does not contain PTC" in result.stderr
    assert not (checkout / ".venv-codex").exists()


def test_missing_allowed_directory_fails_before_install(checkout):
    add_ptc_source(checkout)
    result = run_installer(checkout, "-AllowedDirectories", checkout / "missing reports")
    assert result.returncode == 1
    assert "Allowed directory does not exist" in result.stderr
    assert not (checkout / ".venv-codex").exists()


def test_python_failure_stops_installation(checkout):
    add_ptc_source(checkout)
    failing_python = checkout / "failing-python.cmd"
    failing_python.write_bytes(b"@echo off\r\nexit /b 23\r\n")
    result = run_installer(checkout, "-Python", failing_python)
    assert result.returncode == 1
    assert "Command failed (exit 23)" in result.stderr
    assert not (checkout / ".venv-codex").exists()


def test_locked_launcher_fails_before_pip_or_config_write(checkout):
    add_ptc_source(checkout)
    environment = checkout / ".venv-codex"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(environment)], check=True, timeout=30)
    launcher = environment / "Scripts/openstaad-mcp.exe"
    launcher.write_bytes(b"test launcher")
    sentinel = environment / "openstaad-codex.toml"
    sentinel.write_text("# Keep the existing configuration\n")

    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(str(launcher), 0x80000000, 0, None, 3, 0x80, None)
    assert handle != ctypes.c_void_p(-1).value, ctypes.get_last_error()
    try:
        result = run_installer(checkout)
    finally:
        kernel.CloseHandle(handle)
    assert result.returncode == 1
    assert "server executable is in use" in result.stderr
    assert "No module named pip" not in result.stderr
    assert sentinel.read_text() == "# Keep the existing configuration\n"
    assert launcher.read_bytes() == b"test launcher"
