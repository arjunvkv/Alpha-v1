# Alpha-v1: Institutional Quantitative Trading Desk & OpenCode CIO Brain

Autonomous multi-agent quantitative trading system and institutional reasoning engine integrated with FTMO MetaTrader 5 ($100K Account).

This document provides the complete operations and startup reference for all background daemons, the Cloudflare proxy bridge, Tailscale remote access, OpenCode memory worker service, and trading desk workflows.

---

## 🏛️ System Architecture Overview

```
                           +-------------------------------------------------------------+
                           |                     Tailscale Network                       |
                           |                (e.g., Node IP: 100.95.56.22)                |
                           +------------------------------+------------------------------+
                                                          |
                               +--------------------------+--------------------------+
                               |                                                     |
                               v                                                     v
                    [Mobile / Laptop UI]                                [Remote Proxy Clients]
                 http://100.95.56.22:4096                              http://100.95.56.22:40001
                               |                                                     |
                               +--------------------------+--------------------------+
                                                          |
                                                          v
+-------------------------------------------------------------------------------------------------------------------------+
| Local Trading Workstation (C:\Trading)                                                                                  |
|                                                                                                                         |
|  1. OpenCode Server (Port 4096)                                                                                         |
|     - Model: opencode/big-pickle                                                                                        |
|     - Active CIO Session: Escanor (Autonomous Deliberation)                                                             |
|     - HTTP_PROXY -> 127.0.0.1:40001 (all LLM queries to opencode.ai routed through Cloudflare WARP)                   |
|                                                                                                                         |
|  2. Cloudflare Auto-Connector & Proxy Bridge (C:\Trading\cloudflare_autoconnector.py)                                   |
|     - HTTP Connect & Forward Bridge: 0.0.0.0:40001                                                                      |
|     - Forwards to Cloudflare WARP SOCKS5: 127.0.0.1:40000                                                               |
|     - Auto-rotates WARP IP upon 429 rate limits or connection resets                                                    |
|                                                                                                                         |
|  3. Consolidated Trading Desk Daemon (C:\Trading\Alpha\alpha_trading_desk.py)                                           |
|     - Sensor layer: Real MT5 tick stream (2s), 500ms Watcher engine, Granger 7-layer institutional telemetry            |
|     - Dispatches live Evidence Wakes (HTTP 204 prompt_async) directly into OpenCode CIO session                         |
|                                                                                                                         |
|  4. OpenCode Memory Worker Service (C:\Agent\opencode-mem\dist\services\worker-service.js)                              |
|     - Persistent cross-session vector & semantic memory indexing                                                        |
|     - Powers MCP tools: recall_memory, store_memory, search_memory                                                      |
|                                                                                                                         |
|  5. FastMCP Server (C:\Trading\Alpha\mcp_server\alpha_mcp_server.py)                                                    |
|     - Exposes atomic tools to OpenCode: get_market_regime_context, place_pending_order, execute_trade, update_position  |
|                                                                                                                         |
|  6. MetaTrader 5 Terminal (FTMO $100K Account)                                                                          |
|     - Execution bridge for XAUUSD (Gold) market orders, pending limit/stop ladders, and position modifications          |
+-------------------------------------------------------------------------------------------------------------------------+
```

---

## 📦 Component Breakdown: What Each Service Does

### 1. Cloudflare Auto-Connector & Proxy Bridge (`cloudflare_autoconnector.py`)
- **Location:** `C:\Trading\cloudflare_autoconnector.py`
- **What It Does:**
  - Manages Cloudflare WARP in **Proxy Mode** (SOCKS5 on port `40000`).
  - Hosts a high-throughput, multi-threaded **HTTP CONNECT Proxy Bridge** on `0.0.0.0:40001` (accessible via `localhost` and your Tailscale node `100.95.56.22:40001`).
  - Monitors outbound traffic to `opencode.ai` and external economic calendar / news APIs.
  - Automatically intercepts 429 rate limits, Cloudflare challenges, and network timeouts; disconnects and reconnects WARP to rotate the public exit IP within 2-3 seconds, and seamlessly dispatches continuation prompts so the AI agent never stalls.

### 2. Tailscale Mesh Proxy & Remote Access
- **Service Name:** `Tailscale` / `tailscaled.exe`
- **What It Does:**
  - Creates a zero-config, encrypted peer-to-peer wireguard mesh between your desktop workstation, laptop, and mobile phones.
  - Exposes the OpenCode Web UI (`http://100.95.56.22:4096`) so you can monitor live CIO deliberation, inspect charts, and manage positions remotely from any device.
  - Exposes the Cloudflare Proxy Bridge (`http://100.95.56.22:40001`) to any authorized device on your Tailscale network.

### 3. OpenCode Memory Worker Service (`worker-service.js`)
- **Location:** `C:\Agent\opencode-mem` (`dist/services/worker-service.js`)
- **What It Does:**
  - Operates as a persistent background daemon for the `opencode-mem` MCP server.
  - Ingests transcripts, trade decisions, and post-trade reflections into a local database and vector store.
  - Enables OpenCode to recall past mistakes, winning playbooks, and strategic user directives across new sessions, reboots, and session resets.

### 4. Alpha Consolidated Trading Desk Daemon (`alpha_trading_desk.py`)
- **Location:** `C:\Trading\Alpha\alpha_trading_desk.py`
- **What It Does:**
  - Runs 24/5 continuous market surveillance:
    - **2s Sampling Loop:** Ingests live broker prices, bid/ask spreads, tape velocity, tick CVD, 4M footprint blocks, and multi-timeframe 100-bar roadways.
    - **500ms Universal Watcher:** Monitors pending order fills, price crossovers, and order-flow triggers at sub-second speeds.
    - **News Engine & Catalyst Arbiter:** Pulls direct institutional wires (U.S. Treasury press, Federal Reserve feeds, global macro headlines) with context snippets and calendar proximity checks.
  - Automatically formats the unmanipulated market reality into an **Evidence Wake** and delivers it via asynchronous HTTP prompt to the active OpenCode session.

### 5. OpenCode Server (`opencode serve`)
- **Binary:** `opencode` (listening on port `4096`)
- **What It Does:**
  - Hosts the deliberative AI model (`opencode/big-pickle`).
  - Executes OpenCode CIO reasoning cycles adhering to the 90% News & Macro / 10% Technicals framework, managing FTMO risk guardrails, and executing trades via atomic FastMCP tools.

---

## 🚀 Step-by-Step Startup Guide

Follow this sequence to start the entire autonomous trading stack from scratch.

### Step 1: Start Cloudflare WARP & The Auto-Connector Proxy

1. Open PowerShell and ensure WARP is configured in proxy mode:
   ```powershell
   warp-cli mode proxy
   warp-cli connect
   ```
2. Start the `cloudflare_autoconnector` background process:
   ```powershell
   # Option A: Run directly in a terminal / background:
   python C:\Trading\cloudflare_autoconnector.py

   # Option B: Run via batch script:
   C:\Trading\cloudflare_autoconnector.bat
   ```
3. **Verify Proxy Bridge is Working:**
   ```powershell
   curl.exe -x 127.0.0.1:40001 -s https://cloudflare.com/cdn-cgi/trace
   ```
   *Expected Output:* `warp=on` and your active Cloudflare exit IP.

---

### Step 2: Start OpenCode Memory Worker Service

1. Open PowerShell and start the memory worker daemon using `bun` or `node`:
   ```powershell
   bun C:\Agent\opencode-mem\dist\services\worker-service.js --daemon
   ```
   *(Or via npm script from `C:\Agent\opencode-mem`: `npm run worker:start`)*
2. **Verify Worker Status:**
   ```powershell
   Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*worker-service.js*" }
   ```

---

### Step 3: Start OpenCode Server (Bound to Tailscale & Proxied)

To ensure OpenCode routes all outbound LLM traffic through Cloudflare WARP without breaking local connections or Tailscale, export proxy environment variables before launching:

```cmd
:: In cmd.exe (or save as start_opencode.bat):
set HTTP_PROXY=http://127.0.0.1:40001
set http_proxy=http://127.0.0.1:40001
set HTTPS_PROXY=http://127.0.0.1:40001
set https_proxy=http://127.0.0.1:40001
set ALL_PROXY=http://127.0.0.1:40001
set all_proxy=http://127.0.0.1:40001
set NO_PROXY=localhost,127.0.0.1,::1,100.*
set no_proxy=localhost,127.0.0.1,::1,100.*

opencode serve --port 4096 --hostname 0.0.0.0
```

*Access endpoints:*
- Localhost Web UI: `http://127.0.0.1:4096`
- Tailscale Web UI: `http://100.95.56.22:4096`

---

### Step 4: Start Alpha Consolidated Trading Desk Daemon

Ensure MetaTrader 5 is launched and logged into your FTMO account. Then launch the trading desk daemon:

```powershell
# In PowerShell:
python C:\Trading\Alpha\alpha_trading_desk.py
```

The daemon will:
1. Detect or register with the active OpenCode session (e.g. `Escanor v8`).
2. Dispatch an onboarding status ping to the OpenCode session.
3. Begin streaming live 2-minute active trade briefings / 4-minute idle market scans.

---

## 🛑 How to Stop & Restart Daemons

### Quick Stop Commands (PowerShell)

```powershell
# 1. Terminate Alpha Trading Desk Daemon:
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*alpha_trading_desk.py*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# 2. Terminate Cloudflare Auto-Connector Proxy:
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*cloudflare_autoconnector.py*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# 3. Terminate Memory Worker Service:
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*worker-service.js*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# 4. Terminate OpenCode Server:
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*opencode serve*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

---

## 🔄 How to Rotate the IP & Restart Cloudflare

Whenever you hit rate limits (HTTP 429), connection dropouts, or want a fresh egress identity:

### 1. Manual One-Liner (IP Rotation + Proxy Restart)
Run this complete sequence in PowerShell:
```powershell
# Step A: Disconnect & reconnect WARP to get a fresh IP
warp-cli disconnect
Start-Sleep -Seconds 2
warp-cli connect
Start-Sleep -Seconds 3

# Step B: Terminate existing autoconnector instances
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*cloudflare_autoconnector.py*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Seconds 1

# Step C: Relaunch the Cloudflare Auto-Connector Proxy Bridge
Start-Process python -ArgumentList "C:\Trading\cloudflare_autoconnector.py" -WindowStyle Hidden

# Step D: Verify new public exit IP through the proxy bridge
curl.exe -x 127.0.0.1:40001 -s https://cloudflare.com/cdn-cgi/trace
```
*Verification Check:* Confirm `warp=on` appears and a new `ip=` is printed.

---

## 🔁 How to Restart Individual Daemons

### 1. Restart Cloudflare Auto-Connector Proxy Only
```powershell
# Kill existing instance:
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*cloudflare_autoconnector.py*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# Start fresh instance:
python C:\Trading\cloudflare_autoconnector.py
```

### 2. Restart Alpha Consolidated Trading Desk Daemon (Zombie-Safe Cleanup)
```powershell
# Step A: Find and terminate all existing desk daemon and orphaned child instances across all venvs:
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*alpha_trading_desk.py*" } | ForEach-Object { 
    Write-Host "Terminating daemon PID $($_.ProcessId)..."
    Stop-Process -Id $_.ProcessId -Force 
}
Start-Sleep -Seconds 2

# Step B: Verify zero lingering instances:
$lingering = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*alpha_trading_desk.py*" }
if ($lingering) {
    Write-Warning "Forcing termination on lingering PID(s): $($lingering.ProcessId -join ', ')"
    $lingering | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Start-Sleep -Seconds 1
}

# Step C: Start a single fresh desk daemon:
python C:\Trading\Alpha\alpha_trading_desk.py
```

### 3. Restart OpenCode Memory Worker Service
```powershell
# Kill existing worker:
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*worker-service.js*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# Start fresh daemon via Bun:
bun C:\Agent\opencode-mem\dist\services\worker-service.js --daemon
```

### 4. Restart OpenCode Server
```powershell
# Kill existing server:
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*opencode serve*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

# Launch with proxy environment variables (Cmd / Batch):
set HTTP_PROXY=http://127.0.0.1:40001
set http_proxy=http://127.0.0.1:40001
set HTTPS_PROXY=http://127.0.0.1:40001
set https_proxy=http://127.0.0.1:40001
set ALL_PROXY=http://127.0.0.1:40001
set all_proxy=http://127.0.0.1:40001
set NO_PROXY=localhost,127.0.0.1,::1,100.*
set no_proxy=localhost,127.0.0.1,::1,100.*

opencode serve --port 4096 --hostname 0.0.0.0
```

---

## 🛠️ Diagnostics & Verification Checklist

| Check | Command / URL | Expected Result |
| :--- | :--- | :--- |
| **Cloudflare WARP Tunnel** | `warp-cli status` | `Status update: Connected` |
| **Proxy Bridge HTTP 40001** | `curl.exe -x 127.0.0.1:40001 -s https://ifconfig.me` | Returns active Cloudflare IP (`104.28.x.x` or IPv6) |
| **Tailscale Remote Proxy** | `curl.exe -x 100.95.56.22:40001 -s https://ifconfig.me` | Returns active Cloudflare IP |
| **OpenCode API Status** | `curl.exe http://127.0.0.1:4096/session/status` | Returns JSON mapping of active sessions (`busy` or `idle`) |
| **Desk Telemetry Read** | `python -c "from tradingagents.catalyst_arbiter import CatalystArbiterEngine; print(CatalystArbiterEngine().get_market_regime('XAUUSD')['compact_prompt_badge'])"` | Prints live broker quote, spread, roadways, footprints, and news box |
| **Memory Worker Process** | `Get-Process bun, node -ErrorAction SilentlyContinue` | Shows active Bun/Node runtime for `worker-service.js` |
| **MT5 Live Connection** | `python -c "import MetaTrader5 as mt5; mt5.initialize(); print(mt5.account_info())"` | Returns valid FTMO balance and equity |

---

## 📂 Key Configuration Files

- **`C:\Trading\opencode.json` & `C:\Trading\Alpha\opencode.json`**:
  Configures FastMCP tools, `opencode/big-pickle` model parameters, and operational trading directives (100% synchronized).
- **`C:\Trading\Alpha\MCP_TOOLS_USAGE_GUIDE.md`**:
  Comprehensive directory of all available FastMCP desk tools, input parameters, output schemas, and autonomous reasoning workflows.
- **`C:\Trading\Alpha\config\opencode_session_config.json`**:
  Points the trading desk daemon to the active session ID (e.g. `Escanor v8`) and defines briefing cadences.

