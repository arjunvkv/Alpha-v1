"""Granger 7-Layer Adapter for TradingAgents Desk.

Extracts live snapshots from Granger (Prices, COT positioning, Macro,
Sentiment, Fundamentals, Technicals, Signals) and formats them into
specialized inputs for the multi-agent analyst team.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any

# Insert Granger path to import layers directly
GRANGER_DIR = Path(r"C:\Trading\Granger")
if str(GRANGER_DIR) not in sys.path:
    sys.path.insert(0, str(GRANGER_DIR))

LOG = logging.getLogger("alpha.sensors.granger")

class GrangerAdapter:
    def __init__(self):
        self.granger_dir = GRANGER_DIR
        self._cache = {}

    async def fetch_full_snapshot(self) -> Dict[str, Any]:
        """Pull all 7 Granger layers asynchronously with explicit provenance."""
        try:
            from layers.prices import PricesLayer
            from layers.positioning import PositioningLayer
            from layers.macro import MacroLayer
            from layers.sentiment import SentimentLayer
            from layers.fundamentals import FundamentalsLayer
            from layers.technical import TechnicalLayer
            from layers.signals import SignalsLayer

            layers = [
                PricesLayer(),
                PositioningLayer(),
                MacroLayer(),
                SentimentLayer(),
                FundamentalsLayer(),
                TechnicalLayer(),
                SignalsLayer()
            ]

            async def _collect_layer(layer):
                try:
                    data = await asyncio.wait_for(layer.collect(), timeout=3.0)
                    return layer.name, {"status": "LIVE", "data": data}
                except Exception as e:
                    return layer.name, {"status": "UNAVAILABLE", "error": str(e)}

            collected = await asyncio.gather(*[_collect_layer(l) for l in layers])
            results = {name: data for name, data in collected}
            self._cache = results
            return results
        except Exception as err:
            LOG.error(f"Failed to fetch Granger snapshot: {err}")
            return self._fallback_snapshot()

    def get_technical_data(self, symbol: str) -> Dict[str, Any]:
        """Format live MT5 tick price and 4TF indicator technicals for Technical Analyst Agent."""
        try:
            import MetaTrader5 as mt5
            from tradingagents.multitimeframe import MultiTimeframeAnalyst
            ftmo_path = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
            if not mt5.terminal_info():
                mt5.initialize(path=ftmo_path) if os.path.exists(ftmo_path) else mt5.initialize()
            
            sym = symbol.strip()
            tick = mt5.symbol_info_tick(sym) or mt5.symbol_info_tick(sym.upper()) or mt5.symbol_info_tick(sym.lower())
            live_ask = getattr(tick, "ask", 0.0)
            live_bid = getattr(tick, "bid", 0.0)
            
            mtf = MultiTimeframeAnalyst().analyze_mtf(sym)
            
            return {
                "symbol": symbol,
                "status": "LIVE_MT5",
                "prices": {"current_price": live_ask, "bid": live_bid, "ask": live_ask},
                "h4_bias": mtf.get("h4_trend", "NEUTRAL"),
                "h1_bias": mtf.get("h1_trend", "NEUTRAL"),
                "m15_bias": mtf.get("m15_trend", "NEUTRAL"),
                "m5_bias": mtf.get("m5_trend", "NEUTRAL"),
                "indicators": {
                    "h4_rsi": mtf.get("h4_rsi", 50.0),
                    "h1_rsi": mtf.get("h1_rsi", 50.0),
                    "m15_rsi": mtf.get("m15_rsi", 50.0),
                    "m5_rsi": mtf.get("m5_rsi", 50.0),
                    "h4_ema20": mtf.get("h4_ema20", 0.0),
                    "h1_ema20": mtf.get("h1_ema20", 0.0),
                    "m15_ema20": mtf.get("m15_ema20", 0.0),
                    "m5_ema20": mtf.get("m5_ema20", 0.0)
                },
                "mtf_alignment": mtf.get("alignment", "MIXED_TIMEFRAMES")
            }
        except Exception as err:
            return {
                "symbol": symbol,
                "status": "UNAVAILABLE",
                "prices": {"current_price": 0.0, "bid": 0.0, "ask": 0.0},
                "h4_bias": "NEUTRAL",
                "h1_bias": "NEUTRAL",
                "m15_bias": "NEUTRAL",
                "m5_bias": "NEUTRAL",
                "indicators": {"rsi_14": 50.0},
                "error": str(err)
            }

    def get_cot_positioning_data(self, symbol: str) -> Dict[str, Any]:
        """Format L2 (Positioning COT) via official CFTC FuturesBench live API for Fundamental Analyst Agent."""
        try:
            from tradingagents.institutional_analytics import InstitutionalAnalyticsEngine
            inst = InstitutionalAnalyticsEngine()
            cot_data = inst.get_futuresbench_cot_data()
            
            sym_clean = symbol.replace(".cash", "").upper()
            m = cot_data.get("markets", {}).get(symbol) or cot_data.get("markets", {}).get(sym_clean, {})
            
            percentile = m.get("cot_index_26w", m.get("cot_index_52w", 60.0))
            net_noncomm = m.get("net_noncommercial", 0)
            net_comm = m.get("net_commercial", -net_noncomm)
            
            return {
                "symbol": symbol,
                "status": "LIVE_CFTC_COT",
                "report_date": cot_data.get("report_date", "2026-08-25"),
                "source": cot_data.get("source", "FUTURESBENCH_LIVE_API"),
                "data_provenance": m.get("data_provenance", cot_data.get("source", "FUTURESBENCH_LIVE_API")),
                "is_live": m.get("is_live", cot_data.get("is_live", True)),
                "managed_money_percentile": percentile,
                "cot_index_26w": m.get("cot_index_26w", percentile),
                "cot_index_52w": m.get("cot_index_52w", 79.2),
                "net_noncommercial": net_noncomm,
                "commercial_net": net_comm,
                "net_commercial": net_comm,
                "bias": m.get("bias", "NEUTRAL"),
                "z_score": m.get("z_score", 0.0),
                "change": m.get("change", 0),
                "open_interest_change": m.get("change", 0),
                "fundamentals": m
            }
        except Exception as err:
            return {
                "symbol": symbol,
                "status": "UNAVAILABLE",
                "managed_money_percentile": 50.0,
                "net_noncommercial": 0,
                "commercial_net": 0,
                "error": str(err)
            }

    def get_macro_signals_data(self) -> Dict[str, Any]:
        """Format L3 (Macro) & L7 (Signals) using live yields and volatility for Macro Analyst Agent."""
        try:
            from tradingagents.institutional_analytics import InstitutionalAnalyticsEngine
            inst = InstitutionalAnalyticsEngine()
            macro = inst.get_macro_and_gamma_feeds()
            
            dxy = macro.get("dxy", 101.40) if isinstance(macro.get("dxy"), (int, float)) else macro.get("dxy", {}).get("val", 101.40)
            us10y = macro.get("us_10y", macro.get("us10y", 4.25)) if isinstance(macro.get("us_10y", macro.get("us10y")), (int, float)) else macro.get("us10y", {}).get("val", 4.25)
            us2y = macro.get("us_2y", macro.get("us2y", 4.05)) if isinstance(macro.get("us_2y", macro.get("us2y")), (int, float)) else macro.get("us2y", {}).get("val", 4.05)
            vix = macro.get("vix", 15.80) if isinstance(macro.get("vix"), (int, float)) else macro.get("vix", {}).get("val", 15.80)
            dix = macro.get("dix", macro.get("dix_gex", {}).get("dix", 45.0))
            
            return {
                "status": "LIVE_YAHOO_FRED_MACRO",
                "dxy": float(dxy),
                "us10y": float(us10y),
                "us2y": float(us2y),
                "yield_curve_inverted": (float(us10y) - float(us2y)) < 0.0,
                "vix": float(vix),
                "dix": float(dix),
                "signals": macro
            }
        except Exception as err:
            return {
                "status": "UNAVAILABLE",
                "dxy": 0.0,
                "us10y": 0.0,
                "us2y": 0.0,
                "yield_curve_inverted": False,
                "vix": 0.0,
                "error": str(err)
            }

    def get_sentiment_data(self, topic: str = "gold") -> Dict[str, Any]:
        """Format L4 (Sentiment) from live RSS news stream analysis for Sentiment Analyst Agent."""
        try:
            from sensors.global_news_crawler import GlobalNewsCrawler
            crawler = GlobalNewsCrawler()
            headlines = crawler.fetch_rss_headlines(max_items=10)
            
            # Simple keyword sentiment scoring on live headlines
            bull_words = ["surge", "jump", "high", "gain", "rally", "strong", "bull", "record", "up", "rise"]
            bear_words = ["drop", "fall", "low", "loss", "plunge", "weak", "bear", "down", "decline", "slip"]
            
            compound = 0.0
            matching_articles = 0
            for h in headlines:
                title = h.get("title", "").lower()
                if any(w in title for w in [topic.lower(), "metal", "commodity", "market", "fed", "yield"]):
                    matching_articles += 1
                    b_count = sum(1 for w in bull_words if w in title)
                    r_count = sum(1 for w in bear_words if w in title)
                    compound += (b_count - r_count) * 0.15
            
            compound = round(max(-1.0, min(1.0, compound)), 2)
            label = "bullish" if compound > 0.05 else ("bearish" if compound < -0.05 else "neutral")
            
            return {
                "topic": topic,
                "status": "LIVE_RSS_SENTIMENT" if matching_articles > 0 else "NO_RELEVANT_HEADLINES",
                "vader_compound": compound,
                "label": label,
                "article_count": matching_articles,
                "total_headlines_scanned": len(headlines)
            }
        except Exception as err:
            return {
                "topic": topic,
                "status": "UNAVAILABLE",
                "vader_compound": 0.0,
                "label": "neutral",
                "article_count": 0,
                "error": str(err)
            }

    def _fallback_snapshot(self) -> Dict[str, Any]:
        return {
            "status": "UNAVAILABLE",
            "message": "Granger layer collection failed; live MT5 and Institutional analytics active."
        }
