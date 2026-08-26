"""Daemon v2 ring protocol tests.

Proves: ring fires exactly once on a true rule, latch suppresses repeats
(logged as suppressed_repeat, no wake), reset_rule_ids clears the latch,
expiry disables rules, safety rings fire regardless of latches and ignore
AI resets while the underlying condition holds.
"""

import json
from datetime import timedelta

import pytest

import daemon.daemon_v2 as daemon_v2
from daemon.daemon_v2 import Engine, build_engine
from tests.v2_helpers import make_tick


class FakeProvider:
    """Scripted market data provider. No MT5 anywhere."""

    def __init__(self, ticks=None, account=None, positions=None,
                 bars=None, daily_bars=None, last_data_ts=None):
        self.ticks = list(ticks or [])
        self.account = account or {"balance": 100000.0, "equity": 100000.0,
                                   "margin": 0.0, "free_margin": 100000.0}
        self.positions = list(positions or [])
        self.bars = bars or []
        self.daily_bars = daily_bars or []
        self.last_data_ts = last_data_ts

    def get_market_view(self, symbol):
        tick = self.ticks.pop(0) if self.ticks else make_tick()
        return {"tick": dict(tick), "bars": self.bars,
                "daily_bars": self.daily_bars}

    def get_account(self):
        return dict(self.account)

    def get_positions(self):
        return [dict(p) for p in self.positions]


class FakeClock:
    def __init__(self, start):
        self.t = start

    def __call__(self):
        self.t += timedelta(seconds=10)
        return self.t


@pytest.fixture
def env(tmp_path):
    """Engine wired to temp dirs; returns (engine, provider, paths)."""
    paths = {
        "ring_state": tmp_path / "ring_state.json",
        "wake_prompt": tmp_path / "wake_prompt.txt",
        "action": tmp_path / "action.json",
        "processed": tmp_path / "processed_actions.jsonl",
    }
    banners = []

    def make(provider, rules, clock=None, safety=None):
        cfg = {
            "data_dir": str(tmp_path),
            "dry_run": True,
            "poll_interval": 10,
            "safety": safety or {"max_heat_pct": 6.0,
                                 "min_free_margin_pct": 20.0,
                                 "terminal_silence_sec": 60},
            "watch_symbols": [],
            "granger_snapshot_path": str(tmp_path / "snapshot.json"),
            "point_sizes": {"XAUUSD": 0.01},
            "rules_file": None,   # rules injected directly
        }
        eng = build_engine(cfg)
        eng.provider = provider
        eng.clock = clock or FakeClock(__import__("datetime").datetime(
            2026, 8, 22, 13, 0, tzinfo=__import__("datetime").timezone.utc))
        eng.banner = lambda payload, prompt_path: banners.append(payload["id"])
        eng.load_rules_object(rules)
        eng.state_store.path = paths["ring_state"]
        eng.wake_prompt_file = paths["wake_prompt"]
        eng.action_file = paths["action"]
        eng.processed_file = paths["processed"]
        return eng

    return {"make": make, "paths": paths, "banners": banners}


def rule_price_above(rid="r1", level=100.0, logic="ALL", **over):
    r = {
        "id": rid, "symbol": "XAUUSD", "kind": "entry", "direction": "long",
        "logic": logic, "conditions": [{"type": "price_above", "level": level}],
        "ring_once": True, "expires_utc": None, "note": "test rule",
    }
    r.update(over)
    return r


# ------------------------------------------------------------ fire once ------

def test_ring_fires_exactly_once_on_true_rule(env):
    prov = FakeProvider(ticks=[make_tick(last=101.0), make_tick(last=102.0),
                               make_tick(last=103.0)])
    eng = env["make"](prov, [rule_price_above()])
    fired1 = eng.poll()
    assert [r["id"] for r in fired1] == ["r1"]
    fired2 = eng.poll()
    fired3 = eng.poll()
    assert fired2 == [] and fired3 == []  # latch suppresses wakes
    state = json.loads(env["paths"]["ring_state"].read_text(encoding="utf-8"))
    fires = [e for e in state["events"] if e["event"] == "fired"
             and e["rule_id"] == "r1"]
    assert len(fires) == 1
    assert state["latches"]["r1"]["fire_count"] == 1
    assert env["banners"] == ["r1"]  # banner printed once


def test_suppressed_repeat_logged_without_wake(env):
    prov = FakeProvider(ticks=[make_tick(last=101.0)] * 3)
    eng = env["make"](prov, [rule_price_above()])
    eng.poll()
    before = (env["paths"]["wake_prompt"]).read_text(encoding="utf-8")
    eng.poll()
    state = json.loads(env["paths"]["ring_state"].read_text(encoding="utf-8"))
    reps = [e for e in state["events"] if e["event"] == "suppressed_repeat"
            and e["rule_id"] == "r1"]
    assert len(reps) >= 1
    after = (env["paths"]["wake_prompt"]).read_text(encoding="utf-8")
    assert before == after          # wake prompt untouched on suppression
    assert len(env["banners"]) == 1  # no second banner


def test_reset_rule_ids_clears_latch_and_allows_refire(env, tmp_path):
    prov = FakeProvider(ticks=[make_tick(last=101.0)] * 4)
    eng = env["make"](prov, [rule_price_above()])
    eng.poll()                       # fires, latches
    eng.poll()                       # suppressed
    action = {"decision": "WAIT", "reset_rule_ids": ["r1"]}
    env["paths"]["action"].write_text(json.dumps(action), encoding="utf-8")
    eng.poll()                       # consumes action -> latch cleared
    fired = eng.poll()               # true again -> refires
    assert [r["id"] for r in fired] == ["r1"]
    state = json.loads(env["paths"]["ring_state"].read_text(encoding="utf-8"))
    fires = [e for e in state["events"] if e["event"] == "fired"]
    assert len(fires) == 2
    resets = [e for e in state["events"] if e["event"] == "reset"]
    assert resets and resets[0]["rule_ids"] == ["r1"]
    assert not env["paths"]["action"].exists()  # consumed + archived
    archived = env["paths"]["processed"].read_text(encoding="utf-8").strip()
    assert archived  # audit line appended


def test_expired_rule_never_fires_and_logged_once(env):
    from datetime import datetime, timezone
    past = "2026-08-01T00:00:00+00:00"
    prov = FakeProvider(ticks=[make_tick(last=101.0)] * 3)
    eng = env["make"](prov, [rule_price_above(expires_utc=past)])
    out = eng.poll()
    assert out == []
    out2 = eng.poll()
    assert out2 == []
    state = json.loads(env["paths"]["ring_state"].read_text(encoding="utf-8"))
    exp = [e for e in state["events"] if e["event"] == "expired"]
    assert len(exp) == 1  # logged exactly once, not every poll


def test_future_expiry_still_fires(env):
    from datetime import datetime, timezone, timedelta
    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    prov = FakeProvider(ticks=[make_tick(last=101.0)])
    eng = env["make"](prov, [rule_price_above(expires_utc=future)])
    fired = eng.poll()
    assert [r["id"] for r in fired] == ["r1"]


def test_rule_false_does_not_fire_or_latch(env):
    prov = FakeProvider(ticks=[make_tick(last=99.0)])
    eng = env["make"](prov, [rule_price_above()])
    assert eng.poll() == []
    state = json.loads(env["paths"]["ring_state"].read_text(encoding="utf-8"))
    assert state["events"] == []


def test_any_logic_fires_when_one_condition_true(env):
    r = rule_price_above(rid="any1", logic="ANY")
    r["conditions"] = [
        {"type": "price_above", "level": 5000.0},   # false
        {"type": "price_below", "level": 150.0},    # true at 101
    ]
    prov = FakeProvider(ticks=[make_tick(last=101.0)])
    eng = env["make"](prov, [r])
    fired = eng.poll()
    assert [x["id"] for x in fired] == ["any1"]


def test_all_logic_blocks_when_one_condition_false(env):
    r = rule_price_above(rid="all1", logic="ALL")
    r["conditions"] = [
        {"type": "price_above", "level": 100.0},    # true
        {"type": "spread_below", "max_points": 1},  # spread is 2 points -> false
    ]
    prov = FakeProvider(ticks=[make_tick(last=101.0)])
    eng = env["make"](prov, [r])
    assert eng.poll() == []


# ------------------------------------------------------------- safety --------

def test_safety_heat_fires_despite_entry_latch(env):
    acct = {"balance": 100000.0, "equity": 100000.0, "margin": 0.0,
            "free_margin": 100000.0}
    pos = [{"ticket": 1, "symbol": "XAUUSD", "direction": "long", "lots": 1.0,
            "entry": 100.0, "current": 92.0, "sl": 0.0, "tp": 0.0,
            "pnl": -8000.0}]  # heat 8 pct > 6
    prov = FakeProvider(ticks=[make_tick(last=101.0)] * 3,
                        account=acct, positions=pos)
    eng = env["make"](prov, [rule_price_above()])
    first = eng.poll()      # entry fires AND safety fires
    ids = {r["id"] for r in first}
    assert "r1" in ids and "SAFETY_HEAT" in ids
    second = eng.poll()
    # both latched now: no new rings
    assert second == []


def test_safety_ring_not_cleared_by_ai_reset_while_condition_holds(env):
    acct = {"balance": 100000.0, "equity": 100000.0, "margin": 0.0,
            "free_margin": 10000.0}  # free margin 10 pct < 20
    prov = FakeProvider(ticks=[make_tick(last=101.0)] * 5, account=acct)
    eng = env["make"](prov, [])
    first = eng.poll()
    assert any(r["id"] == "SAFETY_FREE_MARGIN" for r in first)
    action = {"decision": "WAIT",
              "reset_rule_ids": ["SAFETY_FREE_MARGIN"]}  # AI tries to silence it
    env["paths"]["action"].write_text(json.dumps(action), encoding="utf-8")
    eng.poll()  # consumes reset; safety latch must survive
    again = eng.poll()
    # condition still holds: suppressed_repeat style behavior, NOT a fresh ring
    assert all(r["id"] != "SAFETY_FREE_MARGIN" for r in again)
    state = json.loads(env["paths"]["ring_state"].read_text(encoding="utf-8"))
    fires = [e for e in state["events"] if e["event"] == "fired"
             and e["rule_id"] == "SAFETY_FREE_MARGIN"]
    assert len(fires) == 1  # never re-fired while breach persists


def test_safety_ring_rearms_after_condition_clears(env):
    good = {"balance": 100000.0, "equity": 100000.0, "margin": 0.0,
            "free_margin": 100000.0}
    bad = {"balance": 100000.0, "equity": 100000.0, "margin": 0.0,
           "free_margin": 5000.0}  # 5 pct < 20
    prov = FakeProvider(ticks=[make_tick(last=101.0)] * 4, account=bad)
    eng = env["make"](prov, [])
    assert any(r["id"] == "SAFETY_FREE_MARGIN" for r in eng.poll())
    prov.account = good     # breach clears -> auto unlatch
    assert eng.poll() == []
    prov.account = bad      # breach returns -> fires again
    fired = eng.poll()
    assert any(r["id"] == "SAFETY_FREE_MARGIN" for r in fired)


def test_safety_sl_breach_long_position(env):
    pos = [{"ticket": 7, "symbol": "XAUUSD", "direction": "long", "lots": 1.0,
            "entry": 100.0, "current": 97.9, "sl": 98.0, "tp": 0.0,
            "pnl": -210.0}]
    prov = FakeProvider(ticks=[make_tick(last=97.9)], positions=pos)
    eng = env["make"](prov, [])
    fired = eng.poll()
    assert any(r["id"] == "SAFETY_SL_BREACH" for r in fired)


def test_safety_terminal_silence(env):
    prov = FakeProvider(ticks=[make_tick(last=101.0)],
                        last_data_ts=1_000_000.0)
    eng = env["make"](prov, [])
    # clock starts 2026 epoch far beyond 60s of last_data_ts
    fired = eng.poll()
    assert any(r["id"] == "SAFETY_TERMINAL_SILENCE" for r in fired)


def test_safety_ids_use_safety_prefix(env):
    prov = FakeProvider(ticks=[make_tick(last=101.0)],
                        account={"balance": 100000.0, "equity": 100000.0,
                                 "margin": 0.0, "free_margin": 1000.0})
    eng = env["make"](prov, [])
    for r in eng.poll():
        assert r["id"].startswith("SAFETY_")


# ------------------------------------------------------- monitors ------------

def test_monitor_fires_once_with_latch(env):
    mon = {
        "id": "mon-x", "ticket_or_symbol": "XAUUSD", "kind": "monitor",
        "logic": "ANY",
        "conditions": [{"type": "position_exists", "symbol": "XAUUSD",
                        "direction": None}],
        "ring_once": True, "note": "template",
    }
    pos = [{"ticket": 5, "symbol": "XAUUSD", "direction": "long", "lots": 0.1,
            "entry": 100.0, "current": 100.5, "sl": 99.0, "tp": 102.0,
            "pnl": 5.0}]
    prov = FakeProvider(ticks=[make_tick(last=100.5)] * 3, positions=pos)
    eng = env["make"](prov, [], )
    eng.load_monitors([mon])
    first = eng.poll()
    assert any(r["id"] == "mon-x" and r["kind"] == "monitor" for r in first)
    assert eng.poll() == []


# ---------------------------------------------------- wake prompt payload ----

def test_wake_prompt_contains_required_sections(env):
    prov = FakeProvider(ticks=[make_tick(last=101.0)])
    eng = env["make"](prov, [rule_price_above()])
    eng.poll()
    text = env["paths"]["wake_prompt"].read_text(encoding="utf-8")
    for token in ("r1", "entry", "long", "price_above",
                  "bid", "ask", "spread", "balance", "equity",
                  "Granger", "FROM SCRATCH", "reset_rule_ids"):
        assert token in text, f"wake prompt missing: {token}"


def test_build_engine_is_pure_factory_no_mt5_import():
    import sys
    cfg = {"data_dir": ".", "dry_run": True}
    eng = build_engine(cfg)
    assert eng is not None
    assert "MetaTrader5" not in sys.modules


def test_module_importable_without_metatrader():
    import sys
    saved = {k: v for k, v in sys.modules.items() if k == "MetaTrader5"}
    sys.modules.pop("MetaTrader5", None)
    try:
        import importlib
        mod = importlib.reload(daemon_v2)
        assert hasattr(mod, "build_engine")
    finally:
        if saved:
            sys.modules["MetaTrader5"] = saved["MetaTrader5"]
