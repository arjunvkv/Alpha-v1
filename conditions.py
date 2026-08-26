"""
Alpha Condition DSL Evaluator (alpha/conditions.py)

C-compiled TA-Lib indicator evaluation and generic condition logic engine.
Supports price levels, TA-Lib indicators, spread floors, time decay,
Live Macro News events, Cross-Asset surges, Indicator crossovers, and Regime shifts.
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import talib
    import numpy as np
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False


KNOWN_CONDITION_TYPES = {
    "price_above", "price_below", "price_cross_above", "price_cross_below",
    "indicator_state", "spread_below", "time_elapsed_sec", "bars_passed",
    "macro_event_near", "cross_asset_surge", "indicator_crossover", "regime_change"
}


@dataclass
class EvalContext:
    symbol: str = ""
    tick: Dict[str, Any] = field(default_factory=dict)
    prev_tick: Optional[Dict[str, Any]] = None
    bars: List[Dict[str, Any]] = field(default_factory=list)
    daily_bars: List[Dict[str, Any]] = field(default_factory=list)
    snapshot: Dict[str, Any] = field(default_factory=dict)
    account: Dict[str, Any] = field(default_factory=dict)
    positions: List[Dict[str, Any]] = field(default_factory=list)
    now_utc: Optional[datetime] = None
    point_size: float = 0.01
    rule_direction: str = "any"


@dataclass
class EvalResult:
    fired: bool
    detail: str = ""


def _num(value: Any) -> Optional[float]:
    try:
        v = float(value)
        return None if math.isnan(v) or math.isinf(v) else v
    except (TypeError, ValueError):
        return None


def evaluate_condition(cond: Dict[str, Any], ctx: EvalContext) -> EvalResult:
    ctype = cond.get("type", "")
    if ctype == "price_above":
        return _eval_price_above(cond, ctx)
    elif ctype == "price_below":
        return _eval_price_below(cond, ctx)
    elif ctype == "price_cross_above":
        return _eval_price_cross_above(cond, ctx)
    elif ctype == "price_cross_below":
        return _eval_price_cross_below(cond, ctx)
    elif ctype == "indicator_state":
        return _eval_indicator_state(cond, ctx)
    elif ctype == "spread_below":
        return _eval_spread_below(cond, ctx)
    elif ctype == "time_elapsed_sec":
        return _eval_time_elapsed(cond, ctx)
    elif ctype == "macro_event_near":
        return _eval_macro_event_near(cond, ctx)
    elif ctype == "cross_asset_surge":
        return _eval_cross_asset_surge(cond, ctx)
    elif ctype == "indicator_crossover":
        return _eval_indicator_crossover(cond, ctx)
    elif ctype == "regime_change":
        return _eval_regime_change(cond, ctx)
    else:
        return EvalResult(False, f"unknown condition type '{ctype}'")


# --- Price Level Evaluators ---

def _eval_price_above(cond: Dict[str, Any], ctx: EvalContext) -> EvalResult:
    target = _num(cond.get("level"))
    if target is None:
        return EvalResult(False, "missing target level")
    last = _num(ctx.tick.get("last")) or _num(ctx.tick.get("bid"))
    if last is None:
        return EvalResult(False, "no tick price available")
    fired = last >= target
    return EvalResult(fired, f"last={last} >= target={target}")


def _eval_price_below(cond: Dict[str, Any], ctx: EvalContext) -> EvalResult:
    target = _num(cond.get("level"))
    if target is None:
        return EvalResult(False, "missing target level")
    last = _num(ctx.tick.get("last")) or _num(ctx.tick.get("ask"))
    if last is None:
        return EvalResult(False, "no tick price available")
    fired = last <= target
    return EvalResult(fired, f"last={last} <= target={target}")


def _eval_price_cross_above(cond: Dict[str, Any], ctx: EvalContext) -> EvalResult:
    target = _num(cond.get("level"))
    if target is None:
        return EvalResult(False, "missing target level")
    if not ctx.prev_tick:
        return EvalResult(False, "no prev_tick for cross detection")
    prev_last = _num(ctx.prev_tick.get("last")) or _num(ctx.prev_tick.get("bid"))
    curr_last = _num(ctx.tick.get("last")) or _num(ctx.tick.get("bid"))
    if prev_last is None or curr_last is None:
        return EvalResult(False, "incomplete tick data")
    fired = prev_last < target and curr_last >= target
    return EvalResult(fired, f"prev={prev_last} < target={target} <= curr={curr_last}")


def _eval_price_cross_below(cond: Dict[str, Any], ctx: EvalContext) -> EvalResult:
    target = _num(cond.get("level"))
    if target is None:
        return EvalResult(False, "missing target level")
    if not ctx.prev_tick:
        return EvalResult(False, "no prev_tick for cross detection")
    prev_last = _num(ctx.prev_tick.get("last")) or _num(ctx.prev_tick.get("ask"))
    curr_last = _num(ctx.tick.get("last")) or _num(ctx.tick.get("ask"))
    if prev_last is None or curr_last is None:
        return EvalResult(False, "incomplete tick data")
    fired = prev_last > target and curr_last <= target
    return EvalResult(fired, f"prev={prev_last} > target={target} >= curr={curr_last}")


# --- TA-Lib Indicator Evaluator ---

def _eval_indicator_state(cond: Dict[str, Any], ctx: EvalContext) -> EvalResult:
    name = str(cond.get("name", "")).lower()
    op = str(cond.get("op", ">"))
    val = _num(cond.get("value", 0.0))
    params = cond.get("params", {})

    if not ctx.bars or len(ctx.bars) < 15:
        return EvalResult(False, "insufficient bar data for TA-Lib")

    closes = np.array([float(b.get("close", 0.0)) for b in ctx.bars], dtype=np.float64)

    calc_val = None
    if name == "rsi":
        period = int(params.get("period", 14))
        if len(closes) >= period + 1 and TALIB_AVAILABLE:
            res = talib.RSI(closes, period)
            calc_val = res[-1] if not np.isnan(res[-1]) else None
    elif name == "ema":
        period = int(params.get("period", 20))
        if len(closes) >= period and TALIB_AVAILABLE:
            res = talib.EMA(closes, period)
            calc_val = res[-1] if not np.isnan(res[-1]) else None
    elif name == "atr":
        period = int(params.get("period", 14))
        highs = np.array([float(b.get("high", 0.0)) for b in ctx.bars], dtype=np.float64)
        lows = np.array([float(b.get("low", 0.0)) for b in ctx.bars], dtype=np.float64)
        if len(closes) >= period + 1 and TALIB_AVAILABLE:
            res = talib.ATR(highs, lows, closes, period)
            calc_val = res[-1] if not np.isnan(res[-1]) else None

    if calc_val is None:
        return EvalResult(False, f"could not compute indicator '{name}'")

    if op == ">":
        fired = calc_val > val
    elif op == "<":
        fired = calc_val < val
    elif op == ">=":
        fired = calc_val >= val
    elif op == "<=":
        fired = calc_val <= val
    else:
        fired = False

    return EvalResult(fired, f"{name}={calc_val:.2f} {op} {val}")


# --- Spread & Time Evaluators ---

def _eval_spread_below(cond: Dict[str, Any], ctx: EvalContext) -> EvalResult:
    max_pts = _num(cond.get("max_spread_points", 50.0))
    bid = _num(ctx.tick.get("bid"))
    ask = _num(ctx.tick.get("ask"))
    if bid is None or ask is None or ctx.point_size <= 0:
        return EvalResult(False, "missing tick bid/ask")
    spread_pts = (ask - bid) / ctx.point_size
    fired = spread_pts <= max_pts
    return EvalResult(fired, f"spread={spread_pts:.1f}pts <= max={max_pts}pts")


def _eval_time_elapsed(cond: Dict[str, Any], ctx: EvalContext) -> EvalResult:
    target_sec = _num(cond.get("seconds", 3600.0))
    start_ts = _num(cond.get("start_timestamp"))
    now_ts = ctx.now_utc.timestamp() if ctx.now_utc else datetime.now(timezone.utc).timestamp()
    if start_ts is None:
        return EvalResult(False, "missing start_timestamp")
    elapsed = now_ts - start_ts
    fired = elapsed >= target_sec
    return EvalResult(fired, f"elapsed={elapsed:.0f}s >= target={target_sec}s")


# --- NEW: Live Macro Event Evaluator ---

def _eval_macro_event_near(cond: Dict[str, Any], ctx: EvalContext) -> EvalResult:
    target_impact = str(cond.get("impact", "HIGH")).upper()
    mins_before = _num(cond.get("minutes_before", 15.0)) or 15.0

    macro_data = ctx.snapshot.get("layers", {}).get("macro", {}).get("data", {})
    events = macro_data.get("upcoming_events", [])
    now_ts = ctx.now_utc.timestamp() if ctx.now_utc else datetime.now(timezone.utc).timestamp()

    for ev in events:
        impact = str(ev.get("impact", "")).upper()
        ev_ts = _num(ev.get("timestamp"))
        if impact == target_impact and ev_ts is not None:
            time_until_sec = ev_ts - now_ts
            if 0 <= time_until_sec <= (mins_before * 60.0):
                return EvalResult(True, f"EVENT ALERT: {ev.get('title')} ({impact}) in {time_until_sec/60:.1f} mins")

    return EvalResult(False, "no upcoming high-impact events within window")


# --- NEW: Cross-Asset Surge Evaluator ---

def _eval_cross_asset_surge(cond: Dict[str, Any], ctx: EvalContext) -> EvalResult:
    target_asset = str(cond.get("asset", "DXY")).upper()
    target_pct = _num(cond.get("pct_change_5m", 0.3)) or 0.3

    signals = ctx.snapshot.get("layers", {}).get("signals", {}).get("data", {})
    surges = signals.get("asset_surges_5m", {})
    actual_surge = _num(surges.get(target_asset, 0.0)) or 0.0

    fired = abs(actual_surge) >= target_pct
    return EvalResult(fired, f"CROSS-ASSET SURGE [{target_asset}]: {actual_surge:+.2f}% vs threshold {target_pct:.2f}%")


# --- NEW: Indicator Crossover Evaluator ---

def _eval_indicator_crossover(cond: Dict[str, Any], ctx: EvalContext) -> EvalResult:
    fast_period = int(cond.get("fast_period", 9))
    slow_period = int(cond.get("slow_period", 21))
    direction = str(cond.get("direction", "cross_above")).lower()

    if not ctx.bars or len(ctx.bars) < slow_period + 2 or not TALIB_AVAILABLE:
        return EvalResult(False, "insufficient bar data for crossover")

    closes = np.array([float(b.get("close", 0.0)) for b in ctx.bars], dtype=np.float64)
    fast_ema = talib.EMA(closes, fast_period)
    slow_ema = talib.EMA(closes, slow_period)

    prev_diff = fast_ema[-2] - slow_ema[-2]
    curr_diff = fast_ema[-1] - slow_ema[-1]

    if direction in ("cross_above", "bullish"):
        fired = prev_diff < 0 and curr_diff >= 0
    else:
        fired = prev_diff > 0 and curr_diff <= 0

    return EvalResult(fired, f"EMA({fast_period}/{slow_period}) {direction}: prev_diff={prev_diff:.2f}, curr_diff={curr_diff:.2f}")


# --- NEW: Macro Regime Change Evaluator ---

def _eval_regime_change(cond: Dict[str, Any], ctx: EvalContext) -> EvalResult:
    target_regime = str(cond.get("regime", "")).lower()

    signals = ctx.snapshot.get("layers", {}).get("signals", {}).get("data", {})
    current_regime = str(signals.get("macro_regime", {}).get("composite", "mixed")).lower()

    if target_regime:
        fired = current_regime == target_regime
    else:
        prev_regime = str(signals.get("macro_regime", {}).get("previous_composite", "")).lower()
        fired = bool(prev_regime and current_regime != prev_regime)

    return EvalResult(fired, f"REGIME ALERT: current='{current_regime}' (target='{target_regime}')")
