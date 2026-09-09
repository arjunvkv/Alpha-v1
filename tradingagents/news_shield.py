"""
High-Impact Economic News Shield Module.
Monitors USD / Global high-impact events and enforces a 30-minute news freeze window.
"""

import logging
from typing import Dict, Any
from datetime import datetime, timezone

LOG = logging.getLogger("alpha.tradingagents.news_shield")

class NewsShield:
    """Monitors news schedules and flags high-impact event freeze windows directly via cached calendar."""

    def evaluate_news_freeze(self, symbol: str = "XAUUSD") -> Dict[str, Any]:
        """Check for active or upcoming High-Impact economic events via cached economic calendar."""
        try:
            from tradingagents.catalyst_arbiter import CatalystArbiterEngine
            events = CatalystArbiterEngine().fetch_calendar_events()
            now_utc = datetime.now(timezone.utc)
            freeze_active = False
            next_ev = None
            min_diff = float("inf")

            for ev in events:
                if ev.get("impact") in ("High", "Holiday"):
                    d_str = ev.get("date", "")
                    if not d_str:
                        continue
                    try:
                        ev_dt = datetime.fromisoformat(d_str).astimezone(timezone.utc)
                        diff_m = (ev_dt - now_utc).total_seconds() / 60.0
                        if 0 <= diff_m < min_diff:
                            min_diff = diff_m
                            next_ev = {
                                "title": ev.get("title"),
                                "country": ev.get("country"),
                                "impact": ev.get("impact"),
                                "minutes_away": round(diff_m, 1)
                            }
                        if -15.0 <= diff_m <= 15.0:
                            freeze_active = True
                    except Exception:
                        continue

            event_name = next_ev.get("title", "None") if next_ev else "None"
            mins_to_event = next_ev.get("minutes_away", 999.0) if next_ev else 999.0

            return {
                "freeze_active": freeze_active,
                "event_name": event_name,
                "minutes_to_event": mins_to_event,
                "status_text": f"Next: {event_name} in {mins_to_event}m" if next_ev else "No high-impact events today"
            }
        except Exception as err:
            LOG.error(f"News Shield evaluation error: {err}")
            return {
                "freeze_active": False,
                "event_name": "None",
                "minutes_to_event": 999,
                "status_text": "CLEAR (Fallback)"
            }

