# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

project_root = Path.cwd()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from build_tools.pyinstaller_support import collect_package_files


vgamepad_datas = collect_package_files("vgamepad", ["win/vigem/client/**/*.dll"])

a = Analysis(
    ["src\\gamecurveprobe\\__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=vgamepad_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GameCurveProbe",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
