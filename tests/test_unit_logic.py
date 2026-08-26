"""
Alpha Unit Tests — pure logic, no real MT5 required.
Run: python tests/test_unit_logic.py
Exits non-zero on any failure.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, r"C:\Trading\Alpha")

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name} {detail}")


# ════════════════════════════════════════════════════════════════
print("\n=== 1. PositionSizer ===")
from risk.sizing import PositionSizer, get_conviction_multiplier, adjust_for_drawdown

sizer = PositionSizer()

check("conv mult 6.5 -> 0.5", get_conviction_multiplier(6.5) == 0.5)
check("conv mult 8.4 -> 1.0", get_conviction_multiplier(8.4) == 1.0)
check("conv mult 9.7 -> 1.5", get_conviction_multiplier(9.7) == 1.5)
check("conv mult 5.0 -> blocked", get_conviction_multiplier(5.0) == 0.0)

# base math: 100k balance, 2% risk = $2000; stop 100 pips @ $1/pip/lot = $100/lot -> 20 lots
r = sizer.calculate_size(100000, 2.0, 8.5, 100, 1.0)
check("base size = 20.0 lots", abs(r["lots"] - 20.0) < 0.01, f"got {r.get('lots')}")
check("risk capped at 2%", r["risk_pct_final"] <= 2.0)

# conviction 6.5 -> half size
r65 = sizer.calculate_size(100000, 2.0, 6.5, 100, 1.0)
check("conv 6.5 halves size", abs(r65["lots"] - 10.0) < 0.01, f"got {r65['lots']}")

# correlation: same-group position open -> halved
rcorr = sizer.calculate_size(100000, 2.0, 8.5, 100, 1.0,
                             existing_positions=[{"symbol": "XAUUSD"}],
                             symbol="XAGUSD")
check("correlation halves size", abs(rcorr["lots"] - 10.0) < 0.01, f"got {rcorr['lots']}")

# drawdown -6% -> quarter size (beyond -5%*1.4=-7? no: -6 > -7 so half)
rd1 = adjust_for_drawdown(-6.0, 2.0)
check("drawdown -6% -> x0.5", abs(rd1 - 1.0) < 0.01, f"got {rd1}")
rd2 = adjust_for_drawdown(-8.0, 2.0)
check("drawdown -8% -> x0.25", abs(rd2 - 0.5) < 0.01, f"got {rd2}")

# below threshold blocked
rb = sizer.calculate_size(100000, 2.0, 5.5, 100, 1.0)
check("low conviction blocked", rb["lots"] == 0.0 and "reason" in rb)

# invalid stop blocked
ri = sizer.calculate_size(100000, 2.0, 8.5, 0, 1.0)
check("zero stop blocked", ri["lots"] == 0.0)

# ════════════════════════════════════════════════════════════════
print("\n=== 2. ZoneWatcher proximity (from daemon) ===")
from daemon.daemon import ZoneWatcher

zw = ZoneWatcher()
zw.zones = {"XAGUSD": [{"level": 68.50, "type": "SMA20"}]}
hits = zw.check_proximity("XAGUSD", 68.30)   # 0.29% away
check("zone hit at 0.29%", len(hits) == 1 and hits[0]["distance_pct"] == 0.29)
miss = zw.check_proximity("XAGUSD", 70.00)   # 2.2% away
check("no trigger at 2.2%", len(miss) == 0)
edge = zw.check_proximity("XAGUSD", 68.85)   # 0.51% away — just outside
check("no trigger at 0.51%", len(edge) == 0)

# ════════════════════════════════════════════════════════════════
print("\n=== 3. DecisionMemory (temp dir) ===")
from memory import DecisionMemory

with tempfile.TemporaryDirectory() as td:
    mem = DecisionMemory(Path(td))
    did = mem.record_decision({
        "bucket": "mean_reversion", "instrument": "XAGUSD",
        "direction": "LONG", "entry_price": 68.0, "stop_price": 67.0,
        "target1": 70.0, "size_lots": 1.0, "risk_pct": 1.0,
        "conviction": 8.5, "regime_at_entry": "bullish_metals",
    })
    check("decision id format", did.startswith("TRD-2026-"))
    check("open decision listed", len(mem.get_open_decisions()) == 1)

    mem.update_decision(did, {"status": "closed", "r_multiple": 1.8,
                              "exit_reason": "target"})
    closed = mem.get_closed_decisions(bucket="mean_reversion")
    check("closed + filter works", len(closed) == 1 and closed[0]["r_multiple"] == 1.8)

    mid = mem.add_mistake({"mistake": "chased breakout",
                           "rule": "NEVER enter when COT>80 and range>85%",
                           "bucket": "breakout", "regime": None,
                           "instrument": None})
    v = mem.check_mistakes(bucket="breakout", regime="bullish_metals",
                           instrument="XAGUSD")
    check("mistake rule matches bucket", len(v) == 1 and v[0]["id"] == mid)
    v2 = mem.check_mistakes(bucket="mean_reversion", regime="x", instrument="y")
    check("mistake rule skips other bucket", len(v2) == 0)

    mem.update_bucket_stats("mean_reversion", True, 1.8, "bullish_metals")
    k = mem.get_knowledge()
    st = k["buckets"]["mean_reversion"]
    check("bucket stats win_rate", st["win_rate"] == 1.0 and st["total_trades"] == 1)

# ════════════════════════════════════════════════════════════════
print("\n=== 4. TradeLearner ===")
from brain.learner import TradeLearner

with tempfile.TemporaryDirectory() as td:
    mem = DecisionMemory(Path(td))
    learner = TradeLearner(mem)
    did = mem.record_decision({"bucket": "breakout", "instrument": "COPPER",
                               "direction": "LONG", "conviction": 9.2,
                               "regime_at_entry": "bullish_metals"})
    mem.update_decision(did, {"status": "closed", "r_multiple": -1.3,
                              "exit_reason": "stop_loss",
                              "exit_time": "2026-08-21T16:00:00+00:00"})
    review = learner.review_closed_trade(did)
    check("loss reviewed", review["outcome"] == "LOSS")
    check("lessons extracted", len(review["lessons"]) >= 1)
    mistakes = mem.get_mistakes()
    check("big loss -> mistake rule", len(mistakes) == 1)
    rule = list(mistakes.values())[0]["rule"]
    check("high-conv rule mentions overconfidence", "overconfidence" in rule.lower())

    # winner path
    did2 = mem.record_decision({"bucket": "trend_continuation",
                                "instrument": "XAGUSD", "direction": "LONG",
                                "conviction": 8.0,
                                "regime_at_entry": "bullish_metals"})
    mem.update_decision(did2, {"status": "closed", "r_multiple": 2.4,
                               "exit_reason": "target2",
                               "exit_time": "2026-08-21T17:30:00+00:00"})
    rev2 = learner.review_closed_trade(did2)
    check("A+ lesson for 2.4R", any("repeat" in l.lower() for l in rev2["lessons"]))
    weekly = learner.generate_weekly_review()
    check("weekly review totals", weekly["trades_closed"] == 2
          and abs(weekly["total_r"] - 1.1) < 0.01)

# ════════════════════════════════════════════════════════════════
print("\n=== 5. MarketAnalyzer scoring (fake snapshot) ===")
import brain.analyzer as analyzer_mod
from brain.analyzer import MarketAnalyzer

fake_snapshot = {"layers": {
    "prices": {"data": {"silver": {"momentum_20d_pct": 7.0,
                                   "range_position_pct": 55}}},
    "positioning": {"data": {"silver": {"cot_percentile": 15}}},
    "macro": {"data": {"dxy": {"trend_20d": "weakening"}}},
    "sentiment": {"data": {"silver": {"score": -0.6}}},
    "technical": {"data": {"silver": {"signal": "BUY", "rsi_14": 42}}},
    "signals": {"data": {"macro_regime": {"composite": "bullish_metals"},
                         "options": {"put_call_ratio": 0.35}}},
}}
import os
fd, snap_name = tempfile.mkstemp(suffix=".json")
os.close(fd)
tmp_snap = Path(snap_name)
tmp_snap.write_text(json.dumps(fake_snapshot))

an = MarketAnalyzer(snapshot_path=tmp_snap)
snap = an.pull_granger(force=False)
check("snapshot loads", bool(snap))
check("not stale right after pull", not an.is_stale())
check("regime read", an.get_regime() == "bullish_metals")
score = an.score_opportunity("XAGUSD", {"type": "zone_approach"})
check("score elevated on all-bullish", score["score"] >= 8.0,
      f"got {score['score']}")
check("bulls collected", len(score["bulls"]) >= 4)
check("no bears on clean setup", len(score["bears"]) == 0)
tmp_snap.unlink()

# bearish snapshot
bad = dict(fake_snapshot)
bad["layers"] = {
    "prices": {"data": {"silver": {"momentum_20d_pct": -8.0,
                                   "range_position_pct": 95}}},
    "positioning": {"data": {"silver": {"cot_percentile": 88}}},
    "macro": {"data": {"dxy": {"trend_20d": "strengthening"}}},
    "signals": {"data": {"macro_regime": {"composite": "bearish_metals"}}},
}
tmp_snap.write_text(json.dumps(bad))
an2 = MarketAnalyzer(snapshot_path=tmp_snap)
s2 = an2.score_opportunity("XAGUSD", {"type": "zone_approach"})
check("bearish setup scores low", s2["score"] <= 4.0, f"got {s2['score']}")
check("bears collected", len(s2["bears"]) >= 3)
tmp_snap.unlink()

# ════════════════════════════════════════════════════════════════
print("\n=== 6. PortfolioRisk + RiskLimits (FakeMT5) ===")
from risk.portfolio import PortfolioRisk
from risk.limits import RiskLimits


class FakeMT5:
    """Stub matching daemon.MT5Interface API."""
    def __init__(self):
        self._positions = []
        self._account = {"balance": 100000.0, "equity": 100000.0,
                         "margin": 0, "free_margin": 100000, "server": "FAKE"}
        self._ticks = {}

    def get_account(self): return dict(self._account)
    def get_positions(self): return [dict(p) for p in self._positions]
    def get_tick(self, symbol):
        t = self._ticks.get(symbol)
        return dict(t) if t else None

    # test helpers
    def add_position(self, symbol, entry, sl, lots, direction="LONG"):
        self._positions.append({"ticket": len(self._positions) + 1,
                                "symbol": symbol, "direction": direction,
                                "entry": entry, "sl": sl, "current": entry,
                                "lots": lots, "pnl": 0.0, "duration_hours": 1})
    def set_tick(self, symbol, bid, ask):
        self._ticks[symbol] = {"bid": bid, "ask": ask, "spread": round((ask-bid)*1e4, 1)}


fake = FakeMT5()
fake.add_position("XAGUSD", entry=68.0, sl=67.98, lots=1.0)  # 20 pips * $5/pip * 1 lot = $100 = 0.1%
pr = PortfolioRisk(fake)
heat = pr.get_total_heat()
check("heat calc 0.1%", abs(heat - 0.1) < 0.01, f"got {heat}")

ok = pr.check_new_position("XAUUSD", lots=2.0, stop_distance_pips=5000)
# new risk: 5000 * $1.0 * 2.0 / 100000 * 100 = 10.0% → projected 10.1% > 6.0% max → blocked
check("oversized position blocked", not ok["allowed"])

ok2 = pr.check_new_position("XAUUSD", lots=0.01, stop_distance_pips=2000)
# 2000*100*0.01 = $2000 = 2%
check("2% addition allowed", ok2["allowed"], f"projected {ok2['projected_heat_pct']}")

cb = pr.check_circuit_breakers()
check("no breakers at flat pnl", cb["trading_allowed"] and not cb["close_all"])

rl = RiskLimits(pr)
trade_ok = {"instrument": "XAGUSD", "direction": "LONG", "lots": 0.5,
            "risk_pct": 1.0, "stop_distance_pips": 100, "conviction": 8.5}
res = rl.check_all(trade_ok, calendar_events=[])
check("clean trade passes all gates", res["passed"], f"violations={res['violations']}")

bad_risk = dict(trade_ok, risk_pct=3.0)
res2 = rl.check_all(bad_risk)
check("3% single risk blocked", not res2["passed"]
          and any("Single risk" in v for v in res2["violations"]))

naked = dict(trade_ok, stop_distance_pips=0)
res3 = rl.check_all(naked)
check("no-stop blocked", not res3["passed"])

news = [{"impact": "HIGH", "minutes_until": 30}]
res4 = rl.check_all(dict(trade_ok), calendar_events=news)
check("news blackout blocks", not res4["passed"])

for _ in range(5):
    fake.add_position("WTI", 80.0, 79.0, 0.01)
res5 = rl.check_all(dict(trade_ok))
check("max positions blocks", not res5["passed"]
          and any("max" in v.lower() for v in res5["violations"]))

# ════════════════════════════════════════════════════════════════
print("\n=== 7. ErrorMonitor retcode map ===")
from monitor.error_monitor import MT5_RETCODES
check("NO_MONEY is CRITICAL", MT5_RETCODES[10019][1] == "CRITICAL")
check("REQUOTE is WARNING", MT5_RETCODES[10004][1] == "WARNING")
check("DONE is INFO", MT5_RETCODES[10009][1] == "INFO")
check("INVALID_STOPS mapped", MT5_RETCODES[10016][0] == "INVALID_STOPS")

# ════════════════════════════════════════════════════════════════
print(f"\n{'='*60}\nRESULTS: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
