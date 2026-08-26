# 📖 ALPHA DESK SYSTEM SHUTDOWN & CLEAN RESTART OPERATIONAL MANUAL

**Document File Name**: `SYSTEM_SHUTDOWN_AND_RESTART_PROCEDURE.md`  
**File Location**: `C:\Trading\Alpha\docs\SYSTEM_SHUTDOWN_AND_RESTART_PROCEDURE.md`  
**GitHub Repository**: `https://github.com/arjunvkv/Alpha-v1.git`  

---

## 🎯 1. PURPOSE & OVERVIEW

This reference manual documents the exact step-by-step procedures used to completely shut down, terminate, and cleanly restart the **Alpha Trading Desk** background daemon and **OpenCode** execution engine without process duplication or orphaned memory instances.

---

## 🛑 2. STEP-BY-STEP SYSTEM SHUTDOWN & KILL PROCEDURE

### Step 2.1: Audit Active Agent Background Tasks
Before terminating OS processes, inspect all active background tasks running in the agent environment:
```powershell
manage_task Action="list"
```

### Step 2.2: Terminate Agent Background Tasks
Cancel all active daemon tasks by their unique Task ID:
```powershell
manage_task Action="kill" TaskId="<task_id>"
```

### Step 2.3: Force Kill OpenCode & Python Process Trees (OS Level)
Execute a forced process tree termination at the Windows operating system level to ensure all parent/child GUI, server, and daemon processes are killed:
```cmd
cmd.exe /c "taskkill /F /IM opencode.exe /T & wmic process where \"commandline like '%%alpha_trading_desk%%'\" call terminate"
```

### Step 2.4: Verify Zero-Process Clean Slate
Confirm that no orphaned processes remain active on the host system:
1. Verify `opencode.exe` is completely stopped:
   ```cmd
   cmd.exe /c "taskkill /F /IM opencode.exe"
   # Expected Output: ERROR: The process "opencode.exe" not found.
   ```
2. Verify active task list is empty:
   ```powershell
   manage_task Action="list"
   # Expected Output: No background tasks are currently running.
   ```

---

## 🚀 3. CLEAN RESTART & PRIVILEGE ENFORCEMENT PROCEDURE

### Step 3.1: Launch Background Scanner Daemon (Read-Only Mode)
Start the background market scanner daemon as a single daemon task in `C:\Trading\Alpha`:
```cmd
python -u alpha_trading_desk.py run
```

### Step 3.2: Verify Single Process Execution & Status
Check task status to ensure only one non-duplicate instance is active:
```powershell
manage_task Action="status" TaskId="<new_task_id>"
```

---

## 🏛️ 4. MANDATORY EXECUTIVE ROLES & EXECUTION PRIVILEGES

```text
======================================================================
         ALPHA DESK ROLES & TRADING EXECUTION AUTHORITY
======================================================================
1. BACKGROUND SCANNER DAEMON:
   • Operating Posture: STRICT READ-ONLY SCANNER & DOSSIER STREAMER.
   • Responsibilities:  Scans 6 instruments (XAUUSD, XAGUSD, XPTUSD, 
                        XPDUSD, XCUUSD, USOIL.cash) every 3 minutes, 
                        logs market telemetry, and updates persistent 
                        dossiers (logs/full_desk_dossier.md).
   • Execution Privilege: 🛑 ZERO DIRECT TRADING PRIVILEGES (READ-ONLY).

2. OPENCODE BRAIN (OPENCODE CIO):
   • Operating Posture: SOLE EXECUTIVE TRADING AUTHORITY.
   • Responsibilities:  Evaluates multi-timeframe structural confluences, 
                        audits trade memory buckets, and executes high-
                        quality AAA+ institutional trades live on MT5.
   • Execution Tools:     🟢 MCP TOOLS (mcp_alpha_execute_trade, 
                         mcp_alpha_update_position, mcp_alpha_close_position).
======================================================================
```

---

## 🌐 Quick Reference Links
- **Master Mandates Manual**: [`OPENCODE_MANDATES.md`](file:///C:/Trading/Alpha/OPENCODE_MANDATES.md)
- **Trading Desk Script**: [`alpha_trading_desk.py`](file:///C:/Trading/Alpha/alpha_trading_desk.py)
- **Live Markdown Dossier**: [`logs/full_desk_dossier.md`](file:///C:/Trading/Alpha/logs/full_desk_dossier.md)
- **Active OpenCode Session Dashboard**: [http://localhost:4096/session/ses_fc27fa9d7ffe2Lh84kWRvexzhZ](http://localhost:4096/session/ses_fc27fa9d7ffe2Lh84kWRvexzhZ)
