"""Multi-Timeframe Fair Value Gap (FVG) & Imbalance Engine for Alpha Trading Desk.

Computes institutional Fair Value Gaps (FVG) across H4, H1, M15, and M5 timeframes
using real MT5 OHLC rate arrays:
- Bullish FVG (Imbalance): Low of Candle[i] > High of Candle[i-2]
- Bearish FVG (Imbalance): High of Candle[i] < Low of Candle[i-2]
- Consequent Encroachment (CE): 50% midpoint of the imbalance range
- Mitigation Tracking: Checks whether subsequent candles have penetrated the FVG
"""

import os
import logging
import datetime
from typing import Dict, Any, List, Optional
import MetaTrader5 as mt5

LOG = logging.getLogger("alpha.tradingagents.fvg")
FTMO_PATH = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"

TIMEFRAMES = [
    ("H4", mt5.TIMEFRAME_H4, 30),
    ("H1", mt5.TIMEFRAME_H1, 40),
    ("M15", mt5.TIMEFRAME_M15, 50),
    ("M5", mt5.TIMEFRAME_M5, 60),
]

class FairValueGapEngine:
    """Calculates multi-timeframe Fair Value Gaps and mitigation levels with zero bloat."""

    def __init__(self, ftmo_path: Optional[str] = None):
        self.ftmo_path = ftmo_path or FTMO_PATH
        self._ensure_mt5()

    def _ensure_mt5(self) -> bool:
        try:
            if mt5.terminal_info() is not None:
                return True
            if os.path.exists(self.ftmo_path):
                return mt5.initialize(path=self.ftmo_path)
            return mt5.initialize()
        except Exception as err:
            LOG.error(f"MT5 init check failed in FairValueGapEngine: {err}")
            return False

    def get_symbol_fvg_matrix(self, symbol: str) -> Dict[str, Any]:
        """Scans H4, H1, M15, and M5 for active and unmitigated Fair Value Gaps."""
        self._ensure_mt5()
        sym = symbol.strip().upper()
        
        tick = mt5.symbol_info_tick(sym) or mt5.symbol_info_tick(sym.lower())
        sym_info = mt5.symbol_info(sym) or mt5.symbol_info(sym.lower())
        point = getattr(sym_info, "point", 0.01) if sym_info else 0.01
        digits = getattr(sym_info, "digits", 2) if sym_info else 2
        live_price = getattr(tick, "ask", 0.0) if tick else 0.0

        tf_results = {}
        nearest_fvg = None
        min_distance = float("inf")

        for tf_name, tf_const, lookback in TIMEFRAMES:
            try:
                rates = mt5.copy_rates_from_pos(sym, tf_const, 0, lookback)
                if rates is None or len(rates) < 3:
                    tf_results[tf_name] = {"unmitigated_count": 0, "fvgs": []}
                    continue

                fvgs = []
                n = len(rates)
                
                # Scan 3-candle patterns from oldest to newest (excluding candle 0 which is still forming)
                for i in range(2, n - 1):
                    c_prior = rates[i - 2]
                    c_current = rates[i]
                    
                    high_prior = float(c_prior['high'])
                    low_prior = float(c_prior['low'])
                    high_curr = float(c_current['high'])
                    low_curr = float(c_current['low'])

                    # 1. Bullish FVG: Low of candle i > High of candle i-2
                    if low_curr > high_prior:
                        gap_bottom = high_prior
                        gap_top = low_curr
                        gap_size = round(gap_top - gap_bottom, digits)
                        ce_level = round((gap_top + gap_bottom) / 2.0, digits)

                        # Check subsequent candles for mitigation
                        mitigated = False
                        fill_pct = 0.0
                        lowest_subsequent = min([float(r['low']) for r in rates[i+1:]]) if i+1 < n else live_price
                        
                        if lowest_subsequent <= gap_bottom:
                            mitigated = True
                            fill_pct = 100.0
                        elif lowest_subsequent < gap_top:
                            filled_range = gap_top - lowest_subsequent
                            fill_pct = round(min(100.0, max(0.0, (filled_range / max(gap_size, 0.0001)) * 100.0)), 1)
                            if fill_pct >= 85.0:
                                mitigated = True

                        fvg_entry = {
                            "type": "BULLISH_FVG",
                            "timeframe": tf_name,
                            "top": gap_top,
                            "bottom": gap_bottom,
                            "consequent_encroachment": ce_level,
                            "size": gap_size,
                            "size_pts": int(gap_size / point) if point > 0 else int(gap_size * 100),
                            "candle_time": datetime.datetime.fromtimestamp(rates[i-1]['time'], datetime.timezone.utc).strftime("%Y-%m-%d %H:%M"),
                            "mitigated": mitigated,
                            "fill_pct": fill_pct,
                            "status": "MITIGATED" if mitigated else ("PARTIALLY_FILLED" if fill_pct > 0 else "FRESH")
                        }
                        fvgs.append(fvg_entry)

                        if not mitigated and live_price > 0:
                            dist = abs(live_price - ce_level)
                            if dist < min_distance:
                                min_distance = dist
                                nearest_fvg = fvg_entry

                    # 2. Bearish FVG: High of candle i < Low of candle i-2
                    elif high_curr < low_prior:
                        gap_top = low_prior
                        gap_bottom = high_curr
                        gap_size = round(gap_top - gap_bottom, digits)
                        ce_level = round((gap_top + gap_bottom) / 2.0, digits)

                        # Check subsequent candles for mitigation
                        mitigated = False
                        fill_pct = 0.0
                        highest_subsequent = max([float(r['high']) for r in rates[i+1:]]) if i+1 < n else live_price
                        
                        if highest_subsequent >= gap_top:
                            mitigated = True
                            fill_pct = 100.0
                        elif highest_subsequent > gap_bottom:
                            filled_range = highest_subsequent - gap_bottom
                            fill_pct = round(min(100.0, max(0.0, (filled_range / max(gap_size, 0.0001)) * 100.0)), 1)
                            if fill_pct >= 85.0:
                                mitigated = True

                        fvg_entry = {
                            "type": "BEARISH_FVG",
                            "timeframe": tf_name,
                            "top": gap_top,
                            "bottom": gap_bottom,
                            "consequent_encroachment": ce_level,
                            "size": gap_size,
                            "size_pts": int(gap_size / point) if point > 0 else int(gap_size * 100),
                            "candle_time": datetime.datetime.fromtimestamp(rates[i-1]['time'], datetime.timezone.utc).strftime("%Y-%m-%d %H:%M"),
                            "mitigated": mitigated,
                            "fill_pct": fill_pct,
                            "status": "MITIGATED" if mitigated else ("PARTIALLY_FILLED" if fill_pct > 0 else "FRESH")
                        }
                        fvgs.append(fvg_entry)

                        if not mitigated and live_price > 0:
                            dist = abs(live_price - ce_level)
                            if dist < min_distance:
                                min_distance = dist
                                nearest_fvg = fvg_entry

                unmitigated = [f for f in fvgs if not f["mitigated"]]
                tf_results[tf_name] = {
                    "unmitigated_count": len(unmitigated),
                    "total_detected": len(fvgs),
                    "unmitigated_fvgs": unmitigated[-3:]  # Keep latest 3 for clean payload
                }
            except Exception as err:
                LOG.error(f"FVG scan failed for {sym} {tf_name}: {err}")
                tf_results[tf_name] = {"unmitigated_count": 0, "error": str(err)}

        summary_str = "No active unmitigated FVGs nearby"
        if nearest_fvg:
            summary_str = f"{nearest_fvg['timeframe']} {nearest_fvg['type'].replace('_', ' ')} [{nearest_fvg['bottom']} - {nearest_fvg['top']}] (CE: {nearest_fvg['consequent_encroachment']}) [{nearest_fvg['status']}]"

        return {
            "symbol": sym,
            "live_price": live_price,
            "nearest_unmitigated_fvg": nearest_fvg,
            "summary": summary_str,
            "timeframes": tf_results
        }

    def get_fvg_summary_line(self, symbol: str) -> str:
        """Returns an ultra-compact single line for chat briefing stream without token bloat."""
        res = self.get_symbol_fvg_matrix(symbol)
        nearest = res.get("nearest_unmitigated_fvg")
        if not nearest:
            return "FVG: None nearby"
        
        tf = nearest.get("timeframe", "M15")
        f_type = "Bull" if "BULLISH" in nearest.get("type", "") else "Bear"
        return f"FVG: {tf} {f_type} [{nearest.get('bottom')}-{nearest.get('top')}] (CE: {nearest.get('consequent_encroachment')}) [{nearest.get('status')}]"

    # Clean method alias
    get_fvg_matrix = get_symbol_fvg_matrix
