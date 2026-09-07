"""
High-Impact Economic News Shield Module.
Monitors USD / Global high-impact events and enforces a 30-minute news freeze window.
"""

import logging
from typing import Dict, Any
from datetime import datetime

LOG = logging.getLogger("alpha.tradingagents.news_shield")

class NewsShield:
    """Monitors news schedules and flags high-impact event freeze windows via CatalystArbiterEngine."""

    def evaluate_news_freeze(self, symbol: str = "XAUUSD") -> Dict[str, Any]:
        """Check for active or upcoming High-Impact economic events via live CatalystArbiterEngine."""
        try:
            from tradingagents.catalyst_arbiter import CatalystArbiterEngine
            arb = CatalystArbiterEngine()
            reg = arb.get_market_regime(symbol)
            raw = reg.get("raw_metrics", {})
            next_ev = raw.get("next_scheduled_event")
            
            freeze_active = reg.get("regime") == "MACRO_EVENT_ACTIVE"
            event_name = next_ev.get("title", "None") if next_ev else "None"
            mins_to_event = next_ev.get("minutes_away", 999.0) if next_ev else 999.0
            
            return {
                "freeze_active": freeze_active,
                "regime": reg.get("regime"),
                "pricing_power": reg.get("pricing_power"),
                "event_name": event_name,
                "minutes_to_event": mins_to_event,
                "status_text": f"{reg.get('regime')} ({reg.get('pricing_power')}) - Next: {event_name} in {mins_to_event}m" if next_ev else f"{reg.get('regime')} ({reg.get('pricing_power')}) - No high-impact events today",
                "directive": reg.get("actionable_directive")
            }
        except Exception as err:
            LOG.error(f"News Shield evaluation error: {err}")
            return {
                "freeze_active": False,
                "event_name": "None",
                "minutes_to_event": 999,
                "status_text": "CLEAR (Fallback)",
                "directive": "TRADE_BY_STRUCTURE"
            }

