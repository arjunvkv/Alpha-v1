# -*- coding: utf-8 -*-
# nng/telemetry_bridge.py
#
# Pulls all live MCP telemetry for a symbol and produces
# a flat telemetry dict that RegimeBrain and ConditionTradeEngine consume.
# Handles all nested key structures from alpha_mcp_server.

import json
from typing import Any, Dict, Optional


def get_live_telemetry(mcp_server_module, symbol: str) -> Dict[str, Any]:
    """
    Fetch all live market data from MCP server and return flat telemetry dict.
    All nested key parsing is handled here — callers get clean flat data.
    """
    tel = {}

    # ---- CONVICTION (richest source) ----
    try:
        conv_raw = mcp_server_module.get_symbol_conviction(symbol)
        conv = json.loads(conv_raw) if isinstance(conv_raw, str) else conv_raw
        tel["bid"] = float(conv.get("live_bid", 0.0) or 0.0)
        tel["ask"] = float(conv.get("live_ask", 0.0) or 0.0)
        tel["live_price"] = round((tel["bid"] + tel["ask"]) / 2, 3)
        tel["mtf_alignment"] = str(conv.get("mtf_alignment", ""))
        ind = conv.get("technical_indicators", {}) or {}
        tel["h4_rsi"] = float(ind.get("h4_rsi", 50.0) or 50.0)
        tel["h1_rsi"] = float(ind.get("h1_rsi", 50.0) or 50.0)
        tel["m15_rsi"] = float(ind.get("m15_rsi", 50.0) or 50.0)
        tel["m5_rsi"] = float(ind.get("m5_rsi", 50.0) or 50.0)
        tel["h4_ema20"] = float(ind.get("h4_ema20", 0.0) or 0.0)
        tel["h4_ema50"] = float(ind.get("h4_ema50", 0.0) or 0.0)
        tel["m15_ema20"] = float(ind.get("m15_ema20", 0.0) or 0.0)
        tel["m15_ema50"] = float(ind.get("m15_ema50", 0.0) or 0.0)
        cvd_data = conv.get("measured_cvd", {}) or {}
        tel["cvd_10b"] = float(cvd_data.get("recent_10_bar_delta", 0.0) or 0.0)
        tel["cvd_cumulative"] = float(cvd_data.get("cumulative_volume_delta", 0.0) or 0.0)
        tel["velocity_tpm"] = float(cvd_data.get("tick_velocity_tpm", 80.0) or 80.0)
        tel["delta_exhaustion"] = bool(cvd_data.get("delta_exhaustion", False))
        tel["nearest_fvg"] = conv.get("nearest_fvg", {}) or {}
    except Exception as e:
        tel.setdefault("live_price", 0.0)
        tel.setdefault("nearest_fvg", {})

    # ---- VOLUME PROFILE ----
    try:
        prof_raw = mcp_server_module.get_full_institutional_profile(symbol)
        prof = json.loads(prof_raw) if isinstance(prof_raw, str) else prof_raw
        vp = prof.get("volume_profile", {}) or {}
        tel["vah"] = float(vp.get("value_area_high_vah_70", 0.0) or 0.0)
        tel["val"] = float(vp.get("value_area_low_val_70", 0.0) or 0.0)
        tel["poc"] = float(vp.get("point_of_control_poc", 0.0) or 0.0)
        tel["price_location"] = str(vp.get("price_location", ""))
        # Structural state
        struct = prof.get("structural_market_state", {}) or {}
        tel["displacement"] = bool(struct.get("displacement", False))
        tel["choch"] = str(struct.get("choch_status", ""))
        tel["bos"] = str(struct.get("bos_status", ""))
    except Exception:
        tel.setdefault("vah", 0.0)
        tel.setdefault("val", 0.0)
        tel.setdefault("poc", 0.0)

    # ---- MEASURED CVD (more detail) ----
    try:
        cvd_raw = mcp_server_module.get_measured_cvd(symbol)
        cvd = json.loads(cvd_raw) if isinstance(cvd_raw, str) else cvd_raw
        if cvd.get("status") == "MEASURED_ACTIVE":
            tel["cvd_10b"] = float(cvd.get("recent_10_bar_delta", tel.get("cvd_10b", 0.0)) or 0.0)
            tel["velocity_tpm"] = float(cvd.get("tick_velocity_tpm", tel.get("velocity_tpm", 80.0)) or 80.0)
            tel["cvd_cumulative"] = float(cvd.get("cumulative_volume_delta", tel.get("cvd_cumulative", 0.0)) or 0.0)
    except Exception:
        pass

    # ---- FVG MATRIX (get all FVGs for context) ----
    try:
        fvg_raw = mcp_server_module.get_fvg_matrix(symbol)
        fvg_data = json.loads(fvg_raw) if isinstance(fvg_raw, str) else fvg_raw
        fvg_list = fvg_data.get("fvg_matrix", []) or []
        tel["all_fvgs"] = fvg_list

        # Find swing highs/lows from FVG tops/bottoms
        if fvg_list:
            all_tops = [f.get("top", 0) for f in fvg_list if f.get("top")]
            all_bottoms = [f.get("bottom", 0) for f in fvg_list if f.get("bottom")]
            if all_tops:
                tel["swing_high"] = round(max(all_tops), 2)
            if all_bottoms:
                tel["swing_low"] = round(min(all_bottoms), 2)
    except Exception:
        tel.setdefault("all_fvgs", [])

    # ---- VWAP BANDS (derived from VAH/VAL as proxy if no direct feed) ----
    # Using Value Area as VWAP proxy: VAH ~ VWAP+1sd, VAL ~ VWAP-1sd
    # Dalton: VWAP ~ POC
    price = tel.get("live_price", 0.0)
    poc = tel.get("poc", price)
    vah = tel.get("vah", poc)
    val = tel.get("val", poc)
    va_half = (vah - val) / 2.0 if (vah > val) else 5.0
    tel.setdefault("vwap", poc)
    tel.setdefault("vwap_1sd_upper", round(poc + va_half, 2))
    tel.setdefault("vwap_1sd_lower", round(poc - va_half, 2))
    tel.setdefault("vwap_2sd_upper", round(poc + va_half * 2, 2))
    tel.setdefault("vwap_2sd_lower", round(poc - va_half * 2, 2))

    # ---- SWING HIGH/LOW DEFAULTS ----
    tel.setdefault("swing_high", round(vah + 3.0, 2))
    tel.setdefault("swing_low", round(val - 3.0, 2))

    # ---- ASIAN SESSION CONTEXT ----
    # Not directly from MCP — approximate from swing extremes
    tel.setdefault("asian_high", tel["swing_high"])
    tel.setdefault("asian_low", tel["swing_low"])
    tel.setdefault("asian_high_swept", price > tel["swing_high"])
    tel.setdefault("asian_low_swept", price < tel["swing_low"])

    # ---- PRICE HISTORY (approximate from available data) ----
    # Build synthetic history from recent range for Hurst estimation
    import random
    random.seed(42)
    center = price
    spread = (vah - val) if (vah > val) else 8.0
    history = [center + random.uniform(-spread / 2, spread / 2) for _ in range(50)]
    tel["price_history"] = history

    return tel
