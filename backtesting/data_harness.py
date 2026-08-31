"""Data Harness for Pure LLM-Driven Backtesting.

Extracts raw MT5 historical OHLCV candle streams, spreads, and tick volume series.
Zero hardcoded pattern rules or FVG calculations - outputs pure chronological market tables.
"""

import os
import sys
import datetime
import threading
from typing import Dict, Any, List, Optional
import MetaTrader5 as mt5

FTMO_PATH = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
_MT5_LOCK = threading.Lock()

class MT5DataHarness:
    """Extracts and formats raw MT5 candle data into token-efficient tables for LLM evaluation."""

    def __init__(self, ftmo_path: Optional[str] = None):
        self.ftmo_path = ftmo_path or FTMO_PATH

    def _ensure_mt5(self) -> bool:
        with _MT5_LOCK:
            try:
                if mt5.terminal_info() is not None:
                    return True
                if os.path.exists(self.ftmo_path):
                    return mt5.initialize(path=self.ftmo_path)
                return mt5.initialize()
            except Exception:
                return False

    def get_timeframe_const(self, tf_str: str) -> int:
        raw = tf_str.upper().strip().replace(" ", "").replace("-", "").replace("_", "")
        if raw in ("M1", "1M", "1MIN", "1MINUTE"):
            return mt5.TIMEFRAME_M1
        elif raw in ("M2", "2M", "2MIN"):
            return mt5.TIMEFRAME_M2
        elif raw in ("M3", "3M", "3MIN"):
            return mt5.TIMEFRAME_M3
        elif raw in ("M4", "4M", "4MIN"):
            return mt5.TIMEFRAME_M4
        elif raw in ("M5", "5M", "5MIN", "5MINUTE"):
            return mt5.TIMEFRAME_M5
        elif raw in ("M6", "6M", "6MIN"):
            return mt5.TIMEFRAME_M6
        elif raw in ("M10", "10M", "10MIN"):
            return mt5.TIMEFRAME_M10
        elif raw in ("M12", "12M", "12MIN"):
            return mt5.TIMEFRAME_M12
        elif raw in ("M15", "15M", "15MIN", "15MINUTE"):
            return mt5.TIMEFRAME_M15
        elif raw in ("M20", "20M", "20MIN"):
            return mt5.TIMEFRAME_M20
        elif raw in ("M30", "30M", "30MIN", "30MINUTE"):
            return mt5.TIMEFRAME_M30
        elif raw in ("H1", "1H", "1HR", "1HOUR", "HOURLY"):
            return mt5.TIMEFRAME_H1
        elif raw in ("H2", "2H", "2HR", "2HOUR"):
            return mt5.TIMEFRAME_H2
        elif raw in ("H3", "3H", "3HR", "3HOUR"):
            return mt5.TIMEFRAME_H3
        elif raw in ("H4", "4H", "4HR", "4HOUR"):
            return mt5.TIMEFRAME_H4
        elif raw in ("H6", "6H", "6HR", "6HOUR"):
            return mt5.TIMEFRAME_H6
        elif raw in ("H8", "8H", "8HR", "8HOUR"):
            return mt5.TIMEFRAME_H8
        elif raw in ("H12", "12H", "12HR", "12HOUR"):
            return mt5.TIMEFRAME_H12
        elif raw in ("D1", "1D", "1DAY", "DAILY", "D"):
            return mt5.TIMEFRAME_D1
        elif raw in ("W1", "1W", "1WK", "1WEEK", "WEEKLY", "W"):
            return mt5.TIMEFRAME_W1
        elif raw in ("MN1", "1MN", "1MTH", "1MONTH", "MONTHLY", "MN"):
            return mt5.TIMEFRAME_MN1
        return mt5.TIMEFRAME_M5

    def fetch_candle_window(self, symbol: str = "XAUUSD", timeframe: str = "M5", bars: int = 60, offset: int = 0) -> Dict[str, Any]:
        """Pulls raw OHLCV bars from MT5 and formats them into a clean tabular representation."""
        self._ensure_mt5()
        sym = symbol.strip().upper()
        tf_const = self.get_timeframe_const(timeframe)

        with _MT5_LOCK:
            rates = mt5.copy_rates_from_pos(sym, tf_const, offset, bars)
        if rates is None or len(rates) == 0:
            return {
                "status": "DATA_UNAVAILABLE",
                "symbol": sym,
                "timeframe": timeframe,
                "bar_count": 0,
                "bars": [],
                "formatted_table": "No historical candle data available."
            }

        candle_list = []
        table_lines = [
            f"# Historical Candle Series for {sym} ({timeframe}) - {len(rates)} Bars",
            "| Bar # | UTC Timestamp | Open | High | Low | Close | Tick Vol | Spread (pts) |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        ]

        for idx, r in enumerate(rates):
            ts = datetime.datetime.fromtimestamp(r['time'], datetime.timezone.utc).strftime("%Y-%m-%d %H:%M")
            o, h, l, c = float(r['open']), float(r['high']), float(r['low']), float(r['close'])
            vol = int(r['tick_volume'])
            spread = int(r['spread'])

            candle_list.append({
                "bar_index": idx,
                "timestamp": ts,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "tick_volume": vol,
                "spread_pts": spread
            })

            table_lines.append(f"| {idx} | {ts} | {o:.2f} | {h:.2f} | {l:.2f} | {c:.2f} | {vol} | {spread} |")

        return {
            "status": "SUCCESS",
            "symbol": sym,
            "timeframe": timeframe,
            "bar_count": len(candle_list),
            "start_time": candle_list[0]["timestamp"],
            "end_time": candle_list[-1]["timestamp"],
            "bars": candle_list,
            "formatted_table": "\n".join(table_lines)
        }
