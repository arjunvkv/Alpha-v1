@echo off
title Intelligent Trading Desk - System Launcher
cd /d C:\Trading\Alpha

echo ======================================================================
echo       INTELLIGENT TRADINGAGENTS + OPENCODE CIO DESK LAUNCHER
echo ======================================================================
echo.
echo [1/4] Terminating any stale daemon background processes...
python daemon\kill_daemons.py 2>nul
powershell -Command "Start-Sleep -Seconds 1"

echo [2/4] Verifying and Auto-Launching FTMO MetaTrader 5 Terminal...
powershell -Command "$t = Get-Process terminal64 -ErrorAction SilentlyContinue; if (-not $t) { Write-Host '[MT5 LAUNCHING] FTMO MetaTrader 5 terminal not running. Auto-launching FTMO MT5...'; Start-Process 'C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe' } else { Write-Host ('[MT5 OK] FTMO Terminal Active - PID: ' + (($t.Id) -join ', ')) }"
powershell -Command "Start-Sleep -Seconds 2"

echo [3/4] Initializing Live Story Log Stream...
python -c "from logs.story_logger import log_story; log_story('System Launcher', 'Intelligent Trading Desk started via start_trading_system.bat (LIVE MT5 MODE ACTIVE).')" 2>nul

echo [4/4] Launching 24/7 Intelligent Multi-Agent Daemon...
start "Intelligent Trading Daemon" /min python -u "C:\Trading\Alpha\alpha_trading_desk.py" run
start "Live Trading Desk Story Stream" powershell.exe -NoExit -Command "Set-Location C:\Trading\Alpha; Write-Host '======================================================================' -ForegroundColor Cyan; Write-Host '            LIVE TRADING DESK STORY NARRATION STREAM (ALPHA V1)' -ForegroundColor Cyan; Write-Host '======================================================================' -ForegroundColor Cyan; Write-Host ''; Get-Content C:\Trading\Alpha\logs\live_story.log -Wait -Tail 30"

echo.
echo ======================================================================
echo [LAUNCH SUCCESS] Intelligent Trading Desk active in background.
echo                  • Execution Mode:     LIVE FTMO MT5 ORDER PLACEMENT
echo                  • FTMO MT5 Terminal:  Auto-Launched and Verified
echo                  • MCP Server Bridge:  alpha-daemon-mcp
echo                  • OpenCode (CIO):     Active Steering + Proactive Alerts
echo                  • Story Window:       "Live Trading Desk Story Stream"
echo                  • Stop System:        stop_trading_system.bat
echo ======================================================================
echo.
powershell -Command "Start-Sleep -Seconds 2"
exit /b 0
