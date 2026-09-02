# -*- coding: utf-8 -*-
# nng/volatility_regime.py - Multi-Estimator Volatility with Regime Classification
#
# Sources:
#   Garman & Klass (1980) - On the Estimation of Security Price Volatilities
#   Parkinson (1980) - The Extreme Value Method for Estimating the Variance of the Rate of Return
#   Andersen, Bollerslev, Diebold (2001) - The Distribution of Realized Exchange Rate Volatility
#   Rogers & Satchell (1991) - Estimating Variance from High, Low, and Closing Prices
#   Engle (1982) - ARCH

import math
import numpy as np
from typing import List, Tuple, Dict, Any


def garman_klass_vol(highs: List[float], lows: List[float],
                     opens: List[float], closes: List[float]) -> float:
    """
    Garman-Klass Volatility (1980).
    sigma = sqrt(mean(0.5*(ln(H/L))^2 - (2*ln2-1)*(ln(C/O))^2))
    More efficient than close-to-close (uses full OHLC).
    """
    if len(highs) < 2:
        return 0.0
    factor = 2 * math.log(2) - 1  # ~0.386
    terms = []
    for h, l, o, c in zip(highs, lows, opens, closes):
        if h <= 0 or l <= 0 or o <= 0 or c <= 0 or l >= h:
            continue
        hl_term = 0.5 * (math.log(h / l)) ** 2
        co_term = factor * (math.log(c / o)) ** 2
        terms.append(hl_term - co_term)
    if not terms:
        return 0.0
    return float(math.sqrt(max(np.mean(terms), 0.0)))


def parkinson_vol(highs: List[float], lows: List[float]) -> float:
    """
    Parkinson Volatility Estimator (1980).
    sigma = sqrt(1/(4*n*ln2) * sum((ln(H/L))^2))
    Uses only high/low — efficient estimator for range-bounded processes.
    """
    if len(highs) < 2:
        return 0.0
    factor = 4.0 * math.log(2)
    terms = []
    for h, l in zip(highs, lows):
        if h <= 0 or l <= 0 or l >= h:
            continue
        terms.append((math.log(h / l)) ** 2)
    if not terms:
        return 0.0
    return float(math.sqrt(np.mean(terms) / factor))


def realized_volatility(returns: List[float]) -> float:
    """
    Realized Volatility (Andersen, Bollerslev, Diebold 2001).
    RV = sqrt(sum(r_i^2)) over intraday returns.
    More accurate for high-frequency data than GARCH-based estimates.
    """
    if len(returns) < 2:
        return 0.0
    r = np.array(returns, dtype=float)
    return float(math.sqrt(np.sum(r ** 2)))


def volatility_regime(
    current_vol: float,
    vol_history: List[float],
    n_percentile: int = 20
) -> Tuple[str, float, float]:
    """
    Volatility Regime Classification using Z-score and percentile rank.
    Returns (regime, z_score, percentile).
    Regimes: EXTREME_LOW, LOW, NORMAL, HIGH, EXTREME_HIGH
    """
    if len(vol_history) < 5:
        return "NORMAL", 0.0, 50.0
    hist = np.array(vol_history, dtype=float)
    mean_v = float(np.mean(hist))
    std_v = float(np.std(hist))
    z = (current_vol - mean_v) / max(std_v, 1e-10)
    # Percentile rank
    pct = float(np.sum(hist <= current_vol) / len(hist) * 100)
    if z > 2.0:
        regime = "EXTREME_HIGH_VOL"
    elif z > 0.75:
        regime = "HIGH_VOL_EXPANSION"
    elif z < -1.5:
        regime = "EXTREME_LOW_VOL_COMPRESSION"
    elif z < -0.5:
        regime = "LOW_VOL_COILING"
    else:
        regime = "NORMAL_VOL"
    return regime, round(z, 3), round(pct, 1)


def atr_regime(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Tuple[float, str]:
    """
    ATR-based volatility regime. Wilder (1978).
    Returns (current_atr, regime).
    """
    if len(highs) < period + 1:
        return 0.0, "UNKNOWN"
    trs = []
    for i in range(1, len(highs)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        trs.append(tr)
    if len(trs) < period:
        return float(np.mean(trs)) if trs else 0.0, "UNKNOWN"
    # Smoothed ATR (Wilder's method)
    atr = float(np.mean(trs[-period:]))
    # Compare to longer history
    if len(trs) >= period * 2:
        long_atr = float(np.mean(trs[-(period*2):-period]))
        ratio = atr / max(long_atr, 1e-10)
        if ratio > 1.5:
            regime = "ATR_EXPANDING"
        elif ratio < 0.65:
            regime = "ATR_CONTRACTING"
        else:
            regime = "ATR_NORMAL"
    else:
        regime = "ATR_NORMAL"
    return round(atr, 3), regime


def full_volatility_analysis(
    price_history: List[float],
    high_low_pairs: List[Tuple[float, float]] = None,
) -> Dict[str, Any]:
    """
    Full volatility analysis from available price data.
    Returns comprehensive vol regime assessment.
    """
    prices = np.array(price_history, dtype=float)
    returns = np.diff(np.log(prices + 1e-10)).tolist()

    if high_low_pairs and len(high_low_pairs) >= 2:
        highs = [p[0] for p in high_low_pairs]
        lows = [p[1] for p in high_low_pairs]
        opens = [lows[i] + (highs[i] - lows[i]) * 0.3 for i in range(len(highs))]
        closes = [lows[i] + (highs[i] - lows[i]) * 0.6 for i in range(len(highs))]
        gk_vol = garman_klass_vol(highs, lows, opens, closes)
        park_vol = parkinson_vol(highs, lows)
        atr_val, atr_reg = atr_regime(highs, lows, closes)
    else:
        # Approximate from price history using rolling window
        n = len(prices)
        window = min(14, n // 2)
        if window >= 2:
            approx_highs = [float(np.max(prices[max(0,i-window):i+1])) for i in range(window, n)]
            approx_lows = [float(np.min(prices[max(0,i-window):i+1])) for i in range(window, n)]
            gk_vol = parkinson_vol(approx_highs, approx_lows) if approx_highs else 0.0
            park_vol = gk_vol
            atr_val = float(np.mean([h - l for h, l in zip(approx_highs[-14:], approx_lows[-14:])])) if approx_highs else 0.0
            atr_reg = "ATR_NORMAL"
        else:
            gk_vol = park_vol = atr_val = 0.0
            atr_reg = "UNKNOWN"

    rv = realized_volatility(returns[-20:]) if len(returns) >= 5 else 0.0

    primary_vol = gk_vol if gk_vol > 0 else park_vol
    vol_history_approx = [primary_vol * (0.8 + 0.4 * abs(r)) for r in returns[-20:]] if returns else [primary_vol]
    reg, z, pct = volatility_regime(primary_vol, vol_history_approx)

    return {
        "garman_klass_vol": round(gk_vol, 6),
        "parkinson_vol": round(park_vol, 6),
        "realized_vol": round(rv, 6),
        "atr": atr_val,
        "atr_regime": atr_reg,
        "vol_regime": reg,
        "vol_z_score": z,
        "vol_percentile": pct,
        "is_expanding": reg in ("EXTREME_HIGH_VOL", "HIGH_VOL_EXPANSION", "ATR_EXPANDING"),
        "is_compressing": reg in ("EXTREME_LOW_VOL_COMPRESSION", "LOW_VOL_COILING"),
    }
