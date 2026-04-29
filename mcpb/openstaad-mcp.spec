# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the OpenSTAAD MCP server.

Produces one single-file executable:
- openstaad-mcp.exe: console executable for stdio MCP transport.

Both bundle the Python runtime, all dependencies, openstaadpy, and bundled
STAAD skills content.
"""

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata

block_cipher = None

ROOT = Path(SPECPATH).parent

# Collect bundled STAAD skills files (.md/.js) and the WASM evaluator.
skills_data = []
skills_dir = ROOT / "src" / "openstaad_mcp" / "staad_skills"
if skills_dir.exists():
    for f in skills_dir.rglob("*"):
        if f.is_file() and f.suffix in (".md", ".js"):
            rel_parent = f.parent.relative_to(ROOT / "src")
            skills_data.append((str(f), str(rel_parent).replace("\\", "/")))

# Bundle the pre-built WASM evaluator used by the sandbox executor.
sandbox_dir = ROOT / "src" / "openstaad_mcp" / "sandbox"
evaluator_wasm = sandbox_dir / "evaluator.wasm"
if evaluator_wasm.exists():
    skills_data.append((str(evaluator_wasm), "openstaad_mcp/sandbox"))

# fastmcp reads its version via importlib.metadata at import time.
# Include distribution metadata so frozen builds can resolve it.
package_metadata = copy_metadata("fastmcp")

# extism_sys ships a Rust-compiled DLL plus cffi bindings. collect_all picks up
# the binary, the Python shim, and any sibling data files. Using plain
# hiddenimports alone leaves the DLL unloadable at runtime.
extism_sys_datas, extism_sys_binaries, extism_sys_hiddenimports = collect_all("extism_sys")
extism_datas, extism_binaries, extism_hiddenimports = collect_all("extism")

a = Analysis(
    [str(ROOT / "src" / "openstaad_mcp" / "main.py")],
    pathex=[str(ROOT / "src")],
    binaries=extism_sys_binaries + extism_binaries,
    datas=skills_data + package_metadata + extism_sys_datas + extism_datas,
    hiddenimports=[
        "openstaad_mcp",
        "openstaad_mcp.server",
        "openstaad_mcp.connection",
        "openstaad_mcp.sandbox",
        "openstaad_mcp.sandbox.wasm_executor",
        "openstaad_mcp.sandbox.constants",
        "openstaadpy",
        "openstaadpy.os_analytical",
        "uvicorn",
        "fastmcp",
    ] + extism_sys_hiddenimports + extism_hiddenimports,
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
    [],
    exclude_binaries=True,
    name="openstaad-mcp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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

coll = COLLECT(
    console_exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="openstaad-mcp",
)
