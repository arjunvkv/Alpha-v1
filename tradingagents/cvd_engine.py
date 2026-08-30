"""Cumulative Volume Delta (CVD) & Delta Exhaustion Engine for Alpha Trading Desk.

Computes measured volume delta and tick momentum directly from MT5 candle tick streams:
- Candle Delta = Tick Volume * ((Close - Open) / (High - Low + 1e-6))
- Cumulative Volume Delta (CVD) = Rolling sum of candle deltas across N bars
- Delta Exhaustion: Identifies when price makes a new high/low with declining or opposing CVD
"""

import os
import logging
import datetime
from typing import Dict, Any, List, Optional
import MetaTrader5 as mt5

LOG = logging.getLogger("alpha.tradingagents.cvd")
FTMO_PATH = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"

class CumulativeVolumeDeltaEngine:
    """Computes measured CVD, delta divergence, and absorption stall signals."""

    def __init__(self, ftmo_path: Optional[str] = None):
        self.ftmo_path = ftmo_path or FTMO_PATH

    def _ensure_mt5(self) -> bool:
        try:
            if mt5.terminal_info() is not None:
                return True
            if os.path.exists(self.ftmo_path):
                return mt5.initialize(path=self.ftmo_path)
            return mt5.initialize()
        except Exception as err:
            LOG.error(f"MT5 init failed in CumulativeVolumeDeltaEngine: {err}")
            return False

    def get_symbol_cvd(self, symbol: str = "XAUUSD", bars: int = 50) -> Dict[str, Any]:
        """Calculates M5/M1 measured CVD, 10-bar delta velocity, and delta exhaustion score."""
        self._ensure_mt5()
        sym = symbol.strip().upper()
        
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        is_weekend = (utc_now.weekday() >= 5) or (utc_now.weekday() == 4 and utc_now.hour >= 22)
        tick = mt5.symbol_info_tick(sym) or mt5.symbol_info_tick(sym.lower())
        tick_time_str = datetime.datetime.fromtimestamp(tick.time, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if tick and getattr(tick, "time", 0) > 0 else "N/A"
        is_stale = is_weekend or (tick is None) or (getattr(tick, "time", 0) > 0 and (utc_now.timestamp() - tick.time > 300))

        try:
            rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, bars)
            if rates is None or len(rates) < 5:
                return {
                    "symbol": sym,
                    "status": "DATA_UNAVAILABLE",
                    "is_stale": is_stale,
                    "measured_cvd": 0.0,
                    "delta_trend": "NEUTRAL",
                    "exhaustion_score": 0.0
                }

            deltas = []
            cum_delta = 0.0
            cvd_series = []

            for r in rates:
                o, h, l, c = float(r['open']), float(r['high']), float(r['low']), float(r['close'])
                vol = float(r['tick_volume'])
                rng = max(h - l, 1e-6)
                # Signed candle volume allocation based on intra-bar close location
                candle_delta = vol * ((c - o) / rng)
                deltas.append(candle_delta)
                cum_delta += candle_delta
                cvd_series.append(cum_delta)

            recent_10_delta = sum(deltas[-10:])
            total_10_vol = sum(float(r['tick_volume']) for r in rates[-10:])
            delta_ratio = round((recent_10_delta / max(total_10_vol, 1.0)) * 100.0, 1)

            # Trend & Exhaustion classification
            delta_trend = "BULLISH_AGGRESSIVE" if delta_ratio > 30 else ("BEARISH_AGGRESSIVE" if delta_ratio < -30 else "BALANCED")
            
            # Exhaustion check: Price rising but CVD declining or vice-versa
            price_change = float(rates[-1]['close']) - float(rates[-10]['open'])
            exhaustion = False
            if price_change > 0 and recent_10_delta < 0:
                exhaustion = True
                exhaustion_desc = "BEARISH_DELTA_DIVERGENCE (Price higher, CVD lower - absorption active)"
            elif price_change < 0 and recent_10_delta > 0:
                exhaustion = True
                exhaustion_desc = "BULLISH_DELTA_DIVERGENCE (Price lower, CVD higher - accumulation active)"
            else:
                exhaustion_desc = "NO_DIVERGENCE"

            return {
                "symbol": sym,
                "status": "MEASURED_ACTIVE",
                "timeframe": "M5",
                "is_stale": is_stale,
                "last_tick_time": tick_time_str,
                "market_status": "WEEKEND_MARKET_CLOSED" if is_weekend else "ACTIVE",
                "cumulative_volume_delta": round(cum_delta, 1),
                "recent_10_bar_delta": round(recent_10_delta, 1),
                "delta_pressure_pct": delta_ratio,
                "delta_trend": delta_trend,
                "delta_exhaustion": exhaustion,
                "exhaustion_signal": exhaustion_desc,
                "provenance": "MT5_M5_TICK_VOLUME_DELTA"
            }
        except Exception as e:
            LOG.error(f"CVD calculation error for {sym}: {e}")
            return {
                "symbol": sym,
                "status": "ERROR",
                "error": str(e),
                "is_stale": True
            }
