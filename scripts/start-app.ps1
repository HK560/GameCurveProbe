param(
    [switch]$NoBrowser,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$AppArgs
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path

function Assert-NativeSuccess([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE."
    }
}

Push-Location $repoRoot
try {
    Push-Location (Join-Path $repoRoot 'webui')
    try {
        if (-not (Test-Path -LiteralPath 'node_modules')) {
            npm ci
            Assert-NativeSuccess 'npm ci'
        }
        npm run build
        Assert-NativeSuccess 'npm run build'
    } finally {
        Pop-Location
    }

    $webDist = (Resolve-Path (Join-Path $repoRoot 'webui\dist')).Path
    $embeddedDist = Join-Path $repoRoot 'src\gamecurveprobe\web_dist'
    New-Item -ItemType Directory -Path $embeddedDist -Force | Out-Null
    Copy-Item -Path (Join-Path $webDist '*') -Destination $embeddedDist -Recurse -Force

    $launchArgs = @('--extra', 'capture', '--extra', 'controller', 'gamecurveprobe')
    if ($NoBrowser) {
        $launchArgs += '--no-browser'
    }
    $launchArgs += $AppArgs
    uv run @launchArgs
    Assert-NativeSuccess 'GameCurveProbe'
} finally {
    Pop-Location
}
