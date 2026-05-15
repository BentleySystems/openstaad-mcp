# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the OpenSTAAD MCP server.

Produces one single-file executable:
- openstaad-mcp.exe: console executable for stdio MCP transport.

Both bundle the Python runtime, all dependencies, openstaadpy, and bundled
STAAD skills content.
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

block_cipher = None

ROOT = Path(SPECPATH).parent

# Collect bundled STAAD skills files (.md/.py).
skills_data = []
skills_dir = ROOT / "src" / "openstaad_mcp" / "staad_skills"
if skills_dir.exists():
    for f in skills_dir.rglob("*"):
        if f.is_file() and f.suffix in (".md", ".py"):
            rel_parent = f.parent.relative_to(ROOT / "src")
            skills_data.append((str(f), str(rel_parent).replace("\\", "/")))

# fastmcp reads its version via importlib.metadata at import time.
# Include distribution metadata so frozen builds can resolve it.
package_metadata = copy_metadata("fastmcp")

a = Analysis(
    [str(ROOT / "src" / "openstaad_mcp" / "main.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=skills_data + package_metadata,
    hiddenimports=[
        "openstaadpy",
        "openstaadpy.os_analytical",
        "uvicorn",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

console_exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="openstaad-mcp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # TODO: add an .ico file
)
