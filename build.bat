@echo off
chcp 65001 >nul
title GameCurveProbe 一键编译打包

echo ===================================================
echo   GameCurveProbe 2.0 一键独立 EXE 编译打包脚本
echo ===================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build-exe.ps1" %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo ---------------------------------------------------
    echo [错误] 打包过程出现异常，请检查上方日志！
    echo ---------------------------------------------------
    echo.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ---------------------------------------------------
echo [成功] 打包完成！
echo 可执行文件位置: %~dp0dist\GameCurveProbe.exe
echo ---------------------------------------------------
echo.
pause
