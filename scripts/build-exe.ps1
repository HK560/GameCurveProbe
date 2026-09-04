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
        $pkgMgr = if ((Test-Path -LiteralPath 'pnpm-lock.yaml') -and (Get-Command pnpm -ErrorAction SilentlyContinue)) { 'pnpm' } else { 'npm' }
        if (-not (Test-Path -LiteralPath 'node_modules')) {
            if ($pkgMgr -eq 'pnpm') {
                pnpm install
            } else {
                npm ci
            }
            Assert-NativeSuccess 'npm ci'
        }
        & $pkgMgr run typecheck
        Assert-NativeSuccess 'npm run typecheck'
        & $pkgMgr run test
        Assert-NativeSuccess 'npm run test'
        & $pkgMgr run build
        Assert-NativeSuccess 'npm run build'
    } finally {
        Pop-Location
    }

    $webDist = (Resolve-Path (Join-Path $repoRoot 'webui\dist')).Path
    $embeddedDist = [IO.Path]::GetFullPath((Join-Path $repoRoot 'src\gamecurveprobe\web_dist'))
    $expectedPrefix = $repoRoot + [IO.Path]::DirectorySeparatorChar
    if (-not $embeddedDist.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe frontend output path: $embeddedDist"
    }
    if (Test-Path -LiteralPath $embeddedDist) {
        Remove-Item -LiteralPath $embeddedDist -Recurse -Force
    }
    Copy-Item -LiteralPath $webDist -Destination $embeddedDist -Recurse

    uv run pytest
    Assert-NativeSuccess 'pytest'
    uv run --extra capture --extra controller --with pyinstaller pyinstaller --noconfirm --clean .\GameCurveProbe.spec
    Assert-NativeSuccess 'PyInstaller'

    $exe = Join-Path $repoRoot 'dist\GameCurveProbe.exe'
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $smokePort = ([Net.IPEndPoint]$listener.LocalEndpoint).Port
    $listener.Stop()
    $smokeToken = 'build-smoke-token-' + [Guid]::NewGuid().ToString('N')
    $process = Start-Process -FilePath $exe -ArgumentList '--host', '127.0.0.1', '--port', $smokePort, '--token', $smokeToken, '--no-browser' -PassThru -WindowStyle Hidden
    try {
        $healthy = $false
        foreach ($attempt in 1..30) {
            try {
                $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$smokePort/api/health" -TimeoutSec 1
                if ($response.StatusCode -eq 200) {
                    $healthy = $true
                    break
                }
            } catch {
                Start-Sleep -Milliseconds 250
            }
        }
        if (-not $healthy) {
            throw 'GameCurveProbe.exe smoke test failed: /api/health did not become ready.'
        }
    } finally {
        $smokeProcesses = Get-CimInstance Win32_Process | Where-Object {
            $_.ExecutablePath -eq $exe -and $_.CommandLine -like "*$smokeToken*"
        }
        foreach ($smokeProcess in $smokeProcesses) {
            Stop-Process -Id $smokeProcess.ProcessId -Force -ErrorAction SilentlyContinue
            Wait-Process -Id $smokeProcess.ProcessId -Timeout 5 -ErrorAction SilentlyContinue
        }
    }
} finally {
    Pop-Location
}
