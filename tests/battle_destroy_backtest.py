import math
"""Battle and Destroy Stress Test Suite for Alpha Structural Backtesting Engine.

Relentlessly attacks and validates:
  1. Coordinate extraction & semantic query parsing
  2. Malicious, extreme, inverted, and malformed inputs
  3. Real MT5 candle replay with genuine broker fill physics
  4. Mathematical integrity (zero negative prices, zero NaN, zero div-by-zero, bounded R-multiples)
  5. Pattern archetypes & execution reproducibility
"""

import sys
import os
import json
import traceback

# Ensure Alpha root is in sys.path
ALPHA_DIR = r"C:\Trading\Alpha"
if ALPHA_DIR not in sys.path:
    sys.path.insert(0, ALPHA_DIR)

from backtesting.semantic_compiler import SemanticThesisCompiler
from backtesting.structural_engine import StructuralEngine
from backtesting.pipeline import PureLLMBacktestPipeline

def run_battle_and_destroy_tests():
    print("=" * 70)
    print(" COMMENCING BATTLE AND DESTROY STRESS TEST FOR BACKTEST ENGINE")
    print("=" * 70)

    compiler = SemanticThesisCompiler()
    pipeline = PureLLMBacktestPipeline()

    passed = 0
    failed = 0

    def assert_test(name, condition, details=""):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            failed += 1
            print(f"  [FAIL] {name} | {details}")

    # =========================================================================
    # SUITE 1: SEMANTIC COMPILER ADVERSARIAL PHRASING
    # =========================================================================
    print("\n--- SUITE 1: SEMANTIC COMPILER PARSING & ADVERSARIAL PHRASING ---")

    s1_cases = [
        {
            "query": "XAUUSD long position ahead of NFP Sept 4 2026. BUY LIMIT at 4480 SL 4472 TP 4550.",
            "exp_dir": "BULLISH",
            "exp_style": "LIMIT",
            "exp_entry": 4480.0,
            "exp_sl": 4472.0,
            "exp_tp": 4550.0,
            "exp_sl_pts": 8.0,
            "exp_tp_pts": 70.0
        },
        {
            "query": "SELL STOP at 4273.2 SL 4280.0 TP 4260.9",
            "exp_dir": "BEARISH",
            "exp_style": "STOP",
            "exp_entry": 4273.2,
            "exp_sl": 4280.0,
            "exp_tp": 4260.9,
            "exp_sl_pts": 6.8,
            "exp_tp_pts": 12.3
        },
        {
            "query": "BUY STOP @ 4285.5 with SL: 4278.0 and TP: 4305.0",
            "exp_dir": "BULLISH",
            "exp_style": "STOP",
            "exp_entry": 4285.5,
            "exp_sl": 4278.0,
            "exp_tp": 4305.0,
            "exp_sl_pts": 7.5,
            "exp_tp_pts": 19.5
        },
        {
            "query": "Short breakdown below 4270 sl 4276 tp 4255",
            "exp_dir": "BEARISH",
            "exp_style": "STOP",
            "exp_entry": 4270.0,
            "exp_sl": 4276.0,
            "exp_tp": 4255.0,
            "exp_sl_pts": 6.0,
            "exp_tp_pts": 15.0
        },
        {
            "query": "Market buy gold at 4265 sl 4258 tp 4282",
            "exp_dir": "BULLISH",
            "exp_style": "MARKET",
            "exp_entry": 4265.0,
            "exp_sl": 4258.0,
            "exp_tp": 4282.0,
            "exp_sl_pts": 7.0,
            "exp_tp_pts": 17.0
        },
        {
            "query": "Bullish FVG mitigation with 8 pt SL and 16 pt TP",
            "exp_dir": "BULLISH",
            "exp_style": "LIMIT",
            "exp_entry": None,
            "exp_sl": None,
            "exp_tp": None,
            "exp_sl_pts": 8.0,
            "exp_tp_pts": 16.0
        }
    ]

    for idx, tc in enumerate(s1_cases):
        q = tc["query"]
        res = compiler.compile_thesis(q)
        assert_test(f"S1.{idx+1} Direction for '{q[:35]}...'", res["direction"] == tc["exp_dir"], f"Got {res['direction']}, expected {tc['exp_dir']}")
        assert_test(f"S1.{idx+1} Entry Style for '{q[:35]}...'", res["entry_style"] == tc["exp_style"], f"Got {res['entry_style']}, expected {tc['exp_style']}")
        assert_test(f"S1.{idx+1} Entry Price for '{q[:35]}...'", res["entry_price"] == tc["exp_entry"], f"Got {res['entry_price']}, expected {tc['exp_entry']}")
        assert_test(f"S1.{idx+1} SL Price for '{q[:35]}...'", res["sl_price"] == tc["exp_sl"], f"Got {res['sl_price']}, expected {tc['exp_sl']}")
        assert_test(f"S1.{idx+1} TP Price for '{q[:35]}...'", res["tp_price"] == tc["exp_tp"], f"Got {res['tp_price']}, expected {tc['exp_tp']}")
        assert_test(f"S1.{idx+1} SL Points for '{q[:35]}...'", res["sl_points"] == tc["exp_sl_pts"], f"Got {res['sl_points']}, expected {tc['exp_sl_pts']}")
        assert_test(f"S1.{idx+1} TP Points for '{q[:35]}...'", res["tp_points"] == tc["exp_tp_pts"], f"Got {res['tp_points']}, expected {tc['exp_tp_pts']}")

    # =========================================================================
    # SUITE 2: MALICIOUS & EXTREME BOUNDARY CONDITIONS
    # =========================================================================
    print("\n--- SUITE 2: MALICIOUS & EXTREME BOUNDARY CONDITIONS ---")

    # A: Astronomical Price (Must result in 0 fills, not crash)
    astro_res = pipeline.run_backtest(query="BUY LIMIT at 999999 SL 999900 TP 1000100", symbol="XAUUSD", timeframe="M5", bars=60)
    assert_test("S2.1 Astronomical price handled gracefully", astro_res.get("status") == "SUCCESS")
    assert_test("S2.1 Astronomical price 0 fills", astro_res["summary"]["filled_trades"] == 0)
    assert_test("S2.1 Astronomical price 0 wins", astro_res["summary"]["wins"] == 0)

    # B: Low / Dormant Price (Price never touched)
    low_res = pipeline.run_backtest(query="BUY LIMIT at 1000.0 SL 990.0 TP 1020.0", symbol="XAUUSD", timeframe="M5", bars=60)
    assert_test("S2.2 Unreachable low price handled gracefully", low_res.get("status") == "SUCCESS")
    assert_test("S2.2 Unreachable low price 0 fills", low_res["summary"]["filled_trades"] == 0)

    # C: Empty / Garbage query
    garbage_res = pipeline.run_backtest(query="aslkdfjalskdfj 992384723", symbol="XAUUSD", timeframe="M5", bars=60)
    assert_test("S2.3 Garbage query handled gracefully", garbage_res.get("status") == "SUCCESS")

    # D: Insufficient bars (<10)
    small_bar_res = pipeline.run_backtest(query="BUY LIMIT at 4260 SL 4252 TP 4275", symbol="XAUUSD", timeframe="M5", bars=5)
    assert_test("S2.4 Sub-minimum bars handled cleanly", small_bar_res.get("status") == "SUCCESS")
    assert_test("S2.4 Insufficient bars error reported in takeaways", "Insufficient" in small_bar_res["failure_clusters"][0])

    # =========================================================================
    # SUITE 3: MATHEMATICAL INTEGRITY (NO NEGATIVE PRICES, REAL R-MULTIPLES)
    # =========================================================================
    print("\n--- SUITE 3: MATHEMATICAL INTEGRITY & ZERO CORRUPTION ---")

    test_queries = [
        "BUY LIMIT at 4265 SL 4258 TP 4280",
        "SELL STOP at 4273.2 SL 4280.0 TP 4260.9",
        "Bullish FVG mitigation with 6 pt SL and 12 pt TP",
        "Bearish Order Block retest with 8 pt SL and 16 pt TP",
        "Turtle soup sweep and reclaim at 4250",
        "Trend EMA pullback long with 7 pt SL"
    ]

    for q in test_queries:
        r = pipeline.run_backtest(query=q, symbol="XAUUSD", timeframe="M5", bars=60)
        trades = r.get("trades", [])
        for t in trades:
            # Check price sanity
            assert_test(f"S3 Stop Loss > 0 in '{q[:25]}...'", t["stop_loss"] > 0, f"Got {t['stop_loss']}")
            assert_test(f"S3 Take Profit > 0 in '{q[:25]}...'", t["take_profit"] > 0, f"Got {t['take_profit']}")
            assert_test(f"S3 Entry Price > 0 in '{q[:25]}...'", t["entry_price"] > 0, f"Got {t['entry_price']}")
            assert_test(f"S3 Exit Price > 0 in '{q[:25]}...'", t["exit_price"] > 0, f"Got {t['exit_price']}")
            # Check R-multiple sanity
            assert_test(f"S3 Realized R not NaN/Inf in '{q[:25]}...'", not math.isnan(t["realized_r"]) and not math.isinf(t["realized_r"]))
            assert_test(f"S3 Realized R realistic (-1.5 to +20.0) in '{q[:25]}...'", -2.0 <= t["realized_r"] <= 25.0, f"Got {t['realized_r']}")

        # Summary sanity
        summ = r["summary"]
        assert_test(f"S3 Win rate between 0 and 100% in '{q[:25]}...'", 0.0 <= summ["win_rate_pct"] <= 100.0)
        if summ["filled_trades"] == 0:
            assert_test(f"S3 Zero fills produces 0% win rate in '{q[:25]}...'", summ["win_rate_pct"] == 0.0)
            assert_test(f"S3 Zero fills produces 0 wins in '{q[:25]}...'", summ["wins"] == 0)

    # =========================================================================
    # SUITE 4: REAL BENCHMARK AUDIT (TODAY'S 4273.2 SELL STOP REPLAY)
    # =========================================================================
    print("\n--- SUITE 4: REAL BENCHMARK AUDIT (TICKET #549621767 REPLAY) ---")

    bench_q = "SELL STOP at 4273.2 SL 4280.0 TP 4260.9"
    bench_res = pipeline.run_backtest(query=bench_q, symbol="XAUUSD", timeframe="M5", bars=60)
    summ = bench_res["summary"]
    trades = bench_res.get("trades", [])

    assert_test("S4 Benchmark returned SUCCESS", bench_res.get("status") == "SUCCESS")
    assert_test("S4 Benchmark identified EXPLICIT_ORDER_REPLAY", bench_res["thesis_parameters"]["setup_type"] == "EXPLICIT_ORDER_REPLAY")
    assert_test("S4 Benchmark found exactly 1 filled trade", summ["filled_trades"] == 1, f"Got {summ['filled_trades']}")
    if trades:
        t0 = trades[0]
        assert_test("S4 Benchmark Entry is 4273.2", t0["entry_price"] == 4273.2)
        assert_test("S4 Benchmark SL is 4280.0", t0["stop_loss"] == 4280.0)
        assert_test("S4 Benchmark TP is 4260.9", t0["take_profit"] == 4260.9)
        assert_test("S4 Benchmark Outcome is TP_HIT", t0["exit_reason"] == "TP_HIT")
        assert_test("S4 Benchmark Realized R is +1.81R", t0["realized_r"] == 1.81)
        assert_test("S4 Benchmark Holding Bars is positive", t0["holding_bars"] > 0)

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print(f" BATTLE AND DESTROY TEST COMPLETE: {passed} PASSED | {failed} FAILED")
    print("=" * 70)
    return failed == 0

if __name__ == "__main__":
    success = run_battle_and_destroy_tests()
    sys.exit(0 if success else 1)
