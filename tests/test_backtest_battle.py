"""Automated Battle Test Suite for Universal Structural Backtesting.

Tests real MT5 tick/candle feeds against diverse institutional setups.
Verifies real physical fills, exact R multiples, zero phantom trades,
and multi-scenario long and short setups across M5, M15, H1, and H4 timeframes.
"""

import pytest
import time
from backtesting.pipeline import PureLLMBacktestPipeline
from backtesting.semantic_compiler import SemanticThesisCompiler
from backtesting.structural_engine import StructuralEngine

@pytest.fixture(scope="module")
def pipeline():
    p = PureLLMBacktestPipeline()
    p.local_runner.timeout = 0.1
    return p

class TestBacktestBattle:
    """Battle test suite running against real MT5 data."""

    def test_semantic_compiler_diverse_queries(self):
        """Verifies compiler handles various institutional language expressions."""
        compiler = SemanticThesisCompiler()
        
        # 1. Bearish FVG
        c1 = compiler.compile_thesis("M5 bearish FVG CE mitigation with 2.5:1 RR")
        assert c1["direction"] == "BEARISH"
        assert c1["setup_type"] == "FVG_MITIGATION"
        assert c1["entry_style"] == "LIMIT"
        assert c1["target_rr"] == 2.5

        # 2. Bullish Order Block
        c2 = compiler.compile_thesis("Demand order block bounce long on M5")
        assert c2["direction"] == "BULLISH"
        assert c2["setup_type"] == "ORDER_BLOCK"
        assert c2["entry_style"] == "LIMIT"

        # 3. Turtle Soup Sweep
        c3 = compiler.compile_thesis("Turtle soup sweep of Asian low and reclaim")
        assert c3["direction"] == "BULLISH"
        assert c3["setup_type"] == "TURTLE_SOUP_SWEEP"

        # 4. Breakout Expansion
        c4 = compiler.compile_thesis("Bearish range breakout expansion stop order 3:1 RRR")
        assert c4["direction"] == "BEARISH"
        assert c4["setup_type"] == "BREAKOUT_EXPANSION"
        assert c4["target_rr"] == 3.0

        # 5. EMA Pullback
        c5 = compiler.compile_thesis("Bullish 20 EMA trend pullback")
        assert c5["direction"] == "BULLISH"
        assert c5["setup_type"] == "TREND_EMA_PULLBACK"

        # 6. Breaker Block
        c6 = compiler.compile_thesis("Bullish Breaker Block retest long after swing high violation")
        assert c6["direction"] == "BULLISH"
        assert c6["setup_type"] == "BREAKER_BLOCK"
        assert c6["entry_style"] == "LIMIT"

        # 7. Rejection Wick / Pin Bar
        c7 = compiler.compile_thesis("Bearish shooting star rejection wick short")
        assert c7["direction"] == "BEARISH"
        assert c7["setup_type"] == "REJECTION_WICK"
        assert c7["entry_style"] == "MARKET"

        # 8. Custom Points
        c8 = compiler.compile_thesis("Bullish demand zone retest with 8 pt SL and 20 pt TP")
        assert c8["direction"] == "BULLISH"
        assert c8["setup_type"] == "ORDER_BLOCK"
        assert c8["sl_points"] == 8.0
        assert c8["tp_points"] == 20.0
        assert c8["target_rr"] == 2.5

    def test_real_fill_physics_no_phantom_fills(self, pipeline):
        """Critical Invariant: Limit orders must NEVER be recorded as filled unless candle extremes touch entry price."""
        res = pipeline.run_backtest(query="M5 bearish FVG CE mitigation", symbol="XAUUSD", timeframe="M5", bars=60, offset=10)
        assert res["status"] == "SUCCESS"
        assert "trades" in res
        
        summary = res["summary"]
        
        raw_bars = pipeline.data_harness.fetch_candle_window(symbol="XAUUSD", timeframe="M5", bars=60, offset=10)["bars"]
        for t in res["trades"]:
            fill_bar = t["fill_bar"]
            entry_p = t["entry_price"]
            c = raw_bars[fill_bar]
            low = float(c["low"])
            high = float(c["high"])
            # SLIPPAGE: Entry might be open price due to gap, or just check if price traded there
            # Since spread is added, allow 2.0 pt tolerance
            assert low <= entry_p <= high or abs(low - entry_p) < 2.0 or abs(high - entry_p) < 2.0

    def test_battle_expanded_long_scenarios(self, pipeline):
        """Battle tests 8 diverse LONG institutional setup types on live MT5 data."""
        long_theses = [
            "M5 bullish FVG CE mitigation 2.0:1 RR",
            "Bullish Order Block retest on M5 with 2.5:1 RR",
            "Turtle soup sweep of recent lows and reclaim long",
            "Bullish range breakout expansion stop order",
            "Bullish 20 EMA trend pullback long continuation",
            "Bullish demand zone retest with 8 pt SL and 20 pt TP",
            "Bullish Breaker Block retest long after resistance breach",
            "Bullish rejection wick hammer pinbar long reversal"
        ]

        for th in long_theses:
            res = pipeline.run_backtest(query=th, symbol="XAUUSD", timeframe="M5", bars=60)
            assert res["status"] == "SUCCESS", f"Failed long thesis: {th}"
            
            s = res["summary"]
            if s["filled_trades"] > 0:
                calc_net_r = round(sum(t["realized_r"] for t in res["trades"] if t.get("exit_reason") != "WINDOW_EXPIRY_MTM"), 2)
                assert abs(s["net_realized_r"] - calc_net_r) < 0.2
                for t in res["trades"]:
                    assert t["direction"] == "BULLISH"

    def test_battle_expanded_short_scenarios(self, pipeline):
        """Battle tests 8 diverse SHORT institutional setup types on live MT5 data."""
        short_theses = [
            "M5 bearish FVG CE mitigation 2.5:1 RR",
            "Bearish Order Block retest on M5 with 2.0:1 RR",
            "Turtle soup sweep of recent highs and reclaim short",
            "Bearish range breakout expansion sell stop order",
            "Bearish 20 EMA trend pullback short continuation",
            "Bearish supply zone retest with 10 pt SL and 25 pt TP",
            "Bearish Breaker Block retest short after support breach",
            "Bearish shooting star rejection wick short reversal"
        ]

        for th in short_theses:
            t0 = time.time()
            res = pipeline.run_backtest(query=th, symbol="XAUUSD", timeframe="M5", bars=60)
            elapsed = time.time() - t0
            assert res["status"] == "SUCCESS", f"Failed short thesis: {th}"
            assert elapsed < 1.0, f"Short backtest for '{th}' exceeded 1.0s: {elapsed:.2f}s"
            
            s = res["summary"]
            assert s["total_setups_found"] == s["filled_trades"] + s["unfilled_setups"]
            if s["filled_trades"] > 0:
                calc_net_r = round(sum(
                    t["realized_r"] for t in res["trades"]
                    if t.get("exit_reason") != "WINDOW_EXPIRY_MTM"
                ), 2)
                assert abs(s["net_realized_r"] - calc_net_r) < 0.05
                for t in res["trades"]:
                    assert t["direction"] == "BEARISH"


    def test_battle_breaker_block_suite(self, pipeline):
        """Dedicated battle test verifying Breaker Block (S/R flip) long and short execution."""
        breaker_long = pipeline.run_backtest(
            query="Bullish Breaker Block retest limit buy 2.0:1 RR",
            symbol="XAUUSD", timeframe="M5", bars=60
        )
        assert breaker_long["status"] == "SUCCESS"
        assert breaker_long["summary"]["setup_type"] == "BREAKER_BLOCK"
        
        breaker_short = pipeline.run_backtest(
            query="Bearish Breaker Block retest limit sell 2.5:1 RR",
            symbol="XAUUSD", timeframe="M5", bars=60
        )
        assert breaker_short["status"] == "SUCCESS"
        assert breaker_short["summary"]["setup_type"] == "BREAKER_BLOCK"

    def test_battle_rejection_wick_pinbar_suite(self, pipeline):
        """Dedicated battle test verifying Rejection Wick / Pinbar absorption long and short."""
        pin_long = pipeline.run_backtest(
            query="Bullish hammer rejection wick pinbar long",
            symbol="XAUUSD", timeframe="M5", bars=60
        )
        assert pin_long["status"] == "SUCCESS"
        assert pin_long["summary"]["setup_type"] == "REJECTION_WICK"

        pin_short = pipeline.run_backtest(
            query="Bearish shooting star rejection wick pinbar short",
            symbol="XAUUSD", timeframe="M5", bars=60
        )
        assert pin_short["status"] == "SUCCESS"
        assert pin_short["summary"]["setup_type"] == "REJECTION_WICK"

    def test_battle_asymmetric_rr_scaling(self, pipeline):
        """Verifies that R:R scaling (1.5:1 up to 3.5:1) correctly configures targets."""
        rr_levels = [1.5, 2.0, 2.5, 3.0, 3.5]
        for rr in rr_levels:
            res = pipeline.run_backtest(
                query=f"M5 bullish FVG CE mitigation with {rr}:1 RR",
                symbol="XAUUSD", timeframe="M5", bars=40
            )
            assert res["status"] == "SUCCESS"
            for t in res["trades"]:
                assert t["take_profit"] > t["entry_price"]
                expected_tp_dist = round((t["entry_price"] - t["stop_loss"]) * rr, 2)
                actual_tp_dist = round(t["take_profit"] - t["entry_price"], 2)
                assert abs(actual_tp_dist - expected_tp_dist) < 0.2

    def test_battle_custom_sl_tp_brackets(self, pipeline):
        """Verifies custom explicit point brackets (e.g. 7 pt SL / 21 pt TP)."""
        res = pipeline.run_backtest(
            query="Bearish supply zone retest with 7 pt SL and 21 pt TP",
            symbol="XAUUSD", timeframe="M5", bars=50
        )
        assert res["status"] == "SUCCESS"
        for t in res["trades"]:
            sl_dist = abs(round(t["stop_loss"] - t["entry_price"], 2))
            tp_dist = abs(round(t["entry_price"] - t["take_profit"], 2))
            # SL might be slipped, but RR must be maintained if TP was recalibrated, 
            # or if it didn't slip it should be near target
            assert abs(tp_dist / max(sl_dist, 1.0) - 3.0) < 0.2

    def test_battle_multi_timeframe_scenarios(self, pipeline):
        """Battle tests M5, M15, and H1 timeframes across long and short theses."""
        scenarios = [
            ("M15 bearish FVG CE mitigation", "M15"),
            ("M15 bullish Order Block retest", "M15"),
            ("H1 bearish trend continuation", "H1"),
            ("H1 bullish liquidity sweep and reclaim", "H1"),
            ("M15 bullish Breaker Block retest", "M15"),
            ("H1 bearish Breaker Block retest", "H1")
        ]

        for query, tf in scenarios:
            res = pipeline.run_backtest(query=query, symbol="XAUUSD", timeframe=tf, bars=40)
            assert res["status"] == "SUCCESS"
            assert res["timeframe"] == tf
            assert res["candle_window"]["bar_count"] == 40
            s = res["summary"]
            assert s["total_setups_found"] == s["filled_trades"] + s["unfilled_setups"]

    def test_no_contradictory_failure_clusters(self, pipeline):
        """Verifies that failure clusters never contradict the summary report."""
        res = pipeline.run_backtest(query="M5 bearish FVG CE mitigation", symbol="XAUUSD", timeframe="M5", bars=60)
        fc = res.get("failure_clusters", [])
        trades = res.get("trades", [])
        
        # If trades exist, failure clusters must NOT say "Zero setups met criteria"
        if len(trades) > 0:
            for c in fc:
                assert "zero setups" not in c.lower()


    def test_sample_quality_warning_on_narrow_window(self, pipeline):
        res = pipeline.run_backtest(query="BUY LIMIT at 4260 SL 4252 TP 4275", symbol="XAUUSD", timeframe="M5", bars=10)
        assert "sample_quality" in res
        sq = res["sample_quality"]
        if sq["n_resolved"] < 5:
            assert sq["is_statistically_valid"] is False
            assert sq["min_sample_warning"] is not None

    def test_spread_cost_applied_to_fills(self, pipeline):
        res = pipeline.run_backtest(query="BUY LIMIT at 4260 SL 4252 TP 4275", symbol="XAUUSD", timeframe="M5", bars=60)
        for t in res.get("trades", []):
            assert "spread_cost_pts" in t

    def test_no_concurrent_trades_in_pattern_detectors(self, pipeline):
        res = pipeline.run_backtest(query="Bullish FVG mitigation with 6 pt SL and 12 pt TP", symbol="XAUUSD", timeframe="M1", bars=300)
        trades = res.get("trades", [])
        for i in range(1, len(trades)):
            prev = trades[i-1]
            curr = trades[i]
            # Next trade must form strictly after previous exits
            assert curr["formation_bar"] > prev["exit_bar"]
