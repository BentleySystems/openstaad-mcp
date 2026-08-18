# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the OpenSTAAD MCP server.

Produces one single-file executable:
- openstaad-mcp.exe: console executable for stdio MCP transport.

Both bundle the Python runtime, all dependencies, openstaadpy, and bundled
STAAD skills content.
"""

import importlib.util
import os
import tomllib
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

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

# openstaadpy is installed editable in dev venvs: its finder redirects imports to
# the real source checkout, but PyInstaller's static modulegraph analysis does not
# follow that redirection, so hidden-import verification fails even though
# collect_all() can find the submodule names by walking the filesystem. Resolve the
# real source directory via importlib and add its parent to pathex so modulegraph
# treats it like a normal package on the path.
openstaadpy_extra_pathex = []
_openstaadpy_spec = importlib.util.find_spec("openstaadpy")
if _openstaadpy_spec and _openstaadpy_spec.submodule_search_locations:
    openstaadpy_extra_pathex.append(str(Path(list(_openstaadpy_spec.submodule_search_locations)[0]).parent))

openstaadpy_datas, openstaadpy_binaries, openstaadpy_hiddenimports = collect_all("openstaadpy")

# comtypes is openstaadpy's COM layer; collect_all("openstaadpy") does not pull in
# transitive third-party deps, and comtypes dynamically generates/imports
# submodules (comtypes.gen, comtypes.stream, etc.) that static analysis misses.
comtypes_datas, comtypes_binaries, comtypes_hiddenimports = collect_all("comtypes")


def _build_version_info(raw_version):
    """Windows version resource (Bentley copyright, FileVersion, etc.), required
    by the internal ADO signing/compliance audit."""
    parts = (raw_version.split(".") + ["0", "0", "0", "0"])[:4]
    version_tuple = tuple(int(p) for p in parts)
    version_string = ".".join(str(p) for p in version_tuple)
    return VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=version_tuple,
            prodvers=version_tuple,
            mask=0x3F,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        "040904B0",
                        [
                            StringStruct("CompanyName", "Bentley Systems, Incorporated"),
                            StringStruct("FileDescription", "OpenSTAAD MCP Server"),
                            StringStruct("FileVersion", version_string),
                            StringStruct("InternalName", "openstaad-mcp"),
                            StringStruct(
                                "LegalCopyright",
                                "Copyright (c) Bentley Systems, Incorporated. All rights reserved.",
                            ),
                            StringStruct("OriginalFilename", "openstaad-mcp.exe"),
                            StringStruct("ProductName", "OpenSTAAD MCP Server"),
                            StringStruct("ProductVersion", version_string),
                        ],
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )


# ADO exposes its Build.BuildNumber (e.g. "26.0.0.14", tracking the STAAD.Pro
# release train) as the BUILD_BUILDNUMBER env var automatically. GitHub Actions
# and local builds don't set it, so fall back to pyproject.toml's own version.
raw_version = os.environ.get("BUILD_BUILDNUMBER")
if not raw_version:
    with open(ROOT / "pyproject.toml", "rb") as f:
        raw_version = tomllib.load(f)["project"]["version"]
version_info = _build_version_info(raw_version)

a = Analysis(
    [str(ROOT / "src" / "openstaad_mcp" / "main.py")],
    pathex=[str(ROOT / "src")] + openstaadpy_extra_pathex,
    binaries=openstaadpy_binaries + comtypes_binaries,
    datas=skills_data + package_metadata + openstaadpy_datas + comtypes_datas,
    hiddenimports=[
        "openstaad_mcp",
        "openstaad_mcp.server",
        "openstaad_mcp.connection",
        "openstaad_mcp.sandbox",
        "openstaad_mcp.sandbox.executor",
        "uvicorn",
        "fastmcp",
    ]
    + openstaadpy_hiddenimports
    + comtypes_hiddenimports,
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
    version=version_info,
)
