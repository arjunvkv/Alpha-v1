# Kill All Trading Desk Processes PowerShell Script (kill_all_system.ps1)

Set-Location C:\Trading\Alpha

Write-Host "======================================================================" -ForegroundColor Red
Write-Host "         KILL ALL INTELLIGENT TRADING DESK PROCESSES (PS1)" -ForegroundColor Red
Write-Host "======================================================================" -ForegroundColor Red
Write-Host ""
Write-Host "[STOPPING] Terminating all active intelligent daemons, MCP servers, story windows, and background workers..." -ForegroundColor Yellow

Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and ($_.CommandLine -like '*intelligent_daemon*' -or $_.CommandLine -like '*alpha_mcp_server*' -or $_.CommandLine -like '*daemon_v2*' -or $_.CommandLine -like '*start_system*') } | Stop-Process -Force -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'powershell.exe' -and $_.CommandLine -like '*live_story.log*' } | Stop-Process -Force -ErrorAction SilentlyContinue

Write-Host "[STOP OK] All trading processes and background daemons cleanly terminated." -ForegroundColor Green
Start-Sleep -Seconds 1
