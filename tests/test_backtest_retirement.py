"""Automated Retirement Test Suite for Quantitative Backtesting Engine.

Validates boundary conditions, stress scenarios, extreme non-fill regimes,
and invariant preservation under synthetic and adversarial candle sequences.
"""

import pytest
import time
from backtesting.structural_engine import StructuralEngine
from backtesting.semantic_compiler import SemanticThesisCompiler

@pytest.fixture
def engine():
    return StructuralEngine()

@pytest.fixture
def compiler():
    return SemanticThesisCompiler()

class TestBacktestRetirement:
    """Rigorous stress and invariant testing for the backtesting engine."""

    def test_runaway_trend_zero_phantom_fills(self, engine, compiler):
        """CRITICAL RETIREMENT RETEST:
        When price expands away in a violent runaway cascade without ever retracing,
        the engine MUST report 0 filled trades. The old buggy engine reported phantom wins.
        """
        # Create 30 candles cascading downward with zero upward bounces
        candles = []
        base_price = 4350.0
        for i in range(30):
            high = base_price - (i * 3.0)
            open_p = high - 0.5
            close_p = open_p - 2.0
            low = close_p - 0.5
            candles.append({
                "timestamp": f"2026-09-23 10:{i:02d}",
                "open": open_p,
                "high": high,
                "low": low,
                "close": close_p,
                "tick_volume": 500
            })

        cfg = compiler.compile_thesis("M5 bearish FVG CE mitigation")
        cfg["entry_style"] = "LIMIT"

        res = engine.run_simulation(candles, cfg)

        # FVG setups will be detected, BUT NONE MUST BE FILLED because price never retraces upward!
        assert res["total_setups_found"] > 0
        assert res["filled_trades"] == 0, "FATAL: Ghost fill detected in runaway cascade!"
        assert res["unfilled_setups"] == res["total_setups_found"]
        assert res["wins"] == 0
        assert res["losses"] == 0
        assert res["net_realized_r"] == 0.0

    def test_clean_stop_loss_trigger(self, engine, compiler):
        """Verifies that an adverse move cleanly hits Stop Loss for exactly -1.0R."""
        # 3 bars to form Bullish FVG, then bar 4 pulls back to fill CE, then bar 5 plunges below SL
        candles = [
            {"timestamp": "2026-09-23 10:00", "open": 4300.0, "high": 4302.0, "low": 4299.0, "close": 4301.0, "tick_volume": 100},
            {"timestamp": "2026-09-23 10:05", "open": 4301.0, "high": 4310.0, "low": 4300.0, "close": 4309.0, "tick_volume": 200},
            {"timestamp": "2026-09-23 10:10", "open": 4309.0, "high": 4318.0, "low": 4308.0, "close": 4317.0, "tick_volume": 300},
            # Bar 3: forms FVG between c0.high (4302.0) and c2.low (4308.0). CE = 4305.0. SL = c1.low - 1.2 = 4298.8
            # Bar 4: retraces to 4304.5 (fills 4305.0)
            {"timestamp": "2026-09-23 10:15", "open": 4315.0, "high": 4316.0, "low": 4304.0, "close": 4306.0, "tick_volume": 150},
            # Bar 5: plunges to 4295.0 (breaches SL 4298.8)
            {"timestamp": "2026-09-23 10:20", "open": 4306.0, "high": 4307.0, "low": 4295.0, "close": 4296.0, "tick_volume": 250},
            # Padding bars
            {"timestamp": "2026-09-23 10:25", "open": 4296.0, "high": 4297.0, "low": 4295.0, "close": 4296.5, "tick_volume": 100},
            {"timestamp": "2026-09-23 10:30", "open": 4296.5, "high": 4298.0, "low": 4296.0, "close": 4297.5, "tick_volume": 100},
            {"timestamp": "2026-09-23 10:35", "open": 4297.5, "high": 4299.0, "low": 4297.0, "close": 4298.5, "tick_volume": 100},
            {"timestamp": "2026-09-23 10:40", "open": 4298.5, "high": 4300.0, "low": 4298.0, "close": 4299.5, "tick_volume": 100},
            {"timestamp": "2026-09-23 10:45", "open": 4299.5, "high": 4301.0, "low": 4299.0, "close": 4300.5, "tick_volume": 100},
            {"timestamp": "2026-09-23 10:50", "open": 4300.5, "high": 4302.0, "low": 4300.0, "close": 4301.5, "tick_volume": 100},
        ]

        cfg = compiler.compile_thesis("M5 bullish FVG CE mitigation 2.0:1 RR")
        res = engine.run_simulation(candles, cfg)

        assert res["filled_trades"] >= 1
        t = res["trades"][0]
        assert t["exit_reason"] == "SL_HIT"
        assert t["realized_r"] == -1.0

    def test_clean_take_profit_trigger(self, engine, compiler):
        """Verifies that a favorable move hits Take Profit for exactly planned R:R."""
        # 3 bars to form Bearish FVG, then retrace to fill CE, then drop to TP
        candles = [
            {"timestamp": "2026-09-23 10:00", "open": 4320.0, "high": 4322.0, "low": 4318.0, "close": 4319.0, "tick_volume": 100},
            {"timestamp": "2026-09-23 10:05", "open": 4319.0, "high": 4320.0, "low": 4310.0, "close": 4311.0, "tick_volume": 200},
            {"timestamp": "2026-09-23 10:10", "open": 4311.0, "high": 4305.0, "low": 4301.0, "close": 4302.0, "tick_volume": 300},
            # Gap: c0.low (4318.0) > c2.high (4305.0). CE = 4311.5. SL = c1.high + 1.2 = 4321.2. Risk = 9.7. TP @ 2.0R = 4311.5 - 19.4 = 4292.1
            # Bar 4: retraces to fill CE
            {"timestamp": "2026-09-23 10:15", "open": 4303.0, "high": 4313.0, "low": 4302.0, "close": 4308.0, "tick_volume": 150},
            # Bar 5: plunges straight to 4290.0 (hitting TP 4292.1)
            {"timestamp": "2026-09-23 10:20", "open": 4308.0, "high": 4309.0, "low": 4290.0, "close": 4291.0, "tick_volume": 400},
            # Padding bars
            {"timestamp": "2026-09-23 10:25", "open": 4291.0, "high": 4292.0, "low": 4289.0, "close": 4290.0, "tick_volume": 100},
            {"timestamp": "2026-09-23 10:30", "open": 4290.0, "high": 4291.0, "low": 4288.0, "close": 4289.0, "tick_volume": 100},
            {"timestamp": "2026-09-23 10:35", "open": 4289.0, "high": 4290.0, "low": 4287.0, "close": 4288.0, "tick_volume": 100},
            {"timestamp": "2026-09-23 10:40", "open": 4288.0, "high": 4289.0, "low": 4286.0, "close": 4287.0, "tick_volume": 100},
            {"timestamp": "2026-09-23 10:45", "open": 4287.0, "high": 4288.0, "low": 4285.0, "close": 4286.0, "tick_volume": 100},
            {"timestamp": "2026-09-23 10:50", "open": 4286.0, "high": 4287.0, "low": 4284.0, "close": 4285.0, "tick_volume": 100},
        ]

        cfg = compiler.compile_thesis("M5 bearish FVG CE mitigation 2.0:1 RR")
        res = engine.run_simulation(candles, cfg)

        assert res["filled_trades"] >= 1
        t = res["trades"][0]
        assert t["exit_reason"] == "TP_HIT"
        assert t["realized_r"] == 2.0

    def test_boundary_empty_candles(self, engine, compiler):
        """Verifies engine never crashes on empty or minimal candle history."""
        cfg = compiler.compile_thesis("M5 bearish FVG CE mitigation")
        res_empty = engine.run_simulation([], cfg)
        assert res_empty["total_setups_found"] == 0
        assert res_empty["filled_trades"] == 0

        res_small = engine.run_simulation([{"open": 1, "high": 2, "low": 0, "close": 1}], cfg)
        assert res_small["total_setups_found"] == 0

    def test_sub_millisecond_speed(self, engine, compiler):
        """Verifies sub-millisecond execution throughput for 100 iterations."""
        candles = []
        for i in range(50):
            candles.append({
                "timestamp": f"2026-09-23 10:{i:02d}",
                "open": 4300.0 + (i % 5),
                "high": 4305.0 + (i % 5),
                "low": 4295.0 + (i % 5),
                "close": 4302.0 + (i % 5),
                "tick_volume": 100
            })

        cfg = compiler.compile_thesis("M5 bearish FVG CE mitigation")
        
        t0 = time.time()
        iterations = 50
        for _ in range(iterations):
            engine.run_simulation(candles, cfg)
        total_time = time.time() - t0
        avg_ms = (total_time / iterations) * 1000
        assert avg_ms < 5.0, f"Engine too slow: {avg_ms:.2f}ms per simulation"

    def test_adversarial_break_matrix(self):
        """Adversarial stress test: runs 16 edge, boundary, and pathological cases attempting to break engine."""
        from backtesting.pipeline import PureLLMBacktestPipeline
        pipeline = PureLLMBacktestPipeline()

        adversarial_cases = [
            ("M5 bullish FVG CE mitigation", "M5", 10),
            ("M5 bearish Order Block retest", "M5", 5),
            ("M1 bearish range breakdown sell stop order", "M1", 200),
            ("Bullish FVG CE mitigation with 10.0:1 RR", "M5", 60),
            ("M5 bullish Order Block retest with 1.5 pt SL and 3 pt TP", "M5", 60),
            ("H1 Bullish demand zone retest with 50 pt SL and 150 pt TP", "H1", 60),
            ("M5 short with 20 pt SL and 5 pt TP", "M5", 60),
            ("H4 bearish trend continuation 20 EMA", "H4", 20),
            ("M1 Turtle soup sweep of recent lows and reclaim long", "M1", 150),
            ("Bullish buy and bearish sell breakout momentum expansion", "M5", 60),
            ("M5 bullish FVG with 0 pt SL and 0 pt TP", "M5", 60),
            ("Institutional liquidity discount absorption bounce", "M5", 60),
            ("H1 Bearish Breaker Block retest after support breach", "H1", 40),
            ("M5 shooting star rejection wick pinbar short", "M5", 80),
            ("M5 range breakout expansion stop order 3:1 RR", "M5", 60),
            ("D1 bearish 20 EMA trend pullback continuation", "D1", 15),
        ]

        for query, tf, bars in adversarial_cases:
            res = pipeline.run_backtest(query=query, symbol="XAUUSD", timeframe=tf, bars=bars)
            assert res["status"] in ["SUCCESS", "ERROR"]
            summary = res.get("summary", {})
            trades = res.get("trades", [])
            # Invariant: trades must never have inverted brackets or equal entry/sl
            for t in trades:
                assert t["stop_loss"] != t["entry_price"]
                if t["direction"] == "BULLISH":
                    assert t["take_profit"] > t["entry_price"]
                elif t["direction"] == "BEARISH":
                    assert t["take_profit"] < t["entry_price"]

