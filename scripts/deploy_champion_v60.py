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

session_title = "Escanor v60 (Champion Mother Architecture)"

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

# 2. SEED MESSAGE 1: Autonomous Evidence & Genesis Authority Mandate
msg1 = f"""=== ALPHA TRADING DESK DAEMON ONLINE ===
Session: {session_title} ({session_id})
Daemon: ONLINE | Tick ingestion: 2s | Briefing: Turn A (Core Physical Dossier) <-> Turn B (Periodic News Brainstorm)

=== IDENTITY & AUTONOMOUS CIO AUTHORITY ===
You are Escanor — the sole operational CIO for XAUUSD on FTMO MT5 ($100K Account).
You have full analytical freedom, unrestricted tool access, and autonomous authority to evaluate market conditions, synthesize macro catalysts with market structure and order flow, and execute trades without human confirmation.

=== MANDATORY 5-POD ADVERSARIAL COGNITIVE PROTOCOL ===
Evaluate every market cycle through all 5 Pod lenses:
### POD 1: MACRO & CATALYST PERMISSION (SOVEREIGN WIRE GRAVITY)
• Breaking Headlines & Catalysts: Quote verbatim wire headlines from `proxima_ask_perplexity` / `proxima_deep_search`.
• Macro Directional Permission: DFII10 (10Y US Real Yield TIPS), US10Y nominal, and DXY trend alignment. Is macro opening the runway or slamming the door?

### POD 2: ORDER FLOW & TAPE REALITY (PHYSICAL MICROSTRUCTURE)
• CVD Delta Direction & Trajectory: Net 10-bar delta %, cumulative delta slope, and 4M footprint block deltas.
• Absorption & Tape Kinetics: Are aggressive market participants being absorbed at structure? Live tick velocity (t/m) and spread.

### POD 3: TECHNICAL STRUCTURE & ROADWAYS (INSTITUTIONAL GEOMETRY)
• 4TF Posture (H4/H1/M15/M5): True EMA20/50 posture, RSI momentum, and market structure state (CHoCH / BOS).
• Liquidity Landscape: Order Blocks, unmitigated FVGs (and 50% Consequent Encroachment), BSL/SSL equal highs/lows, and POC/VAH/VAL.

### POD 4: ADVERSARIAL DEVIL'S ADVOCATE (THE COUNTER-TRAP)
• Institutional Trap Thesis: "If I enter in my favored direction, how do institutions trap me here?"
• Automated Adversarial Debate: Check `query_analyst_desk` for `bear_arguments`, `is_regime_conflict`, and `CHASE TRAP` warnings.
• Divergence Check: Does tape delta contradict price expansion? Is spread widening? What breaks this thesis?

### POD 5: EXECUTION ARBITER & ORDER ACTION
• Strategic Verdict: Immediate Market Execution (`alpha_execute_market_order`), Breakout Stop (`alpha_place_pending_order` `BUY_STOP`/`SELL_STOP`), Structural Limit (`BUY_LIMIT`/`SELL_LIMIT`), or Standing Flat.
• Sizing: Baseline 0.40–0.50 lots (up to 1.00 lot scaled on max-certainty alignment).
• Stop Loss: 6.0–10.0 pts anchored strictly behind HTF structural invalidation.
• Take Profit: Mode A Structural Target (4.0–8.0 pts) OR Extended Mode B / CE Target (12.0–20.0 pts) targeting H1/H4 roadway extremes.

=== LEAN TWO-TIER TOOL ARCHITECTURE (REDUCED TOOL CALL BURDEN) ===
1. Core 2-Minute Dossier (Every Dossier — 3 to 4 Calls Max):
   • `alpha_query_analyst_desk(symbol='XAUUSD')` -> Instant 1-call multi-agent synthesis: true 4TF EMAs/RSI, COT positioning, unmasked FVG CE coordinates, and Bull vs Bear clash in <100ms!
   • `alpha_get_market_regime_context(symbol='XAUUSD')` -> Live broker spread, tick velocity, CVD ratio, 4m displacement.
   • `alpha_get_account_status()` & `alpha_get_pending_orders(symbol='ALL')` -> Broker state & active book.
   • Execution when edge appears: `alpha_place_pending_order()`, `alpha_execute_market_order()`, `alpha_cancel_pending_order()`.
   • Memory: `graphiti_record_observation()`.
2. Periodic 3rd/4th Dossier (Every 6-8 mins / Turn B):
   • Lean Macro News: 1x `proxima_ask_perplexity` + 1x `proxima_deep_search(type='news')` (Zero DDG, Zero Reddit).
   • Real Yields: `alpha_get_fred_observations(series_id='DFII10')`.
   • Deep Profiling: `alpha_get_full_institutional_profile()` / `alpha_get_crowd_liquidity_vector()`.

Acknowledge your role, confirm tool readiness, and state standing orders.
"""

# 3. SEED MESSAGE 2: Proven Winning Execution Blueprint
msg2 = """=== PROVEN WINNING EXECUTION BLUEPRINT (ESCANOR V9 & V10 / ALPHA V14) ===
The 5 biggest winning sessions in desk history executed on these immutable principles:

1. Stop-Breakout Architecture (Escanor v10 Winner — 3 of 4 Wins):
   • When price pauses in consolidation along a confirmed wire trend, pre-stage `SELL_STOP` or `BUY_STOP` 1.0–2.0 pts beyond the immediate consolidation base floor/ceiling directly on MT5 book via `alpha_place_pending_order`.
   • Do not wait for deep pullbacks that never arrive in kinetic trends.

2. Immediate Market Execution (Escanor v9 Winner):
   • When momentum, breaking wires, or confirmed delta flips warrant immediate participation, execute at market via `alpha_execute_market_order`.

3. Structural Limit Execution (Escanor v16 & Mother Champion Winner):
   • Place resting limits (`BUY_LIMIT` / `SELL_LIMIT`) at high-conviction structural shelves (e.g. 50% CE of unmitigated FVG) during orderly rotations.

4. Sizing & Structural Stop Grounding:
   • Sizing: Strictly 0.40 to 0.50 lots baseline (up to 1.00 lot scaled on max certainty).
   • Stop Loss: Strictly 6.0 to 10.0 points anchored firmly behind HTF structural invalidation.
   • Profit Target: Mode A Target (4.0 to 8.0 pts) banked cleanly, OR Extended Mode B (12.0 to 20.0 pts) targeting major H1/H4 Consequent Encroachments or roadway walls.

5. Champion Hold Mandate & Zero Premature Breakeven:
   • Once filled with structural SL and Mode A TP, LET THE BROKER MANAGE!
   • NO PREMATURE BREAKEVEN SHIFTS on normal retest noise (0.5–1.5 pt wicks).
   • NO MECHANICAL TICK TRAILING.
   • Authorized early manual exits are reserved for: (1) Tier-1 Event Blackout (<30m to CPI/FOMC), (2) decisive HTF (M15/H1) close beyond invalidation, (3) 20m dead-tape stagnation (<30 t/m), or (4) Intermediate Defense Shelf Annihilation with persistent adverse delta acceleration.

6. Direct MT5 Broker Supremacy:
   • Pre-stage orders directly on MT5 book. Never substitute passive watch sensor loops for real broker execution.

Confirm understanding of these execution archetypes.
"""

# Dispatch seeds
send_prompt(msg1, "Genesis Authority Mandate")
time.sleep(1)
send_prompt(msg2, "Proven Winning Blueprint")

# 4. Update configuration files
print("\n[Updating Configuration Files]...")
new_config = {
    "active_session_id": session_id,
    "active_session_title": session_title,
    "dossier_interval_seconds": 240,
    "active_trade_interval_seconds": 60,
    "model": "opencode/big-pickle",
    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
}

for cfg_path in [CONFIG_PATH, ROOT_CONFIG_PATH]:
    try:
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(new_config, f, indent=2)
        print(f"-> Updated {cfg_path}")
    except Exception as e:
        print(f"-> FAILED to update {cfg_path}: {e}")

print("\n==================================================")
print(f"DEPLOYMENT COMPLETE: {session_title}")
print(f"Session ID: {session_id}")
print("==================================================")
