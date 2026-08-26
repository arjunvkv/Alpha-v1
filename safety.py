"""Account safety checks (DAEMON_V2_SPEC.md section 10).

Four hard-stop monitors evaluated every poll. Each fires ONCE while a
breach persists; the latch survives AI reset attempts until the breach
actually clears, then re-arms automatically.
"""

import time
from datetime import datetime, timezone

SAFETY_HEAT = "SAFETY_HEAT"
SAFETY_FREE_MARGIN = "SAFETY_FREE_MARGIN"
SAFETY_SL_BREACH = "SAFETY_SL_BREACH"
SAFETY_TERMINAL_SILENCE = "SAFETY_TERMINAL_SILENCE"

SAFETY_IDS = {SAFETY_HEAT, SAFETY_FREE_MARGIN, SAFETY_SL_BREACH,
              SAFETY_TERMINAL_SILENCE}


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def check_safety(account, positions, cfg, provider_ts=None, now_ts=None):
    """Return a list of safety payload dicts for current breaches."""
    payloads = []
    now_ts = now_ts if now_ts is not None else time.time()
    account = account or {}
    equity = _num(account.get("equity")) or 0.0

    def _payload(sid, detail):
        return {
            "id": sid,
            "kind": "safety",
            "direction": "any",
            "severity": "critical",
            "detail": detail,
            "ts": datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat(),
        }

    if equity > 0:
        heat_pct = sum(abs(_num(p.get("pnl")) or 0.0)
                       for p in positions or []) / equity * 100.0
        max_heat = _num(cfg.get("max_heat_pct"))
        if max_heat is not None and heat_pct > max_heat:
            payloads.append(_payload(
                SAFETY_HEAT, "open heat %.2f%% exceeds max %.2f%%"
                % (heat_pct, max_heat)))

        free_margin = _num(account.get("free_margin"))
        min_free = _num(cfg.get("min_free_margin_pct"))
        if free_margin is not None and min_free is not None:
            free_pct = free_margin / equity * 100.0
            if free_pct < min_free:
                payloads.append(_payload(
                    SAFETY_FREE_MARGIN,
                    "free margin %.2f%% below floor %.2f%%"
                    % (free_pct, min_free)))

    breaches = []
    for pos in positions or []:
        sl = _num(pos.get("sl"))
        current = _num(pos.get("current"))
        direction = pos.get("direction")
        if sl is None or sl <= 0 or current is None:
            continue
        if direction == "long" and current < sl:
            breaches.append("%s long %.5f under SL %.5f"
                            % (pos.get("symbol"), current, sl))
        elif direction == "short" and current > sl:
            breaches.append("%s short %.5f over SL %.5f"
                            % (pos.get("symbol"), current, sl))
    if breaches:
        payloads.append(_payload(SAFETY_SL_BREACH,
                                 "; ".join(breaches)))

    silence_sec = _num(cfg.get("terminal_silence_sec"))
    if provider_ts is not None and silence_sec is not None:
        silent_for = now_ts - provider_ts
        if silent_for > silence_sec:
            payloads.append(_payload(
                SAFETY_TERMINAL_SILENCE,
                "no terminal data for %.0fs (limit %.0fs)"
                % (silent_for, silence_sec)))
    return payloads
