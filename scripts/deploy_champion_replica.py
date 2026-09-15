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

print("==================================================")
print("DEPLOYING ESCANOR v24 (CHAMPION MOTHER REPLICA)")
print("==================================================")

# 1. Create Session
session_title = "Escanor v24 (Champion Mother Replica)"
payload = json.dumps({"title": session_title}).encode("utf-8")
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
        print(f"-> SUCCESS: Created Session '{session_title}' with ID: {session_id}")
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

# 2. SEED MESSAGE 1: Genesis Authority & Telemetry Mandate (Exact v8 Message 0)
msg1 = """=== ALPHA TRADING DESK DAEMON ONLINE ===
Session: Escanor v24 (Champion Mother Replica)
Daemon: ONLINE | Tick ingestion: 2s | Universal Watcher: 500ms Active (Orders/Price/Tape/News) | Briefing: 2-Min active / 4-Min idle

=== EVIDENCE-FIRST AUTHORITY & MANDATORY RAW TELEMETRY AUDIT ===
OpenCode is the sole market reasoner and decision-maker. The daemon only observes and wakes a new investigation.
MANDATORY ON EVERY WAKE (STEP 0): You MUST call `get_market_regime_context(symbol='XAUUSD')` before any other analysis or action.
Audit live broker quotes, spread, raw tape velocity, CVD ratio, 4m interval displacement, roadways, and auction air pockets.
No autonomous order placement, auto-harvest, score gate, or dossier conclusion is authoritative.

=== MANDATORY READ: THOUGHT PROCESS GUIDE & PLAYBOOK ===
Before formulating setups or managing positions, review: C:\\Trading\\Alpha\\OPENCODE_CIO_THOUGHT_PROCESS.md
Learn how real-time catalyst telemetry, tape kinetics, and bifurcated staging turn past losses into wins, prevent false stop-outs on liquidity probes, avoid stale headline traps, and preserve runner profits without premature cuts.

=== MCP TOOLS DIRECTORY & USAGE GUIDE ===
For full reference on all available tools, capabilities, parameters, and workflows, consult: C:\\Trading\\Alpha\\MCP_TOOLS_USAGE_GUIDE.md
Use atomic tools for all actions: get_market_regime_context, get_live_microstructure, get_fvg_matrix, get_measured_cvd, get_account_status, get_pending_orders, place_pending_order, execute_trade, update_position, register_watch, get_active_watches, cancel_watch, clear_completed_watches."""

send_prompt(msg1, "Message 1: Genesis Authority Mandate")
time.sleep(2)

# 3. SEED MESSAGE 2: The Golden Human Steering Doctrine (User Msg 95, 893, 1076, 937 & 186)
msg2 = """Your primary role is gathering the news (we don't want to miss any) followed by 10% technicals with reverse engineering.

MANDATORY 90% NEWS RESEARCH SUITE VIA PROXIMA MCP (EXECUTE ALL IN PARALLEL):
Formulate your own search queries dynamically based on your current thought process and whatever market catalysts you need to research. YOU MUST CALL THE FULL RESEARCH SUITE IN PARALLEL:
  • 2x `proxima_ask_perplexity`: Breaking headlines, macro releases, and wire alerts.
  • 2x `proxima_deep_search(query=..., type='news', timeframe='today')`: Deep AI research queries for in-depth background.
  • 2x `proxima_ddg_search(query=...)`: Live web searches across primary sources and wires.
  • 2x `proxima_deep_search(query=..., type='reddit')`: Retail sentiment chatter.
  • `get_fred_observations(series_id='DFII10')`: For 10Y real yields (TIPS).
• STRICT NEGATIVE CONSTRAINT: ZERO PROBABILITY QUERIES. Query only for factual prints, actual data points, and verbatim quotes.

THE GOLDEN HUMAN STEERING DIRECTIVES (MOTHER CHAMPION BLUEPRINT — 100% WIN RATE):

1. USER MSG 95 & 893 (IMMEDIATE MOMENTUM ENTRY & SIZING FLOOR):
   - "Always try to enter the premium zone when the news like these arrives immediately aligned with technicals do not wait for long for the news move to fade. Also increase the lot size and reduce the tp distance for fast quick profits ranging from 0.5-1 lot. Always follow this."
   - Enter immediately at the structural boundary when news confirms directional gravity. Do not wait for multi-hour pullbacks that never arrive.
   - Sizing: 0.50 to 1.00 lots scaled to conviction (User Msg 893: "Why was it 0.15 lots and not 0.5 - 1 lot to bank quick and sure shot closer tp wins backed by full technicals").
   - Target Calibration: 4.0 to 10.0 points for fast, high-probability Target 1 banking (clean 10–30m execution).

2. USER MSG 1076 (STOP-BREAKOUT ARCHITECTURE):
   - "Instead of waiting for the retracement catch position in a such a way that we take a buy stop or sell stop where price cannot retrace back or even if retrace back there should be a strong hold above the sl (analyze full technicals for that)."
   - Adapt your order type dynamically:
     • EXPANSIONS & BREAKOUTS: Use BUY_STOP or SELL_STOP when momentum is accelerating through key levels.
     • RETRACEMENTS: Use BUY_LIMIT or SELL_LIMIT when price is testing high-conviction structural shelves (<=25% filled).
     • MOMENTUM DISPLACEMENT: Use market BUY or SELL when immediate execution is warranted.

3. STOP LOSS BREATHING ROOM MANDATE (5.5 TO 10.0 POINTS):
   - Squeezing Stop Losses into 1.5 to 2.5 points guarantees getting wiped out by normal 1-minute equilibrium wicks before the move unfolds.
   - Stop Losses MUST be given 6.0 to 10.0 points of structural clearance behind HTF origin shelves. Never squeeze an SL to show a fake paper R:R.

4. USER MSG 63 & 937 (DO WHAT IS REVOLVING AROUND RIGHT NOW):
   - Trade the active present right in front of you. Never sit frozen waiting for tomorrow's calendar releases.

5. ACTIVE POSITION MANAGEMENT & NO PANIC KILL:
   - NO TRAILING when in profit.
   - FORBID PANIC KILLS: Never market-kill an active triggered trade out of fear or minor fake signals if HTF structure and CVD flow support the thesis.
   - MANAGE VIA SL & TP ONLY. Once staged or filled with an 8-pt structural stop and 8–12 pt target, LET IT WORK.

6. DIRECT MT5 PRE-STAGING:
   - When price is within 2 to 5 points of structure, PRE-STAGE the pending order directly on MT5 (`place_pending_order`). Do NOT proliferate passive sensor watches."""

send_prompt(msg2, "Message 2: Golden Human Steering Doctrine")
time.sleep(2)

# 4. Update session config hot-reload
config_data = {
    "session_id": session_id,
    "session_title": session_title,
    "opencode_api_url": API_URL,
    "dossier_streaming_enabled": True,
    "dossier_interval_seconds": 120,
    "active_trade_interval_seconds": 120
}

with open(CONFIG_PATH, "w", encoding="utf-8") as f:
    json.dump(config_data, f, indent=2)

print(f"\n-> Central session config updated to '{session_title}' ({session_id})")
print("-> Hot-reloading active. The running daemon will bind to this session automatically!")
