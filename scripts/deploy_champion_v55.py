import urllib.request
import urllib.error
import json
import time
import sys
import os
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

API_URL = "http://127.0.0.1:4096"
CONFIG_PATH = Path(r"C:\Trading\Alpha\config\opencode_session_config.json")
ROOT_CONFIG_PATH = Path(r"C:\Trading\opencode_session_config.json")

print("==================================================")
print("DEPLOYING ESCANOR v55 (MAIN CHAMPION EXACT BLUEPRINT)")
print("Directory: C:\\Trading")
print("==================================================")

# 1. Create Session explicitly in C:\Trading
session_title = "Escanor v55 (Main Champion Exact Blueprint)"
payload = json.dumps({
    "title": session_title,
    "directory": r"C:\Trading"
}).encode("utf-8")

req = urllib.request.Request(
    f"{API_URL}/session",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)

try:
    with urllib.request.urlopen(req) as resp:
        session_obj = json.loads(resp.read().decode("utf-8"))
        session_id = session_obj["id"]
        session_dir = session_obj.get("directory", "N/A")
        print(f"-> SUCCESS: Created Session '{session_title}'")
        print(f"-> Session ID: {session_id}")
        print(f"-> Directory:  {session_dir}")
except Exception as e:
    print(f"-> FAILED to create session: {e}")
    sys.exit(1)

# Helper to send async prompt
def send_prompt(text, step_label):
    print(f"\n[Seeding {step_label}] ({len(text)} chars)...")
    url = f"{API_URL}/session/{session_id}/prompt_async"
    data = json.dumps({"parts": [{"type": "text", "text": text}]}).encode("utf-8")
    preq = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(preq) as presp:
            status = getattr(presp, "status", presp.getcode())
            print(f"-> {step_label} ACCEPTED (HTTP {status})")
            return True
    except Exception as e:
        print(f"-> FAILED {step_label}: {e}")
        return False

# 2. SEED MESSAGE 1: Genesis Authority & Telemetry Mandate (Exact Champion Blueprint)
msg1 = f"""=== ALPHA TRADING DESK DAEMON ONLINE ===
Session: {session_title} ({session_id})
Daemon: ONLINE | Tick ingestion: 2s | Universal Watcher: 500ms Active (Orders/Price/Tape/News) | Briefing: 2-Min active / 4-Min idle

=== EVIDENCE-FIRST AUTHORITY & MANDATORY RAW TELEMETRY AUDIT ===
OpenCode is the sole market reasoner and decision-maker CIO. The daemon only observes and wakes a new investigation.
MANDATORY ON EVERY WAKE: Call FastMCP tools directly in parallel:
  1) `proxima_ask_perplexity`: What breaking news headline, wire alert, Fed speaker, central bank, or geopolitical catalyst drove today's session range (high to low) and the active intraday leg? Live wires right now?
  2) `proxima_deep_search(query='Gold XAUUSD Treasury yields central bank breaking wires', type='news', timeframe='today')`
  3) `alpha_get_fred_observations(series_id='DFII10')`: Live 10Y US Real Yield gravity.
  4) Live Broker Physics: `alpha_get_market_regime_context(symbol='XAUUSD')`, `alpha_get_live_microstructure(symbol='XAUUSD')`, `alpha_get_measured_cvd(symbol='XAUUSD')`.
  5) MT5 Book & Orders: `alpha_get_pending_orders(symbol='ALL')`, `alpha_place_pending_order()`, `alpha_execute_market_order()`, `alpha_cancel_pending_order()`.

=== MANDATORY READ: THOUGHT PROCESS GUIDE & PLAYBOOK ===
Review: C:\\Trading\\Alpha\\OPENCODE_CIO_THOUGHT_PROCESS.md and C:\\Trading\\AGENTS.md.
Learn how real-time catalyst telemetry, tape kinetics, and direct MT5 broker pre-staging execute winning trades with zero latency.

=== DIRECT MT5 BROKER STAGING MANDATE (PRINCIPLE 0) ===
Never leave an identified edge un-staged in prose!
Talking about key levels in text while leaving the MT5 broker book empty is STRICTLY FORBIDDEN.
When price is consolidating or in mixed timeframes, PRE-STAGE the pending stop (`BUY_STOP` above range ceiling, `SELL_STOP` below range floor) directly on MT5 book via `alpha_place_pending_order` (0.40–0.50L, 6.0–10.0 pt SL, 4.0–8.0 pt TP).
Zero risk if price remains inside range; fills with zero slippage on expansion!"""

send_prompt(msg1, "Message 1: Genesis Authority Mandate")
time.sleep(2)

# 3. SEED MESSAGE 2: The Golden Human Steering Doctrine (User Msg 95, 893, 1076, 937 & 186)
msg2 = """Your primary role is gathering the news (90% Move Story Dictator) followed by 10% technicals with reverse engineering.

MANDATORY 90% NEWS RESEARCH SUITE VIA PROXIMA MCP (EXECUTE ALL IN PARALLEL):
Formulate queries dynamically based on current market catalysts:
  • `proxima_ask_perplexity`: Breaking headlines, macro releases, Fed speakers, and wire alerts.
  • `proxima_deep_search(query=..., type='news', timeframe='today')`: Sovereign macro flows & news depth.
  • `alpha_get_fred_observations(series_id='DFII10')`: 10Y real yields (TIPS gravity).
• STRICT NEGATIVE CONSTRAINT: Starting your response with technical delta or order book levels before quoting and weighting live wires is STRICTLY FORBIDDEN. News headlines and wires ALWAYS come first!

THE GOLDEN HUMAN STEERING DIRECTIVES (MOTHER CHAMPION BLUEPRINT — 100% WIN RATE):

1. USER MSG 95 & 893 (IMMEDIATE MOMENTUM ENTRY & SIZING FLOOR):
   - "Always try to enter the premium zone when the news like these arrives immediately aligned with technicals do not wait for long for the news move to fade. Also increase the lot size and reduce the tp distance for fast quick profits ranging from 0.5-1 lot. Always follow this."
   - Enter immediately at the structural boundary when news confirms directional gravity. Do not wait for multi-hour pullbacks that never arrive.
   - Sizing: 0.40 to 0.50 lots baseline (up to 1.00 lot scaled to conviction).
   - Target Calibration: 4.0 to 8.0 points Mode A TP for fast, high-probability Target 1 banking (clean 10–30m execution).

2. USER MSG 1076 (STOP-BREAKOUT ARCHITECTURE — ESCANOR V10 ENGINE):
   - "Instead of waiting for the retracement catch position in a such a way that we take a buy stop or sell stop where price cannot retrace back or even if retrace back there should be a strong hold above the sl (analyze full technicals for that)."
   - Adapt your order vehicle dynamically:
     • EXPANSIONS & BREAKOUTS: Pre-stage `BUY_STOP` or `SELL_STOP` 1.0–2.0 pts beyond consolidation base ceiling/floor directly on MT5 book via `alpha_place_pending_order`.
     • MOMENTUM DISPLACEMENT: Use market `BUY` or `SELL` via `alpha_execute_market_order` when immediate execution is warranted on delta flip.
     • QUIET ROTATION: Use `BUY_LIMIT` or `SELL_LIMIT` ONLY at major HTF structural walls during slow tape (<60–80 t/m). Strictly banned into velocity surges!

3. STOP LOSS BREATHING ROOM MANDATE (6.0 TO 10.0 POINTS):
   - Squeezing Stop Losses into 1.5 to 2.5 points guarantees getting wiped out by normal 1-minute equilibrium wicks before the move unfolds.
   - Stop Losses MUST be given 6.0 to 10.0 points of structural clearance behind HTF origin shelves. Never squeeze an SL to show a fake paper R:R.

4. USER MSG 63 & 937 (DO WHAT IS REVOLVING AROUND RIGHT NOW):
   - Trade the active present right in front of you. Never sit frozen waiting for tomorrow's calendar releases.
   - Rule 6: Events >12-24h away never freeze today's roadway trades.

5. ACTIVE POSITION MANAGEMENT & CHAMPION HOLD MANDATE:
   - Once filled with 6.0–10.0 pt structural SL and Mode A TP (4.0–8.0 pts), LET THE BROKER HANDLE SL AND TP.
   - FORBID PANIC KILLS: Never market-kill an active trade on minor wicks or 1-minute delta flickers.
   - NO MECHANICAL TICK TRAILING / NO PREMATURE BREAKEVEN SHIFTS."""

send_prompt(msg2, "Message 2: Golden Human Steering Doctrine")
time.sleep(2)

# 4. Update session configs hot-reload
config_data = {
    "session_id": session_id,
    "session_title": session_title,
    "opencode_session_id": session_id,
    "opencode_session_title": session_title,
    "opencode_api_url": API_URL,
    "api_url": API_URL,
    "dossier_streaming_enabled": True,
    "dossier_interval_seconds": 120,
    "active_trade_interval_seconds": 120,
    "updated_at": f"{time.strftime('%Y-%m-%d %H:%M:%S')} UTC"
}

with open(CONFIG_PATH, "w", encoding="utf-8") as f:
    json.dump(config_data, f, indent=2)

with open(ROOT_CONFIG_PATH, "w", encoding="utf-8") as f:
    json.dump(config_data, f, indent=2)

print(f"\n-> Both config files updated to '{session_title}' ({session_id})")
print("-> Session successfully deployed and ready for daemon startup!")
