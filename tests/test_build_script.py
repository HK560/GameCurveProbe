from pathlib import Path


def test_exe_build_script_runs_all_quality_gates_and_smoke_test() -> None:
    script = Path("scripts/build-exe.ps1").read_text(encoding="utf-8")

    for expected in (
        "npm ci",
        "npm run typecheck",
        "npm run test",
        "npm run build",
        "uv run pytest",
        "pyinstaller",
        "GameCurveProbe.exe",
        "/api/health",
    ):
        assert expected in script


def test_start_script_builds_syncs_and_launches_app() -> None:
    script = Path("scripts/start-app.ps1").read_text(encoding="utf-8")

    for expected in (
        "npm run build",
        "webui\\dist",
        "web_dist",
        "Copy-Item",
        "--extra', 'capture'",
        "--extra', 'controller'",
        "gamecurveprobe",
    ):
        assert expected in script
