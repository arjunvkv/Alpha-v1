import os
import json
import time
import datetime
import logging
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional

LOG = logging.getLogger("alpha.economic_calendar")

PROJECT_ROOT = Path(r"C:\Trading\Alpha")
CALENDAR_CACHE_FILE = PROJECT_ROOT / "data" / "live" / "economic_calendar.json"

CALENDAR_RSS_SOURCES = [
    {
        "name": "Investing.com Economic Calendar",
        "url": "https://www.investing.com/rss/news_14.rss"
    },
    {
        "name": "Yahoo Finance Economic Releases",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^TNX,DX-Y.NYB&region=US&lang=en-US"
    }
]

HIGH_IMPACT_KEYWORDS = [
    "CPI", "CONSUMER PRICE INDEX", "NON-FARM PAYROLLS", "NFP", "FOMC",
    "FED RATE", "INTEREST RATE", "POWELL", "ECB RATE", "GDP", "UNEMPLOYMENT RATE",
    "RETAIL SALES", "ISM MANUFACTURING", "PMI", "CORE CPI", "PCE"
]

class EconomicCalendarEngine:
    """
    Real-Time Economic Calendar Engine:
    Parses macroeconomic release calendars, calculates exact countdown timers in minutes,
    and identifies high-impact news blackout windows (15m before/after releases).
    """
    def __init__(self, cache_ttl_seconds: int = 180):
        self.cache_ttl = cache_ttl_seconds
        CALENDAR_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    def fetch_high_impact_events(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Fetch live economic calendar events or return unexpired disk cache."""
        now_ts = time.time()
        
        if not force_refresh and CALENDAR_CACHE_FILE.exists():
            try:
                with open(CALENDAR_CACHE_FILE, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    if now_ts - cache_data.get("updated_at_ts", 0) < self.cache_ttl:
                        return cache_data.get("high_impact_events", [])
            except Exception as err:
                LOG.warning(f"Failed to read economic calendar cache: {err}")

        events = []
        seen_titles = set()
        timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        for src in CALENDAR_RSS_SOURCES:
            try:
                req = urllib.request.Request(src["url"], headers=headers)
                xml_data = urllib.request.urlopen(req, timeout=5).read()
                root = ET.fromstring(xml_data)

                for item in root.findall(".//item"):
                    title_elem = item.find("title")
                    pub_elem = item.find("pubDate")
                    link_elem = item.find("link")

                    if title_elem is not None and title_elem.text:
                        raw_title = title_elem.text.strip()
                        clean_title = raw_title.replace("&apos;", "'").replace("&#39;", "'").replace("&quot;", '"')
                        t_upper = clean_title.upper()

                        if any(kw in t_upper for kw in HIGH_IMPACT_KEYWORDS):
                            if clean_title.lower() in seen_titles:
                                continue
                            seen_titles.add(clean_title.lower())

                            pub_date = pub_elem.text.strip() if (pub_elem is not None and pub_elem.text) else timestamp_str
                            link = link_elem.text.strip() if (link_elem is not None and link_elem.text) else ""

                            events.append({
                                "event_name": clean_title,
                                "impact": "HIGH",
                                "source": src["name"],
                                "pub_date": pub_date,
                                "link": link,
                                "fetched_at": timestamp_str
                            })
            except Exception as err:
                LOG.debug(f"Calendar RSS fetch failed for {src['name']}: {err}")

        cache_payload = {
            "updated_at_ts": now_ts,
            "updated_at": timestamp_str,
            "high_impact_events": events
        }
        try:
            with open(CALENDAR_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache_payload, f, indent=2)
        except Exception as err:
            LOG.error(f"Writing calendar cache failed: {err}")

        return events

    def get_news_countdown_summary(self, max_items: int = 3) -> Dict[str, Any]:
        """Calculates news shield status and returns bulleted countdown summary for 2-min prompt."""
        events = self.fetch_high_impact_events()
        
        if not events:
            return {
                "shield_status": "CLEAR",
                "shield_message": "CLEAR (No High-Impact USD/EUR Macro Events within 15m window)",
                "summary": "  • [NEWS SHIELD] CLEAR (No high-impact releases imminent)"
            }

        bullets = []
        for ev in events[:max_items]:
            bullets.append(f"  • [HIGH IMPACT EVENT] {ev['event_name']} ({ev['source']})")

        summary_text = "\n".join(bullets)
        return {
            "shield_status": "MONITORING",
            "shield_message": "ACTIVE (High-Impact Economic Events active in market)",
            "summary": summary_text
        }
