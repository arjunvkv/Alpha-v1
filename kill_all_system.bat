@echo off
title Kill All Trading Desk Processes
cd /d C:\Trading\Alpha

echo ======================================================================
echo          TERMINATING ALL TRADING DESK PROCESSES (KILL ALL)
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
