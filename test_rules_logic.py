import sys, types
sys.path.insert(0, r"C:\Trading\Alpha\daemon")
import daemon as D

# Build a daemon instance (connects to MT5, which is up) WITHOUT starting the loop.
d = D.AlphaDaemon()

print("=== RSI logic ===")
prices_up = [100 + i for i in range(20)]      # strong uptrend -> RSI should be high
prices_down = [200 - i for i in range(20)]    # strong downtrend -> RSI should be low
rsi_up = d._rsi(prices_up, 14)
rsi_down = d._rsi(prices_down, 14)
print(f"RSI uptrend  = {rsi_up:.2f}")
print(f"RSI downtrend= {rsi_down:.2f}")
assert rsi_up is not None and rsi_down is not None

print("\n=== rsi_below condition (needs buffer) ===")
d._ai_price_buf["XAUUSD"] = list(prices_down)   # RSI low
ok, why = d._eval_ai_conditions(
    [{"type": "rsi_below", "period": 14, "value": 50}], "ALL", "XAUUSD", 180.0, 40)
print(f"rsi_below(50) on downtrend buffer -> {ok}  ({why})")
assert ok is True

print("\n=== cross_above / cross_below ===")
d._ai_prev_price["XPT"] = 1889.0
ok_up, why_up = d._eval_ai_conditions(
    [{"type": "price_cross_above", "level": 1890.0}], "ALL", "XPT", 1891.0, 424)
print(f"cross_above 1890 (prev 1889 -> 1891) -> {ok_up}  ({why_up})")
assert ok_up is True

d._ai_prev_price["XPT"] = 1891.0
ok_dn, why_dn = d._eval_ai_conditions(
    [{"type": "price_cross_below", "level": 1890.0}], "ALL", "XPT", 1889.0, 424)
print(f"cross_below 1890 (prev 1891 -> 1889) -> {ok_dn}  ({why_dn})")
assert ok_dn is True

# cross must NOT fire without a real cross (prev already above level)
d._ai_prev_price["XPT"] = 1895.0
ok_no, why_no = d._eval_ai_conditions(
    [{"type": "price_cross_above", "level": 1890.0}], "ALL", "XPT", 1896.0, 424)
print(f"cross_above 1890 (prev 1895, already above) -> {ok_no}  ({why_no})")
assert ok_no is False

print("\nALL CONDITION LOGIC TESTS PASSED")
