"""Data Harness for Pure LLM-Driven Backtesting.

Extracts raw MT5 historical OHLCV candle streams, spreads, and tick volume series.
Zero hardcoded pattern rules or FVG calculations - outputs pure chronological market tables.
"""

import os
import sys
import datetime
from typing import Dict, Any, List, Optional
import MetaTrader5 as mt5

FTMO_PATH = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"

class MT5DataHarness:
    """Extracts and formats raw MT5 candle data into token-efficient tables for LLM evaluation."""

    def __init__(self, ftmo_path: Optional[str] = None):
        self.ftmo_path = ftmo_path or FTMO_PATH

    def _ensure_mt5(self) -> bool:
        try:
            if mt5.terminal_info() is not None:
                return True
            if os.path.exists(self.ftmo_path):
                return mt5.initialize(path=self.ftmo_path)
            return mt5.initialize()
        except Exception:
            return False

    def get_timeframe_const(self, tf_str: str) -> int:
        tf = tf_str.upper().strip()
        if tf in ("M1", "1M"):
            return mt5.TIMEFRAME_M1
        elif tf in ("M5", "5M"):
            return mt5.TIMEFRAME_M5
        elif tf in ("M15", "15M"):
            return mt5.TIMEFRAME_M15
        elif tf in ("H1", "1H"):
            return mt5.TIMEFRAME_H1
        elif tf in ("H4", "4H"):
            return mt5.TIMEFRAME_H4
        elif tf in ("D1", "1D"):
            return mt5.TIMEFRAME_D1
        return mt5.TIMEFRAME_M5

    def fetch_candle_window(self, symbol: str = "XAUUSD", timeframe: str = "M5", bars: int = 60, offset: int = 0) -> Dict[str, Any]:
        """Pulls raw OHLCV bars from MT5 and formats them into a clean tabular representation."""
        self._ensure_mt5()
        sym = symbol.strip().upper()
        tf_const = self.get_timeframe_const(timeframe)

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
