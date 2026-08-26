"""Daemon v2 DRY_RUN integration tests.

Full engine against synthetic tick streams: seed rules load and fire,
latch/reset cycle works end to end, ORDER decisions route through the
executor wrapper, zero real MT5 calls happen anywhere, and v2 emits no
legacy zone_approach / daily_scan wakes.
"""

import json
import sys

import pytest

from daemon.daemon_v2 import Engine, build_engine
from daemon.rule_loader import load_rules
from tests.v2_helpers import make_bar, make_tick


SEED_RULES = r"C:\Trading\Alpha\data\live\alert_rules.json"
V2_MODULES = [
    "daemon/conditions.py",
    "daemon/rule_loader.py",
    "daemon/ring_state.py",
    "daemon/market_data.py",
    "daemon/order_router.py",
    "daemon/wake_prompt.py",
    "daemon/safety.py",
    "daemon/daemon_v2.py",
]
FORBIDDEN_LEGACY_TOKENS = ["zone_approach", "daily_scan"]


class ScriptedProvider:
    def __init__(self, script):
        # script: list of dicts {"tick":..., "bars":..., "daily_bars":...}
        self.script = list(script)
        self.account = {"balance": 100000.0, "equity": 100000.0,
                        "margin": 0.0, "free_margin": 100000.0}
        self.positions = []
        self.last_data_ts = None

    def get_market_view(self, symbol):
        step = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        return {"tick": step.get("tick") or make_tick(),
                "bars": step.get("bars", []),
                "daily_bars": step.get("daily_bars", [])}

    def get_account(self):
        return dict(self.account)

    def get_positions(self):
        return [dict(p) for p in self.positions]


@pytest.fixture
def engine(tmp_path):
    banners = []
    cfg = {
        "data_dir": str(tmp_path),
        "dry_run": True,
        "poll_interval": 10,
        "safety": {"max_heat_pct": 6.0, "min_free_margin_pct": 20.0,
                   "terminal_silence_sec": 60},
        "watch_symbols": [],
        "granger_snapshot_path": str(tmp_path / "all_layers_snapshot.json"),
        "point_sizes": {"XAUUSD": 0.01, "XPTUSD": 0.01},
        "rules_file": None,
    }
    eng = build_engine(cfg)
    eng.banner = lambda payload, path: banners.append(payload["id"])
    eng.wake_prompt_file = tmp_path / "wake_prompt.txt"
    eng.action_file = tmp_path / "action.json"
    eng.processed_file = tmp_path / "processed_actions.jsonl"
    eng.state_store.path = tmp_path / "ring_state.json"
    eng.banners = banners
    return eng


def test_seed_alert_rules_file_loads_clean():
    res = load_rules(SEED_RULES)
    assert res.errors == []
    ids = {r["id"] for r in res.rules}
    assert {
        "xptusd-bb-breakout-long-v1",
        "xauusd-bb-breakout-long-v1",
        "xauusd-bb-breakout-short-v1",
        "xagusd-sma200-reclaim-long-v1",
        "xpdusd-range-watch-any-v1",
    } <= ids
    assert len(res.monitors) >= 1  # monitor template present


def test_seed_levels_match_zones_json():
    with open(r"C:\Trading\Alpha\data\live\zones.json",
              encoding="utf-8") as f:
        zones = json.load(f)
    res = load_rules(SEED_RULES)
    by_id = {r["id"]: r for r in res.rules}

    xpt_bb = next(z["level"] for z in zones["XPTUSD"]
                  if z["type"] == "BB_UPPER")
    conds = by_id["xptusd-bb-breakout-long-v1"]["conditions"]
    levels = [c.get("level") for c in conds if "level" in c]
    assert xpt_bb in levels

    xau_bb_up = next(z["level"] for z in zones["XAUUSD"]
                     if z["type"] == "BB_UPPER")
    conds = by_id["xauusd-bb-breakout-long-v1"]["conditions"]
    assert xau_bb_up in [c.get("level") for c in conds if "level" in c]

    xag_sma200 = next(z["level"] for z in zones["XAGUSD"]
                      if z["type"] == "SMA200")
    conds = by_id["xagusd-sma200-reclaim-long-v1"]["conditions"]
    assert xag_sma200 in [c.get("level") for c in conds if "level" in c]


def test_full_ring_latch_reset_cycle_dry_run(engine):
    """Spec section 12.3: injected rule demonstrates ring -> latch -> reset."""
    bb_level = 1879.81  # XPTUSD BB_UPPER from zones.json
    rule = {
        "id": "inject-price-above-once",
        "symbol": "XPTUSD", "kind": "entry", "direction": "long",
        "logic": "ALL",
        "conditions": [{"type": "price_above", "level": bb_level}],
        "ring_once": True, "expires_utc": None,
        "note": "injected test rule - no order expected",
    }
    engine.load_rules_object([rule])
    engine.provider = ScriptedProvider([
        {"tick": make_tick(bid=1880.0, ask=1880.05, last=1880.02)},
        {"tick": make_tick(bid=1881.0, ask=1881.05, last=1881.02)},
        {"tick": make_tick(bid=1882.0, ask=1882.05, last=1882.02)},
        {"tick": make_tick(bid=1883.0, ask=1883.05, last=1883.02)},
    ])

    fired = engine.poll()
    assert [r["id"] for r in fired] == ["inject-price-above-once"]
    assert engine.banners == ["inject-price-above-once"]

    suppressed = engine.poll()
    assert suppressed == []

    # AI responds: WAIT + reset -> latch clears deterministically
    engine.action_file.write_text(
        json.dumps({"decision": "WAIT",
                    "reset_rule_ids": ["inject-price-above-once"]}),
        encoding="utf-8")
    engine.poll()
    refire = engine.poll()
    assert [r["id"] for r in refire] == ["inject-price-above-once"]

    state = json.loads(
        engine.state_store.path.read_text(encoding="utf-8"))
    fire_events = [e for e in state["events"] if e["event"] == "fired"]
    assert len(fire_events) == 2
    assert state["filled_tickets"] == []  # no order was placed


def test_breakout_rule_fires_on_synthetic_daily_close_volume_retest(engine):
    """xptusd-bb-breakout pattern: daily close beyond BB upper + volume
    expansion + retest hold -> ALL logic fires exactly once."""
    res = load_rules(SEED_RULES)
    rule = next(r for r in res.rules if r["id"] == "xptusd-bb-breakout-long-v1")
    level = rule["conditions"][0]["level"]

    bars = [make_bar(level * 0.995, volume=100) for _ in range(20)]
    bars.append(make_bar(level * 1.001, volume=180))   # ratio 1.8 vs avg 100
    daily = [make_bar(level * 1.002)]                  # close beyond band

    engine.load_rules_object([rule])
    engine.provider = ScriptedProvider([
        {"tick": make_tick(last=level * 1.0005), "bars": bars,
         "daily_bars": daily},
        {"tick": make_tick(last=level * 1.0006), "bars": bars,
         "daily_bars": daily},
    ])

    fired = engine.poll()
    assert [r["id"] for r in fired] == ["xptusd-bb-breakout-long-v1"]
    payload = fired[0]
    assert payload["kind"] == "entry"
    assert payload["direction"] == "long"
    assert all(c["fired"] for c in payload["conditions"])
    assert engine.poll() == []  # ring_once latch holds


def test_order_decision_routes_through_executor_in_poll_loop(engine,
                                                             monkeypatch):
    calls = []

    def fake_place(spec, dry_run=None):
        calls.append((spec, dry_run))
        return {"success": True, "ticket": 777777, "fill_price": 100.02}

    import brain.executor as executor_mod
    monkeypatch.setattr(executor_mod, "place_market_order", fake_place)

    rule = {
        "id": "order-flow-rule", "symbol": "XAUUSD", "kind": "entry",
        "direction": "long", "logic": "ALL",
        "conditions": [{"type": "price_above", "level": 50.0}],
        "ring_once": True, "expires_utc": None, "note": "",
    }
    engine.load_rules_object([rule])
    engine.provider = ScriptedProvider([{"tick": make_tick(last=101.0)}])
    engine.poll()  # fires

    engine.action_file.write_text(json.dumps({
        "decision": "ORDER", "symbol": "XAUUSD", "side": "buy",
        "volume": 1.0, "sl": 99.0, "tp": 103.0, "rr": 2.0,
        "reason": "test", "timestamp": "2026-08-22T13:00:00+00:00",
        "reset_rule_ids": ["order-flow-rule"],
    }), encoding="utf-8")

    engine.provider = ScriptedProvider([{"tick": make_tick(last=101.0)}])
    engine.poll()  # consumes action, routes order

    assert len(calls) == 1
    assert calls[0][1] is True  # dry_run flag propagated to wrapper
    state = json.loads(engine.state_store.path.read_text(encoding="utf-8"))
    assert state["filled_tickets"][0]["ticket"] == 777777


def test_zero_real_mt5_calls_across_full_cycle(engine, monkeypatch):
    """The strongest guarantee: any attempt to import MetaTrader5 during the
    entire poll/consume/order cycle fails the test."""
    import builtins
    real_import = builtins.__import__

    def guard(name, *args, **kwargs):
        if name == "MetaTrader5":
            raise AssertionError("real MT5 import attempted in DRY_RUN cycle")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guard)
    monkeypatch.delenv("ALPHA_DRY_RUN", raising=False)

    rule = {
        "id": "dry-cycle", "symbol": "XAUUSD", "kind": "entry",
        "direction": "long", "logic": "ALL",
        "conditions": [{"type": "price_above", "level": 10.0}],
        "ring_once": True, "expires_utc": None, "note": "",
    }
    engine.load_rules_object([rule])
    engine.provider = ScriptedProvider([
        {"tick": make_tick(last=11.0)},
        {"tick": make_tick(last=12.0)},
    ])
    assert engine.poll()
    engine.action_file.write_text(json.dumps(
        {"decision": "REJECT", "reason": "trap detected",
         "reset_rule_ids": ["dry-cycle"]}), encoding="utf-8")
    engine.poll()
    assert "MetaTrader5" not in sys.modules


def test_v2_emits_no_legacy_wake_templates(engine):
    """Legacy regression: price hugging old zone levels produces NO wake.
    Also: v2 runtime modules never reference retired trigger templates."""
    rule = {
        "id": "near-zone-noise", "symbol": "XAUUSD", "kind": "entry",
        "direction": "long", "logic": "ALL",
        "conditions": [{"type": "price_above", "level": 9999.0}],  # never true
        "ring_once": True, "expires_utc": None, "note": "",
    }
    engine.load_rules_object([rule])
    # price sits exactly on an old zone level (SMA20 4280.05) - legacy v1
    # would spam zone_approach here; v2 must stay silent.
    engine.provider = ScriptedProvider([
        {"tick": make_tick(last=4280.05)} for _ in range(3)])
    for _ in range(3):
        assert engine.poll() == []
    assert engine.banners == []

    from pathlib import Path
    alpha_root = Path(r"C:\Trading\Alpha")
    for rel in V2_MODULES:
        src = (alpha_root / rel).read_text(encoding="utf-8")
        for token in FORBIDDEN_LEGACY_TOKENS:
            assert token not in src, f"{rel} references retired token {token}"


def test_wake_banner_channel_writes_prompt_and_state(engine):
    rule = {
        "id": "banner-rule", "symbol": "XAUUSD", "kind": "entry",
        "direction": "long", "logic": "ALL",
        "conditions": [{"type": "price_above", "level": 10.0}],
        "ring_once": True, "expires_utc": None, "note": "",
    }
    engine.load_rules_object([rule])
    engine.provider = ScriptedProvider([{"tick": make_tick(last=11.0)}])
    engine.poll()
    prompt = engine.wake_prompt_file.read_text(encoding="utf-8")
    assert "banner-rule" in prompt
    state = json.loads(engine.state_store.path.read_text(encoding="utf-8"))
    evt = state["events"][0]
    assert evt["event"] == "fired" and evt["rule_id"] == "banner-rule"
    assert "market" in evt  # market snapshot appended per spec section 6
    # atomic write leaves no .tmp litter behind
    leftovers = list(engine.state_store.path.parent.glob("*.tmp"))
    assert leftovers == []


def test_engine_survives_provider_failure_poll(engine):
    class ExplodingProvider(ScriptedProvider):
        def get_market_view(self, symbol):
            raise OSError("terminal gone")

    engine.load_rules_object([])
    engine.provider = ExplodingProvider([])
    rings = engine.poll()  # must log and continue, not raise
    assert rings == []
