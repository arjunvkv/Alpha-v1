"""Crowd and Liquidity Intelligence Engine for Alpha Trading Desk.

Extracts pure institutional order-flow telemetry from MT5 ticks and price action:
- spot_price, probe_high_watermark, probe_low_watermark
- retail_avg_entry (session volume-weighted accumulation zone)
- retail_long_pct_trail (rolling buyer vs seller volume percentage)
- bsl_clusters and ssl_clusters (resting Buy/Sell Stop Liquidity pools)
- displacement_pts_trail, probe_delta_trail, cum_cvd_trail, velocity_trail

Provides an in-situ reasoning helper to guide OpenCode deduction without bloating AGENTS.md.
"""

import time
import datetime
import logging
from typing import Dict, Any, List, Optional
import MetaTrader5 as mt5

LOG = logging.getLogger("alpha.crowd_liquidity")

class CrowdLiquidityEngine:
    """Computes pure numeric value trails for crowd entrapment, resting stops, and absorption."""

    def __init__(self):
        self._last_payload: Optional[Dict[str, Any]] = None
        self._last_time: float = 0.0
        self._cache_ttl_sec: float = 2.0

    def _ensure_mt5(self) -> bool:
        try:
            if mt5.terminal_info() is not None and getattr(mt5.terminal_info(), "connected", False):
                return True
            from tradingagents.mt5_connector import ensure_mt5_connected
            return ensure_mt5_connected(timeout=3000)
        except Exception as err:
            LOG.error(f"MT5 init failed in CrowdLiquidityEngine: {err}")
            return False

    def get_live_crowd_liquidity_payload(self, symbol: str = "XAUUSD") -> Dict[str, Any]:
        """Returns the lean, raw numeric value trails and in-situ helper."""
        now = time.time()
        if self._last_payload and (now - self._last_time) < self._cache_ttl_sec:
            return self._last_payload

        self._ensure_mt5()
        sym = symbol.strip().upper()

        helper_block = {
            "purpose": "Fills blindspots on crowd entrapment and institutional absorption to prevent premature exits or counter-trend fakes.",
            "guide": [
                "1. TRAP CHECK: If spot is below retail_avg_entry, retail longs are underwater fuel. Do not exit shorts on minor green wicks.",
                "2. ABSORPTION CHECK: If probe_delta decays to <=0 while displacement stays <0.5 pts, aggressive flow was absorbed by limit walls (rejection imminent).",
                "3. MAGNET CHECK: Compare probe_high_watermark to bsl_clusters[0]. If it fell short, liquidity was front-run, trapping late breakout chasers.",
                "4. ON-DEMAND PRECEDENT AUDIT: When vetting a setup at structure, call `graphiti-memory-mcp_graphiti_search_facts(patterns=[...])` to pull verified historical contrast pairs on-demand.",
                "5. STANDING ORDERS: Standard AGENTS.md rules govern all sizing (0.50-1.00L), structural stops (6-10 pts), Mode A targets (4-8 pts), and the Kinetic Breakeven Protocol."
            ]
        }

        try:
            rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 60)
            tick = mt5.symbol_info_tick(sym)
            if rates is None or len(rates) < 15 or tick is None:
                return {
                    "helper": helper_block,
                    "symbol": sym,
                    "status": "DATA_UNAVAILABLE"
                }

            spot = round(float(tick.bid), 2)
            highs = [float(r['high']) for r in rates]
            lows = [float(r['low']) for r in rates]
            closes = [float(r['close']) for r in rates]
            opens = [float(r['open']) for r in rates]
            vols = [float(r['tick_volume']) for r in rates]

            probe_high = round(max(highs[-12:]), 2)
            probe_low = round(min(lows[-12:]), 2)

            # Swing Detection for Resting Stop Clusters
            bsl_raw = []
            for i in range(2, len(rates) - 2):
                if highs[i] > highs[i-1] and highs[i] > highs[i+1] and highs[i] > highs[i-2] and highs[i] > highs[i+2]:
                    lvl = round(highs[i] + 0.35, 2)
                    if lvl > spot and lvl not in bsl_raw:
                        bsl_raw.append(lvl)
            bsl_raw.sort()
            bsl_clusters = bsl_raw[:3] if bsl_raw else [round(probe_high + 1.0, 2)]

            ssl_raw = []
            for i in range(2, len(rates) - 2):
                if lows[i] < lows[i-1] and lows[i] < lows[i+1] and lows[i] < lows[i-2] and lows[i] < lows[i+2]:
                    lvl = round(lows[i] - 0.35, 2)
                    if lvl < spot and lvl not in ssl_raw:
                        ssl_raw.append(lvl)
            ssl_raw.sort(reverse=True)
            ssl_clusters = ssl_raw[:3] if ssl_raw else [round(probe_low - 1.0, 2)]

            # 5-bar displacement trail
            displacement_pts_trail = [round(abs(closes[i] - opens[i]), 2) for i in range(-5, 0)]

            # 5-bar probe delta trail
            probe_delta_trail = [
                round(vols[i] * ((closes[i] - opens[i]) / max(highs[i] - lows[i], 1e-6)), 1)
                for i in range(-5, 0)
            ]

            # 5-bar velocity trail
            velocity_trail = [round(float(vols[i]), 1) for i in range(-5, 0)]

            # 5-bar cumulative volume delta trail
            cum_cvd_trail = []
            running_cvd = 0.0
            for i in range(len(rates)):
                d = vols[i] * ((closes[i] - opens[i]) / max(highs[i] - lows[i], 1e-6))
                running_cvd += d
                if i >= len(rates) - 5:
                    cum_cvd_trail.append(round(running_cvd, 1))

            # Session accumulation VWAP (retail average entry)
            tot_vol = sum(vols)
            retail_avg_entry = round(
                sum(closes[i] * vols[i] for i in range(len(rates))) / max(tot_vol, 1.0),
                2
            )

            # Retail long percentage trail across 5 rolling windows (5 bars each)
            chunks = [rates[-25:-20], rates[-20:-15], rates[-15:-10], rates[-10:-5], rates[-5:]]
            retail_long_pct_trail = []
            for chunk in chunks:
                b_vol = sum(r['tick_volume'] * ((r['close'] - r['low']) / max(r['high'] - r['low'], 1e-6)) for r in chunk)
                t_vol = sum(r['tick_volume'] for r in chunk)
                ratio = round(float((b_vol / max(t_vol, 1.0)) * 100.0), 1)
                retail_long_pct_trail.append(ratio)

            # Cluster density estimation in lots
            cluster_density_lots = [
                int(vols[-5] * 1.5) if len(vols) >= 5 else 850,
                int(vols[-3] * 2.1) if len(vols) >= 3 else 1400
            ]

            payload = {
                "helper": helper_block,
                "spot_price": spot,
                "probe_high_watermark": probe_high,
                "probe_low_watermark": probe_low,
                "retail_avg_entry": retail_avg_entry,
                "retail_long_pct_trail": retail_long_pct_trail,
                "bsl_clusters": bsl_clusters,
                "ssl_clusters": ssl_clusters,
                "cluster_density_lots": cluster_density_lots,
                "displacement_pts_trail": displacement_pts_trail,
                "probe_delta_trail": probe_delta_trail,
                "cum_cvd_trail": cum_cvd_trail,
                "velocity_trail": velocity_trail
            }

            self._last_payload = payload
            self._last_time = now
            return payload

        except Exception as err:
            LOG.error(f"Error calculating crowd liquidity payload: {err}")
            return {
                "helper": helper_block,
                "symbol": sym,
                "status": "ERROR",
                "error": str(err)
            }
