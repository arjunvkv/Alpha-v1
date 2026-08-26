"""Market data providers for Daemon v2 (DAEMON_V2_SPEC.md section 9).

SimulatedProvider replays scripted ticks for tests and dry runs.
LiveMT5Provider talks to MetaTrader5 with LAZY import so this module stays
import-safe on headless machines without an MT5 terminal.
"""

import time


class SimulatedProvider:
    """Replays a script of tick dicts; repeats the last one when exhausted."""

    def __init__(self, script=None):
        self._script = list(script or [])
        self._index = 0
        self.last_data_ts = time.time()

    def get_account(self):
        return {"balance": 100000.0, "equity": 100000.0,
                "margin_used": 0.0, "free_margin": 100000.0,
                "currency": "USD"}

    def get_positions(self):
        return []

    def get_market_view(self, symbol):
        if not self._script:
            raise RuntimeError("SimulatedProvider has empty script")
        idx = min(self._index, len(self._script) - 1)
        self._index += 1
        return {"symbol": symbol, "tick": dict(self._script[idx])}


class LiveMT5Provider:
    """Real terminal provider. Import of MetaTrader5 is deferred until
    construction so unit tests never require the package."""

    def __init__(self, symbols=None):
        import MetaTrader5 as mt5  # noqa: lazy - only on live path
        self._mt5 = mt5
        # PIN TO FTMO TERMINAL (2026-08-24): dual MT5 installs caused bare
        # initialize() to bind the unauthorized generic terminal while the
        # operator logged into the FTMO one -> every start failed (-6 auth).
        _FTMO_TERMINAL = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
        import os as _os
        ok = mt5.initialize(
            path=_FTMO_TERMINAL if _os.path.exists(_FTMO_TERMINAL) else None
        )
        if not ok:
            raise RuntimeError("MetaTrader5 initialize failed: %s"
                               % mt5.last_error())
        self.symbols = list(symbols or [])
        for sym in self.symbols:
            mt5.symbol_select(sym, True)
        self.last_data_ts = time.time()

    def get_account(self):
        info = self._mt5.account_info()
        if info is None:
            raise RuntimeError("account_info returned None")
        self.last_data_ts = time.time()
        return {
            "login": info.login,
            "balance": info.balance,
            "equity": info.equity,
            "margin_used": info.margin,
            "free_margin": info.margin_free,
            "currency": info.currency,
        }

    def get_positions(self):
        positions = self._mt5.positions_get() or []
        self.last_data_ts = time.time()
        out = []
        for p in positions:
            ptype = 1 if p.type == self._mt5.POSITION_TYPE_BUY else -1
            symbol_info = self._mt5.symbol_info(p.symbol)
            point = symbol_info.point if symbol_info else 0.01
            entry = p.price_open
            current = p.price_current
            out.append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "direction": "long" if ptype == 1 else "short",
                "volume": p.volume,
                "entry": entry,
                "current": current,
                "sl": p.sl,
                "tp": p.tp,
                "pnl": p.profit,
            })
        return out
