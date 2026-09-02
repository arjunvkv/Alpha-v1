# -*- coding: utf-8 -*-
# nng/condition_trade_engine.py
#
# Reads the condition from RegimeBrain and extracts the EXACT trade coordinates
# (entry, stop, target) from the market's own structure — not invented.
#
# Each condition knows where its entry, stop, and target live geometrically.
# The engine just measures those from the live telemetry.

from typing import Dict, Any, Optional

BUFFER_PTS = 1.5   # Minimum buffer beyond structural level for stops


def extract_trade(condition_result: Dict[str, Any], telemetry: Dict[str, Any]) -> Dict[str, Any]:
    """
    Given a classified condition and live telemetry, return precise
    entry/stop/target coordinates from the condition's structural geometry.
    """
    cid = condition_result.get("condition_id", "DEAD_ZONE_NO_CONDITION")
    direction = condition_result.get("direction", "FLAT")

    if direction == "FLAT" or cid == "DEAD_ZONE_NO_CONDITION":
        return _no_trade(cid, "No active market condition — no trade.")

    price = float(telemetry.get("live_price", 0.0))
    bid = float(telemetry.get("bid", price))
    ask = float(telemetry.get("ask", price))
    vah = float(telemetry.get("vah", 0.0))
    val = float(telemetry.get("val", 0.0))
    poc = float(telemetry.get("poc", 0.0))
    vwap = float(telemetry.get("vwap", price))
    vwap_2sd_upper = float(telemetry.get("vwap_2sd_upper", vwap + 10))
    vwap_2sd_lower = float(telemetry.get("vwap_2sd_lower", vwap - 10))
    fvg = telemetry.get("nearest_fvg", {})
    fvg_ce = float(fvg.get("consequent_encroachment", 0.0) or 0.0)
    fvg_top = float(fvg.get("top", 0.0) or 0.0)
    fvg_bottom = float(fvg.get("bottom", 0.0) or 0.0)
    fvg_type = str(fvg.get("type", "")).upper()
    swing_high = float(telemetry.get("swing_high", price + 8))
    swing_low = float(telemetry.get("swing_low", price - 8))

    entry = stop = target = None
    order_type = "LIMIT"

    # ===== TREND BOS PULLBACK =====
    if cid == "TREND_BOS_PULLBACK":
        if "BULLISH" in fvg_type or telemetry.get("mtf_alignment", "").upper().count("BULLISH") >= 2:
            entry = round(fvg_ce, 2)
            stop = round(fvg_bottom - BUFFER_PTS, 2)
            target = round(swing_high, 2)
            order_type = "BUY_LIMIT"
        else:
            entry = round(fvg_ce, 2)
            stop = round(fvg_top + BUFFER_PTS, 2)
            target = round(swing_low, 2)
            order_type = "SELL_LIMIT"

    # ===== LIQUIDITY SWEEP REVERSAL =====
    elif cid == "LIQUIDITY_SWEEP_REVERSAL":
        asian_high = float(telemetry.get("asian_high", swing_high))
        asian_low = float(telemetry.get("asian_low", swing_low))
        asian_high_swept = bool(telemetry.get("asian_high_swept", False))
        if asian_high_swept:
            # Sweep of Asian High = SHORT reversal
            entry = round(fvg_ce if fvg_ce > 0 else price, 2)
            stop = round(asian_high + BUFFER_PTS, 2)
            target = round(asian_low, 2)
            order_type = "SELL_LIMIT"
        else:
            # Sweep of Asian Low = LONG reversal
            entry = round(fvg_ce if fvg_ce > 0 else price, 2)
            stop = round(asian_low - BUFFER_PTS, 2)
            target = round(asian_high, 2)
            order_type = "BUY_LIMIT"

    # ===== FVG MITIGATION RETURN =====
    elif cid == "FVG_MITIGATION_RETURN":
        if "BEARISH" in fvg_type:
            # Price coming up to fill Bearish FVG = SHORT from CE
            entry = round(fvg_ce, 2)
            stop = round(fvg_top + BUFFER_PTS, 2)
            target = round(val if val > 0 else price - 8, 2)
            order_type = "SELL_LIMIT"
        else:
            # Price coming down to fill Bullish FVG = LONG from CE
            entry = round(fvg_ce, 2)
            stop = round(fvg_bottom - BUFFER_PTS, 2)
            target = round(vah if vah > 0 else price + 8, 2)
            order_type = "BUY_LIMIT"

    # ===== VALUE AREA ROTATION SHORT =====
    elif cid == "VALUE_AREA_ROTATION_SHORT":
        entry = round(vah, 2)
        stop = round(vah + BUFFER_PTS + 1.0, 2)
        target = round(poc if poc > 0 else val, 2)
        order_type = "SELL_LIMIT"

    # ===== VALUE AREA ROTATION LONG =====
    elif cid == "VALUE_AREA_ROTATION_LONG":
        entry = round(val, 2)
        stop = round(val - BUFFER_PTS - 1.0, 2)
        target = round(poc if poc > 0 else vah, 2)
        order_type = "BUY_LIMIT"

    # ===== VWAP 2SD SHORT =====
    elif cid == "VWAP_2SD_MEAN_REVERSION_SHORT":
        entry = round(fvg_ce if fvg_ce > price else price, 2)
        stop = round(vwap_2sd_upper + BUFFER_PTS, 2)
        target = round(vwap, 2)
        order_type = "SELL_LIMIT"

    # ===== VWAP 2SD LONG =====
    elif cid == "VWAP_2SD_MEAN_REVERSION_LONG":
        entry = round(fvg_ce if 0 < fvg_ce < price else price, 2)
        stop = round(vwap_2sd_lower - BUFFER_PTS, 2)
        target = round(vwap, 2)
        order_type = "BUY_LIMIT"

    # ===== WYCKOFF SPRING (LONG) =====
    elif cid == "WYCKOFF_SPRING_REVERSAL":
        spring_low = float(telemetry.get("swing_low", val - 2))
        entry = round(val + 0.5, 2)          # First close back inside VA
        stop = round(spring_low - BUFFER_PTS, 2)
        target = round(vah, 2)
        order_type = "BUY_LIMIT"

    # ===== WYCKOFF UTAD (SHORT) =====
    elif cid == "WYCKOFF_UTAD_REVERSAL":
        utad_high = float(telemetry.get("swing_high", vah + 2))
        entry = round(vah - 0.5, 2)          # First close back inside VA
        stop = round(utad_high + BUFFER_PTS, 2)
        target = round(val, 2)
        order_type = "SELL_LIMIT"

    # ===== COMPRESSION BREAKOUT LONG =====
    elif cid == "COMPRESSION_BREAKOUT_LONG":
        range_high = float(telemetry.get("compression_range_high", vah))
        range_low = float(telemetry.get("compression_range_low", val))
        range_width = range_high - range_low
        entry = round(range_high, 2)
        stop = round(range_high - range_width * 0.5, 2)
        target = round(range_high + range_width, 2)
        order_type = "BUY_STOP"

    # ===== COMPRESSION BREAKOUT SHORT =====
    elif cid == "COMPRESSION_BREAKOUT_SHORT":
        range_high = float(telemetry.get("compression_range_high", vah))
        range_low = float(telemetry.get("compression_range_low", val))
        range_width = range_high - range_low
        entry = round(range_low, 2)
        stop = round(range_low + range_width * 0.5, 2)
        target = round(range_low - range_width, 2)
        order_type = "SELL_STOP"

    else:
        return _no_trade(cid, f"No geometry defined for condition {cid}")

    if entry is None or stop is None or target is None:
        return _no_trade(cid, "Incomplete price levels — cannot build trade geometry.")

    # Validate geometry is sensible
    if "BUY" in order_type:
        if not (stop < entry < target):
            return _no_trade(cid, f"Invalid BUY geometry: stop={stop} entry={entry} target={target}")
        risk = round(entry - stop, 2)
        reward = round(target - entry, 2)
    else:
        if not (target < entry < stop):
            return _no_trade(cid, f"Invalid SELL geometry: target={target} entry={entry} stop={stop}")
        risk = round(stop - entry, 2)
        reward = round(entry - target, 2)

    rr = round(reward / risk, 2) if risk > 0 else 0.0
    direction_final = "LONG" if "BUY" in order_type else "SHORT"

    return {
        "trade_valid": True,
        "condition_id": cid,
        "direction": direction_final,
        "order_type": order_type,
        "entry": entry,
        "stop_loss": stop,
        "take_profit": target,
        "risk_pts": risk,
        "reward_pts": reward,
        "rr_ratio": rr,
        "lot_size": 1.0,
        "condition_name": condition_result.get("condition_name", ""),
        "literature": condition_result.get("literature", ""),
        "why": condition_result.get("when_description", ""),
        "brain_layers": condition_result.get("brain_layers", {}),
    }


def _no_trade(cid: str, reason: str) -> Dict[str, Any]:
    return {
        "trade_valid": False,
        "condition_id": cid,
        "direction": "FLAT",
        "order_type": None,
        "entry": None,
        "stop_loss": None,
        "take_profit": None,
        "risk_pts": 0,
        "reward_pts": 0,
        "rr_ratio": 0,
        "lot_size": 0,
        "reason": reason,
    }
