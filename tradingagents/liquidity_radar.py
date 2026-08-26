import os
import time
import datetime
import logging
import MetaTrader5 as mt5
from typing import Dict, Any, List

LOG = logging.getLogger("alpha.liquidity_radar")
FTMO_PATH = r"C:\Program Files\FTMO MetaTrader 5\terminal64.exe"

class LiquidityRadarEngine:
    """
    Real-Time Liquidity Radar Engine:
    Tracks Asian Session High/Low (00:00-07:00 UTC) & Yesterday High/Low pools.
    Detects institutional liquidity sweeps (Bull/Bear Traps) for 5m-4h trade setups.
    """
    def __init__(self):
        self._ensure_mt5()

    def _ensure_mt5(self):
        try:
            if not mt5.initialize():
                if os.path.exists(FTMO_PATH):
                    mt5.initialize(path=FTMO_PATH)
        except Exception as err:
            LOG.error(f"MT5 init failed in LiquidityRadarEngine: {err}")

    def get_symbol_liquidity(self, symbol: str) -> Dict[str, Any]:
        """Calculates live Asian & Yesterday liquidity pools and checks active sweeps."""
        try:
            self._ensure_mt5()
            sym = symbol.upper()
            tick = mt5.symbol_info_tick(sym)
            if not tick:
                return {
                    "asian_high": "N/A", "asian_low": "N/A",
                    "yest_high": "N/A", "yest_low": "N/A",
                    "sweep_status": "NORMAL_RANGE",
                    "trap_warning": "CLEAR"
                }

            live_ask = tick.ask
            live_bid = tick.bid
            now_utc = datetime.datetime.now(datetime.timezone.utc)

            # 1. Yesterday High / Low
            d1_rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, 3)
            yest_high = 0.0
            yest_low = 0.0
            if d1_rates is not None and len(d1_rates) >= 2:
                yest_high = round(float(d1_rates[-2]['high']), 2)
                yest_low = round(float(d1_rates[-2]['low']), 2)

            # 2. Asian Session High / Low (00:00 - 07:00 UTC)
            h1_rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 24)
            asian_high = 0.0
            asian_low = 0.0
            if h1_rates is not None:
                asian_candles = []
                for r in h1_rates:
                    dt = datetime.datetime.fromtimestamp(r['time'], tz=datetime.timezone.utc)
                    if dt.date() == now_utc.date() and 0 <= dt.hour < 7:
                        asian_candles.append(r)
                if asian_candles:
                    asian_high = round(float(max([c['high'] for c in asian_candles])), 2)
                    asian_low = round(float(min([c['low'] for c in asian_candles])), 2)

            # Detect Liquidity Sweeps (Price broke above Asian/Yesterday High or below Low)
            sweep_status = "IN_RANGE"
            trap_warning = "CLEAR"

            if asian_high > 0 and live_ask > asian_high:
                sweep_status = f"ASIAN_HIGH_SWEPT (+{(live_ask - asian_high):.2f})"
                trap_warning = "BULL_TRAP_RISK (Institutional Liquidity Grab above Asian High)"
            elif asian_low > 0 and live_bid < asian_low:
                sweep_status = f"ASIAN_LOW_SWEPT (-{(asian_low - live_bid):.2f})"
                trap_warning = "BEAR_TRAP_RISK (Institutional Liquidity Grab below Asian Low)"
            elif yest_high > 0 and live_ask > yest_high:
                sweep_status = f"YEST_HIGH_SWEPT (+{(live_ask - yest_high):.2f})"
                trap_warning = "BULL_TRAP_RISK (Liquidity Sweep above Yesterday's High)"
            elif yest_low > 0 and live_bid < yest_low:
                sweep_status = f"YEST_LOW_SWEPT (-{(yest_low - live_bid):.2f})"
                trap_warning = "BEAR_TRAP_RISK (Liquidity Sweep below Yesterday's Low)"

            return {
                "asian_high": asian_high if asian_high > 0 else "N/A",
                "asian_low": asian_low if asian_low > 0 else "N/A",
                "yest_high": yest_high if yest_high > 0 else "N/A",
                "yest_low": yest_low if yest_low > 0 else "N/A",
                "sweep_status": sweep_status,
                "trap_warning": trap_warning
            }
        except Exception as err:
            LOG.error(f"Liquidity radar check failed for {symbol}: {err}")
            return {
                "asian_high": "N/A", "asian_low": "N/A",
                "yest_high": "N/A", "yest_low": "N/A",
                "sweep_status": "N/A", "trap_warning": "CLEAR"
            }
