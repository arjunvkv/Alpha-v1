# -*- coding: utf-8 -*-
# nng/momentum_analytics.py - Multi-Timeframe Momentum Analytics
#
# Sources:
#   Moskowitz, Ooi & Pedersen (2012) - Time Series Momentum, JFE
#   Jegadeesh & Titman (1993) - Returns to Buying Winners and Selling Losers, JF
#   Elder (1995) - Trading for a Living - divergence concepts
#   Wilder (1978) - New Concepts in Technical Trading Systems - RSI
#   Appel (1979) - MACD indicator

import numpy as np
from typing import List, Dict, Any, Optional, Tuple


def tsmom_signal(prices: List[float], lookback: int = 20) -> Tuple[str, float]:
    """
    Time Series Momentum (Moskowitz, Ooi, Pedersen 2012).
    Signal = sign(return over lookback period).
    Intraday adaptation: lookback in bars (5-min bars recommended).
    Returns (signal, normalized_return).
    """
    if len(prices) < lookback + 1:
        return "NEUTRAL", 0.0
    past_return = (prices[-1] - prices[-lookback]) / max(prices[-lookback], 1e-10)
    vol = float(np.std(np.diff(prices[-lookback:]) / np.array(prices[-lookback:-1]) + 1e-10))
    vol_scaled_return = past_return / max(vol, 1e-10)
    if vol_scaled_return > 0.5:
        signal = "TSMOM_LONG"
    elif vol_scaled_return < -0.5:
        signal = "TSMOM_SHORT"
    else:
        signal = "TSMOM_NEUTRAL"
    return signal, round(vol_scaled_return, 3)


def compute_rsi(prices: List[float], period: int = 14) -> float:
    """
    Wilder RSI (1978). Standard implementation.
    """
    if len(prices) < period + 1:
        return 50.0
    deltas = np.diff(prices[-period-1:])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = float(np.mean(gains))
    avg_loss = float(np.mean(losses))
    if avg_loss < 1e-10:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - 100.0 / (1.0 + rs))


def detect_rsi_divergence(
    prices: List[float],
    rsi_values: List[float],
    lookback: int = 10
) -> Dict[str, Any]:
    """
    RSI Divergence Detector. Elder (1995).
    Regular Bearish Divergence: price makes higher high, RSI makes lower high = exhaustion (SHORT signal)
    Regular Bullish Divergence: price makes lower low, RSI makes higher low = exhaustion (LONG signal)
    Hidden Bullish Divergence: price makes higher low, RSI makes lower low = continuation LONG
    Hidden Bearish Divergence: price makes lower high, RSI makes higher high = continuation SHORT
    """
    result = {
        "regular_bearish": False,
        "regular_bullish": False,
        "hidden_bullish": False,
        "hidden_bearish": False,
        "divergence_type": "NONE",
    }
    n = min(lookback, len(prices), len(rsi_values))
    if n < 4:
        return result

    p = prices[-n:]
    r = rsi_values[-n:]
    mid = n // 2

    price_first_half_high = max(p[:mid])
    price_second_half_high = max(p[mid:])
    price_first_half_low = min(p[:mid])
    price_second_half_low = min(p[mid:])
    rsi_first_half_high = max(r[:mid])
    rsi_second_half_high = max(r[mid:])
    rsi_first_half_low = min(r[:mid])
    rsi_second_half_low = min(r[mid:])

    # Regular Bearish: price HH, RSI LH
    if price_second_half_high > price_first_half_high and rsi_second_half_high < rsi_first_half_high:
        result["regular_bearish"] = True
        result["divergence_type"] = "REGULAR_BEARISH"
    # Regular Bullish: price LL, RSI HL
    elif price_second_half_low < price_first_half_low and rsi_second_half_low > rsi_first_half_low:
        result["regular_bullish"] = True
        result["divergence_type"] = "REGULAR_BULLISH"
    # Hidden Bullish: price HL (higher low), RSI LL (lower low) = continuation up
    elif price_second_half_low > price_first_half_low and rsi_second_half_low < rsi_first_half_low:
        result["hidden_bullish"] = True
        result["divergence_type"] = "HIDDEN_BULLISH_CONTINUATION"
    # Hidden Bearish: price LH (lower high), RSI HH (higher high) = continuation down
    elif price_second_half_high < price_first_half_high and rsi_second_half_high > rsi_first_half_high:
        result["hidden_bearish"] = True
        result["divergence_type"] = "HIDDEN_BEARISH_CONTINUATION"

    return result


def ema(prices: List[float], period: int) -> float:
    """Exponential Moving Average."""
    if not prices:
        return 0.0
    k = 2.0 / (period + 1)
    result = prices[0]
    for p in prices[1:]:
        result = p * k + result * (1 - k)
    return float(result)


def macd_histogram_regime(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, Any]:
    """
    MACD Histogram Regime. Appel (1979).
    Expanding histogram = momentum acceleration (with trend)
    Contracting histogram = momentum loss (potential reversal warning)
    """
    if len(prices) < slow + signal:
        return {"macd_histogram": 0.0, "macd_regime": "INSUFFICIENT_DATA"}
    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)
    macd_line = ema_fast - ema_slow
    # Signal line: EMA of last N MACD values (approximated)
    macd_values = []
    for i in range(slow, len(prices)):
        ef = ema(prices[:i], fast)
        es = ema(prices[:i], slow)
        macd_values.append(ef - es)
    if len(macd_values) < signal:
        return {"macd_histogram": 0.0, "macd_regime": "INSUFFICIENT_DATA"}
    signal_line = ema(macd_values, signal)
    histogram = macd_line - signal_line
    # Regime based on histogram trend
    recent_hist = macd_values[-5:] if len(macd_values) >= 5 else macd_values
    hist_trend = recent_hist[-1] - recent_hist[0] if len(recent_hist) >= 2 else 0.0
    if histogram > 0 and hist_trend > 0:
        regime = "MACD_BULLISH_ACCELERATING"
    elif histogram > 0 and hist_trend < 0:
        regime = "MACD_BULLISH_DECELERATING"
    elif histogram < 0 and hist_trend < 0:
        regime = "MACD_BEARISH_ACCELERATING"
    elif histogram < 0 and hist_trend > 0:
        regime = "MACD_BEARISH_DECELERATING"
    else:
        regime = "MACD_NEUTRAL"
    return {
        "macd_line": round(macd_line, 4),
        "signal_line": round(signal_line, 4),
        "macd_histogram": round(histogram, 4),
        "macd_regime": regime,
    }


def ema_cross_state(
    m5_ema20: float, m5_ema50: float,
    m15_ema20: float, m15_ema50: float,
    h1_ema20: float, h1_ema50: float,
    h4_ema20: float, h4_ema50: float,
) -> Dict[str, Any]:
    """
    EMA Cross State across 4 timeframes.
    When all 4 TFs have EMA20 > EMA50 = FULL_BULL_ALIGNMENT.
    """
    states = {
        "m5": "BULL" if m5_ema20 > m5_ema50 else "BEAR",
        "m15": "BULL" if m15_ema20 > m15_ema50 else "BEAR",
        "h1": "BULL" if h1_ema20 > h1_ema50 else "BEAR",
        "h4": "BULL" if h4_ema20 > h4_ema50 else "BEAR",
    }
    bull_count = sum(1 for v in states.values() if v == "BULL")
    if bull_count == 4:
        alignment = "FULL_BULL_4TF"
    elif bull_count == 3:
        alignment = "BULL_LEANING_3TF"
    elif bull_count == 1:
        alignment = "BEAR_LEANING_3TF"
    elif bull_count == 0:
        alignment = "FULL_BEAR_4TF"
    else:
        alignment = "MIXED_2TF"
    return {"ema_states": states, "ema_alignment": alignment, "bull_tf_count": bull_count}


def full_momentum_analysis(
    price_history: List[float],
    rsi_m15: float = 50.0,
    rsi_h1: float = 50.0,
    rsi_h4: float = 50.0,
    m5_ema20: float = 0.0, m5_ema50: float = 0.0,
    m15_ema20: float = 0.0, m15_ema50: float = 0.0,
    h1_ema20: float = 0.0, h1_ema50: float = 0.0,
    h4_ema20: float = 0.0, h4_ema50: float = 0.0,
) -> Dict[str, Any]:
    prices = price_history
    tsmom_sig, tsmom_norm = tsmom_signal(prices, lookback=min(20, len(prices)//2))
    rsi_now = compute_rsi(prices[-15:]) if len(prices) >= 15 else rsi_m15
    rsi_hist = [rsi_m15, rsi_h1, rsi_h4]  # simplified: use passed RSI values
    rsi_approx_series = [rsi_m15 - i * 2 for i in range(len(prices))][::-1]
    div = detect_rsi_divergence(prices, rsi_approx_series[-min(10, len(prices)):])
    macd = macd_histogram_regime(prices)
    ema_state = ema_cross_state(m5_ema20, m5_ema50, m15_ema20, m15_ema50, h1_ema20, h1_ema50, h4_ema20, h4_ema50)
    return {
        "tsmom_signal": tsmom_sig,
        "tsmom_normalized_return": tsmom_norm,
        "rsi_current": round(rsi_now, 1),
        "rsi_overbought": rsi_now > 70,
        "rsi_oversold": rsi_now < 30,
        "divergence": div,
        "macd": macd,
        "ema_alignment": ema_state,
    }
