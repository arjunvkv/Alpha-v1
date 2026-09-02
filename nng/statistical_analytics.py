# -*- coding: utf-8 -*-
# nng/statistical_analytics.py - Pure Statistical Regime Signals
#
# Sources:
#   Z-score price deviation: standard statistical analysis
#   Ornstein-Uhlenbeck half-life: Avellaneda & Lee (2010), Chan (2013)
#   Percentile rank: non-parametric regime detection

import math
import numpy as np
from typing import List, Tuple, Dict, Any


def price_zscore(price: float, price_history: List[float], window: int = 20) -> Tuple[float, str]:
    """
    Z-score of current price vs rolling window. Standard statistics.
    Returns (z_score, regime_label).
    """
    if len(price_history) < window:
        return 0.0, "NEUTRAL"
    hist = np.array(price_history[-window:], dtype=float)
    mean = float(np.mean(hist))
    std = float(np.std(hist))
    if std < 1e-10:
        return 0.0, "NEUTRAL"
    z = (price - mean) / std
    if z > 2.0:
        regime = "STATISTICALLY_EXTREME_HIGH"
    elif z > 1.0:
        regime = "STATISTICALLY_ELEVATED"
    elif z < -2.0:
        regime = "STATISTICALLY_EXTREME_LOW"
    elif z < -1.0:
        regime = "STATISTICALLY_DEPRESSED"
    else:
        regime = "STATISTICALLY_NEUTRAL"
    return round(z, 3), regime


def volume_zscore(current_velocity: float, velocity_history: List[float], window: int = 20) -> Tuple[float, str]:
    """
    Volume Z-score: current velocity vs rolling mean.
    >2σ = institutional activity (Andersen, Bollerslev 1998).
    """
    if len(velocity_history) < 3:
        return 0.0, "NORMAL_VOLUME"
    hist = np.array(velocity_history[-window:], dtype=float)
    mean = float(np.mean(hist))
    std = float(np.std(hist))
    if std < 1e-10:
        return 0.0, "NORMAL_VOLUME"
    z = (current_velocity - mean) / std
    if z > 2.0:
        regime = "INSTITUTIONAL_VOLUME_SPIKE"
    elif z > 1.0:
        regime = "ELEVATED_VOLUME"
    elif z < -1.0:
        regime = "LOW_VOLUME"
    else:
        regime = "NORMAL_VOLUME"
    return round(z, 3), regime


def ou_halflife(price_series: List[float]) -> float:
    """
    Ornstein-Uhlenbeck Half-Life of Mean Reversion.
    Chan (2013) Algorithmic Trading: regrass y(t) on y(t-1).
    Half-life = -ln(2) / ln(1 + lambda_coef)
    Fast half-life (<5 bars) = strong mean reversion regime.
    """
    if len(price_series) < 10:
        return float('inf')
    y = np.array(price_series, dtype=float)
    y_lag = y[:-1]
    y_curr = y[1:]
    # OLS: dy = lambda * y_lag + mu
    try:
        X = np.column_stack([y_lag, np.ones(len(y_lag))])
        coefs = np.linalg.lstsq(X, y_curr, rcond=None)[0]
        lam = coefs[0] - 1  # lambda = beta - 1
        if lam >= 0 or lam <= -1:
            return float('inf')
        halflife = -math.log(2) / math.log(1 + lam)
        return round(halflife, 2)
    except Exception:
        return float('inf')


def percentile_rank(current_value: float, history: List[float]) -> float:
    """
    Percentile rank of current value in history.
    100 = all-time high in window, 0 = all-time low.
    """
    if not history:
        return 50.0
    return float(np.sum(np.array(history) <= current_value) / len(history) * 100)


def statistical_analysis(
    price: float,
    price_history: List[float],
    velocity_tpm: float,
    velocity_history: List[float] = None,
) -> Dict[str, Any]:
    """Full statistical regime analysis."""
    p_z, p_regime = price_zscore(price, price_history)
    v_history = velocity_history or [velocity_tpm] * 10
    v_z, v_regime = volume_zscore(velocity_tpm, v_history)
    halflife = ou_halflife(price_history[-30:] if len(price_history) >= 10 else price_history)
    p_pct = percentile_rank(price, price_history)

    statistical_extreme = abs(p_z) > 2.0
    institutional_volume = v_z > 1.5
    fast_mean_reversion = halflife < 8 and halflife > 0

    return {
        "price_zscore": p_z,
        "price_regime": p_regime,
        "volume_zscore": v_z,
        "volume_regime": v_regime,
        "ou_halflife_bars": halflife,
        "price_percentile": round(p_pct, 1),
        "statistical_extreme": statistical_extreme,
        "institutional_volume": institutional_volume,
        "fast_mean_reversion": fast_mean_reversion,
        "statistical_long_signal": p_z < -2.0 and institutional_volume,
        "statistical_short_signal": p_z > 2.0 and institutional_volume,
    }
