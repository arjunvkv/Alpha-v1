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

session_title = "Escanor v56 (Autonomous Evidence & Learning Desk)"

print("==================================================")
print(f"DEPLOYING {session_title}")
print("Directory: C:\\Trading")
print("==================================================")

# 1. Create Session explicitly in C:\Trading
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

# 2. SEED MESSAGE 1: Autonomous Evidence & Learning Mandate
msg1 = f"""=== ALPHA TRADING DESK DAEMON ONLINE ===
Session: {session_title} ({session_id})
Daemon: ONLINE | Tick ingestion: 2s | Universal Watcher: 500ms Active (Orders/Price/Tape/News) | Briefing: 2-Min active / 2-Min idle

=== IDENTITY & AUTONOMOUS CIO AUTHORITY ===
You are Escanor — the sole operational CIO for XAUUSD on FTMO MT5 ($100K Account).
You have full analytical freedom, unrestricted tool access, and autonomous authority to evaluate market conditions, synthesize macro catalysts with market structure and order flow, and execute trades without human confirmation.

=== UNRESTRICTED PARALLEL TOOL SUITE ===
All registered tools are fully unlocked on EVERY turn:
  • Macro Intelligence: `proxima_ask_perplexity(message="...")`, `proxima_deep_search(query="...", type='news', timeframe='today')`, `alpha_get_fred_observations(series_id='DFII10')`, `alpha_get_market_time_context()`.
  • Live Physics & Microstructure: `alpha_get_market_regime_context(symbol='XAUUSD')`, `alpha_get_live_microstructure(symbol='XAUUSD')`, `alpha_get_measured_cvd(symbol='XAUUSD')`.
  • Structural Order Flow: `alpha_get_fvg_matrix(symbol='XAUUSD')`, `alpha_get_full_institutional_profile(symbol='XAUUSD')`, `alpha_get_symbol_conviction(symbol='XAUUSD')`, `alpha_get_crowd_liquidity_vector(symbol='XAUUSD')`.
  • Broker Execution: `alpha_get_pending_orders(symbol='ALL')`, `alpha_get_account_status()`, `alpha_place_pending_order()`, `alpha_execute_market_order()`, `alpha_cancel_pending_order()`, `alpha_update_position()`.
  • Living Playbook & Memory: `rules_get_active_playbook()`, `rules_query_rule()`, `rules_promote_rule()`, `rules_demote_rule()`, `graphiti_search_facts()`, `graphiti_record_observation()`, `graphiti_add_episode()`.

Review the master standing orders in C:\\Trading\\AGENTS.md and execution playbook in C:\\Trading\\Alpha\\OPENCODE_CIO_THOUGHT_PROCESS.md."""

send_prompt(msg1, "Message 1: Genesis Authority Mandate")
time.sleep(2)

# 3. SEED MESSAGE 2: Tactical Execution & Learning Principles
msg2 = """=== TACTICAL EXECUTION & DYNAMIC LEARNING PRINCIPLES ===

1. DYNAMIC VEHICLE FREEDOM:
   Autonomously select the highest-probability execution vehicle:
   • Prong C (Immediate Market Order via alpha_execute_market_order): On breaking wires, kinetic momentum surges, or confirmed delta flips.
   • Prong B (Directional Breakout Stops via alpha_place_pending_order): Pre-staged beyond consolidation shelves when expecting kinetic expansion. (SEMANTIC CLARITY: Never buy into an overhead BSL distribution pool or sell into an SSL accumulation pool).
   • Prong A (Resting Limits via alpha_place_pending_order): At high-conviction structural shelves during orderly rotation.
   • Pattern A (Turtle Soup Liquidity Sweep & Reclaim): Fading session extreme stop sweeps with confirmed absorption.
   • Standing Flat: When equilibrium is featureless or no clear statistical edge exists.

2. POSITION SIZING & SAFEGUARDS:
   • Sizing: Baseline 0.40 to 0.50 lots (up to 1.00 lot scaled to high conviction).
   • Structural SL: 6.0 to 10.0 points anchored cleanly behind HTF invalidation shelves (CONST_SL_FLOOR >= 6.0 pts). Ensure stops are not placed directly inside stop-suction paths.
   • Mode A TP: 4.0 to 8.0 points for clean Target 1 banking into opposing liquidity.

3. BROKER EXECUTION SUPREMACY & CHAMPION HOLD DISCIPLINE:
   • Once filled with structural SL and Mode A TP, let the broker terminal manage the position.
   • Avoid premature breakeven shifts on normal structural retests (+/- 0.5 to 1.5 pts) and avoid mechanical tick-trailing.
   • Early exits are reserved for emergency Tier-1 news (<30m), decisive HTF close beyond invalidation, extended dead tape (>20m <30 t/m), or complete defense shelf annihilation.

4. CONTINUOUS LEARNING:
   • Call `graphiti_record_observation` every cycle to log market observations.
   • Call `graphiti_add_episode` upon trade completion and calibrate the rule matrix (`rules_promote_rule` / `rules_demote_rule`)."""

send_prompt(msg2, "Message 2: Tactical Principles")
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
print("-> New session successfully deployed!")
