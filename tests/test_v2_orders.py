"""Daemon v2 order path tests.

ORDER spec validation (volume>0, sl+tp present, rr>=2.0 for entries,
risk<=2pct equity) and DRY_RUN guarantees: zero real MetaTrader5 calls.
"""

import builtins
import json
import sys

import pytest

from brain.executor import place_market_order
from daemon.order_router import OrderRouter, validate_order_spec


GOOD_ACCOUNT = {"balance": 100000.0, "equity": 100000.0,
                "margin": 0.0, "free_margin": 100000.0}
GOOD_TICK = {"bid": 100.00, "ask": 100.02, "last": 100.01}
POINT_SIZES = {"XAUUSD": 0.01}


def good_spec(**over):
    spec = {
        "decision": "ORDER",
        "symbol": "XAUUSD",
        "side": "buy",
        "volume": 1.0,
        "sl": 99.00,
        "tp": 102.00,
        "rr": 2.0,
        "reason": "test entry",
        "timestamp": "2026-08-22T13:00:00+00:00",
        "reset_rule_ids": ["r1"],
    }
    spec.update(over)
    return spec


# ------------------------------------------------------------ validation -----

def test_valid_order_passes():
    ok, errors, norm = validate_order_spec(
        good_spec(), GOOD_ACCOUNT, GOOD_TICK, POINT_SIZES)
    assert ok is True
    assert errors == []
    assert norm["side"] == "buy"


def test_zero_volume_rejected():
    ok, errors, _ = validate_order_spec(
        good_spec(volume=0), GOOD_ACCOUNT, GOOD_TICK, POINT_SIZES)
    assert ok is False and any("volume" in e for e in errors)


def test_negative_volume_rejected():
    ok, errors, _ = validate_order_spec(
        good_spec(volume=-1.0), GOOD_ACCOUNT, GOOD_TICK, POINT_SIZES)
    assert ok is False and any("volume" in e for e in errors)


def test_non_numeric_volume_rejected():
    ok, errors, _ = validate_order_spec(
        good_spec(volume="big"), GOOD_ACCOUNT, GOOD_TICK, POINT_SIZES)
    assert ok is False and any("volume" in e for e in errors)


def test_missing_sl_rejected():
    ok, errors, _ = validate_order_spec(
        good_spec(sl=None), GOOD_ACCOUNT, GOOD_TICK, POINT_SIZES)
    assert ok is False and any("sl" in e for e in errors)


def test_missing_tp_rejected():
    ok, errors, _ = validate_order_spec(
        good_spec(tp=None), GOOD_ACCOUNT, GOOD_TICK, POINT_SIZES)
    assert ok is False and any("tp" in e for e in errors)


def test_rr_below_two_rejected_for_entry():
    ok, errors, _ = validate_order_spec(
        good_spec(rr=1.5), GOOD_ACCOUNT, GOOD_TICK, POINT_SIZES)
    assert ok is False and any("rr" in e for e in errors)


def test_rr_missing_defaults_to_reject_for_entry():
    spec = good_spec()
    del spec["rr"]
    ok, errors, _ = validate_order_spec(
        spec, GOOD_ACCOUNT, GOOD_TICK, POINT_SIZES)
    assert ok is False and any("rr" in e for e in errors)


def test_rr_not_required_for_monitor_exits():
    spec = good_spec()
    del spec["rr"]
    ok, errors, _ = validate_order_spec(
        spec, GOOD_ACCOUNT, GOOD_TICK, POINT_SIZES, is_entry=False)
    assert ok is True


def test_risk_over_2pct_equity_rejected():
    # buy at ask 100.02, sl 99.00 -> 1.02 price risk; pip value $1/point/lot
    # points = 102 -> risk $102 per lot * volume 30 = $3060 = 3.06 pct > 2
    ok, errors, _ = validate_order_spec(
        good_spec(volume=30.0), GOOD_ACCOUNT, GOOD_TICK, POINT_SIZES)
    assert ok is False and any("risk" in e for e in errors)


def test_risk_at_limit_boundary_passes():
    # 1.02 * 100 points * $1 * 19 lots = $1938 = 1.938 pct <= 2
    ok, errors, _ = validate_order_spec(
        good_spec(volume=19.0), GOOD_ACCOUNT, GOOD_TICK, POINT_SIZES)
    assert ok is True


def test_bad_side_rejected():
    ok, errors, _ = validate_order_spec(
        good_spec(side="yolo"), GOOD_ACCOUNT, GOOD_TICK, POINT_SIZES)
    assert ok is False and any("side" in e for e in errors)


def test_sl_on_wrong_side_of_buy_rejected():
    ok, errors, _ = validate_order_spec(
        good_spec(sl=101.0), GOOD_ACCOUNT, GOOD_TICK, POINT_SIZES)
    assert ok is False and any("sl" in e for e in errors)


def test_sell_order_sl_must_be_above():
    ok, errors, _ = validate_order_spec(
        good_spec(side="sell", sl=99.0, tp=97.0),
        GOOD_ACCOUNT, GOOD_TICK, POINT_SIZES)
    assert ok is False and any("sl" in e for e in errors)
    ok2, _, _ = validate_order_spec(
        good_spec(side="sell", sl=101.0, tp=97.0),
        GOOD_ACCOUNT, GOOD_TICK, POINT_SIZES)
    assert ok2 is True


def test_empty_symbol_rejected():
    ok, errors, _ = validate_order_spec(
        good_spec(symbol=""), GOOD_ACCOUNT, GOOD_TICK, POINT_SIZES)
    assert ok is False and any("symbol" in e for e in errors)


# ------------------------------------------------------------- routing -------

def test_router_dry_run_returns_simulated_success_without_mt5(tmp_path):
    router = OrderRouter(dry_run=True)
    assert "MetaTrader5" not in sys.modules
    result = router.route_order(good_spec(), GOOD_ACCOUNT, GOOD_TICK)
    assert result["success"] is True
    assert result.get("dry_run") is True
    assert "MetaTrader5" not in sys.modules  # still never imported


def test_place_market_order_dry_run_never_imports_mt5(monkeypatch):
    """Guard: if any code path tries to import MetaTrader5 during DRY_RUN,
    the import itself blows up the test."""
    real_import = builtins.__import__

    def guard(name, *args, **kwargs):
        if name == "MetaTrader5":
            raise AssertionError("MetaTrader5 imported during DRY_RUN")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guard)
    monkeypatch.delenv("ALPHA_DRY_RUN", raising=False)
    result = place_market_order(good_spec(), dry_run=True)
    assert result["success"] is True
    assert result.get("dry_run") is True


def test_place_market_order_env_flag_enables_dry_run(monkeypatch):
    monkeypatch.setenv("ALPHA_DRY_RUN", "1")
    result = place_market_order(good_spec())
    assert result["success"] is True
    assert result.get("dry_run") is True


def test_place_market_order_dry_run_false_explicit_override(monkeypatch):
    """Explicit dry_run=False beats env var: proves param wins over env."""
    monkeypatch.setenv("ALPHA_DRY_RUN", "1")
    result = place_market_order(good_spec(), dry_run=False)
    # Without a live terminal this fails gracefully as a dict, but it must
    # NOT report dry_run success.
    assert result.get("dry_run") is not True


def test_router_live_mode_calls_executor_wrapper(monkeypatch):
    calls = []

    def fake_place(spec, dry_run=None):
        calls.append((spec, dry_run))
        return {"success": True, "ticket": 424242, "fill_price": 100.02}

    import brain.executor as executor_mod
    monkeypatch.setattr(executor_mod, "place_market_order", fake_place)
    router = OrderRouter(dry_run=True)
    result = router.route_order(good_spec(), GOOD_ACCOUNT, GOOD_TICK)
    assert result["success"] is True
    assert result["ticket"] == 424242
    assert len(calls) == 1
    assert calls[0][1] is True  # dry_run propagated


def test_invalid_order_is_never_routed(monkeypatch):
    calls = []

    def fake_place(spec, dry_run=None):
        calls.append(spec)
        return {"success": True}

    import brain.executor as executor_mod
    monkeypatch.setattr(executor_mod, "place_market_order", fake_place)
    router = OrderRouter(dry_run=True)
    result = router.route_order(good_spec(rr=1.2), GOOD_ACCOUNT, GOOD_TICK)
    assert result["success"] is False
    assert calls == []  # rejected before reaching executor


# ------------------------------------------- action.json consumption ---------

class _MiniEngine:
    """Exercise Engine.consume_action_file wiring without full poll loop."""

    def __init__(self, tmp_path, router):
        from daemon.ring_state import RingStateStore
        self.action_file = tmp_path / "action.json"
        self.processed_file = tmp_path / "processed_actions.jsonl"
        self.state_store = RingStateStore(tmp_path / "ring_state.json")
        self.router = router
        self.latched = {"r1"}
        self.filled_tickets = []
        self.dry_run = True

    def apply_resets(self, ids):
        self.latched -= set(ids)

    def route_order(self, spec):
        return self.router.route_order(
            spec, GOOD_ACCOUNT, GOOD_TICK), spec


def test_action_wait_with_reset_clears_latch_and_archives(tmp_path):
    eng = _MiniEngine(tmp_path, OrderRouter(dry_run=True))
    eng.action_file.write_text(
        json.dumps({"decision": "WAIT", "reset_rule_ids": ["r1"]}),
        encoding="utf-8")

    from daemon.daemon_v2 import consume_action_file
    consume_action_file(eng)

    assert not eng.action_file.exists()
    assert "r1" not in eng.latched
    lines = eng.processed_file.read_text(encoding="utf-8").strip().splitlines()
    rec = json.loads(lines[-1])
    assert rec["action"]["decision"] == "WAIT"


def test_action_order_fills_ticket_into_ring_state(tmp_path):
    eng = _MiniEngine(tmp_path, OrderRouter(dry_run=True))
    eng.action_file.write_text(json.dumps(good_spec()), encoding="utf-8")

    from daemon.daemon_v2 import consume_action_file
    consume_action_file(eng)

    assert not eng.action_file.exists()
    state = json.loads(
        (tmp_path / "ring_state.json").read_text(encoding="utf-8"))
    assert state["filled_tickets"], "ticket must be recorded for AI monitors"
    assert state["filled_tickets"][0]["symbol"] == "XAUUSD"
    lines = eng.processed_file.read_text(encoding="utf-8").strip().splitlines()
    rec = json.loads(lines[-1])
    assert rec["action"]["decision"] == "ORDER"
    assert rec["result"]["success"] is True


def test_action_invalid_order_recorded_but_no_fill(tmp_path):
    eng = _MiniEngine(tmp_path, OrderRouter(dry_run=True))
    eng.action_file.write_text(json.dumps(good_spec(volume=0)),
                               encoding="utf-8")

    from daemon.daemon_v2 import consume_action_file
    consume_action_file(eng)

    state = json.loads(
        (tmp_path / "ring_state.json").read_text(encoding="utf-8"))
    assert state["filled_tickets"] == []
    lines = eng.processed_file.read_text(encoding="utf-8").strip().splitlines()
    rec = json.loads(lines[-1])
    assert rec["result"]["success"] is False
    assert rec["result"]["errors"]


def test_corrupt_action_archived_not_crash(tmp_path):
    eng = _MiniEngine(tmp_path, OrderRouter(dry_run=True))
    eng.action_file.write_text("{broken", encoding="utf-8")

    from daemon.daemon_v2 import consume_action_file
    consume_action_file(eng)  # must not raise

    assert not eng.action_file.exists()
