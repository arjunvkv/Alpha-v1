"""
Step 3 — E2E dry run: real MT5, real daemon components, NO order placement,
NO opencode spawning (stubbed). Validates the full loop safely.
Run with Aletheia venv python:
    & C:\\Trading\\Aletheia\\.venv\\Scripts\\python.exe tests/e2e_dry_run.py
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Trading\Alpha")

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name} {detail}")


print("=== E2E Dry Run ===")
from daemon.daemon import (AlphaDaemon, ACTION_FILE, DATA_DIR, TRIGGER_FILE,
                           DATA_DIR as LIVE)

d = AlphaDaemon()

# Stub anything that would leave the machine
fired = []
d._fire_trigger = lambda trigger: fired.append(trigger)

# 1. Connect (also subscribes all configured symbols)
check("MT5 connect", d.mt5.connect())
acct = d.mt5.get_account()
check("account live", acct is not None and acct["balance"] > 0,
      str(acct)[:80])

# 2. One pass of every monitor stage
d._check_positions()          # no open positions -> no-op
check("position scan ok", True)
try:
    d._check_regime()         # returns None by design; must not raise
    check("regime scan ok", True)
except Exception as e:
    check("regime scan ok", False, str(e))
d._check_zones()
# A fired trigger is only a failure if it's NOT a genuine ≤0.5% zone approach
legit = all(
    (t.get("trigger", {}).get("zone", {}).get("distance_pct", 99) <= 0.5)
    for t in fired
)
check("zone scan ok (only legit triggers)", legit,
      f"fired: {[(t.get('symbol'), t.get('trigger', {}).get('zone', {}).get('distance_pct')) for t in fired]}")
fired.clear()
d._full_scan()
check("full scan ok", True)

# 3. Force a REAL zone trigger from a live tick
tick = d.mt5.get_tick("XAGUSD")
check("live XAGUSD tick", bool(tick) and tick["bid"] > 0)
if not tick:
    print("\nNo tick — aborting E2E (market closed?)")
    sys.exit(1)
bid = tick["bid"]
trigger = d.trigger_builder.build_zone_trigger(
    "XAGUSD",
    {"level": round(bid, 2), "type": "E2E_TEST_LEVEL",
     "distance_pct": 0.0, "significance": "dry-run synthetic"},
    {"last": bid, "bid": bid, "ask": tick["ask"],
     "spread": tick["spread"]},
)
check("trigger built with regime", bool(trigger.get("regime")))
check("trigger built with calendar", "calendar" in trigger)
check("trigger built with account+heat", "heat_pct" in (trigger.get("account") or {}))

# Write artifacts exactly as _fire_trigger would (minus opencode)
LIVE.mkdir(parents=True, exist_ok=True)
TRIGGER_FILE.write_text(json.dumps(trigger, indent=2, default=str))
prompt = d._build_wake_prompt(trigger)
(DATA_DIR / "wake_prompt.txt").write_text(prompt)
check("trigger.json written", TRIGGER_FILE.exists())
check("wake prompt substantial", len(prompt) > 800, f"{len(prompt)} chars")
check("prompt marks daemon origin", "[ALPHA DAEMON TRIGGER]" in prompt)

# 4. Action consumer: non-executing decision
ACTION_FILE.write_text(json.dumps({"decision": "WAIT",
                                   "reason": "e2e dry run"}))
d._process_actions()
check("WAIT consumed + cleared", not ACTION_FILE.exists())

# 5. Action consumer: ENTER without stop MUST be refused
ACTION_FILE.write_text(json.dumps({
    "decision": "ENTER", "symbol": "XAGUSD", "direction": "LONG",
    "lots": 0.01, "sl": None}))
positions_before = len(d.mt5.get_positions())
d._process_actions()
time.sleep(0.5)
positions_after = len(d.mt5.get_positions())
check("naked ENTER refused", positions_after == positions_before)
archive = DATA_DIR / "processed_actions.jsonl"
last_line = archive.read_text().strip().splitlines()[-1]
check("refusal archived", "no_stop" in last_line)

# 6. Error monitor captured the refusal
recent = [e["type"] for e in __import__(
    "monitor.error_monitor", fromlist=["error_monitor"]
).error_monitor.get_recent(5)]
check("error monitor saw refusal", "NO_STOP_REFUSED" in recent, str(recent))

# Cleanup test artifacts
for f in ["trigger.json", "wake_prompt.txt"]:
    (DATA_DIR / f).unlink(missing_ok=True)

d.mt5.disconnect()
print(f"\n{'='*60}\nRESULTS: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
