# -*- coding: utf-8 -*-
# nng/intermarket.py - Intermarket and COT Analysis
#
# Sources:
#   Murphy, J.J. (1999) - Intermarket Analysis
#   Briese, S. (2008) - The Commitments of Traders Bible
#   CFTC COT Report - Weekly positioning data
#   Gold/DXY negative correlation: empirically established 1973-present

from typing import Dict, Any, List, Tuple


def cot_index(current_net: float, net_history: List[float]) -> float:
    """
    COT Index (Briese 2008).
    COT Index = (current_net - min_net) / (max_net - min_net) * 100
    0 = most bearish positioning ever, 100 = most bullish.
    Extremes (>90 or <10) = contrarian signal.
    """
    if not net_history or len(net_history) < 2:
        return 50.0
    min_n = min(net_history)
    max_n = max(net_history)
    if max_n == min_n:
        return 50.0
    return round((current_net - min_n) / (max_n - min_n) * 100, 1)


def cot_regime(
    commercial_net: float,
    large_spec_net: float,
    commercial_net_history: List[float],
) -> Dict[str, Any]:
    """
    COT Regime Classification. Briese (2008).
    Commercials are the smart money (producers/consumers hedging).
    When commercials are at extreme net long = price likely to rise.
    When commercials are at extreme net short = price likely to fall.
    Large Specs are the trend followers (often wrong at extremes).
    """
    idx = cot_index(commercial_net, commercial_net_history)
    large_spec_opposing = (large_spec_net > 0 and commercial_net < 0) or (large_spec_net < 0 and commercial_net > 0)

    if idx > 90:
        regime = "COT_EXTREME_BULLISH_SETUP"
        signal = "LONG"
    elif idx > 75:
        regime = "COT_BULLISH_POSITIONING"
        signal = "LONG_BIAS"
    elif idx < 10:
        regime = "COT_EXTREME_BEARISH_SETUP"
        signal = "SHORT"
    elif idx < 25:
        regime = "COT_BEARISH_POSITIONING"
        signal = "SHORT_BIAS"
    else:
        regime = "COT_NEUTRAL"
        signal = "NEUTRAL"

    return {
        "cot_index": idx,
        "commercial_net": commercial_net,
        "large_spec_net": large_spec_net,
        "large_spec_opposing_commercials": large_spec_opposing,
        "cot_regime": regime,
        "cot_signal": signal,
        "contrarian_signal_active": idx > 90 or idx < 10,
    }


def dxy_correlation_bias(
    dxy_direction: str,
    symbol: str = "XAUUSD"
) -> str:
    """
    Intermarket directional bias from DXY. Murphy (1999).
    Gold (XAUUSD): historically strong negative correlation with DXY (-0.8 to -0.95).
    DXY UP = Gold bearish bias. DXY DOWN = Gold bullish bias.
    """
    gold_symbols = ["XAUUSD", "GOLD", "GC"]
    if any(s in symbol.upper() for s in gold_symbols):
        if dxy_direction == "UP":
            return "BEARISH_BIAS_DXY_CORRELATION"
        elif dxy_direction == "DOWN":
            return "BULLISH_BIAS_DXY_CORRELATION"
    return "NO_CORRELATION_SIGNAL"


def real_yields_bias(tips_yield: float, tips_yield_change: float) -> str:
    """
    Real Yields (TIPS) impact on Gold.
    Rising real yields = opportunity cost of holding gold rises = bearish gold.
    Falling real yields = bullish gold.
    Source: WGC research + academic consensus.
    """
    if tips_yield_change > 0.05:
        return "BEARISH_RISING_REAL_YIELDS"
    elif tips_yield_change < -0.05:
        return "BULLISH_FALLING_REAL_YIELDS"
    return "NEUTRAL_REAL_YIELDS"


def intermarket_bias(
    cot_signal: str,
    dxy_bias: str,
    real_yields_bias_signal: str,
) -> Dict[str, Any]:
    """
    Combine all intermarket signals into a net directional bias.
    """
    bull_signals = sum([
        1 if "BULLISH" in cot_signal or "LONG" in cot_signal else 0,
        1 if "BULLISH" in dxy_bias else 0,
        1 if "BULLISH" in real_yields_bias_signal else 0,
    ])
    bear_signals = sum([
        1 if "BEARISH" in cot_signal or "SHORT" in cot_signal else 0,
        1 if "BEARISH" in dxy_bias else 0,
        1 if "BEARISH" in real_yields_bias_signal else 0,
    ])
    if bull_signals >= 2:
        net_bias = "MACRO_BULLISH"
    elif bear_signals >= 2:
        net_bias = "MACRO_BEARISH"
    else:
        net_bias = "MACRO_NEUTRAL"
    return {
        "bull_signals": bull_signals,
        "bear_signals": bear_signals,
        "net_macro_bias": net_bias,
        "cot_signal": cot_signal,
        "dxy_bias": dxy_bias,
        "real_yields_bias": real_yields_bias_signal,
    }
