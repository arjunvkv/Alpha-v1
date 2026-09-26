import urllib.request
import json
import time
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

API_URL = "http://127.0.0.1:4096"
session_id = "ses_f27665383ffefPVWxdrRDBSgl9"
session_title = "Escanor v81 (Pure Flow Supremacy & Root Realism)"

print(f"Completing deployment for session {session_id}...")

# 1. Send SEED 2
msg2 = """=== PROVEN WINNING EXECUTION BLUEPRINT (ALPHA GRANGER 7-LAYER ARCHITECTURE) ===
The desk's greatest compounding growth models executed on these immutable principles:

1. Stop-Breakout Architecture (Escanor v10 Winner):
   • When price pauses in consolidation along a confirmed directional expansion, pre-stage `SELL_STOP` or `BUY_STOP` 1.0–2.0 pts beyond the immediate consolidation base floor/ceiling directly on MT5 book via `alpha_place_pending_order`.
   • Do not wait for deep pullbacks that never arrive in kinetic trends.

2. Immediate Market Execution (Escanor v9 Winner):
   • When momentum, breaking wires, or confirmed delta flips warrant immediate participation, execute at market via `alpha_execute_market_order`.

3. Structural Limit Execution (Escanor v16 & Mother Champion Winner):
   • Place resting limits (`BUY_LIMIT` / `SELL_LIMIT`) at high-conviction structural shelves (e.g. 50% CE of unmitigated FVG) during orderly rotations.

4. Sizing Realism & Positive Asymmetric R:R (>= 1.5:1 to 2.5:1+ Floor):
   • Sizing: Strictly 0.50 to 1.00 lots (1.00L standard on high conviction >= 8.0/10 + 4TF alignment; 0.50L on baseline 7.0-7.9).
   • Stop Loss: Strictly 6.0 to 12.0 points anchored firmly behind HTF structural invalidation + 1.5x ATR14 buffer.
   • Profit Target: Major Opposing Structural Liquidity Target (12.0 to 25.0 pts) delivering Positive R:R >= 1.5:1 to 2.5:1+.
   • Anti-Inverted-R:R Gate: VETO any order where planned target is less than 1.5x the stop distance. Inverted negative R:R (<1.5:1) is strictly prohibited.

5. Champion Hold Mandate & Progressive Structural Trailing:
   • Once filled with structural SL and asymmetric TP, LET THE BROKER MANAGE!
   • NO PREMATURE BREAKEVEN SHIFTS on normal retest noise (0.5–1.5 pt wicks).
   • NO MECHANICAL TICK TRAILING inside noise bands.
   • Progressive Structural Trailing: When a trade achieves a meaningful advance (> +1.0R into profit), trail SL behind intermediate structural swing shelves with a 3–5 pt buffer (BE -> +1R -> +2R), letting winners run to bank +$1,000 to +$2,500.

6. Direct MT5 Broker Supremacy:
   • Pre-stage orders directly on MT5 book. Never substitute passive watch sensor loops for real broker execution.

7. Post-Trade Forensics & Living Memory:
   • Upon trade completion (SL, TP, or early exit), record the post-trade autopsy in Graphiti memory (`graphiti_add_episode`) and calibrate the rule matrix (`rules_promote_rule` / `rules_demote_rule`).

Confirm understanding of these execution archetypes.
"""

url = f"{API_URL}/session/{session_id}/prompt_async"
data = json.dumps({"parts": [{"type": "text", "text": msg2}]}).encode("utf-8")
preq = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(preq) as presp:
    print(f"-> SEED 2 ACCEPTED (HTTP {presp.getcode()})")

# Wait for response
print("-> Waiting for confirmation...")
start_t = time.time()
while time.time() - start_t < 90:
    time.sleep(3.0)
    try:
        murl = f"{API_URL}/session/{session_id}/message"
        with urllib.request.urlopen(murl) as mresp:
            msgs = json.loads(mresp.read().decode("utf-8"))
            last = msgs[-1]
            ptypes = [p.get("type") for p in last.get("parts", [])]
            finish = last.get("info", {}).get("finish")
            if "step-finish" in ptypes or finish == "stop":
                print("-> SEED 2 Confirmation received!")
                break
    except Exception as e:
        pass

# 2. Update configs
CONFIG_PATH = Path(r"C:\Trading\Alpha\config\opencode_session_config.json")
ROOT_CONFIG_PATH = Path(r"C:\Trading\opencode_session_config.json")
config_data = {
    "session_id": session_id,
    "title": session_title,
    "session_title": session_title,
    "active_session_id": session_id,
    "active_session_title": session_title,
    "dossier_interval_seconds": 240,
    "active_trade_interval_seconds": 60,
    "model": "opencode/big-pickle",
    "api_url": API_URL,
    "deployed_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    "description": "Escanor v81 CIO operating with pure flow supremacy, root realism, 5-Pod adversarial reasoning, and zero DOM noise",
    "dossier_streaming_enabled": True
}

for cfg_path in [CONFIG_PATH, ROOT_CONFIG_PATH]:
    try:
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        print(f"-> Updated {cfg_path}")
    except Exception as e:
        print(f"-> FAILED {cfg_path}: {e}")

data_live_dir = Path(r"C:\Trading\Alpha\data\live")
data_live_dir.mkdir(parents=True, exist_ok=True)
with open(data_live_dir / "session_id.txt", "w", encoding="utf-8") as f:
    f.write(session_id.strip())

with open(data_live_dir / "session_config.json", "w", encoding="utf-8") as f:
    json.dump(config_data, f, indent=2)

print("ALL CONFIGS POINTING TO ESCANOR v81!")
