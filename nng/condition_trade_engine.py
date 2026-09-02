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

    # ===== VWAP 2SD SHORT — Entry at current price (at 2sd extreme), stop above price, target VWAP =====
    elif cid == "VWAP_2SD_MEAN_REVERSION_SHORT":
        entry = round(price, 2)
        stop = round(price + BUFFER_PTS + 2.0, 2)   # Stop above current extreme price
        target = round(vwap, 2)                       # Target: mean reversion to VWAP/POC
        order_type = "SELL_LIMIT"

    # ===== VWAP 2SD LONG — Entry at current price (at -2sd extreme), stop below price, target VWAP =====
    elif cid == "VWAP_2SD_MEAN_REVERSION_LONG":
        entry = round(price, 2)
        stop = round(price - BUFFER_PTS - 2.0, 2)   # Stop below current extreme price
        target = round(vwap, 2)
        order_type = "BUY_LIMIT"


    # ===== TSMOM LONG — Pullback to M15 EMA20 in trending market =====
    elif cid == "TSMOM_LONG_SIGNAL":
        m15_ema20 = float(telemetry.get("m15_ema20", vah))
        entry = round(m15_ema20, 2) if m15_ema20 > val else round(vah, 2)
        stop = round(swing_low - BUFFER_PTS, 2)
        target = round(vah + (vah - val), 2)  # Measured move above VAH
        order_type = "BUY_LIMIT"

    # ===== TSMOM SHORT — Pullback to M15 EMA20 from below in downtrend =====
    elif cid == "TSMOM_SHORT_SIGNAL":
        m15_ema20 = float(telemetry.get("m15_ema20", val))
        entry = round(m15_ema20, 2) if m15_ema20 < vah else round(val, 2)
        stop = round(swing_high + BUFFER_PTS, 2)
        target = round(val - (vah - val), 2)  # Measured move below VAL
        order_type = "SELL_LIMIT"

    # ===== REGULAR DIVERGENCE LONG =====
    elif cid == "REGULAR_DIVERGENCE_REVERSAL_LONG":
        entry = round(fvg_ce if fvg_ce > 0 and fvg_ce > val else val, 2)
        stop = round(swing_low - BUFFER_PTS, 2)
        target = round(swing_high, 2)
        order_type = "BUY_LIMIT"

    # ===== REGULAR DIVERGENCE SHORT =====
    elif cid == "REGULAR_DIVERGENCE_REVERSAL_SHORT":
        entry = round(fvg_ce if 0 < fvg_ce < vah else vah, 2)
        stop = round(swing_high + BUFFER_PTS, 2)
        target = round(swing_low, 2)
        order_type = "SELL_LIMIT"

    # ===== HIDDEN DIVERGENCE LONG (trend continuation) =====
    elif cid == "HIDDEN_DIVERGENCE_CONTINUATION_LONG":
        m15_ema20 = float(telemetry.get("m15_ema20", price))
        entry = round(max(m15_ema20, fvg_ce) if fvg_ce > 0 else m15_ema20, 2)
        stop = round(swing_low - BUFFER_PTS, 2)
        target = round(swing_high, 2)
        order_type = "BUY_LIMIT"

    # ===== HIDDEN DIVERGENCE SHORT (trend continuation) =====
    elif cid == "HIDDEN_DIVERGENCE_CONTINUATION_SHORT":
        m15_ema20 = float(telemetry.get("m15_ema20", price))
        entry = round(min(m15_ema20, fvg_ce) if fvg_ce > 0 else m15_ema20, 2)
        stop = round(swing_high + BUFFER_PTS, 2)
        target = round(swing_low, 2)
        order_type = "SELL_LIMIT"

    # ===== ICT LONDON SWEEP LONG =====
    elif cid == "ICT_LONDON_SWEEP_LONG":
        asian_low = float(telemetry.get("asian_low", val - 3))
        asian_high = float(telemetry.get("asian_high", vah + 3))
        entry = round(fvg_ce if fvg_ce > 0 else val, 2)
        stop = round(asian_low - BUFFER_PTS, 2)
        target = round(asian_high, 2)
        order_type = "BUY_LIMIT"

    # ===== ICT LONDON SWEEP SHORT =====
    elif cid == "ICT_LONDON_SWEEP_SHORT":
        asian_high = float(telemetry.get("asian_high", vah + 3))
        asian_low = float(telemetry.get("asian_low", val - 3))
        entry = round(fvg_ce if 0 < fvg_ce < asian_high else vah, 2)
        stop = round(asian_high + BUFFER_PTS, 2)
        target = round(asian_low, 2)
        order_type = "SELL_LIMIT"

    # ===== ICT NY REVERSAL LONG =====
    elif cid == "ICT_NY_REVERSAL_LONG":
        entry = round(fvg_ce if fvg_ce > 0 else val, 2)
        stop = round(swing_low - BUFFER_PTS, 2)
        target = round(vah + 3, 2)
        order_type = "BUY_LIMIT"

    # ===== ICT NY REVERSAL SHORT =====
    elif cid == "ICT_NY_REVERSAL_SHORT":
        entry = round(fvg_ce if 0 < fvg_ce < price else vah, 2)
        stop = round(swing_high + BUFFER_PTS, 2)
        target = round(val - 3, 2)
        order_type = "SELL_LIMIT"

    # ===== COT COMMERCIAL EXTREME LONG =====
    elif cid == "COT_COMMERCIAL_EXTREME_LONG":
        entry = round(fvg_ce if fvg_ce > 0 else val, 2)
        stop = round(val - BUFFER_PTS - 2.0, 2)
        target = round(vah + (vah - val), 2)
        order_type = "BUY_LIMIT"

    # ===== COT COMMERCIAL EXTREME SHORT =====
    elif cid == "COT_COMMERCIAL_EXTREME_SHORT":
        entry = round(fvg_ce if 0 < fvg_ce < price else vah, 2)
        stop = round(vah + BUFFER_PTS + 2.0, 2)
        target = round(val - (vah - val), 2)
        order_type = "SELL_LIMIT"

    # ===== STATISTICAL EXTREME LONG =====
    elif cid == "STATISTICAL_EXTREME_REVERSAL_LONG":
        poc = float(telemetry.get("poc", price + 5))
        entry = round(price, 2)
        stop = round(swing_low - BUFFER_PTS, 2)
        target = round(poc, 2)
        order_type = "BUY_LIMIT"

    # ===== STATISTICAL EXTREME SHORT =====
    elif cid == "STATISTICAL_EXTREME_REVERSAL_SHORT":
        poc = float(telemetry.get("poc", price - 5))
        entry = round(price, 2)
        stop = round(swing_high + BUFFER_PTS, 2)
        target = round(poc, 2)
        order_type = "SELL_LIMIT"

    # ===== PDARRAY TRIPLE CONFLUENCE LONG =====
    elif cid == "PDARRAY_TRIPLE_CONFLUENCE_LONG":
        entry = round(fvg_ce if fvg_ce > 0 else val, 2)
        stop = round(val - BUFFER_PTS - 1.0, 2)
        target = round(vah, 2)
        order_type = "BUY_LIMIT"

    # ===== PDARRAY TRIPLE CONFLUENCE SHORT =====
    elif cid == "PDARRAY_TRIPLE_CONFLUENCE_SHORT":
        entry = round(fvg_ce if 0 < fvg_ce < price else vah, 2)
        stop = round(vah + BUFFER_PTS + 1.0, 2)
        target = round(val, 2)
        order_type = "SELL_LIMIT"

    # ===== KYLE LAMBDA INFORMED FLOW =====
    elif cid == "KYLE_LAMBDA_INFORMED_FLOW":
        # Follow the informed flow direction (from OFI)
        cvd = float(telemetry.get("cvd_10b", 0.0))
        if cvd > 0:
            entry = round(fvg_ce if fvg_ce > 0 else val, 2)
            stop = round(swing_low - BUFFER_PTS, 2)
            target = round(swing_high, 2)
            order_type = "BUY_LIMIT"
        else:
            entry = round(fvg_ce if 0 < fvg_ce < price else vah, 2)
            stop = round(swing_high + BUFFER_PTS, 2)
            target = round(swing_low, 2)
            order_type = "SELL_LIMIT"

    # ===== VOLATILITY EXPANSION CONTINUATION =====
    elif cid == "VOLATILITY_EXPANSION_CONTINUATION":
        if "BEARISH" in fvg_type or price < vah:
            entry = round(fvg_ce if fvg_ce > 0 else val, 2)
            stop = round(fvg_bottom - BUFFER_PTS if fvg_bottom > 0 else swing_low - BUFFER_PTS, 2)
            target = round(swing_high, 2)
            order_type = "BUY_LIMIT"
        else:
            entry = round(fvg_ce if 0 < fvg_ce < price else vah, 2)
            stop = round(fvg_top + BUFFER_PTS if fvg_top > 0 else swing_high + BUFFER_PTS, 2)
            target = round(swing_low, 2)
            order_type = "SELL_LIMIT"

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
        "brain_modules": condition_result.get("brain_modules", condition_result.get("brain_layers", {})),
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

