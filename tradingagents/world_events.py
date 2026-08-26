import os
import json
import time
import datetime
import logging
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional

LOG = logging.getLogger("alpha.world_events")

PROJECT_ROOT = Path(r"C:\Trading\Alpha")
EVENTS_CACHE_FILE = PROJECT_ROOT / "data" / "live" / "live_world_events.json"

RSS_SOURCES = [
    {
        "name": "Yahoo Finance Commodities & Yields",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F,CL=F,DX-Y.NYB,^TNX&region=US&lang=en-US",
        "default_category": "COMMODITIES_ENERGY"
    },
    {
        "name": "Investing.com Forex & Central Bank News",
        "url": "https://www.investing.com/rss/news_1.rss",
        "default_category": "CENTRAL_BANKS_FED"
    },
    {
        "name": "MarketWatch Top World Stories",
        "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "default_category": "MACRO_ECONOMIC_INDICATORS"
    },
    {
        "name": "Investing.com Economy & Macro",
        "url": "https://www.investing.com/rss/news_14.rss",
        "default_category": "GEOPOLITICAL_GLOBAL"
    }
]

class LiveWorldEventsEngine:
    """
    Real-Time Institutional Live World Events Engine:
    Parses live multi-feed financial, central bank, commodity, and geopolitical news.
    Categorizes events, deduplicates headlines, and caches results on disk.
    """
    def __init__(self, cache_ttl_seconds: int = 120):
        self.cache_ttl = cache_ttl_seconds
        EVENTS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _categorize(self, title: str, default_cat: str) -> str:
        t_upper = title.upper()
        if any(w in t_upper for w in ["FED", "INFLATION", "CPI", "PCE", "YIELD", "RATE", "POWELL", "CENTRAL BANK", "ECB", "BOJ", "TREASURY"]):
            return "CENTRAL_BANKS_FED"
        elif any(w in t_upper for w in ["GOLD", "SILVER", "OIL", "CRUDE", "OPEC", "ENERGY", "METALS", "GAS"]):
            return "COMMODITIES_ENERGY"
        elif any(w in t_upper for w in ["WAR", "SANCTION", "RUSSIA", "CHINA", "MIDDLE EAST", "TARIFF", "ELECTION", "GEOPOLITICAL"]):
            return "GEOPOLITICAL_GLOBAL"
        elif any(w in t_upper for w in ["GDP", "PAYROLL", "JOBS", "UNEMPLOYMENT", "PMI", "RETAIL SALES", "TRADE DEFICIT"]):
            return "MACRO_ECONOMIC_INDICATORS"
        return default_cat

    def fetch_live_events(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Fetch live world events from RSS feeds or return unexpired disk cache."""
        now_ts = time.time()
        
        if not force_refresh and EVENTS_CACHE_FILE.exists():
            try:
                with open(EVENTS_CACHE_FILE, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    last_fetch = cache_data.get("updated_at_ts", 0)
                    if now_ts - last_fetch < self.cache_ttl:
                        return cache_data.get("events", [])
            except Exception as err:
                LOG.warning(f"Failed to read events cache: {err}")

        events = []
        seen_titles = set()
        timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        for src in RSS_SOURCES:
            try:
                req = urllib.request.Request(src["url"], headers=headers)
                xml_data = urllib.request.urlopen(req, timeout=5).read()
                root = ET.fromstring(xml_data)

                for item in root.findall(".//item"):
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pub_elem = item.find("pubDate")

                    if title_elem is not None and title_elem.text:
                        raw_title = title_elem.text.strip()
                        # Clean special encoding glitches if any
                        clean_title = raw_title.replace("&apos;", "'").replace("&#39;", "'").replace("&quot;", '"')
                        
                        if clean_title.lower() in seen_titles:
                            continue
                        seen_titles.add(clean_title.lower())

                        cat = self._categorize(clean_title, src["default_category"])
                        link = link_elem.text.strip() if (link_elem is not None and link_elem.text) else ""
                        pub_date = pub_elem.text.strip() if (pub_elem is not None and pub_elem.text) else timestamp_str

                        events.append({
                            "title": clean_title,
                            "category": cat,
                            "source": src["name"],
                            "pub_date": pub_date,
                            "link": link,
                            "fetched_at": timestamp_str
                        })
            except Exception as err:
                LOG.debug(f"RSS fetch failed for {src['name']}: {err}")

        # Save to cache
        cache_payload = {
            "updated_at_ts": now_ts,
            "updated_at": timestamp_str,
            "total_events": len(events),
            "events": events
        }
        try:
            with open(EVENTS_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache_payload, f, indent=2)
        except Exception as err:
            LOG.error(f"Writing live events cache failed: {err}")

        return events

    def get_formatted_summary(self, max_items: int = 5) -> str:
        """Returns a bulleted text summary of top live world events for prompt payload streaming."""
        events = self.fetch_live_events()
        if not events:
            return "  • No high-impact live world events detected at this moment."

        bullets = []
        for ev in events[:max_items]:
            bullets.append(f"  • [{ev['category']}] {ev['title']} ({ev['source']})")

        return "\n".join(bullets)
