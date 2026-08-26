import os
import time
import datetime
import logging
import MetaTrader5 as mt5

LOG = logging.getLogger("alpha.world_market")

FTMO_PATH = r"C:\Program Files\FTMO MetaTrader 5\terminal64.exe"

class IntradayInstitutionalEngine:
    """
    Institutional Data Stream for 5m to 4h Trade Horizons:
    1. Session Clock (London/NY Overlap vs Asian consolidation)
    2. ADR(20) Expansion Capacity (% Daily Range Used)
    3. Session Open Anchors (London Open 07:00 UTC & NY Open 13:00 UTC)
    4. Live Tick Velocity Index (ticks/min order flow intensity)
    5. Gold/Silver Ratio (GSR) Intermarket Arbitrage
    """
    def __init__(self):
        self._ensure_mt5()

    def _ensure_mt5(self):
        try:
            if not mt5.initialize():
                if os.path.exists(FTMO_PATH):
                    mt5.initialize(path=FTMO_PATH)
        except Exception as err:
            LOG.error(f"MT5 initialization in IntradayInstitutionalEngine failed: {err}")

    def get_session_status(self) -> dict:
        """Evaluates current UTC hour for global institutional session windows."""
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        hour = now_utc.hour
        
        if 13 <= hour < 17:
            session_name = "LONDON_NY_OVERLAP"
            desc = "Peak Institutional Volume & Momentum Window"
        elif 7 <= hour < 13:
            session_name = "LONDON_SESSION"
            desc = "London Institutional Liquidity Window"
        elif 13 <= hour < 21:
            session_name = "NEW_YORK_SESSION"
            desc = "US Institutional Session"
        else:
            session_name = "ASIAN_SESSION"
            desc = "Asian Session Range / Consolidation Window"

        return {
            "session": session_name,
            "description": desc,
            "utc_time": now_utc.strftime("%H:%M UTC")
        }

    def get_adr_metrics(self, symbol: str) -> dict:
        """Calculates 20-day Average Daily Range (ADR20) and Current % Range Used."""
        try:
            self._ensure_mt5()
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 21)
            if rates is None or len(rates) < 2:
                return {"adr_20": 0.0, "today_range": 0.0, "pct_used": 0.0, "status": "N/A"}

            # Calculate 20-day average daily range (excluding today's incomplete candle)
            past_rates = rates[:-1]
            daily_ranges = [r['high'] - r['low'] for r in past_rates]
            adr_20 = sum(daily_ranges) / len(daily_ranges) if daily_ranges else 1.0

            # Today's incomplete candle range
            today_candle = rates[-1]
            today_range = today_candle['high'] - today_candle['low']
            pct_used = (today_range / adr_20) * 100.0 if adr_20 > 0 else 0.0

            if pct_used > 85.0:
                capacity_status = "EXHAUSTED (>85% Used)"
            elif pct_used > 60.0:
                capacity_status = "MODERATE (60-85% Used)"
            else:
                capacity_status = "HIGH_CAPACITY (<60% Used)"

            return {
                "adr_20": round(adr_20, 2),
                "today_range": round(today_range, 2),
                "pct_used": round(pct_used, 1),
                "capacity_status": capacity_status
            }
        except Exception as err:
            LOG.error(f"ADR calculation failed for {symbol}: {err}")
            return {"adr_20": 0.0, "today_range": 0.0, "pct_used": 0.0, "capacity_status": "N/A"}

    def get_session_anchors(self, symbol: str) -> dict:
        """Finds London Open (07:00 UTC) and NY Open (13:00 UTC) price levels."""
        try:
            self._ensure_mt5()
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            # Fetch last 24 H1 candles
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 24)
            if rates is None or len(rates) == 0:
                return {"london_open": "N/A", "ny_open": "N/A"}

            sym_info = mt5.symbol_info(symbol)
            live_ask = sym_info.ask if sym_info else 0.0

            london_open = "N/A"
            ny_open = "N/A"

            for r in rates:
                dt = datetime.datetime.fromtimestamp(r['time'], tz=datetime.timezone.utc)
                if dt.date() == now_utc.date():
                    if dt.hour == 7 and london_open == "N/A":
                        london_open = round(r['open'], 2)
                    elif dt.hour == 13 and ny_open == "N/A":
                        ny_open = round(r['open'], 2)

            lon_dist = f"{(live_ask - london_open):+.2f}" if isinstance(london_open, float) and live_ask > 0 else "N/A"
            ny_dist = f"{(live_ask - ny_open):+.2f}" if isinstance(ny_open, float) and live_ask > 0 else "N/A"

            return {
                "london_open": london_open,
                "london_open_dist": lon_dist,
                "ny_open": ny_open,
                "ny_open_dist": ny_dist
            }
        except Exception as err:
            LOG.error(f"Session anchors failed for {symbol}: {err}")
            return {"london_open": "N/A", "ny_open": "N/A"}

    def get_tick_velocity(self, symbol: str) -> dict:
        """Measures MT5 tick execution speed per minute (ticks/min)."""
        try:
            self._ensure_mt5()
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 1)
            if rates is not None and len(rates) > 0:
                tick_vol = int(rates[0]['tick_volume'])
                if tick_vol > 150:
                    status = "HIGH_INSTITUTIONAL_BURST"
                elif tick_vol > 80:
                    status = "ELEVATED_VELOCITY"
                else:
                    status = "NORMAL_VELOCITY"
                return {"ticks_per_min": tick_vol, "status": status}
            return {"ticks_per_min": 0, "status": "NORMAL_VELOCITY"}
        except Exception as err:
            LOG.error(f"Tick velocity failed for {symbol}: {err}")
            return {"ticks_per_min": 0, "status": "N/A"}

    def get_gsr_ratio(self) -> dict:
        """Calculates real-time Gold/Silver Ratio (GSR = XAUUSD / XAGUSD)."""
        try:
            self._ensure_mt5()
            gold_info = mt5.symbol_info("XAUUSD")
            silver_info = mt5.symbol_info("XAGUSD")
            if gold_info and silver_info and silver_info.ask > 0:
                gsr = gold_info.ask / silver_info.ask
                if gsr > 80.0:
                    status = "SILVER_HISTORICALLY_CHEAP (GSR > 80)"
                elif gsr < 65.0:
                    status = "GOLD_HISTORICALLY_CHEAP (GSR < 65)"
                else:
                    status = "BALANCED_RANGE (65-80)"
                return {"gsr": round(gsr, 2), "status": status}
            return {"gsr": 0.0, "status": "N/A"}
        except Exception as err:
            LOG.error(f"GSR ratio calculation failed: {err}")
            return {"gsr": 0.0, "status": "N/A"}
