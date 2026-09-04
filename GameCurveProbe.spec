# -*- mode: python ; coding: utf-8 -*-

import sys
from pathlib import Path

project_root = Path.cwd()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from build_tools.pyinstaller_support import collect_package_files


vgamepad_datas = collect_package_files("vgamepad", ["win/vigem/client/**/*.dll"])
wgc_datas = collect_package_files("windows_capture", ["**/*.dll", "**/*.pyd"])

# Include Vue frontend static build
web_dist_path = project_root / "src" / "gamecurveprobe" / "web_dist"
datas = vgamepad_datas + wgc_datas + [
    (str(web_dist_path), "gamecurveprobe/web_dist"),
]

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "windows_capture",
    "dxcam",
    "fastapi",
    "pydantic",
]

a = Analysis(
    ["src\\gamecurveprobe\\__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6", "tkinter", "matplotlib"],
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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "assets" / "icon.ico"),
)
