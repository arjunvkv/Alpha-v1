# Alpha-v1: Institutional Quantitative Trading Desk & OpenCode CIO Brain

Autonomous multi-agent quantitative trading system and institutional reasoning engine integrated with FTMO MetaTrader 5 ($100K Account).

Alpha separates evidence gathering from deliberative reasoning:
- **Collectors & Sensors**: Ingest live MT5 market feeds, tick velocity, raw CVD, volume profiles, unmitigated FVGs, and global news wires.
- **FastMCP Market Telemetry & Execution Tools**: Provide atomic evidence on demand without bloating prompt context.
- **OpenCode CIO**: The sole deliberative decision-maker running **`opencode/big-pickle`** via a resilient Cloudflare WARP proxy bridge.
- **Execution Safeguards**: FTMO risk guardrails, objective structural invalidations, and non-trailing target protection.

---

## 🏗️ System Architecture

- **Remote Access (Tailscale)**: Connect from mobile phone, laptop, or remote browser via Tailscale mesh (`100.95.56.22:4096` for OpenCode, `100.95.56.22:40001` for Proxy Bridge).
- **Consolidated Trading Desk (`alpha_trading_desk.py`)**: Gathers market state, monitors positions, and dispatches evidence wakes to OpenCode.
- **OpenCode Server (`opencode serve`)**: Listens on `0.0.0.0:4096`, hosting active reasoning session `Escanor`. Outbound calls to `opencode.ai` (Big-Pickle) route through the Cloudflare proxy.
- **Cloudflare Auto-Connector (`cloudflare_autoconnector.py`)**: Maintains an HTTP CONNECT bridge on `0.0.0.0:40001`, forwarding to Cloudflare WARP SOCKS5 (`127.0.0.1:40000`) in proxy mode with automatic rate limit rotation.
- **FastMCP Server (`mcp_server/alpha_mcp_server.py`)**: Exposes atomic market telemetry, account actions, and order management tools directly to OpenCode.

---

## 🚀 Quick Start & How to Use

### 1. Start Cloudflare WARP & The Auto-Connector Proxy
The Auto-Connector runs WARP strictly in **Proxy Mode** (port 40000), binds an HTTP CONNECT bridge to `0.0.0.0:40001`, and exposes it to localhost and Tailscale peers without disrupting network routes.

```powershell
# Ensure WARP is in proxy mode and connected:
warp-cli mode proxy
warp-cli connect

# Start the Auto-Connector Proxy Bridge:
python C:\Trading\Alpha\cloudflare_autoconnector.py
```
*Proxy Bridge will be live at:*
- Localhost: `http://127.0.0.1:40001`
- Tailscale Mesh: `http://100.95.56.22:40001`

### 2. Start the OpenCode Server (Bound to Tailscale & Proxied)
Launch OpenCode with proxy environment variables configured so that all outbound LLM traffic to `opencode.ai` is tunneled through Cloudflare WARP, while local and Tailscale peer traffic remains direct:

```cmd
:: In cmd.exe (or batch script):
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
*OpenCode Web UI and API will be live at:*
- Localhost: `http://127.0.0.1:4096`
- Tailscale Mesh: `http://100.95.56.22:4096`

### 3. Start the Alpha Consolidated Trading Desk
The trading desk continuously evaluates market structure, manages active positions, tracks armed price watches, and dispatches evidence briefings to OpenCode.

```powershell
# From C:\Trading\Alpha:
python alpha_trading_desk.py
```

---

## 📱 Accessing from Tailscale (Phone, Laptop, or Remote Web UI)

Any authorized device on your Tailscale network can access OpenCode directly:

1. **Web Interface**:
   Open `http://100.95.56.22:4096` in any mobile or desktop browser to inspect active sessions, monitor real-time deliberations, and send manual instructions.
2. **Model Selection**:
   The default model is configured as **`opencode/big-pickle`** in `opencode.json`. It connects seamlessly through the Cloudflare proxy bridge.
3. **Direct Tailscale Proxy Usage**:
   If remote tools or scripts require routing through Cloudflare WARP, specify `http://100.95.56.22:40001` as their HTTP/HTTPS proxy.

---

## 🔍 Verification & Health Checks

### Test 1: Verify Proxy Route & Cloudflare Exit IP
```powershell
python -c "import urllib.request; p=urllib.request.ProxyHandler({'http':'http://100.95.56.22:40001','https':'http://100.95.56.22:40001'}); o=urllib.request.build_opener(p); print('Exit IP:', o.open('https://api.ipify.org').read().decode())"
```
*Expected Output:* Cloudflare WARP exit IP (e.g. `104.28.x.x`).

### Test 2: Verify Big-Pickle Deliberation via Tailscale
```powershell
python -c "import urllib.request, json; u='http://100.95.56.22:4096/session/ses_f83dc6d2dffeNDoT8xwgsWbfWA/message'; p=json.dumps({'parts':[{'type':'text','text':'Ping'}]}).encode(); req=urllib.request.Request(u, data=p, headers={'Content-Type':'application/json'}); print(urllib.request.urlopen(req).read().decode()[:200])"
```
*Expected Output:* HTTP 200 response with model `opencode/big-pickle` reasoning.

---

## ⚙️ Configuration Reference

### Session Configuration (`config/opencode_session_config.json`)
```json
{
  "session_id": "ses_f83f4c997ffeN7AZBk0c2C6w1z",
  "session_title": "Escanor v1",
  "opencode_session_id": "ses_f83f4c997ffeN7AZBk0c2C6w1z",
  "opencode_session_title": "Escanor v1",
  "opencode_api_url": "http://127.0.0.1:4096",
  "dossier_interval_seconds": 240,
  "active_trade_interval_seconds": 60,
  "dossier_streaming_enabled": true
}
```

### OpenCode Configuration (`opencode.json`)
- **Default Model**: `"model": "opencode/big-pickle"`
- **FastMCP Tool Integration**: Registered under `alpha-daemon-mcp` pointing to `alpha_mcp_server.py`.
- **Subagent Support**: `explore` subagent with full FastMCP tool access.

---

## 🛡️ Trading Principles & Authority Flow

1. **OpenCode is Sole Reasoner**: Collectors and daemon modules provide raw factual evidence. None may force, censor, or override OpenCode's reasoning.
2. **A Wake is Not a Signal**: OpenCode begins every wake by classifying whether an actionable decision exists. If conditions are mid-range chop, OpenCode chooses `WAIT` or `NO TRADE`.
3. **Position Management**: Active trades are managed through structural invalidations (SL adjustments behind protected swing shelves) and institutional targets (TP adjustments to unmitigated FVGs / opposite Value Area). Mechanical trailing stops and panic market-kills are forbidden.
4. **Rate Limit Resilience**: If Cloudflare triggers a rate limit or mitigation, `cloudflare_autoconnector.py` rotates WARP tunnel keys in background, resumes connection within 3 seconds, and dispatches continuation without losing session context.

