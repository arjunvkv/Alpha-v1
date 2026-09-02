# -*- coding: utf-8 -*-
# nng/microstructure.py - Market Microstructure Analytics
#
# Sources:
#   Kyle (1985) - Continuous Auctions and Insider Trading - lambda price impact
#   Amihud (2002) - Illiquidity and Stock Returns - illiquidity ratio
#   Roll (1984) - A Simple Implicit Measure of the Effective Bid-Ask Spread
#   Lee & Ready (1991) - Inferring Trade Direction from Intraday Data - tick rule
#   Bouchaud et al. (2018) - Trades, Quotes and Prices - comprehensive LOB text

import math
import numpy as np
from typing import List, Dict, Any, Tuple


def kyle_lambda(price_changes: List[float], signed_volumes: List[float]) -> float:
    """
    Kyle Lambda: price impact coefficient. Kyle (1985).
    lambda = cov(dP, Q) / var(Q)
    Higher lambda = more illiquid, each trade moves price more.
    Returns lambda in price-pts per unit volume.
    """
    if len(price_changes) < 3 or len(signed_volumes) < 3:
        return 0.0
    dp = np.array(price_changes, dtype=float)
    q = np.array(signed_volumes, dtype=float)
    var_q = np.var(q)
    if var_q < 1e-10:
        return 0.0
    cov_dp_q = np.cov(dp, q)[0, 1]
    lam = cov_dp_q / var_q
    return float(lam)


def amihud_illiquidity(abs_returns: List[float], dollar_volumes: List[float]) -> Tuple[float, str]:
    """
    Amihud Illiquidity Ratio (2002).
    ILLIQ = mean(|R_t| / VOL_t)
    Returns (ratio, regime_label).
    Regime: LOW_ILLIQ (liquid), MEDIUM_ILLIQ, HIGH_ILLIQ (illiquid = large impact).
    """
    if not abs_returns or not dollar_volumes:
        return 0.0, "UNKNOWN"
    ratios = []
    for r, v in zip(abs_returns, dollar_volumes):
        if v > 0:
            ratios.append(abs(r) / v)
    if not ratios:
        return 0.0, "UNKNOWN"
    illiq = float(np.mean(ratios))
    # Regime thresholds (calibrated for intraday gold futures)
    if illiq < 1e-6:
        regime = "LOW_ILLIQ_LIQUID"
    elif illiq < 5e-6:
        regime = "MEDIUM_ILLIQ"
    else:
        regime = "HIGH_ILLIQ_IMPACT"
    return illiq, regime


def roll_spread(price_series: List[float]) -> float:
    """
    Roll Implicit Spread Estimator (1984).
    Spread = 2 * sqrt(-cov(dP_t, dP_{t+1}))
    Negative cov assumed (bid-ask bounce). If cov >= 0, returns 0.
    """
    if len(price_series) < 4:
        return 0.0
    prices = np.array(price_series, dtype=float)
    dp = np.diff(prices)
    if len(dp) < 2:
        return 0.0
    cov = float(np.cov(dp[:-1], dp[1:])[0, 1])
    if cov >= 0:
        return 0.0  # Invalid: price trending rather than bouncing
    return float(2.0 * math.sqrt(-cov))


def tick_rule_direction(price_series: List[float]) -> Tuple[str, float]:
    """
    Lee & Ready (1991) Tick Rule.
    Classify each tick: uptick (+1), downtick (-1), zero-tick (carry forward).
    Returns (direction_signal, net_buy_fraction in [-1, +1]).
    """
    if len(price_series) < 2:
        return "NEUTRAL", 0.0
    signs = []
    last_nonzero = 0
    for i in range(1, len(price_series)):
        diff = price_series[i] - price_series[i - 1]
        if diff > 0:
            last_nonzero = 1
        elif diff < 0:
            last_nonzero = -1
        signs.append(last_nonzero)
    if not signs:
        return "NEUTRAL", 0.0
    net = float(np.mean(signs))
    if net > 0.2:
        direction = "BUY_DOMINATED"
    elif net < -0.2:
        direction = "SELL_DOMINATED"
    else:
        direction = "BALANCED"
    return direction, net


def microstructure_regime(
    cvd_10b: float,
    velocity_tpm: float,
    live_spread_pts: float,
    price_history: List[float]
) -> Dict[str, Any]:
    """
    Full microstructure regime summary from available MCP data.
    """
    # Approximate signed volumes from CVD
    n = len(price_history)
    signed_vols = [cvd_10b / max(n, 1)] * n
    price_changes = [price_history[i] - price_history[i-1] for i in range(1, n)]

    lam = kyle_lambda(price_changes, signed_vols[1:])
    tick_dir, tick_net = tick_rule_direction(price_history)

    # Approximate Amihud from velocity (higher velocity ~ lower illiquidity)
    illiq_proxy = 1.0 / max(velocity_tpm, 1.0)
    illiq_regime = "LOW_ILLIQ_LIQUID" if velocity_tpm > 100 else ("MEDIUM_ILLIQ" if velocity_tpm > 40 else "HIGH_ILLIQ_IMPACT")

    roll_s = roll_spread(price_history[-20:]) if len(price_history) >= 4 else live_spread_pts

    # Informed flow signal: high lambda + directional tick rule = informed trader active
    lambda_spike = abs(lam) > 0.01
    informed_flow = lambda_spike and (tick_dir != "BALANCED")

    return {
        "kyle_lambda": round(lam, 6),
        "lambda_spike": lambda_spike,
        "roll_spread_pts": round(roll_s, 3),
        "live_spread_pts": live_spread_pts,
        "tick_rule_direction": tick_dir,
        "tick_net": round(tick_net, 3),
        "amihud_regime": illiq_regime,
        "informed_flow_detected": informed_flow,
        "microstructure_regime": "INFORMED_FLOW" if informed_flow else ("HIGH_IMPACT" if illiq_regime == "HIGH_ILLIQ_IMPACT" else "NORMAL"),
    }
