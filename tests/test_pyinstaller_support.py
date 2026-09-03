from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_collect_package_files():
    module_path = Path(__file__).resolve().parents[1] / "build_tools" / "pyinstaller_support.py"
    spec = importlib.util.spec_from_file_location("pyinstaller_support", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.collect_package_files


def test_collect_package_files_keeps_vgamepad_client_dll_layout() -> None:
    collect_package_files = _load_collect_package_files()
    datas = collect_package_files("vgamepad", ["win/vigem/client/**/*.dll"])
    normalized = {(source.replace("\\", "/"), target.replace("\\", "/")) for source, target in datas}

    assert any(
        source.endswith("/vgamepad/win/vigem/client/x64/ViGEmClient.dll")
        and target == "vgamepad/win/vigem/client/x64"
        for source, target in normalized
    )
    assert any(
        source.endswith("/vgamepad/win/vigem/client/x86/ViGEmClient.dll")
        and target == "vgamepad/win/vigem/client/x86"
        for source, target in normalized
    )


def test_spec_collects_wgc_native_files_and_web_assets() -> None:
    text = (Path(__file__).resolve().parents[1] / "GameCurveProbe.spec").read_text(encoding="utf-8")
    normalized = text.replace("\\", "/")

    assert 'collect_package_files("windows_capture"' in text
    assert '"**/*.dll"' in text
    assert '"**/*.pyd"' in text
    assert "gamecurveprobe/web_dist" in normalized
