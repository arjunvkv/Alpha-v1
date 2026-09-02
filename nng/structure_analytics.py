# -*- coding: utf-8 -*-
# nng/structure_analytics.py - Advanced Market Structure Analysis
#
# Sources:
#   Huddleston ICT - Order Blocks, Breaker Blocks, PD Arrays, BPR
#   Williams, B. (1995) - Trading Chaos - fractal structure
#   Schwager, J. (1984) - A Complete Guide to the Futures Market - swing analysis

import numpy as np
from typing import List, Dict, Any, Tuple, Optional


def detect_swing_structure(prices: List[float], window: int = 5) -> Dict[str, Any]:
    """
    Swing High/Low detection and HH/HL/LH/LL classification.
    Used for full structural market state mapping.
    """
    if len(prices) < window * 2 + 1:
        return {"swing_highs": [], "swing_lows": [], "structure": "INSUFFICIENT_DATA"}

    swing_highs = []
    swing_lows = []
    for i in range(window, len(prices) - window):
        if all(prices[i] >= prices[j] for j in range(i - window, i + window + 1) if j != i):
            swing_highs.append((i, prices[i]))
        if all(prices[i] <= prices[j] for j in range(i - window, i + window + 1) if j != i):
            swing_lows.append((i, prices[i]))

    # Determine HH/HL/LH/LL
    structure = "RANGING"
    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        higher_highs = swing_highs[-1][1] > swing_highs[-2][1]
        higher_lows = swing_lows[-1][1] > swing_lows[-2][1]
        if higher_highs and higher_lows:
            structure = "UPTREND_HH_HL"
        elif not higher_highs and not higher_lows:
            structure = "DOWNTREND_LH_LL"
        elif higher_lows and not higher_highs:
            structure = "POTENTIAL_UPTREND_HL_LH"
        elif higher_highs and not higher_lows:
            structure = "POTENTIAL_DOWNTREND_HH_LL"

    last_sh = swing_highs[-1][1] if swing_highs else 0.0
    last_sl = swing_lows[-1][1] if swing_lows else 0.0

    return {
        "swing_highs": [(i, round(p, 3)) for i, p in swing_highs[-3:]],
        "swing_lows": [(i, round(p, 3)) for i, p in swing_lows[-3:]],
        "last_swing_high": round(last_sh, 3),
        "last_swing_low": round(last_sl, 3),
        "structure": structure,
    }


def count_pdarray_confluence(
    price: float,
    vah: float, val: float, poc: float,
    fvg_ce: float, fvg_type: str,
    tolerance_pts: float = 3.0
) -> Dict[str, Any]:
    """
    PDArray Stack Counter. ICT concept.
    Counts how many institutional reference levels are within tolerance_pts of price.
    Stack of 3+ = highest-probability trade zone.
    """
    levels = {
        "VAH": vah,
        "VAL": val,
        "POC": poc,
        "FVG_CE": fvg_ce if fvg_ce > 0 else None,
    }
    nearby = []
    for name, lvl in levels.items():
        if lvl and abs(price - lvl) <= tolerance_pts:
            nearby.append(name)

    stack_count = len(nearby)
    is_high_confluence = stack_count >= 2
    bias = "NONE"
    if is_high_confluence:
        avg_lvl = np.mean([levels[n] for n in nearby if levels[n]])
        bias = "LONG" if price < avg_lvl else "SHORT"

    return {
        "nearby_levels": nearby,
        "confluence_count": stack_count,
        "is_high_confluence": is_high_confluence,
        "confluence_bias": bias,
    }


def is_narrow_range(prices: List[float], n: int = 7) -> bool:
    """
    NR7 - Narrowest Range in N bars (Toby Crabel 1990).
    When current range is smallest of last N bars = volatility coil.
    """
    if len(prices) < n:
        return False
    ranges = []
    for i in range(1, n + 1):
        if i < len(prices):
            ranges.append(abs(prices[-i] - prices[-i-1]) if i < len(prices) else 0)
    if not ranges:
        return False
    current_range = abs(prices[-1] - prices[-2]) if len(prices) >= 2 else 0
    return current_range <= min(ranges)


def structure_analysis(
    price_history: List[float],
    price: float,
    vah: float, val: float, poc: float,
    fvg_ce: float = 0.0,
    fvg_type: str = "",
    fvg_fill: float = 100.0,
) -> Dict[str, Any]:
    """Full structure analysis."""
    swing = detect_swing_structure(price_history)
    confluence = count_pdarray_confluence(price, vah, val, poc, fvg_ce if fvg_fill < 30 else 0.0, fvg_type)
    nr7 = is_narrow_range(price_history)
    fvg_fresh = fvg_fill < 30.0 and fvg_ce > 0

    return {
        "swing_structure": swing,
        "market_trend": swing.get("structure", "RANGING"),
        "pdarray_confluence": confluence,
        "nr7_coil": nr7,
        "fvg_fresh": fvg_fresh,
        "last_swing_high": swing.get("last_swing_high", price + 8),
        "last_swing_low": swing.get("last_swing_low", price - 8),
    }
