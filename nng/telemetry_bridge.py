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

    # ---- REAL PRICE HISTORY FROM MT5 ----
    # Pull actual M5 OHLCV data for Hurst, TSMOM, divergence, OU half-life, vol
    # Fallback to synthetic only if MT5 unavailable
    try:
        import MetaTrader5 as mt5
        if mt5.initialize():
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
            if rates is not None and len(rates) >= 20:
                tel["price_history"] = [float(r['close']) for r in rates]
                tel["high_history"] = [float(r['high']) for r in rates]
                tel["low_history"] = [float(r['low']) for r in rates]
                tel["open_history"] = [float(r['open']) for r in rates]
                tel["volume_history"] = [float(r['tick_volume']) for r in rates]
                tel["high_low_pairs"] = [(float(r['high']), float(r['low'])) for r in rates]
                # Also pull H1 for larger structure
                h1_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 50)
                if h1_rates is not None and len(h1_rates) >= 5:
                    tel["h1_price_history"] = [float(r['close']) for r in h1_rates]
                    tel["h1_high_history"] = [float(r['high']) for r in h1_rates]
                    tel["h1_low_history"] = [float(r['low']) for r in h1_rates]
                # Pull H4 closes for Wyckoff phase context
                h4_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, 30)
                if h4_rates is not None and len(h4_rates) >= 5:
                    tel["h4_price_history"] = [float(r['close']) for r in h4_rates]
                # Previous Day High/Low from D1
                d1_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 1, 5)
                if d1_rates is not None and len(d1_rates) >= 1:
                    tel["pdh"] = float(d1_rates[-1]['high'])   # yesterday's high
                    tel["pdl"] = float(d1_rates[-1]['low'])    # yesterday's low
                    if len(d1_rates) >= 2:
                        tel["pdph"] = float(d1_rates[-2]['high'])  # 2-day old high
                        tel["pdpl"] = float(d1_rates[-2]['low'])   # 2-day old low
                # Asian session range from M5 (22:00-01:00 UTC)
                import datetime
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                # Approximate Asian range from recent M5 data (first 3 hours of day)
                today_start = rates[0]['time'] if rates is not None else 0
                asian_bars = [r for r in rates if r['time'] < today_start + 3 * 3600] if rates is not None else []
                if asian_bars:
                    tel["asian_high"] = float(max(r['high'] for r in asian_bars))
                    tel["asian_low"] = float(min(r['low'] for r in asian_bars))
                # DXY proxy: EURUSD negative correlation with DXY
                # EURUSD falling = DXY rising = bearish XAUUSD
                eurusd_rates = mt5.copy_rates_from_pos('EURUSD', mt5.TIMEFRAME_H1, 0, 10)
                if eurusd_rates is not None and len(eurusd_rates) >= 3:
                    eurusd_now = float(eurusd_rates[-1]['close'])
                    eurusd_prev = float(eurusd_rates[-5]['close']) if len(eurusd_rates) >= 6 else float(eurusd_rates[0]['close'])
                    eurusd_change = (eurusd_now - eurusd_prev) / eurusd_prev
                    # EURUSD falling = DXY rising = bearish gold
                    if eurusd_change < -0.001:
                        tel["dxy_direction"] = "UP"  # DXY rising, bearish gold
                    elif eurusd_change > 0.001:
                        tel["dxy_direction"] = "DOWN"  # DXY falling, bullish gold
                    else:
                        tel["dxy_direction"] = "FLAT"
                    tel["eurusd_5bar_change"] = round(eurusd_change * 100, 4)
                # EMA from H1 rates for momentum module
                if h1_rates is not None and len(h1_rates) >= 20:
                    closes = [float(r['close']) for r in h1_rates]
                    k20 = 2.0 / 21
                    k50 = 2.0 / 51
                    ema20 = closes[0]
                    ema50 = closes[0]
                    for c in closes[1:]:
                        ema20 = c * k20 + ema20 * (1 - k20)
                        ema50 = c * k50 + ema50 * (1 - k50)
                    tel.setdefault("h1_ema20", round(ema20, 3))
                    tel.setdefault("h1_ema50", round(ema50, 3))
    except Exception as _mt5_err:
        pass  # Fall through to synthetic fallback

    # ---- SYNTHETIC FALLBACK (if MT5 unavailable) ----
    if "price_history" not in tel or len(tel.get("price_history", [])) < 10:
        import random
        random.seed(int(price * 100) % 9999)
        center = price
        spread = (vah - val) if (vah > val) else 8.0
        history = []
        p = center
        for _ in range(80):
            p += random.gauss(0, spread / 20)
            p = max(min(p, center + spread), center - spread)
            history.append(p)
        tel["price_history"] = history
        tel.setdefault("high_history", [p + spread * 0.1 for p in history])
        tel.setdefault("low_history", [p - spread * 0.1 for p in history])
        tel.setdefault("high_low_pairs", list(zip(tel["high_history"], tel["low_history"])))

    # ---- SPREAD ----
    tel["live_spread_pts"] = round((tel.get("ask", price) - tel.get("bid", price)) * 10, 1)  # in points (0.01 each)

    # ---- FINAL DEFAULTS ----
    tel.setdefault("pdh", round(vah + 8.0, 2))
    tel.setdefault("pdl", round(val - 8.0, 2))
    tel.setdefault("asian_high", tel.get("swing_high", round(vah + 3.0, 2)))
    tel.setdefault("asian_low", tel.get("swing_low", round(val - 3.0, 2)))
    tel.setdefault("asian_high_swept", price > tel["asian_high"])
    tel.setdefault("asian_low_swept", price < tel["asian_low"])
    tel.setdefault("dxy_direction", "FLAT")
    tel.setdefault("tips_yield_change", 0.0)
    tel.setdefault("cot_commercial_net", 0.0)
    tel.setdefault("cot_large_spec_net", 0.0)
    tel.setdefault("cot_commercial_net_history", [0.0] * 10)
    tel.setdefault("h1_ema20", price)
    tel.setdefault("h1_ema50", price)

    return tel
