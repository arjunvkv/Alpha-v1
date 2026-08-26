# Intelligent Trading Desk - System Launcher (PowerShell)

Set-Location C:\Trading\Alpha

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "       INTELLIGENT TRADINGAGENTS + OPENCODE CIO DESK LAUNCHER (PS1)" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[1/4] Terminating any stale daemon background processes..." -ForegroundColor Yellow

# Clean up stale processes
python daemon\kill_daemons.py 2>$null

Start-Sleep -Seconds 1
Write-Host "[2/4] Verifying & Auto-Launching FTMO MetaTrader 5 Terminal..." -ForegroundColor Yellow

$mt5 = Get-Process terminal64 -ErrorAction SilentlyContinue
if (-not $mt5) {
    Write-Host "[MT5 LAUNCHING] FTMO MetaTrader 5 terminal not running. Auto-launching FTMO MT5..." -ForegroundColor Yellow
    Start-Process "C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
    Start-Sleep -Seconds 3
} else {
    Write-Host ("[MT5 OK] FTMO Terminal Active - PID: " + (($mt5.Id) -join ', ')) -ForegroundColor Green
}

Start-Sleep -Seconds 1
Write-Host "[3/4] Initializing Live Story Log Stream..." -ForegroundColor Yellow
python -c "from logs.story_logger import log_story; log_story('System Launcher', 'Intelligent Trading Desk started via start_trading_system.ps1 (LIVE MT5 MODE ACTIVE).')" 2>$null

Start-Sleep -Seconds 1
Write-Host "[4/4] Launching 24/7 Intelligent Multi-Agent Daemon & Story Stream..." -ForegroundColor Yellow

Start-Process -FilePath "python.exe" -ArgumentList "-u", "C:\Trading\Alpha\daemon\intelligent_daemon.py" -WindowStyle Hidden
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location C:\Trading\Alpha; Write-Host '======================================================================' -ForegroundColor Cyan; Write-Host '            LIVE TRADING DESK STORY NARRATION STREAM (LIVE MT5)' -ForegroundColor Cyan; Write-Host '======================================================================' -ForegroundColor Cyan; Write-Host ''; Get-Content C:\Trading\Alpha\logs\live_story.log -Wait -Tail 30"

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host "[LAUNCH SUCCESS] Intelligent Trading Desk active in background." -ForegroundColor Green
Write-Host "                 • Execution Mode:     LIVE FTMO MT5 ORDER PLACEMENT" -ForegroundColor Green
Write-Host "                 • FTMO MT5 Terminal:  Auto-Launched & Verified" -ForegroundColor Green
Write-Host "                 • MCP Server Bridge:  alpha-daemon-mcp" -ForegroundColor Green
Write-Host "                 • OpenCode (CIO):     Active Steering + Proactive Alerts" -ForegroundColor Green
Write-Host "                 • Story Window:       Live Trading Desk Story Stream" -ForegroundColor Green
Write-Host "                 • Stop System:        .\stop_trading_system.ps1" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Green
Write-Host ""
Start-Sleep -Seconds 2
