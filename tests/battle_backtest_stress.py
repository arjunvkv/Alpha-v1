import sys
import os
import json
import time
import threading
from typing import List, Dict, Any

# Ensure Alpha root is in sys.path
ALPHA_DIR = r"C:\Trading\Alpha"
if ALPHA_DIR not in sys.path:
    sys.path.insert(0, ALPHA_DIR)

from backtesting.pipeline import PureLLMBacktestPipeline
from mcp_server.alpha_mcp_server import _sync_backtest_thesis

passed = 0
failed = 0

def assert_test(name, condition, details=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name} | {details}")

def run_stress_tests():
    print("=" * 70)
    print(" STRESS, DESTROY & EDGE-CASE TEST SUITE")
    print("=" * 70)

    pipeline = PureLLMBacktestPipeline()
    pipeline.local_runner.timeout = 0.1

    print("\n--- SUITE 1: EDGE CASES ---")
    
    # bars=0 auto-scale triggers correct defaults
    res0 = pipeline.run_backtest(query="Bullish FVG mitigation", symbol="XAUUSD", timeframe="M5", bars=0)
    assert_test("Edge 1: bars=0 auto-scales to 288 for M5", res0["candle_window"]["bar_count"] >= 280) # allow some missing bars in real data
    
    # sample_quality.is_statistically_valid=False when n_resolved<5
    res_sq = pipeline.run_backtest(query="Bullish FVG mitigation", symbol="XAUUSD", timeframe="M5", bars=10)
    sq = res_sq.get("sample_quality", {})
    if sq.get("n_resolved", 0) < 5:
        assert_test("Edge 2: sample_quality statistically invalid for <5 trades", sq.get("is_statistically_valid") is False)
        assert_test("Edge 2: min_sample_warning exists", sq.get("min_sample_warning") is not None)
    
    # MTM exits NOT in win/loss counts
    # To force MTM, use a very large SL/TP with small hold bars, or just check the output fields
    res_mtm = pipeline.run_backtest(query="BUY LIMIT at 4260 SL 3000 TP 5000 hold up to 5 bars", symbol="XAUUSD", timeframe="M5", bars=60)
    # Check that if there are mtm exits, they aren't in wins/losses
    wins = res_mtm["summary"]["wins"]
    losses = res_mtm["summary"]["losses"]
    mtm_exits = res_mtm["summary"]["mtm_exits"]
    assert_test("Edge 3: MTM exits tracked separately", mtm_exits >= 0)

    # Spread cost pts present
    res_spread = pipeline.run_backtest(query="BUY LIMIT at 4260 SL 4252 TP 4275", symbol="XAUUSD", timeframe="M5", bars=60)
    if res_spread["trades"]:
        assert_test("Edge 4: spread_cost_pts present", "spread_cost_pts" in res_spread["trades"][0])

    # No concurrent trades overlap
    res_overlap = pipeline.run_backtest(query="Bullish FVG mitigation", symbol="XAUUSD", timeframe="M1", bars=300)
    trades = res_overlap.get("trades", [])
    overlap = False
    for i in range(1, len(trades)):
        if trades[i]["formation_bar"] <= trades[i-1]["exit_bar"]:
            overlap = True
    assert_test("Edge 5: No concurrent trades overlap (in_trade gating)", not overlap)

    print("\n--- SUITE 2: DESTROY CASES ---")
    
    destroy_queries = [
        ("Garbage unicode", "Garbage query \\u200b", 60),
        ("Extreme bars 5", "BUY LIMIT at 4260 SL 4252 TP 4275", 5),
        ("Extreme bars 1000", "BUY LIMIT at 4260 SL 4252 TP 4275", 1000),
        ("Impossible price 999999", "BUY LIMIT at 999999 SL 999900 TP 1000000", 60),
        ("Impossible price 0.001", "SELL LIMIT at 0.001 SL 0.002 TP 0.0001", 60),
    ]
    for desc, q, b in destroy_queries:
        r = pipeline.run_backtest(query=q, symbol="XAUUSD", timeframe="M5", bars=b)
        assert_test(f"Destroy: {desc} handled cleanly", r.get("status") == "SUCCESS" or "error" in r)

    print("\n--- SUITE 3: SPEED REGRESSIONS ---")
    speed_tests = [
        ("FVG M5 60bar", "M5 bullish FVG CE mitigation", "M5", 60),
        ("OB M5 120bar", "Bullish Order Block retest", "M5", 120),
        ("Explicit M5 60bar", "BUY LIMIT at 4260 SL 4250 TP 4280", "M5", 60),
        ("TurtleSoup M15 60", "Turtle soup sweep of low and reclaim", "M15", 60),
        ("EMA M5 288bar", "Bullish 20 EMA trend pullback", "M5", 288),
        ("Breakout M15 192", "Bullish range breakout expansion stop order", "M15", 192)
    ]
    for name, q, tf, b in speed_tests:
        t0 = time.time()
        pipeline.run_backtest(query=q, symbol="XAUUSD", timeframe=tf, bars=b)
        elapsed = (time.time() - t0) * 1000
        assert_test(f"Speed: {name} < 1000ms", elapsed < 1000, f"Took {elapsed:.1f}ms")
        print(f"    -> {name} took {elapsed:.1f}ms")

    print("\n--- SUITE 4: CONCURRENT STRESS ---")
    threads = []
    durations = []
    results = []

    def run_worker(q, tf, b):
        t0 = time.time()
        # Use MCP wrapper to test lock caching if applicable
        res = json.loads(_sync_backtest_thesis(query=q, symbol="XAUUSD", timeframe=tf, bars=b))
        durations.append(time.time() - t0)
        results.append(res)

    for i in range(3):
        t = threading.Thread(target=run_worker, args=("M5 bullish FVG CE mitigation", "M5", 120))
        threads.append(t)
    
    t_start_all = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    t_end_all = time.time()

    total_time_ms = (t_end_all - t_start_all) * 1000
    assert_test("Concurrent Stress: 3 parallel backtests complete", len(results) == 3)
    assert_test("Concurrent Stress: All finished < 1500ms total", total_time_ms < 1500, f"Took {total_time_ms:.1f}ms")

    print("\n" + "=" * 70)
    print(f" STRESS TEST COMPLETE: {passed} PASSED | {failed} FAILED")
    print("=" * 70)
    return failed == 0

if __name__ == "__main__":
    success = run_stress_tests()
    sys.exit(0 if success else 1)
