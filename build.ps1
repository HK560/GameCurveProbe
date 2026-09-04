<#
.SYNOPSIS
    GameCurveProbe 2.0 一键编译打包独立 Windows EXE 脚本
.DESCRIPTION
    自动执行 WebUI 前端编译、测试、后端 Python 测试与 PyInstaller 独立打包及冒烟验证。
#>

$repoRoot = $PSScriptRoot
$script = Join-Path $repoRoot 'scripts\build-exe.ps1'

if (Test-Path -LiteralPath $script) {
    & $script @args
} else {
    Write-Error "找不到打包脚本: $script"
    exit 1
}
