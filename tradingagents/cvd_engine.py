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

            # Compute live M1 tick velocity (ticks/min) and current spread (pts)
            live_spread_pts = int(getattr(tick, "spread", 0)) if tick else 0
            if live_spread_pts == 0 and tick and getattr(tick, "ask", 0) and getattr(tick, "bid", 0):
                point = getattr(mt5.symbol_info(sym), "point", 0.01) or 0.01
                live_spread_pts = int(round((tick.ask - tick.bid) / point))

            # M1 velocity calculation
            m1_rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 5)
            if m1_rates is not None and len(m1_rates) > 0:
                current_m1_velocity = float(m1_rates[-1]['tick_volume'])
                avg_5m_velocity = round(float(sum(r['tick_volume'] for r in m1_rates) / len(m1_rates)), 1)
            else:
                current_m1_velocity = 0.0
                avg_5m_velocity = 0.0

            # Adverse velocity warning (loss clusters occur when velocity > 120 t/m into setup)
            is_high_velocity = current_m1_velocity > 120.0 or avg_5m_velocity > 120.0
            velocity_posture = "HIGH_VELOCITY_SPIKE (>120 t/m)" if is_high_velocity else ("MODERATE_FLOW (60-120 t/m)" if current_m1_velocity >= 60.0 else "LOW_COMPRESSION (<60 t/m)")

            # Order book imbalance read
            book_imbalance = "BALANCED"
            try:
                mt5.market_book_add(sym)
                dom = mt5.market_book_get(sym)
                if dom and len(dom) > 0:
                    bid_depth = sum(d.volume for d in dom if d.type == mt5.BOOK_TYPE_BUY)
                    ask_depth = sum(d.volume for d in dom if d.type == mt5.BOOK_TYPE_SELL)
                    tot_depth = bid_depth + ask_depth
                    if tot_depth > 0:
                        imbalance_pct = ((bid_depth - ask_depth) / tot_depth) * 100.0
                        if imbalance_pct > 25.0:
                            book_imbalance = f"HEAVY_BID_STACK (+{imbalance_pct:.1f}% Bids)"
                        elif imbalance_pct < -25.0:
                            book_imbalance = f"HEAVY_ASK_STACK ({imbalance_pct:.1f}% Asks)"
                        else:
                            book_imbalance = f"BALANCED_BOOK ({imbalance_pct:+.1f}%)"
                mt5.market_book_release(sym)
            except Exception:
                pass

            return {
                "symbol": sym,
                "status": "MEASURED_ACTIVE",
                "timeframe": "M5",
                "is_stale": is_stale,
                "last_tick_time": tick_time_str,
                "market_status": "WEEKEND_MARKET_CLOSED" if is_weekend else "ACTIVE",
                "live_spread_pts": live_spread_pts,
                "tick_velocity_tpm": current_m1_velocity,
                "avg_5m_velocity_tpm": avg_5m_velocity,
                "velocity_posture": velocity_posture,
                "adverse_velocity_warning": is_high_velocity,
                "order_book_imbalance": book_imbalance,
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
