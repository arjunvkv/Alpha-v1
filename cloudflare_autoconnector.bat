@echo off
title Cloudflare Auto-Connector for OpenCode (Tailscale Safe)
color 0A
cd /d "%~dp0"

echo ======================================================================
echo       Starting Cloudflare Auto-Connector (Tailscale Compatible)
echo ======================================================================
echo.

where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found in PATH!
    echo Please install Python or ensure it is in your system PATH.
    pause
    exit /b 1
)

python "%~dp0cloudflare_autoconnector.py"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Auto-Connector exited with an error.
    pause
)
