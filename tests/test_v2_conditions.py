"""Daemon v2 condition DSL tests.

Covers every condition type from DAEMON_V2_SPEC.md section 4 with
synthetic tick/bar inputs. Pure logic, zero MT5 involvement.
"""

import pytest

from tests.v2_helpers import (
    make_bar,
    make_ctx,
    make_tick,
    rising_bars,
    falling_bars,
    utc,
)
from daemon.conditions import (
    KNOWN_CONDITION_TYPES,
    compute_ema,
    compute_macd,
    compute_rsi,
    evaluate_condition,
)


# ---------------------------------------------------------------- registry ---

def test_all_spec_condition_types_are_known():
    expected = {
        "price_cross_above", "price_cross_below",
        "price_above", "price_below",
        "daily_close_beyond", "volume_expansion", "retest_hold",
        "indicator_state", "snapshot_field", "time_window", "spread_below",
        "position_exists", "pnl_pct_below", "pnl_pct_above", "price_reached",
    }
    assert expected == set(KNOWN_CONDITION_TYPES)


def test_unknown_condition_type_is_rejected_not_crash():
    res = evaluate_condition({"type": "moon_phase_gauge"}, make_ctx())
    assert res.fired is False
    assert "unknown" in res.detail.lower()


# ---------------------------------------------------------- edge triggered ---

def test_price_cross_above_fires_on_upward_cross():
    prev = make_tick(bid=99.9, ask=99.92, last=99.91)
    cur = make_tick(bid=100.1, ask=100.12, last=100.11)
    ctx = make_ctx(tick=cur, prev_tick=prev)
    res = evaluate_condition({"type": "price_cross_above", "level": 100.0}, ctx)
    assert res.fired is True


def test_price_cross_above_no_fire_when_already_above():
    prev = make_tick(last=100.5)
    cur = make_tick(last=100.6)
    ctx = make_ctx(tick=cur, prev_tick=prev)
    res = evaluate_condition({"type": "price_cross_above", "level": 100.0}, ctx)
    assert res.fired is False


def test_price_cross_above_no_fire_without_prev_tick():
    ctx = make_ctx(tick=make_tick(last=101.0), prev_tick=None)
    res = evaluate_condition({"type": "price_cross_above", "level": 100.0}, ctx)
    assert res.fired is False


def test_price_cross_above_no_fire_on_downward_move():
    prev = make_tick(last=100.2)
    cur = make_tick(last=99.8)
    ctx = make_ctx(tick=cur, prev_tick=prev)
    res = evaluate_condition({"type": "price_cross_above", "level": 100.0}, ctx)
    assert res.fired is False


def test_price_cross_below_fires_on_downward_cross():
    prev = make_tick(last=100.2)
    cur = make_tick(last=99.7)
    ctx = make_ctx(tick=cur, prev_tick=prev)
    res = evaluate_condition({"type": "price_cross_below", "level": 100.0}, ctx)
    assert res.fired is True


def test_price_cross_below_no_fire_when_already_below():
    prev = make_tick(last=99.5)
    cur = make_tick(last=99.4)
    ctx = make_ctx(tick=cur, prev_tick=prev)
    res = evaluate_condition({"type": "price_cross_below", "level": 100.0}, ctx)
    assert res.fired is False


# --------------------------------------------------------- level triggered ---

def test_price_above_true_when_last_gt_level():
    ctx = make_ctx(tick=make_tick(last=101.0))
    assert evaluate_condition({"type": "price_above", "level": 100.0}, ctx).fired
    assert not evaluate_condition({"type": "price_above", "level": 102.0}, ctx).fired


def test_price_below_true_when_last_lt_level():
    ctx = make_ctx(tick=make_tick(last=99.0))
    assert evaluate_condition({"type": "price_below", "level": 100.0}, ctx).fired
    assert not evaluate_condition({"type": "price_below", "level": 98.0}, ctx).fired


def test_daily_close_beyond_above():
    bars = [make_bar(104.0), make_bar(105.5)]
    ctx = make_ctx(daily_bars=bars)
    cond = {"type": "daily_close_beyond", "level": 105.0, "direction": "above"}
    assert evaluate_condition(cond, ctx).fired is True
    cond_hi = {"type": "daily_close_beyond", "level": 106.0, "direction": "above"}
    assert evaluate_condition(cond_hi, ctx).fired is False


def test_daily_close_beyond_below():
    bars = [make_bar(96.0), make_bar(94.5)]
    ctx = make_ctx(daily_bars=bars)
    cond = {"type": "daily_close_beyond", "level": 95.0, "direction": "below"}
    assert evaluate_condition(cond, ctx).fired is True


def test_daily_close_beyond_without_daily_bars_is_false():
    ctx = make_ctx(daily_bars=[])
    cond = {"type": "daily_close_beyond", "level": 100.0, "direction": "above"}
    res = evaluate_condition(cond, ctx)
    assert res.fired is False
    assert "no_daily" in res.detail


def test_volume_expansion_fires_vs_20bar_avg():
    bars = [make_bar(100.0 + i * 0.1, volume=100) for i in range(20)]
    bars.append(make_bar(102.0, volume=200))  # ratio 2.0 vs avg 100
    ctx = make_ctx(bars=bars)
    cond = {"type": "volume_expansion", "min_ratio": 1.5}
    assert evaluate_condition(cond, ctx).fired is True


def test_volume_expansion_no_fire_below_ratio():
    bars = [make_bar(100.0, volume=100) for _ in range(20)]
    bars.append(make_bar(100.5, volume=120))  # ratio 1.2
    ctx = make_ctx(bars=bars)
    cond = {"type": "volume_expansion", "min_ratio": 1.5}
    assert evaluate_condition(cond, ctx).fired is False


def test_volume_expansion_insufficient_bars_false():
    bars = [make_bar(100.0, volume=500)] * 5
    ctx = make_ctx(bars=bars)
    cond = {"type": "volume_expansion", "min_ratio": 1.5}
    res = evaluate_condition(cond, ctx)
    assert res.fired is False
    assert "insufficient" in res.detail


def test_retest_hold_fires_after_hold_window():
    # bar before window closes outside band; last 3 closes hug level 100.
    bars = [
        make_bar(98.0),                       # outside band (below)
        make_bar(100.1),
        make_bar(99.9),
        make_bar(100.2),
    ]
    ctx = make_ctx(bars=bars)
    cond = {"type": "retest_hold", "level": 100.0, "tolerance_pct": 0.5, "bars": 3}
    assert evaluate_condition(cond, ctx).fired is True


def test_retest_hold_no_fire_when_window_breaks_band():
    bars = [make_bar(98.0), make_bar(100.1), make_bar(101.0), make_bar(100.2)]
    ctx = make_ctx(bars=bars)
    cond = {"type": "retest_hold", "level": 100.0, "tolerance_pct": 0.5, "bars": 3}
    assert evaluate_condition(cond, ctx).fired is False


def test_retest_hold_no_fire_without_prior_outside_bar():
    bars = [make_bar(100.1), make_bar(99.9), make_bar(100.2)]
    ctx = make_ctx(bars=bars)
    cond = {"type": "retest_hold", "level": 100.0, "tolerance_pct": 0.5, "bars": 3}
    assert evaluate_condition(cond, ctx).fired is False


# ------------------------------------------------------------ indicators -----

def test_rsi_high_in_uptrend():
    bars = rising_bars(n=40, start=100.0, step=1.0)
    ctx = make_ctx(bars=bars)
    cond = {"type": "indicator_state", "name": "rsi",
            "params": {"period": 14}, "op": ">", "value": 70}
    assert evaluate_condition(cond, ctx).fired is True


def test_rsi_low_in_downtrend():
    bars = falling_bars(n=40, start=140.0, step=-1.0)
    ctx = make_ctx(bars=bars)
    cond = {"type": "indicator_state", "name": "rsi",
            "params": {"period": 14}, "op": "<", "value": 30}
    assert evaluate_condition(cond, ctx).fired is True


def test_rsi_cross_up_detected_within_series():
    # 20 down bars then 5 strong up bars: RSI turns up through 50.
    bars = falling_bars(n=20, start=120.0, step=-1.0)
    bars += rising_bars(n=5, start=100.0, step=3.0)
    ctx = make_ctx(bars=bars)
    cond = {"type": "indicator_state", "name": "rsi",
            "params": {"period": 14}, "op": "cross_up", "value": 50}
    assert evaluate_condition(cond, ctx).fired is True


def test_macd_positive_in_uptrend():
    bars = rising_bars(n=40, start=100.0, step=1.0)
    ctx = make_ctx(bars=bars)
    cond = {"type": "indicator_state", "name": "macd",
            "params": {}, "op": ">", "value": 0}
    assert evaluate_condition(cond, ctx).fired is True


def test_macd_negative_in_downtrend():
    bars = falling_bars(n=40, start=140.0, step=-1.0)
    ctx = make_ctx(bars=bars)
    cond = {"type": "indicator_state", "name": "macd",
            "params": {}, "op": "<", "value": 0}
    assert evaluate_condition(cond, ctx).fired is True


def test_macd_cross_up_after_flat_then_jump():
    bars = [make_bar(100.0, volume=10) for _ in range(40)]
    bars.append(make_bar(103.0))
    bars.append(make_bar(112.0))
    ctx = make_ctx(bars=bars)
    cond = {"type": "indicator_state", "name": "macd",
            "params": {}, "op": ">", "value": 0}
    assert evaluate_condition(cond, ctx).fired is True


def test_ema_compare_ops():
    bars = [make_bar(100.0, volume=10) for _ in range(40)]
    ctx = make_ctx(bars=bars)
    above = {"type": "indicator_state", "name": "ema",
             "params": {"period": 20}, "op": ">", "value": 90}
    below = {"type": "indicator_state", "name": "ema",
             "params": {"period": 20}, "op": "<", "value": 110}
    assert evaluate_condition(above, ctx).fired is True
    assert evaluate_condition(below, ctx).fired is True


def test_indicator_insufficient_bars_false():
    ctx = make_ctx(bars=[make_bar(100.0)])
    cond = {"type": "indicator_state", "name": "rsi",
            "params": {"period": 14}, "op": ">", "value": 50}
    res = evaluate_condition(cond, ctx)
    assert res.fired is False
    assert "insufficient" in res.detail


def test_indicator_unknown_name_false():
    bars = rising_bars(n=40)
    ctx = make_ctx(bars=bars)
    cond = {"type": "indicator_state", "name": "ichimoku",
            "params": {}, "op": ">", "value": 0}
    res = evaluate_condition(cond, ctx)
    assert res.fired is False
    assert "unsupported" in res.detail


def test_indicator_series_functions_pure_math():
    closes = [float(100 + i) for i in range(30)]
    rsi = compute_rsi(closes, 14)
    assert rsi[-1] > 90.0  # straight up trend
    ema = compute_ema(closes, 10)
    assert 120.0 < ema[-1] < 130.0
    macd_line, signal_line = compute_macd(closes)
    assert len(macd_line) == len(signal_line) == len(closes)


# -------------------------------------------------------- snapshot field -----

def test_snapshot_field_numeric_gt():
    snap = {"layers": {"signals": {"macro_regime": {"vix": 25.4}}}}
    ctx = make_ctx(snapshot=snap)
    cond = {"type": "snapshot_field",
            "path": "layers.signals.macro_regime.vix", "op": ">", "value": 20}
    assert evaluate_condition(cond, ctx).fired is True


def test_snapshot_field_equality_string():
    snap = {"layers": {"signals": {"macro_regime": {"composite": "risk_off"}}}}
    ctx = make_ctx(snapshot=snap)
    cond = {"type": "snapshot_field",
            "path": "layers.signals.macro_regime.composite",
            "op": "=", "value": "risk_off"}
    assert evaluate_condition(cond, ctx).fired is True


def test_snapshot_field_in_list():
    snap = {"layers": {"technical": {"data": {"regime_tags": ["trend", "risk_off"]}}}}
    ctx = make_ctx(snapshot=snap)
    cond = {"type": "snapshot_field",
            "path": "layers.technical.data.regime_tags",
            "op": "in", "value": "risk_off"}
    assert evaluate_condition(cond, ctx).fired is True


def test_snapshot_field_missing_path_false():
    ctx = make_ctx(snapshot={})
    cond = {"type": "snapshot_field", "path": "a.b.c", "op": ">", "value": 1}
    res = evaluate_condition(cond, ctx)
    assert res.fired is False
    assert "missing" in res.detail


# ------------------------------------------------------------- time window ---

def test_time_window_inside_session():
    ctx = make_ctx(now=utc(hh=13, mm=30))
    cond = {"type": "time_window", "start_utc": "13:00", "end_utc": "21:00"}
    assert evaluate_condition(cond, ctx).fired is True


def test_time_window_outside_session():
    ctx = make_ctx(now=utc(hh=22, mm=15))
    cond = {"type": "time_window", "start_utc": "13:00", "end_utc": "21:00"}
    assert evaluate_condition(cond, ctx).fired is False


def test_time_window_wraps_midnight():
    ctx_night = make_ctx(now=utc(hh=23, mm=30))
    ctx_morning = make_ctx(now=utc(hh=9, mm=0))
    cond = {"type": "time_window", "start_utc": "22:00", "end_utc": "02:00"}
    assert evaluate_condition(cond, ctx_night).fired is True
    assert evaluate_condition(cond, ctx_morning).fired is False


# ------------------------------------------------------------ spread ---------

def test_spread_below_true():
    ctx = make_ctx(tick=make_tick(bid=100.00, ask=100.05), point_size=0.01)
    cond = {"type": "spread_below", "max_points": 10}
    assert evaluate_condition(cond, ctx).fired is True


def test_spread_below_false_when_too_wide():
    ctx = make_ctx(tick=make_tick(bid=100.00, ask=100.05), point_size=0.01)
    cond = {"type": "spread_below", "max_points": 3}
    assert evaluate_condition(cond, ctx).fired is False


# ------------------------------------------------- position / monitor preds --

LONG_POS = {
    "ticket": 111, "symbol": "XAUUSD", "direction": "long", "lots": 0.5,
    "entry": 100.0, "current": 99.0, "sl": 98.0, "tp": 104.0, "pnl": -50.0,
}


def test_position_exists_match_symbol_and_direction():
    ctx = make_ctx(positions=[dict(LONG_POS)], symbol="XAUUSD")
    cond = {"type": "position_exists", "symbol": "XAUUSD", "direction": "long"}
    assert evaluate_condition(cond, ctx).fired is True


def test_position_exists_null_direction_matches_any():
    ctx = make_ctx(positions=[dict(LONG_POS)], symbol="XAUUSD")
    cond = {"type": "position_exists", "symbol": "XAUUSD", "direction": None}
    assert evaluate_condition(cond, ctx).fired is True


def test_position_exists_no_match_wrong_direction():
    ctx = make_ctx(positions=[dict(LONG_POS)], symbol="XAUUSD")
    cond = {"type": "position_exists", "symbol": "XAUUSD", "direction": "short"}
    assert evaluate_condition(cond, ctx).fired is False


def test_position_exists_no_match_wrong_symbol():
    ctx = make_ctx(positions=[dict(LONG_POS)], symbol="XAUUSD")
    cond = {"type": "position_exists", "symbol": "XAGUSD", "direction": None}
    assert evaluate_condition(cond, ctx).fired is False


def test_pnl_pct_below_long_against_move():
    pos = dict(LONG_POS)
    pos["entry"], pos["current"] = 100.0, 99.0   # -1 pct price move
    ctx = make_ctx(positions=[pos], symbol="XAUUSD", rule_direction="long")
    cond = {"type": "pnl_pct_below", "value": -0.5}
    assert evaluate_condition(cond, ctx).fired is True


def test_pnl_pct_below_short_against_move():
    pos = dict(LONG_POS)
    pos["direction"] = "short"
    pos["entry"], pos["current"] = 100.0, 101.0  # short losing 1 pct
    ctx = make_ctx(positions=[pos], symbol="XAUUSD", rule_direction="short")
    cond = {"type": "pnl_pct_below", "value": -0.5}
    assert evaluate_condition(cond, ctx).fired is True


def test_pnl_pct_above_long_in_profit():
    pos = dict(LONG_POS)
    pos["entry"], pos["current"] = 100.0, 101.5  # +1.5 pct
    ctx = make_ctx(positions=[pos], symbol="XAUUSD", rule_direction="long")
    cond = {"type": "pnl_pct_above", "value": 1.0}
    assert evaluate_condition(cond, ctx).fired is True


def test_pnl_pct_no_positions_false():
    ctx = make_ctx(positions=[], symbol="XAUUSD")
    cond = {"type": "pnl_pct_below", "value": -0.5}
    assert evaluate_condition(cond, ctx).fired is False


def test_price_reached_long_side():
    ctx = make_ctx(tick=make_tick(last=101.0), rule_direction="long")
    cond = {"type": "price_reached", "level": 100.0}
    assert evaluate_condition(cond, ctx).fired is True
    ctx_low = make_ctx(tick=make_tick(last=99.0), rule_direction="long")
    assert evaluate_condition(cond, ctx_low).fired is False


def test_price_reached_short_side():
    ctx = make_ctx(tick=make_tick(last=99.0), rule_direction="short")
    cond = {"type": "price_reached", "level": 100.0}
    assert evaluate_condition(cond, ctx).fired is True
    ctx_high = make_ctx(tick=make_tick(last=101.0), rule_direction="short")
    assert evaluate_condition(cond, ctx_high).fired is False


# ------------------------------------------------------- malformed input -----

def test_missing_required_param_is_false_with_detail():
    ctx = make_ctx()
    res = evaluate_condition({"type": "price_above"}, ctx)  # no level
    assert res.fired is False
    assert res.detail  # non-empty explanation


def test_non_dict_condition_is_false_with_detail():
    res = evaluate_condition("price_above", make_ctx())
    assert res.fired is False
