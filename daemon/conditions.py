"""Daemon v2 generic condition DSL evaluator (DAEMON_V2_SPEC.md section 4).

Pure stdlib. Zero MetaTrader5 references. Every evaluator returns a
ConditionResult(fired, detail) and never raises on malformed input.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


KNOWN_CONDITION_TYPES = {
    "price_cross_above", "price_cross_below",
    "price_above", "price_below",
    "daily_close_beyond", "volume_expansion", "retest_hold",
    "indicator_state", "snapshot_field", "time_window", "spread_below",
    "position_exists", "pnl_pct_below", "pnl_pct_above", "price_reached",
}


@dataclass
class ConditionResult:
    fired: bool = False
    detail: str = ""


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
    now_utc: Any = None
    point_size: float = 0.01
    rule_direction: str = "any"


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _last_price(tick):
    px = _num(tick.get("last"))
    if px is not None:
        return px
    bid, ask = _num(tick.get("bid")), _num(tick.get("ask"))
    if bid is not None and ask is not None:
        return (bid + ask) / 2.0
    return bid if bid is not None else ask


def _bar_closes(bars):
    """All bar closes as floats, or None if any close is missing/bad."""
    out: List[float] = []
    for bar in bars:
        close = _num(bar.get("close"))
        if close is None:
            return None
        out.append(close)
    return out


# ------------------------------------------------------------- indicators ----

import numpy as np
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False


def compute_ema(closes, period):
    """Compute EMA via TA-Lib with fallback."""
    if not closes:
        return []
    if HAS_TALIB:
        arr = np.asarray(closes, dtype=np.float64)
        res = talib.EMA(arr, timeperiod=period)
        out = []
        for i, val in enumerate(res):
            if np.isnan(val):
                out.append(float(closes[0]) if i == 0 else out[-1])
            else:
                out.append(float(val))
        return out

    # Fallback EMA
    k = 2.0 / (period + 1.0)
    out = [float(closes[0])]
    for px in closes[1:]:
        out.append(px * k + out[-1] * (1.0 - k))
    return out


def compute_rsi(closes, period=14):
    """Compute RSI via TA-Lib with fallback."""
    n = len(closes)
    if n <= period:
        return [None] * n
    if HAS_TALIB:
        arr = np.asarray(closes, dtype=np.float64)
        res = talib.RSI(arr, timeperiod=period)
        return [float(val) if not np.isnan(val) else None for val in res]

    # Fallback RSI
    out: List[Optional[float]] = [None] * n
    gains, losses = [], []
    for i in range(1, n):
        chg = closes[i] - closes[i - 1]
        gains.append(max(chg, 0.0))
        losses.append(max(-chg, 0.0))
    for i in range(period, n):
        win_g = gains[i - period:i]
        win_l = losses[i - period:i]
        ag = sum(win_g) / period
        al = sum(win_l) / period
        if al == 0:
            out[i] = 100.0
        else:
            rs = ag / al
            out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out


def compute_macd(closes, fast=12, slow=26, signal=9):
    """Compute MACD via TA-Lib with fallback."""
    if HAS_TALIB and len(closes) >= (slow + signal - 1):
        arr = np.asarray(closes, dtype=np.float64)
        macd_line, signal_line, _ = talib.MACD(arr, fastperiod=fast, slowperiod=slow, signalperiod=signal)
        m_out = [float(val) if not np.isnan(val) else 0.0 for val in macd_line]
        s_out = [float(val) if not np.isnan(val) else 0.0 for val in signal_line]
        return m_out, s_out

    # Fallback MACD
    e_fast = compute_ema(closes, fast)
    e_slow = compute_ema(closes, slow)
    macd_line = [f - s for f, s in zip(e_fast, e_slow)]
    signal_line = compute_ema(macd_line, signal)
    return macd_line, signal_line


def _compare(op, left, right):
    try:
        if op == ">":
            return left > right
        if op == "<":
            return left < right
        if op == ">=":
            return left >= right
        if op == "<=":
            return left <= right
        if op in ("=", "=="):
            return left == right
    except TypeError:
        return False
    return False


# ------------------------------------------------------------ evaluators -----

def _price_above(cond, ctx):
    level = _num(cond.get("level"))
    if level is None:
        return ConditionResult(False, "missing level")
    px = _last_price(ctx.tick)
    if px is None:
        return ConditionResult(False, "no price")
    return ConditionResult(px > level, "last %s > %s" % (px, level))


def _price_below(cond, ctx):
    level = _num(cond.get("level"))
    if level is None:
        return ConditionResult(False, "missing level")
    px = _last_price(ctx.tick)
    if px is None:
        return ConditionResult(False, "no price")
    return ConditionResult(px < level, "last %s < %s" % (px, level))


def _cross(cond, ctx, upward):
    level = _num(cond.get("level"))
    if level is None:
        return ConditionResult(False, "missing level")
    if ctx.prev_tick is None:
        return ConditionResult(False, "no previous tick")
    prev_px, cur_px = _last_price(ctx.prev_tick), _last_price(ctx.tick)
    if prev_px is None or cur_px is None:
        return ConditionResult(False, "no price")
    if upward:
        fired = prev_px <= level < cur_px
    else:
        fired = prev_px >= level > cur_px
    return ConditionResult(fired, "%s -> %s vs %s" % (prev_px, cur_px, level))


def _price_cross_above(cond, ctx):
    return _cross(cond, ctx, upward=True)


def _price_cross_below(cond, ctx):
    return _cross(cond, ctx, upward=False)


def _daily_close_beyond(cond, ctx):
    level = _num(cond.get("level"))
    direction = cond.get("direction")
    if level is None or direction not in ("above", "below"):
        return ConditionResult(False, "need level + direction above|below")
    if not ctx.daily_bars:
        return ConditionResult(False, "no_daily_bars")
    close = _num(ctx.daily_bars[-1].get("close"))
    if close is None:
        return ConditionResult(False, "no_daily_bars")
    if direction == "above":
        return ConditionResult(close > level, "daily close %s > %s" % (close, level))
    return ConditionResult(close < level, "daily close %s < %s" % (close, level))


def _volume_expansion(cond, ctx):
    min_ratio = _num(cond.get("min_ratio")) or 1.5
    bars = ctx.bars
    if len(bars) < 21:
        return ConditionResult(False, "insufficient bars (%d)" % len(bars))
    vols = [_num(b.get("volume")) or 0.0 for b in bars]
    base = sum(vols[:-1][-20:]) / 20.0
    if base <= 0:
        return ConditionResult(False, "insufficient volume history")
    ratio = vols[-1] / base
    return ConditionResult(ratio >= min_ratio,
                           "ratio %.2f vs %.2f" % (ratio, min_ratio))


def _retest_hold(cond, ctx):
    level = _num(cond.get("level"))
    tol = _num(cond.get("tolerance_pct"))
    hold_n = int(_num(cond.get("bars")) or 0)
    if level is None or tol is None or hold_n <= 0:
        return ConditionResult(False, "need level, tolerance_pct, bars")
    closes = _bar_closes(ctx.bars)
    if closes is None or len(closes) < hold_n + 1:
        return ConditionResult(False, "insufficient bars (%d)" % len(ctx.bars))
    band = level * tol / 100.0
    window = closes[-hold_n:]
    if any(abs(c - level) > band for c in window):
        return ConditionResult(False, "hold window broke band")
    prior = closes[:-hold_n]
    if not any(abs(c - level) > band for c in prior):
        return ConditionResult(False, "no prior close outside band")
    return ConditionResult(True, "held %d bars within %.2f%% of %s"
                           % (hold_n, tol, level))


def _indicator_state(cond, ctx):
    name = str(cond.get("name", "")).lower()
    if name not in ("rsi", "macd", "ema"):
        return ConditionResult(False, "unsupported indicator '%s'" % name)
    closes = [_num(b.get("close")) for b in ctx.bars]
    if any(c is None for c in closes):
        return ConditionResult(False, "insufficient bars")
    params = cond.get("params") or {}
    op = cond.get("op", ">")
    value = cond.get("value")
    if name == "rsi":
        period = int(_num(params.get("period")) or 14)
        if len(closes) <= period:
            return ConditionResult(False, "insufficient bars (%d)" % len(closes))
        series = compute_rsi(closes, period)
        thr = _num(value)
        if thr is None:
            return ConditionResult(False, "missing value")
        if op == "cross_up":
            prev, cur = series[-2], series[-1]
            if prev is None or cur is None:
                return ConditionResult(False, "insufficient bars")
            return ConditionResult(prev <= thr < cur,
                                   "rsi %s -> %s vs %s" % (prev, cur, thr))
        cur = series[-1]
        if cur is None:
            return ConditionResult(False, "insufficient bars")
        return ConditionResult(_compare(op, cur, thr),
                               "rsi %s %s %s" % (cur, op, thr))
    if name == "ema":
        period = int(_num(params.get("period")) or 20)
        if len(closes) < period:
            return ConditionResult(False, "insufficient bars (%d)" % len(closes))
        series = compute_ema(closes, period)
        thr = _num(value)
        if thr is None:
            return ConditionResult(False, "missing value")
        cur = series[-1]
        if op == "cross_up":
            prev = series[-2] if len(series) > 1 else None
            if prev is None:
                return ConditionResult(False, "insufficient bars")
            return ConditionResult(prev <= thr < cur,
                                   "ema %s -> %s vs %s" % (prev, cur, thr))
        return ConditionResult(_compare(op, cur, thr),
                               "ema %s %s %s" % (cur, op, thr))
    # macd
    if len(closes) < 2:
        return ConditionResult(False, "insufficient bars")
    macd_line, signal_line = compute_macd(closes)
    cur, sig_prev = macd_line[-1], signal_line[-2]
    sig = signal_line[-1]
    if op == "cross_up":
        thr = _num(value)
        if thr is not None:
            prev = macd_line[-2]
            fired = prev <= thr < cur
            return ConditionResult(fired, "macd %s -> %s vs %s"
                                   % (prev, cur, thr))
        fired = macd_line[-2] <= sig_prev and cur > sig
        return ConditionResult(fired, "macd %s vs signal %s" % (cur, sig))
    thr = _num(value)
    if thr is None:
        thr = 0.0
    return ConditionResult(_compare(op, cur, thr),
                           "macd %s %s %s" % (cur, op, thr))


def _walk(snapshot, dotted):
    node = snapshot
    for part in dotted.split("."):
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return None
    return node


def _snapshot_field(cond, ctx):
    path = cond.get("path")
    if not path:
        return ConditionResult(False, "missing path")
    value = _walk(ctx.snapshot, path)
    if value is None:
        return ConditionResult(False, "missing path '%s'" % path)
    op = cond.get("op", "=")
    target = cond.get("value")
    if op == "in":
        if isinstance(value, (list, tuple, set)):
            return ConditionResult(target in value,
                                   "'%s' in %s" % (target, list(value)))
        return ConditionResult(False, "field not a collection")
    if isinstance(target, str):
        return ConditionResult(_compare(op, str(value), target),
                               "%r %s %r" % (value, op, target))
    num = _num(value)
    tgt = _num(target)
    if num is None or tgt is None:
        return ConditionResult(_compare(op, value, target),
                               "%r %s %r" % (value, op, target))
    return ConditionResult(_compare(op, num, tgt),
                           "%s %s %s" % (num, op, tgt))


def _parse_hhmm(text):
    parts = str(text).split(":")
    if len(parts) != 2:
        return None
    hh, mm = _num(parts[0]), _num(parts[1])
    if hh is None or mm is None:
        return None
    return int(hh) * 60 + int(mm)


def _time_window(cond, ctx):
    start = _parse_hhmm(cond.get("start_utc"))
    end = _parse_hhmm(cond.get("end_utc"))
    if start is None or end is None or ctx.now_utc is None:
        return ConditionResult(False, "need start_utc/end_utc + now")
    cur = ctx.now_utc.hour * 60 + ctx.now_utc.minute
    if start <= end:
        fired = start <= cur < end
    else:
        fired = cur >= start or cur < end
    return ConditionResult(fired, "utc minute %d in [%d,%d)" % (cur, start, end))


def _spread_below(cond, ctx):
    max_points = _num(cond.get("max_points"))
    bid, ask = _num(ctx.tick.get("bid")), _num(ctx.tick.get("ask"))
    if max_points is None or bid is None or ask is None or ctx.point_size <= 0:
        return ConditionResult(False, "need max_points + bid/ask + point_size")
    points = (ask - bid) / ctx.point_size
    return ConditionResult(points <= max_points,
                           "spread %.1f pts vs max %.1f"
                           % (points, max_points))


def _matching_positions(ctx, symbol=None, direction=None):
    out = []
    for p in ctx.positions:
        if symbol is not None and p.get("symbol") != symbol:
            continue
        if direction is not None and p.get("direction") != direction:
            continue
        out.append(p)
    return out


def _position_exists(cond, ctx):
    sym = cond.get("symbol")
    direction = cond.get("direction")
    matches = _matching_positions(ctx, symbol=sym, direction=direction)
    return ConditionResult(bool(matches),
                           "%d matching positions" % len(matches))


def _pnl_pct(cond, ctx, want_above):
    bound = _num(cond.get("value"))
    if bound is None:
        return ConditionResult(False, "missing value")
    direction = ctx.rule_direction if ctx.rule_direction != "any" else None
    positions = _matching_positions(ctx, symbol=ctx.symbol or None,
                                    direction=direction)
    if not positions:
        return ConditionResult(False, "no open positions for rule side")
    best = None
    for p in positions:
        entry, cur = _num(p.get("entry")), _num(p.get("current"))
        if entry in (None, 0.0) or cur is None:
            continue
        move_pct = (cur - entry) / entry * 100.0
        if p.get("direction") == "short":
            move_pct = -move_pct
        best = move_pct if best is None else max(best, move_pct)
    if best is None:
        return ConditionResult(False, "positions lack entry/current")
    if want_above:
        return ConditionResult(best >= bound,
                               "pnl pct %.2f >= %s" % (best, bound))
    return ConditionResult(best <= bound,
                           "pnl pct %.2f <= %s" % (best, bound))


def _pnl_pct_below(cond, ctx):
    return _pnl_pct(cond, ctx, want_above=False)


def _pnl_pct_above(cond, ctx):
    return _pnl_pct(cond, ctx, want_above=True)


def _price_reached(cond, ctx):
    level = _num(cond.get("level"))
    if level is None:
        return ConditionResult(False, "missing level")
    px = _last_price(ctx.tick)
    if px is None:
        return ConditionResult(False, "no price")
    if ctx.rule_direction == "short":
        return ConditionResult(px <= level, "last %s <= %s (short)" % (px, level))
    return ConditionResult(px >= level, "last %s >= %s (long)" % (px, level))


_EVALUATORS = {
    "price_above": _price_above,
    "price_below": _price_below,
    "price_cross_above": _price_cross_above,
    "price_cross_below": _price_cross_below,
    "daily_close_beyond": _daily_close_beyond,
    "volume_expansion": _volume_expansion,
    "retest_hold": _retest_hold,
    "indicator_state": _indicator_state,
    "snapshot_field": _snapshot_field,
    "time_window": _time_window,
    "spread_below": _spread_below,
    "position_exists": _position_exists,
    "pnl_pct_below": _pnl_pct_below,
    "pnl_pct_above": _pnl_pct_above,
    "price_reached": _price_reached,
}


def evaluate_condition(cond, ctx):
    """Evaluate one condition dict against an EvalContext. Never raises."""
    if not isinstance(cond, dict):
        return ConditionResult(False, "condition must be a dict")
    ctype = cond.get("type")
    if not isinstance(ctype, str):
        return ConditionResult(False, "condition missing 'type'")
    fn = _EVALUATORS.get(ctype)
    if fn is None:
        return ConditionResult(False, "unknown condition type %r" % (ctype,))
    try:
        return fn(cond, ctx)
    except Exception as exc:  # defensive: bad data must not kill the poll
        return ConditionResult(False, "evaluation error: %s" % exc)
