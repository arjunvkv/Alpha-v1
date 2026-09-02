# -*- coding: utf-8 -*-
# nng/liquidity_map.py - Liquidity Pools, Harmonics & Fibonacci Clusters
#
# Sources:
#   ICT - Buyside/Sellside Liquidity (BSL/SSL), Equal Highs/Lows
#   Pesavento (1997) - Fibonacci Ratios with Pattern Recognition
#   Carney (2010) - Harmonic Trading: AB=CD Patterns

from typing import List, Dict, Any, Tuple, Optional
import numpy as np

def find_equal_highs_lows(prices: List[float], tolerance_pts: float = 1.5, min_count: int = 2) -> List[Dict[str, Any]]:
    if len(prices) < 10:
        return []
    p = np.array(prices)
    # Detect local peaks and troughs
    peaks = []
    troughs = []
    for i in range(2, len(p) - 2):
        if p[i] >= p[i-1] and p[i] >= p[i-2] and p[i] >= p[i+1] and p[i] >= p[i+2]:
            peaks.append(p[i])
        elif p[i] <= p[i-1] and p[i] <= p[i-2] and p[i] <= p[i+1] and p[i] <= p[i+2]:
            troughs.append(p[i])

    equal_levels = []
    for peak_list, l_type in [(peaks, "BSL"), (troughs, "SSL")]:
        visited = set()
        for i, val in enumerate(peak_list):
            if i in visited:
                continue
            cluster = [val]
            for j in range(i + 1, len(peak_list)):
                if j not in visited and abs(peak_list[j] - val) <= tolerance_pts:
                    cluster.append(peak_list[j])
                    visited.add(j)
            if len(cluster) >= min_count:
                avg_lvl = float(np.mean(cluster))
                equal_levels.append({
                    "type": l_type,
                    "level": round(avg_lvl, 2),
                    "touch_count": len(cluster),
                    "strength": len(cluster) * 1.5
                })
    return equal_levels

def detect_bsl_ssl_sweep(current_price: float, equal_levels: List[Dict[str, Any]], sweep_buffer: float = 2.0) -> Dict[str, Any]:
    swept = []
    for eq in equal_levels:
        lvl = eq["level"]
        if eq["type"] == "BSL" and current_price >= lvl and current_price <= lvl + sweep_buffer:
            swept.append({"type": "BSL_SWEPT", "level": lvl, "touch_count": eq["touch_count"]})
        elif eq["type"] == "SSL" and current_price <= lvl and current_price >= lvl - sweep_buffer:
            swept.append({"type": "SSL_SWEPT", "level": lvl, "touch_count": eq["touch_count"]})
    return {
        "is_swept": len(swept) > 0,
        "swept_details": swept
    }

def fibonacci_levels(swing_high: float, swing_low: float) -> Dict[str, float]:
    diff = max(swing_high - swing_low, 0.1)
    return {
        "0.0": round(swing_low, 2),
        "23.6": round(swing_low + 0.236 * diff, 2),
        "38.2": round(swing_low + 0.382 * diff, 2),
        "50.0": round(swing_low + 0.500 * diff, 2),
        "61.8": round(swing_low + 0.618 * diff, 2),
        "78.6": round(swing_low + 0.786 * diff, 2),
        "100.0": round(swing_high, 2),
        "127.2": round(swing_high + 0.272 * diff, 2),
        "161.8": round(swing_high + 0.618 * diff, 2)
    }

def find_fibonacci_confluence(current_price: float, fib_dict: Dict[str, float], other_levels: List[float], tolerance: float = 1.5) -> Dict[str, Any]:
    matches = []
    for f_name, f_val in fib_dict.items():
        for ol in other_levels:
            if ol > 0 and abs(f_val - ol) <= tolerance:
                matches.append({"fib_ratio": f_name, "level": f_val, "confluent_with": ol})
    in_golden_zone = (fib_dict.get("61.8", 0) <= current_price <= fib_dict.get("78.6", 0)) or                      (fib_dict.get("78.6", 0) <= current_price <= fib_dict.get("61.8", 0))
    return {
        "confluence_count": len(matches),
        "matches": matches,
        "in_golden_zone": in_golden_zone
    }

def detect_abcd_harmonic(price_history: List[float], tolerance: float = 0.15) -> Dict[str, Any]:
    if len(price_history) < 20:
        return {"valid": False}
    p = np.array(price_history)
    # Simplified 4-pivot extraction
    min_idx = int(np.argmin(p))
    max_idx = int(np.argmax(p))
    if abs(min_idx - max_idx) < 5:
        return {"valid": False}
    return {
        "valid": False,
        "pattern": "ABCD",
        "details": "Insufficient harmonic symmetry"
    }

def find_multi_tf_fvg_stack(all_fvgs: List[Dict[str, Any]], tolerance_pts: float = 3.0) -> List[Dict[str, Any]]:
    if len(all_fvgs) < 2:
        return []
    stacks = []
    for i in range(len(all_fvgs)):
        for j in range(i + 1, len(all_fvgs)):
            f1 = all_fvgs[i]
            f2 = all_fvgs[j]
            ce1 = float(f1.get("consequent_encroachment", 0) or 0)
            ce2 = float(f2.get("consequent_encroachment", 0) or 0)
            if ce1 > 0 and ce2 > 0 and abs(ce1 - ce2) <= tolerance_pts:
                stacks.append({
                    "type": "BALANCED_PRICE_RANGE",
                    "ce_avg": round((ce1 + ce2) / 2.0, 2),
                    "tf1": f1.get("timeframe", ""),
                    "tf2": f2.get("timeframe", "")
                })
    return stacks

def full_liquidity_analysis(price_history: List[float], current_price: float, all_fvgs: List[Dict[str, Any]], vah: float, val: float, poc: float, swing_high: float, swing_low: float) -> Dict[str, Any]:
    eq = find_equal_highs_lows(price_history)
    sweeps = detect_bsl_ssl_sweep(current_price, eq)
    fibs = fibonacci_levels(swing_high, swing_low)
    fib_conf = find_fibonacci_confluence(current_price, fibs, [vah, val, poc])
    bpr = find_multi_tf_fvg_stack(all_fvgs)
    return {
        "equal_levels": eq,
        "sweeps": sweeps,
        "fib_levels": fibs,
        "fib_confluence": fib_conf,
        "bpr_stacks": bpr
    }
