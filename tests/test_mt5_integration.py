"""
Step 2 — Live MT5 integration test against FTMO terminal.
Safe: only places an order if autotrading is enabled AND account is demo.
Run: python tests/test_mt5_integration.py
"""

import sys
import time

sys.path.insert(0, r"C:\Trading\Alpha")
import MetaTrader5 as mt5

from config import MT5_TERMINAL_PATH, MT5_LOGIN, MT5_PASSWORD, MT5_SERVER

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name} {detail}")


print("=== MT5 Integration Test ===")

# 1. Initialize (launches terminal if needed)
kwargs = {}
if MT5_LOGIN:
    kwargs = {"login": int(MT5_LOGIN), "password": MT5_PASSWORD, "server": MT5_SERVER}
ok = mt5.initialize(path=MT5_TERMINAL_PATH, **kwargs) or mt5.initialize(**kwargs)
check("initialize", ok, str(mt5.last_error()))
if not ok:
    print("\nTerminal not reachable. Is FTMO MT5 installed/running?")
    sys.exit(1)

# 2. Terminal + account info
term = mt5.terminal_info()
check("terminal_info", term is not None)
if term:
    check("terminal connected to broker", term.connected)
    check("trade allowed in terminal", term.trade_allowed,
          "(enable AutoTrading button if False)")

acct = mt5.account_info()
check("account_info", acct is not None)
if acct:
    print(f"        account: {acct.login} @ {acct.server} | "
          f"balance ${acct.balance:,.2f} | leverage 1:{acct.leverage}")
    is_demo = "demo" in (acct.server or "").lower() or acct.trade_mode == 0
    check("account is DEMO (safe)", is_demo, f"server={acct.server}")

# 3. Market data — our instruments
for sym in ["XAGUSD", "XAUUSD", "XPTUSD"]:
    info = mt5.symbol_info(sym)
    if info and not info.visible:
        mt5.symbol_select(sym, True)
    tick = mt5.symbol_info_tick(sym)
    check(f"tick {sym}", tick is not None and tick.bid > 0,
          f"bid={getattr(tick, 'bid', None)}")
    if tick:
        print(f"        {sym}: bid={tick.bid} ask={tick.ask}")

# 4. Historical bars
rates = mt5.copy_rates_from_pos("XAGUSD", mt5.TIMEFRAME_M15, 0, 50)
check("M15 bars XAGUSD (50)", rates is not None and len(rates) == 50)

# 5. Order execution — ONLY on demo with autotrading enabled
if acct and is_demo and term and term.trade_allowed:
    tick = mt5.symbol_info_tick("XAGUSD")
    point = mt5.symbol_info("XAGUSD").point
    sl = tick.bid - 500 * point   # wide stop, tiny size
    tp = tick.bid + 500 * point
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": "XAGUSD",
        "volume": 0.01,
        "type": mt5.ORDER_TYPE_BUY,
        "price": tick.ask,
        "sl": round(sl, 3),
        "tp": round(tp, 3),
        "magic": 20260821,
        "comment": "Alpha:integration_test",
        "type_filling": mt5.ORDER_FILLING_IOC,
        "type_time": mt5.ORDER_TIME_GTC,
    }
    res = mt5.order_send(req)
    check("demo order_send executed", res is not None and res.retcode == mt5.TRADE_RETCODE_DONE,
          f"retcode={getattr(res, 'retcode', None)} comment={getattr(res, 'comment', '')}")
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"        filled ticket={res.order} @ {res.price}")
        time.sleep(1)
        # close it immediately
        pos = mt5.positions_get(ticket=res.order)
        if pos:
            close_req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": "XAGUSD",
                "volume": pos[0].volume,
                "type": mt5.ORDER_TYPE_SELL,
                "position": pos[0].ticket,
                "price": mt5.symbol_info_tick("XAGUSD").bid,
                "magic": 20260821,
                "comment": "Alpha:test_close",
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            cres = mt5.order_send(close_req)
            check("demo position closed", cres is not None
                  and cres.retcode == mt5.TRADE_RETCODE_DONE,
                  f"retcode={getattr(cres, 'retcode', None)}")
else:
    print("  SKIP  order execution (needs demo account + AutoTrading enabled)")

mt5.shutdown()
print(f"\n{'='*60}\nRESULTS: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
