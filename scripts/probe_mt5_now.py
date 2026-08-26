"""Direct MT5 probe - fulfills [ALPHA SYSTEM START] 'probe account/prices'."""
import json
import MetaTrader5 as mt5

out = {}
try:
    ok = mt5.initialize()
    out["initialize"] = bool(ok)
    if ok:
        acc = mt5.account_info()
        out["account"] = {
            "login": getattr(acc, "login", None),
            "server": getattr(acc, "server", None),
            "balance": getattr(acc, "balance", None),
            "equity": getattr(acc, "equity", None),
            "margin": getattr(acc, "margin", None),
            "free_margin": getattr(acc, "free_margin", None),
        } if acc else None
        for sym in ("XAUUSD", "XPTUSD", "XAGUSD"):
            info = mt5.symbol_info(sym)
            tick = mt5.symbol_info_tick(sym)
            out[sym] = {
                "bid": getattr(tick, "bid", None),
                "ask": getattr(tick, "ask", None),
                "spread_points": getattr(info, "spread", None),
                "trade_mode": getattr(info, "trade_mode", None),
                "visible": getattr(info, "visible", None),
            }
        pos = mt5.positions_get()
        out["open_positions"] = len(pos) if pos else 0
        mt5.shutdown()
except Exception as e:
    out["error"] = repr(e)
print(json.dumps(out, indent=1, default=str))
