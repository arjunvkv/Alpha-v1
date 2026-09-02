# -*- coding: utf-8 -*-
# nng/regime_brain.py - Real Quantitative Market Regime Brain
#
# Research Foundations:
#   - Hurst Exponent (R/S Analysis): Peters 1994 Fractal Market Hypothesis
#   - Order Flow Imbalance (OFI): Cont, Kukanov & Stoikov 2014
#   - Wyckoff Phase Detection: Richard Wyckoff 1930s, Pruden 2007
#   - Auction Market Theory (AMT): Steidlmayer 1985, Dalton 1990
#   - VWAP Deviation Bands: Harris 2003, Berkowitz 1988
#
# Classifies live market into ONE named condition.
# Each condition owns its trade geometry — no invented heuristics.

import math
import numpy as np
from typing import Dict, Any, Optional, Tuple


def compute_hurst(prices: list, max_lag: int = 20) -> float:
    """
    Hurst Exponent via R/S analysis. Peters (1994).
    H > 0.55 = TRENDING  H < 0.45 = MEAN_REVERTING  else = RANDOM_WALK
    """
    if len(prices) < max_lag + 2:
        return 0.5
    ts = np.log(np.array(prices, dtype=float) + 1e-9)
    lags = range(2, min(max_lag, len(ts) // 2))
    tau = []
    for lag in lags:
        diffs = np.subtract(ts[lag:], ts[:-lag])
        std = float(np.std(diffs))
        tau.append(std if std > 0 else 1e-9)
    if len(tau) < 2:
        return 0.5
    try:
        poly = np.polyfit(np.log(list(lags)), np.log(tau), 1)
        return float(np.clip(poly[0] * 2.0, 0.0, 1.0))
    except Exception:
        return 0.5


def compute_ofi(cvd_10b: float, velocity_tpm: float, cumulative_cvd: float) -> float:
    """
    Order Flow Imbalance (OFI). Cont, Kukanov & Stoikov (2014).
    Proxy from tick CVD. Returns normalized [-1, 1].
    Positive = buy pressure. Negative = sell pressure.
    """
    total_vol = abs(cvd_10b) + abs(cumulative_cvd) + 1.0
    velocity_weight = min(velocity_tpm / 200.0, 1.0)
    ofi_raw = (cvd_10b / total_vol) * velocity_weight
    return float(np.clip(ofi_raw, -1.0, 1.0))


def detect_wyckoff_phase(
    price: float, vah: float, val: float, poc: float,
    cvd_10b: float, velocity_tpm: float, displacement: bool, choch: str
) -> str:
    """
    Wyckoff phase detection. Wyckoff (1930), Pruden (2007).
    Spring = false low with positive OFI recovery.
    UTAD = false high with negative OFI rejection.
    """
    price_above = price > vah
    price_below = price < val
    price_in_range = val <= price <= vah

    if price_below and cvd_10b > 400:
        return "WYCKOFF_ACCUMULATION_SPRING"
    if price_above and cvd_10b < -300:
        return "WYCKOFF_DISTRIBUTION_UTAD"
    if displacement and "UP" in choch.upper() and price_above:
        return "WYCKOFF_MARKUP_BOS"
    if displacement and ("DOWN" in choch.upper() or "BEARISH" in choch.upper()) and price_below:
        return "WYCKOFF_MARKDOWN_BREAK"
    if price_in_range and velocity_tpm < 70:
        return "WYCKOFF_REACCUMULATION_BALANCE"
    return "WYCKOFF_UNCLEAR"


def classify_amt_day_type(
    price: float, vah: float, val: float, poc: float,
    vwap: float, vwap_2sd_upper: float, vwap_2sd_lower: float,
    mtf_alignment: str, h4_rsi: float
) -> str:
    """
    AMT day-type classification. Steidlmayer (1985), Dalton (1990).
    TREND_DAY: directional expansion from VWAP.
    NORMAL_VARIATION: single leg extension, rotates back.
    TRADING_RANGE: balanced inside Value Area.
    NON_TREND: random, no committed direction.
    """
    is_above_2sd = price > vwap_2sd_upper
    is_below_2sd = price < vwap_2sd_lower
    is_bullish_mtf = "BULLISH" in mtf_alignment.upper()
    is_trending_h4 = h4_rsi > 57 or h4_rsi < 43

    if (is_above_2sd or is_below_2sd) and is_trending_h4:
        return "AMT_TREND_DAY"
    if (price > vah or price < val):
        return "AMT_NORMAL_VARIATION"
    if val <= price <= vah:
        return "AMT_TRADING_RANGE"
    return "AMT_NON_TREND"


def classify_vwap_regime(
    price: float, vwap: float,
    vwap_1sd_upper: float, vwap_1sd_lower: float,
    vwap_2sd_upper: float, vwap_2sd_lower: float
) -> Tuple[str, float]:
    """
    VWAP deviation band classification.
    Harris (2003): 95% of intraday volume within VWAP +-2sd.
    Beyond +-2sd mean reversion probability ~68% (empirical).
    """
    if price > vwap_2sd_upper:
        return "VWAP_EXTREME_PREMIUM_SELL", ((price - vwap_2sd_upper) / max(price, 1)) * 100
    elif price < vwap_2sd_lower:
        return "VWAP_EXTREME_DISCOUNT_BUY", ((vwap_2sd_lower - price) / max(price, 1)) * 100
    elif price > vwap_1sd_upper:
        return "VWAP_PREMIUM_ZONE", ((price - vwap) / max(vwap, 1)) * 100
    elif price < vwap_1sd_lower:
        return "VWAP_DISCOUNT_ZONE", ((vwap - price) / max(vwap, 1)) * 100
    return "VWAP_EQUILIBRIUM", 0.0


# ===================================================================
# CONDITION CATALOG - Every named market condition with its natural
# trade geometry. The trade comes FROM the condition, not invented.
# ===================================================================
CONDITION_CATALOG = {
    "TREND_BOS_PULLBACK": {
        "name": "Trend Breakout Structure Pullback",
        "literature": "Dalton AMT + Wyckoff Markup + ICT BOS/CHoCH",
        "when": "BOS displacement occurred. Price retesting fresh FVG left behind in trend direction.",
        "direction": "WITH_TREND",
        "entry_anchor": "NEAREST_FVG_CE_IN_TREND_DIRECTION",
        "stop_anchor": "BEYOND_FVG_BOUNDARY",
        "target_anchor": "NEXT_LIQUIDITY_POOL_IN_TREND",
    },
    "LIQUIDITY_SWEEP_REVERSAL": {
        "name": "Smart Money Liquidity Sweep Reversal",
        "literature": "ICT PD Arrays + Bouchaud LOB Absorption (2018)",
        "when": "Price sweeps Asian High/Low capturing retail stops, OFI immediately reverses direction.",
        "direction": "AGAINST_SWEEP",
        "entry_anchor": "FIRST_FVG_CE_INSIDE_RANGE_AFTER_SWEEP",
        "stop_anchor": "BEYOND_SWEEP_EXTREME",
        "target_anchor": "OPPOSITE_SESSION_BOUNDARY",
    },
    "FVG_MITIGATION_RETURN": {
        "name": "Fresh Institutional FVG Mitigation",
        "literature": "ICT FVG Anatomy + Dalton Market Profile imbalance fills",
        "when": "Price approaching a fresh unmitigated FVG (fill <30%). Institutional algo rebalance.",
        "direction": "CONTINUATION_FROM_FVG_ORIGIN",
        "entry_anchor": "FVG_50PCT_CE",
        "stop_anchor": "FVG_FULL_BOUNDARY_INVALIDATION",
        "target_anchor": "NEXT_STRUCTURE_OR_OPPOSITE_VA_LEVEL",
    },
    "VALUE_AREA_ROTATION_SHORT": {
        "name": "Dalton 80% Value Area Rotation Short",
        "literature": "Dalton Mind Over Markets (1990) - empirical 80% stat",
        "when": "Price above VAH. 2 consecutive M15 closes back inside Value Area. Rotate to opposite boundary.",
        "direction": "SHORT",
        "entry_anchor": "VAH_RETEST_FROM_ABOVE",
        "stop_anchor": "ABOVE_VAH_WICK_HIGH",
        "target_anchor": "VAL_OR_POC",
    },
    "VALUE_AREA_ROTATION_LONG": {
        "name": "Dalton 80% Value Area Rotation Long",
        "literature": "Dalton Mind Over Markets (1990) - empirical 80% stat",
        "when": "Price below VAL. 2 consecutive M15 closes back inside Value Area. Rotate to opposite boundary.",
        "direction": "LONG",
        "entry_anchor": "VAL_RETEST_FROM_BELOW",
        "stop_anchor": "BELOW_VAL_WICK_LOW",
        "target_anchor": "VAH_OR_POC",
    },
    "VWAP_2SD_MEAN_REVERSION_SHORT": {
        "name": "VWAP +2-Sigma Extreme Premium Reversal Short",
        "literature": "Harris 2003 + Berkowitz 1988 - 95% vol within +-2sd, ~68% revert",
        "when": "Price beyond VWAP +2sd with negative OFI. Statistical extreme. Revert to VWAP mid.",
        "direction": "SHORT",
        "entry_anchor": "CURRENT_PRICE_OR_NEAREST_FVG_CE",
        "stop_anchor": "ABOVE_VWAP_2SD_UPPER_PLUS_BUFFER",
        "target_anchor": "VWAP_MID",
    },
    "VWAP_2SD_MEAN_REVERSION_LONG": {
        "name": "VWAP -2-Sigma Extreme Discount Reversal Long",
        "literature": "Harris 2003 + Berkowitz 1988",
        "when": "Price beyond VWAP -2sd with positive OFI. Statistical extreme. Revert to VWAP mid.",
        "direction": "LONG",
        "entry_anchor": "CURRENT_PRICE_OR_NEAREST_FVG_CE",
        "stop_anchor": "BELOW_VWAP_2SD_LOWER_MINUS_BUFFER",
        "target_anchor": "VWAP_MID",
    },
    "WYCKOFF_SPRING_REVERSAL": {
        "name": "Wyckoff Accumulation Spring Long",
        "literature": "Wyckoff (1930), Pruden The Three Skills of Top Trading (2007)",
        "when": "Price briefly breaks below VAL (stops swept), fast OFI recovery. Classic Spring.",
        "direction": "LONG",
        "entry_anchor": "ABOVE_SPRING_LOW_ON_RECOVERY_CLOSE",
        "stop_anchor": "BELOW_SPRING_LOW",
        "target_anchor": "VAH_OR_OVERHEAD_RESISTANCE",
    },
    "WYCKOFF_UTAD_REVERSAL": {
        "name": "Wyckoff Distribution UTAD Short",
        "literature": "Wyckoff (1930), Pruden (2007)",
        "when": "Price briefly breaks above VAH (UTAD), strong negative OFI, no follow-through. Reversal.",
        "direction": "SHORT",
        "entry_anchor": "BELOW_UTAD_HIGH_ON_REJECTION_CLOSE",
        "stop_anchor": "ABOVE_UTAD_HIGH",
        "target_anchor": "VAL_OR_SUPPORT",
    },
    "COMPRESSION_BREAKOUT_LONG": {
        "name": "Volatility Compression Expansion Long",
        "literature": "Engle ARCH (1982) + Steidlmayer Normal Variation Day",
        "when": "Price coiling in tight range. Breaks above range high with velocity burst and volume expansion.",
        "direction": "LONG",
        "entry_anchor": "RETEST_OF_RANGE_HIGH_AS_SUPPORT",
        "stop_anchor": "BELOW_RANGE_HIGH",
        "target_anchor": "MEASURED_MOVE_EQUAL_TO_RANGE_WIDTH",
    },
    "COMPRESSION_BREAKOUT_SHORT": {
        "name": "Volatility Compression Expansion Short",
        "literature": "Engle ARCH (1982) + Steidlmayer Normal Variation Day",
        "when": "Price coiling in tight range. Breaks below range low with velocity burst and volume expansion.",
        "direction": "SHORT",
        "entry_anchor": "RETEST_OF_RANGE_LOW_AS_RESISTANCE",
        "stop_anchor": "ABOVE_RANGE_LOW",
        "target_anchor": "MEASURED_MOVE_DOWN_EQUAL_TO_RANGE_WIDTH",
    },
    "DEAD_ZONE_NO_CONDITION": {
        "name": "No Active Condition - Stand Flat",
        "literature": "Dalton AMT: No forced trades in No-Mans Land",
        "when": "Price inside mid Value Area, no fresh FVGs, no sweep, no Hurst signal, no structure event.",
        "direction": "FLAT",
        "entry_anchor": None,
        "stop_anchor": None,
        "target_anchor": None,
    },
}


class RegimeBrain:
    """
    Real quantitative market regime brain.
    5 research-backed layers classifying live market into ONE condition.
    """

    def __init__(self):
        self.catalog = CONDITION_CATALOG

    def classify(self, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        price = float(telemetry.get("live_price", 4376.0))
        vah = float(telemetry.get("vah", 4375.0))
        val = float(telemetry.get("val", 4368.0))
        poc = float(telemetry.get("poc", 4372.0))
        vwap = float(telemetry.get("vwap", price))
        vwap_1sd_upper = float(telemetry.get("vwap_1sd_upper", vwap + 5))
        vwap_1sd_lower = float(telemetry.get("vwap_1sd_lower", vwap - 5))
        vwap_2sd_upper = float(telemetry.get("vwap_2sd_upper", vwap + 10))
        vwap_2sd_lower = float(telemetry.get("vwap_2sd_lower", vwap - 10))
        cvd_10b = float(telemetry.get("cvd_10b", 0.0))
        cvd_cumulative = float(telemetry.get("cvd_cumulative", 0.0))
        velocity_tpm = float(telemetry.get("velocity_tpm", 80.0))
        displacement = bool(telemetry.get("displacement", False))
        choch = str(telemetry.get("choch", ""))
        mtf_alignment = str(telemetry.get("mtf_alignment", ""))
        h4_rsi = float(telemetry.get("h4_rsi", 50.0))
        nearest_fvg = telemetry.get("nearest_fvg", {})
        price_history = telemetry.get("price_history", [price] * 50)
        asian_high_swept = bool(telemetry.get("asian_high_swept", False))
        asian_low_swept = bool(telemetry.get("asian_low_swept", False))

        # LAYER 1: Hurst Exponent
        hurst = compute_hurst(price_history)
        is_trending = hurst > 0.55
        is_mean_reverting = hurst < 0.45

        # LAYER 2: OFI
        ofi = compute_ofi(cvd_10b, velocity_tpm, cvd_cumulative)
        strong_buy_ofi = ofi > 0.25
        strong_sell_ofi = ofi < -0.25

        # LAYER 3: Wyckoff
        wyckoff = detect_wyckoff_phase(price, vah, val, poc, cvd_10b, velocity_tpm, displacement, choch)

        # LAYER 4: AMT Day Type
        amt_day = classify_amt_day_type(price, vah, val, poc, vwap, vwap_2sd_upper, vwap_2sd_lower, mtf_alignment, h4_rsi)

        # LAYER 5: VWAP Deviation
        vwap_regime, vwap_dev_pct = classify_vwap_regime(price, vwap, vwap_1sd_upper, vwap_1sd_lower, vwap_2sd_upper, vwap_2sd_lower)

        # FVG signals
        fvg_type = str(nearest_fvg.get("type", "")).upper()
        fvg_ce = float(nearest_fvg.get("consequent_encroachment", 0.0) or 0.0)
        fvg_fill = float(nearest_fvg.get("fill_pct", 100.0) or 100.0)
        fvg_fresh = fvg_fill < 30.0 and fvg_ce > 0
        fvg_above = fvg_ce > price
        fvg_below = 0 < fvg_ce < price

        # ===== CONDITION RESOLUTION — Priority Order =====
        # Rule: The condition fires when its defining market signature is present.
        # We only block a trade when CONFLICTING evidence is overwhelming, not just absent.
        cid = None

        # 1. VWAP ±2σ EXTREME — Statistical extreme. Hurst mean-reverting = confirm.
        #    At extreme, even neutral OFI is enough; we only block if OFI strongly disagrees.
        if vwap_regime == "VWAP_EXTREME_PREMIUM_SELL" and is_mean_reverting and not strong_buy_ofi:
            cid = "VWAP_2SD_MEAN_REVERSION_SHORT"
        elif vwap_regime == "VWAP_EXTREME_DISCOUNT_BUY" and is_mean_reverting and not strong_sell_ofi:
            cid = "VWAP_2SD_MEAN_REVERSION_LONG"

        # 2. WYCKOFF SPRING — False low + fast OFI recovery (stops swept below VAL)
        elif wyckoff == "WYCKOFF_ACCUMULATION_SPRING":
            cid = "WYCKOFF_SPRING_REVERSAL"

        # 3. WYCKOFF UTAD — False high + OFI reversal (stops swept above VAH)
        elif wyckoff == "WYCKOFF_DISTRIBUTION_UTAD":
            cid = "WYCKOFF_UTAD_REVERSAL"

        # 4. TREND BOS PULLBACK — Displacement happened, FVG printed, price retesting it
        elif displacement and fvg_fresh and is_trending:
            cid = "TREND_BOS_PULLBACK"

        # 5. FRESH FVG MITIGATION — Price approaching the 50% CE of fresh FVG
        elif fvg_fresh and abs(price - fvg_ce) <= 8.0:
            cid = "FVG_MITIGATION_RETURN"

        # 6. VALUE AREA ROTATION — Dalton 80% Rule. Price outside VA + Hurst mean-reverting
        elif price > vah and is_mean_reverting and not strong_buy_ofi:
            cid = "VALUE_AREA_ROTATION_SHORT"
        elif price < val and is_mean_reverting and not strong_sell_ofi:
            cid = "VALUE_AREA_ROTATION_LONG"

        # 7. LIQUIDITY SWEEP REVERSAL — Asian session high/low taken + FVG inside range
        elif asian_high_swept and (strong_sell_ofi or cvd_10b < -100) and fvg_fresh:
            cid = "LIQUIDITY_SWEEP_REVERSAL"
        elif asian_low_swept and (strong_buy_ofi or cvd_10b > 100) and fvg_fresh:
            cid = "LIQUIDITY_SWEEP_REVERSAL"

        # 8. COMPRESSION BREAKOUT — Velocity burst + displacement + outside range
        elif displacement and velocity_tpm > 140 and price > vah:
            cid = "COMPRESSION_BREAKOUT_LONG"
        elif displacement and velocity_tpm > 140 and price < val:
            cid = "COMPRESSION_BREAKOUT_SHORT"

        # DEAD ZONE — No condition signature present. No trade.
        else:
            cid = "DEAD_ZONE_NO_CONDITION"


        meta = self.catalog.get(cid, self.catalog["DEAD_ZONE_NO_CONDITION"])

        return {
            "condition_id": cid,
            "condition_name": meta["name"],
            "literature": meta["literature"],
            "when_description": meta["when"],
            "direction": meta["direction"],
            "entry_anchor": meta["entry_anchor"],
            "stop_anchor": meta["stop_anchor"],
            "target_anchor": meta["target_anchor"],
            "brain_layers": {
                "hurst": round(hurst, 3),
                "hurst_regime": "TRENDING" if is_trending else ("MEAN_REVERTING" if is_mean_reverting else "RANDOM_WALK"),
                "ofi": round(ofi, 3),
                "ofi_signal": "BUY_PRESSURE" if ofi > 0.15 else ("SELL_PRESSURE" if ofi < -0.15 else "NEUTRAL"),
                "wyckoff_phase": wyckoff,
                "amt_day_type": amt_day,
                "vwap_regime": vwap_regime,
                "vwap_deviation_pct": round(vwap_dev_pct, 3),
            },
        }
