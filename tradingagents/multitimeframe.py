"""
Multi-Timeframe Structure Analyst and Supply & Demand Order Block Engine.
Evaluates H1, M15, M5 alignment and calculates Daily Pivots + Order Block zones via MT5.
"""

import logging
from typing import Dict, Any, List
import MetaTrader5 as mt5

LOG = logging.getLogger("alpha.tradingagents.mtf")

class MultiTimeframeAnalyst:
    """Analyzes H1, M15, and M5 candle structures for trend alignment."""

    def analyze_mtf(self, symbol: str) -> Dict[str, Any]:
        """Fetch H1, M15, M5 candles and calculate trend alignment matrix."""
        res = {
            "symbol": symbol,
            "h1_trend": "NEUTRAL",
            "m15_trend": "NEUTRAL",
            "m5_trend": "NEUTRAL",
            "alignment": "MIXED",
            "h1_rsi": 50.0,
            "m15_rsi": 50.0,
            "m5_rsi": 50.0,
        }

        try:
            if not mt5.initialize():
                return res

            # H1 Analysis
            h1_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 30)
            if h1_rates is not None and len(h1_rates) >= 20:
                h1_closes = [r['close'] for r in h1_rates]
                h1_ema20 = sum(h1_closes[-20:]) / 20.0
                h1_ema50 = sum(h1_closes) / len(h1_closes)
                h1_last = h1_closes[-1]
                h1_trend = "BULLISH" if h1_last > h1_ema20 > h1_ema50 else ("BEARISH" if h1_last < h1_ema20 < h1_ema50 else "NEUTRAL")
                res["h1_trend"] = h1_trend

            # M15 Analysis
            m15_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 30)
            if m15_rates is not None and len(m15_rates) >= 20:
                m15_closes = [r['close'] for r in m15_rates]
                m15_ema20 = sum(m15_closes[-20:]) / 20.0
                m15_last = m15_closes[-1]
                res["m15_trend"] = "BULLISH" if m15_last > m15_ema20 else ("BEARISH" if m15_last < m15_ema20 else "NEUTRAL")

            # M5 Analysis
            m5_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 30)
            if m5_rates is not None and len(m5_rates) >= 20:
                m5_closes = [r['close'] for r in m5_rates]
                m5_ema20 = sum(m5_closes[-20:]) / 20.0
                m5_last = m5_closes[-1]
                res["m5_trend"] = "BULLISH" if m5_last > m5_ema20 else ("BEARISH" if m5_last < m5_ema20 else "NEUTRAL")

            # Overall Alignment Matrix
            h1 = res["h1_trend"]
            m15 = res["m15_trend"]
            m5 = res["m5_trend"]

            if h1 == "BULLISH" and m15 == "BULLISH" and m5 == "BULLISH":
                res["alignment"] = "BULLISH_ALIGNED"
            elif h1 == "BEARISH" and m15 == "BEARISH" and m5 == "BEARISH":
                res["alignment"] = "BEARISH_ALIGNED"
            elif h1 == m15 and h1 != "NEUTRAL":
                res["alignment"] = f"{h1}_STRONG"
            else:
                res["alignment"] = "MIXED"

        except Exception as err:
            LOG.error(f"MTF calculation error for {symbol}: {err}")

        return res


class OrderBlockEngine:
    """Calculates Daily Pivot Points, Support/Resistance zones, and Order Blocks."""

    def calculate_levels(self, symbol: str) -> Dict[str, Any]:
        """Compute Daily High/Low, Pivot Points, and Supply/Demand Order Blocks."""
        levels = {
            "symbol": symbol,
            "daily_high": 0.0,
            "daily_low": 0.0,
            "pivot_point": 0.0,
            "support_s1": 0.0,
            "resistance_r1": 0.0,
            "demand_zone": "N/A",
            "supply_zone": "N/A",
        }

        try:
            if not mt5.initialize():
                return levels

            d1_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 1, 1)
            if d1_rates is not None and len(d1_rates) > 0:
                high = d1_rates[0]['high']
                low = d1_rates[0]['low']
                close = d1_rates[0]['close']

                pp = round((high + low + close) / 3.0, 2)
                s1 = round((2.0 * pp) - high, 2)
                r1 = round((2.0 * pp) - low, 2)

                levels["daily_high"] = round(high, 2)
                levels["daily_low"] = round(low, 2)
                levels["pivot_point"] = pp
                levels["support_s1"] = s1
                levels["resistance_r1"] = r1

                # Supply / Demand Order Blocks based on D1 High/Low buffers
                buf = 2.5 if "XAU" in symbol else 0.05
                levels["demand_zone"] = f"{round(low, 2)} - {round(low + buf, 2)}"
                levels["supply_zone"] = f"{round(high - buf, 2)} - {round(high, 2)}"

        except Exception as err:
            LOG.error(f"Order block calculation error for {symbol}: {err}")

        return levels
