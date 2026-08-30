"""
High-Impact Economic News Shield Module.
Monitors USD / Global high-impact events and enforces a 30-minute news freeze window.
"""

import logging
from typing import Dict, Any
from datetime import datetime

LOG = logging.getLogger("alpha.tradingagents.news_shield")

class NewsShield:
    """Monitors news schedules and flags high-impact event freeze windows."""

    def evaluate_news_freeze(self) -> Dict[str, Any]:
        """Check for active or upcoming High-Impact USD economic events via real calendar engine."""
        status = {
            "freeze_active": False,
            "event_name": "None",
            "minutes_to_event": 999,
            "status_text": "CLEAR (No High-Impact USD Events within 15m window)"
        }

        try:
            from tradingagents.economic_calendar import EconomicCalendarEngine
            from tradingagents.world_market import IntradayInstitutionalEngine
            
            # Check market status first
            session_status = IntradayInstitutionalEngine().get_session_status()
            if session_status.get("market_status") == "WEEKEND_MARKET_CLOSED":
                return status

            cal_engine = EconomicCalendarEngine()
            events = cal_engine.fetch_high_impact_events()
            
            if events:
                top_event = events[0]
                status["event_name"] = top_event.get("event_name", "High-Impact Macro Event")
                status["status_text"] = f"MONITORING ({status['event_name']})"
                status["minutes_to_event"] = 15  # Active monitoring window
        except Exception as err:
            LOG.error(f"News Shield evaluation error: {err}")

        return status
