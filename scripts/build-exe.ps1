Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot
try {
    uv run --extra capture --extra controller --with pyinstaller pyinstaller --noconfirm --clean .\GameCurveProbe.spec
} finally {
    Pop-Location
}
