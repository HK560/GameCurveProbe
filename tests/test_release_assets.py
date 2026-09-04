import re
from pathlib import Path


def test_readmes_are_bilingual_and_emoji_free() -> None:
    english = Path('README.md').read_text(encoding='utf-8')
    chinese = Path('README.zh-CN.md').read_text(encoding='utf-8')

    assert '[中文](README.zh-CN.md)' in english
    assert '[English](README.md)' in chinese
    assert '核心特性' not in english
    assert not re.search(r'[\U0001F300-\U0001FAFF]', english + chinese)


def test_exe_workflow_is_manual_and_uploads_the_build_script_output() -> None:
    workflow = Path('.github/workflows/build-exe.yml').read_text(encoding='utf-8')

    assert 'workflow_dispatch:' in workflow
    assert not re.search(r'^\s+(push|pull_request|schedule):', workflow, re.MULTILINE)
    assert 'runs-on: windows-latest' in workflow
    assert 'scripts/build-exe.ps1' in workflow
    assert 'dist/GameCurveProbe.exe' in workflow
