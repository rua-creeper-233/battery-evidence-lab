@echo off
setlocal
chcp 65001 >nul
title Battery Evidence Lab
cd /d "%~dp0"
set "launchScript=start.ps1"
if /I "%~1"=="rag" set "launchScript=start-rag.ps1"
if /I "%~1"=="share" set "launchScript=start-share.ps1"
if not "%~1"=="" if /I not "%~1"=="rag" if /I not "%~1"=="share" (
    echo Usage: start.bat [rag^|share]
    exit /b 2
)
echo Battery Evidence Lab - keep this window open; Ctrl+C stops the service.
if /I "%~1"=="share" (
    start "" "https://rua-creeper-233.github.io/battery-evidence-lab/"
) else (
    start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8765"
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\%launchScript%"
echo.
echo Service stopped.
pause
