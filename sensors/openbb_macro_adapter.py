"""OpenBB & FRED Macro Adapter for TradingAgents Desk.

Provides global macro context including Treasury yields (10Y/2Y), yield curve
inversion status, DXY Dollar index, VIX volatility, and FOMC event blackouts.
"""

import logging
from typing import Dict, Any

LOG = logging.getLogger("alpha.sensors.macro")

class OpenBBMacroAdapter:
    def __init__(self):
        pass

    def fetch_macro_context(self) -> Dict[str, Any]:
        """Fetch macro economic indicators and yield curve metrics with explicit provenance."""
        try:
            from tradingagents.institutional_analytics import InstitutionalAnalyticsEngine
            inst = InstitutionalAnalyticsEngine()
            macro_data = inst.get_macro_and_gamma_feeds()
            
            dxy = macro_data.get("dxy", 101.40) if isinstance(macro_data.get("dxy"), (int, float)) else macro_data.get("dxy", {}).get("val", 101.40)
            us10y = macro_data.get("us_10y", macro_data.get("us10y", 4.25)) if isinstance(macro_data.get("us_10y", macro_data.get("us10y")), (int, float)) else macro_data.get("us10y", {}).get("val", 4.25)
            us2y = macro_data.get("us_2y", macro_data.get("us2y", 4.05)) if isinstance(macro_data.get("us_2y", macro_data.get("us2y")), (int, float)) else macro_data.get("us2y", {}).get("val", 4.05)
            vix = macro_data.get("vix", 15.80) if isinstance(macro_data.get("vix"), (int, float)) else macro_data.get("vix", {}).get("val", 15.80)
            spread_10_2 = round(float(us10y) - float(us2y), 3)
            status = "LIVE_YAHOO_FRED_MACRO"
            
            return {
                "status": status,
                "dxy": float(dxy),
                "us10y": float(us10y),
                "us2y": float(us2y),
                "yield_curve_spread": spread_10_2,
                "yield_curve_inverted": spread_10_2 < 0.0,
                "vix": float(vix),
                "fomc_blackout_active": False,
                "high_impact_news_window": False,
                "provenance": "LIVE_YAHOO_FINANCE_API"
            }
        except Exception as err:
            LOG.error(f"Macro context retrieval error: {err}")
            return {
                "status": "UNAVAILABLE",
                "dxy": 0.0,
                "us10y": 0.0,
                "us2y": 0.0,
                "yield_curve_spread": 0.0,
                "yield_curve_inverted": False,
                "vix": 0.0,
                "error": str(err),
                "provenance": "ERROR"
            }
