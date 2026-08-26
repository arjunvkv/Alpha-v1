@echo off
title Intelligent Trading Desk - System Stopper
cd /d C:\Trading\Alpha

echo ======================================================================
echo          TERMINATING INTELLIGENT TRADING DESK PROCESSES
echo ======================================================================
echo.
echo [STOPPING] Terminating all active intelligent daemons, MCP servers, story windows, and workers...
python daemon\kill_daemons.py
taskkill /f /fi "WINDOWTITLE eq Live Trading Desk Story Stream*" 2>nul
taskkill /f /fi "WINDOWTITLE eq Intelligent Trading Daemon*" 2>nul

echo [STOP OK] All trading processes and background daemons cleanly terminated.
echo.
powershell -Command "Start-Sleep -Seconds 2"
exit /b 0
