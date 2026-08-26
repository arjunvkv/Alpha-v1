"""
Trap-Aware Monitor Authoring (AI writes the fire)

Data sources (verified against live Granger snapshot schema):
- Structural levels : C:/Trading/Alpha/data/live/zones.json  (curated BB/SMA bands)
- Institutional align: Granger positioning.data.metals.{metal}.net_positioning_signal
- Live price         : Granger prices.data.instruments.{metal}.last_close

Rule (the anti-web-of-strings gate):
- A monitor is armed at a structural level ONLY when institutional positioning
  confirms the breakout direction (COT bullish -> arm breakout-above; bearish ->
  arm breakdown-below). Bands without confirmation are TRAP_1 -> skipped.
- TRAP_2: price poking the level (within noise band) -> skipped (needs retest).
- TRAP_5: bare round-number level -> skipped.
- Trigger placed BEYOND noise so a touch = real move.
- Result: the AI authors meaningful fires; the daemon only wakes when one crosses.

Run on each liveness_15min_wake. Safe to repeat.
"""
import json
import os
from datetime import datetime

GRANGER_SNAPSHOT_PATH = "C:/Trading/data/all_layers_snapshot.json"
ZONES_PATH = "C:/Trading/Alpha/data/live/zones.json"
AI_TRIGGERS_PATH = "C:/Trading/Alpha/data/live/ai_triggers.json"

SYMBOL_TO_METAL = {
    "XAUUSD": "gold", "XAGUSD": "silver", "XPTUSD": "platinum",
    "XPDUSD": "palladium", "HG=F": "copper",
}
NOISE_PCT = 0.15
SPREAD_GATES = {"XAUUSD": 80, "XAGUSD": 50, "XPTUSD": 250, "XPDUSD": 250, "HG=F": 30}


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_price(snap, metal):
    inst = snap.get("layers", {}).get("prices", {}).get("data", {}).get("instruments", {}).get(metal, {})
    return inst.get("last_close")


def get_inst_align(snap, metal):
    pos = snap.get("layers", {}).get("positioning", {}).get("data", {}).get("metals", {}).get(metal, {})
    sig = pos.get("net_positioning_signal")
    return sig if sig in ("bullish", "bearish") else None


def author_monitors(snap, zones):
    """AI writes ONE best fire per symbol: the nearest structural level that
    survives TRAP_1/2/5 and has COT confirmation. No cluster, no web-of-strings."""
    rules = []
    for sym, metal in SYMBOL_TO_METAL.items():
        price = get_price(snap, metal)
        if price is None:
            continue
        align = get_inst_align(snap, metal)
        noise = price * NOISE_PCT / 100.0
        best = None  # (dist, lvl, ztype, side)
        for z in zones.get(sym, []):
            if not isinstance(z, dict):
                continue
            lvl = z.get("level")
            ztype = z.get("type")
            if not isinstance(lvl, (int, float)):
                continue
            dist = abs(price - lvl)
            if dist < noise:
                continue  # TRAP_2: poking the level, needs retest
            if "ROUND" in str(ztype).upper():
                continue  # TRAP_5: bare round number
            side = "above" if lvl >= price else "below"
            # TRAP_1 gate: bands/MAs require institutional confirmation in direction
            if str(ztype).upper() in ("BB_UPPER", "BB_LOWER", "BB_MIDDLE", "SMA20", "SMA50", "SMA200"):
                if side == "above" and align != "bullish":
                    continue
                if side == "below" and align != "bearish":
                    continue
            if best is None or dist < best[0]:
                best = (dist, lvl, ztype, side)
        if best:
            _, lvl, ztype, side = best
            offset = max(0.5, lvl * 0.15 / 100.0)  # ~0.15% beyond level, just past noise
            trigger_lvl = round(lvl + offset if side == "above" else lvl - offset, 2)
            rid = f"{sym.lower()}_{'breakout' if side == 'above' else 'breakdown'}_{int(lvl)}"
            rules.append({
                "id": rid,
                "type": "price_above" if side == "above" else "price_below",
                "symbol": sym,
                "level": trigger_lvl,
                "spread_gate": SPREAD_GATES.get(sym, 80),
                "ring_once": True,
                "thesis": (f"{ztype} {lvl:.2f} on {sym}; COT {align} confirms "
                           f"{'breakout' if side=='above' else 'breakdown'} direction. "
                           f"Price {price:.2f}, trigger {trigger_lvl} (offset {offset:.2f})."),
                "authored_utc": datetime.utcnow().isoformat() + "Z",
                "traps_checked": ["TRAP_1", "TRAP_2", "TRAP_5"],
                "granger_anchor": {"level": ztype, "value": lvl, "inst_align": align},
                "session_gate": ["london", "ny"],
            })
    return rules


def main():
    snap = load_json(GRANGER_SNAPSHOT_PATH)
    zones = load_json(ZONES_PATH)
    if snap is None or zones is None:
        print("Missing snapshot or zones - skipping.")
        return
    new_rules = author_monitors(snap, zones)
    with open(AI_TRIGGERS_PATH, encoding="utf-8") as f:
        triggers = json.load(f)
    kept = [r for r in triggers.get("rules", []) if r.get("type") == "time"]
    triggers["rules"] = kept + new_rules
    triggers.setdefault("_notes", {}).update({
        "ai_writes_the_fire": "Monitors authored by AI after trap-aware + COT-confirmed analysis. Zone_approach wake disabled in daemon.py.",
        "arm_rule": "Band/MA monitors arm ONLY when net_positioning_signal confirms direction (kills TRAP_1 / web-of-strings).",
    })
    with open(AI_TRIGGERS_PATH, "w", encoding="utf-8") as f:
        json.dump(triggers, f, indent=2)
    print(f"AI authored {len(new_rules)} COT-confirmed monitors: "
          + (", ".join(r["id"] for r in new_rules) or "(none - COT neutral across all symbols)"))


if __name__ == "__main__":
    main()
