"""
Multi-Timeframe Structure Analyst and Supply & Demand Order Block Engine.
Evaluates H1, M15, M5 alignment and calculates Daily Pivots + Order Block zones via MT5.
"""

import logging
from typing import Dict, Any, List
import MetaTrader5 as mt5

LOG = logging.getLogger("alpha.tradingagents.mtf")

class MultiTimeframeAnalyst:
    """Analyzes H4, H1, M15, and M5 candle structures for full 4-timeframe trend alignment."""

    def analyze_mtf(self, symbol: str) -> Dict[str, Any]:
        """Fetch H4, H1, M15, M5 candles and calculate granular 4-timeframe trend & indicator breakdown."""
        res = {
            "symbol": symbol,
            "h4_trend": "NEUTRAL",
            "h1_trend": "NEUTRAL",
            "m15_trend": "NEUTRAL",
            "m5_trend": "NEUTRAL",
            "alignment": "MIXED_TIMEFRAMES",
            "h4_rsi": 50.0,
            "h1_rsi": 50.0,
            "m15_rsi": 50.0,
            "m5_rsi": 50.0,
            "h4_ema20": 0.0,
            "h4_ema50": 0.0,
            "h1_ema20": 0.0,
            "h1_ema50": 0.0,
            "m15_ema20": 0.0,
            "m15_ema50": 0.0,
            "m5_ema20": 0.0,
            "m5_ema50": 0.0,
            "formatted_4tf": "H4(NEUTRAL) H1(NEUTRAL) M15(NEUTRAL) M5(NEUTRAL) -> MIXED_TIMEFRAMES"
        }

        try:
            if not mt5.initialize():
                return res

            tf_map = [
                ("h4", mt5.TIMEFRAME_H4),
                ("h1", mt5.TIMEFRAME_H1),
                ("m15", mt5.TIMEFRAME_M15),
                ("m5", mt5.TIMEFRAME_M5),
            ]

            bull_count = 0.0
            bear_count = 0.0

            for prefix, tf in tf_map:
                rates = mt5.copy_rates_from_pos(symbol, tf, 0, 40)
                if rates is not None and len(rates) >= 20:
                    closes = [r['close'] for r in rates]
                    curr_p = closes[-1]
                    ema20 = sum(closes[-20:]) / 20.0
                    ema50 = sum(closes[-min(len(closes), 50):]) / min(len(closes), 50)
                    
                    # RSI(14) calculation
                    diffs = [closes[i] - closes[i-1] for i in range(1, len(closes))]
                    gains = [d if d > 0 else 0 for d in diffs[-14:]]
                    losses = [-d if d < 0 else 0 for d in diffs[-14:]]
                    avg_gain = sum(gains) / 14.0 if gains else 0.0001
                    avg_loss = sum(losses) / 14.0 if losses else 0.0001
                    rs = avg_gain / (avg_loss if avg_loss > 0 else 0.0001)
                    rsi14 = round(100.0 - (100.0 / (1.0 + rs)), 1)

                    if curr_p > ema20 > ema50:
                        trend = "BULLISH"
                        bull_count += 1.0
                    elif curr_p < ema20 < ema50:
                        trend = "BEARISH"
                        bear_count += 1.0
                    elif curr_p > ema20:
                        trend = "BULLISH_BIAS"
                        bull_count += 0.5
                    elif curr_p < ema20:
                        trend = "BEARISH_BIAS"
                        bear_count += 0.5
                    else:
                        trend = "NEUTRAL"

                    res[f"{prefix}_trend"] = trend
                    res[f"{prefix}_rsi"] = rsi14
                    res[f"{prefix}_ema20"] = round(ema20, 3)
                    res[f"{prefix}_ema50"] = round(ema50, 3)

            # Determine 4TF Confluence
            if bull_count >= 3.0:
                res["alignment"] = "4TF_STRONG_BULLISH_CONFLUENCE"
            elif bear_count >= 3.0:
                res["alignment"] = "4TF_STRONG_BEARISH_CONFLUENCE"
            elif bull_count > bear_count and bull_count >= 2.0:
                res["alignment"] = "4TF_BULLISH_LEANING"
            elif bear_count > bull_count and bear_count >= 2.0:
                res["alignment"] = "4TF_BEARISH_LEANING"
            else:
                res["alignment"] = "MIXED_TIMEFRAMES"

            res["formatted_4tf"] = (
                f"H4({res['h4_trend']}) H1({res['h1_trend']}) M15({res['m15_trend']}) M5({res['m5_trend']}) -> {res['alignment']}"
            )

        except Exception as err:
            LOG.error(f"4TF calculation error for {symbol}: {err}")

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
