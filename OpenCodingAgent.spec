# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onefile spec. Console app (not windowed) -- OpenCodingAgent is
a terminal tool, double-clicking the exe should open a real console window.

Run from the repo root: `pyinstaller OpenCodingAgent.spec --noconfirm`
Output: dist/OpenCodingAgent.exe
"""

from pathlib import Path

ROOT = Path(SPECPATH)  # noqa: F821 -- injected by PyInstaller

VERSION = "0.1.1"
FILEVERS = (0, 1, 1, 0)

VERSION_INFO_PATH = ROOT / "version_info.txt"
VERSION_INFO_PATH.write_text(
    "VSVersionInfo(\n"
    "  ffi=FixedFileInfo(\n"
    f"    filevers={FILEVERS!r},\n"
    f"    prodvers={FILEVERS!r},\n"
    "    mask=0x3f,\n"
    "    flags=0x0,\n"
    "    OS=0x40004,\n"
    "    fileType=0x1,\n"
    "    subtype=0x0,\n"
    "    date=(0, 0),\n"
    "  ),\n"
    "  kids=[\n"
    "    StringFileInfo(\n"
    "      [\n"
    "        StringTable(\n"
    "          '040904B0',\n"
    "          [\n"
    "            StringStruct('CompanyName', 'Hamzah Muhammad (@Humzeeny)'),\n"
    "            StringStruct('FileDescription', 'OpenCodingAgent - a free coding agent for your terminal'),\n"
    f"            StringStruct('FileVersion', {VERSION!r}),\n"
    "            StringStruct('InternalName', 'OpenCodingAgent'),\n"
    "            StringStruct('OriginalFilename', 'OpenCodingAgent.exe'),\n"
    "            StringStruct('ProductName', 'OpenCodingAgent'),\n"
    f"            StringStruct('ProductVersion', {VERSION!r}),\n"
    "          ],\n"
    "        )\n"
    "      ]\n"
    "    ),\n"
    "    VarFileInfo([VarStruct('Translation', [1033, 1200])]),\n"
    "  ],\n"
    ")\n",
    encoding="utf-8",
)

a = Analysis(  # noqa: F821
    ["open_coding_agent/__main__.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(ROOT / "open_coding_agent" / "SYSTEM_PROMPT.md"), "open_coding_agent")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="OpenCodingAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=str(ROOT / "OpenCodingAgent.ico"),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(VERSION_INFO_PATH),
)
