import os
import json
import time
import datetime
import email.utils
import logging
import urllib.request
import xml.etree.ElementTree as ET
import html
import threading
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

LOG = logging.getLogger("alpha.world_events")

PROJECT_ROOT = Path(r"C:\Trading\Alpha")
EVENTS_CACHE_FILE = PROJECT_ROOT / "data" / "live" / "live_world_events.json"

MACRO_PATTERNS = [
    r"\bWAR\b", r"\bIRAN\b", r"\bTANKER\b", r"\bVESSEL\b", r"\bHORMUZ\b", r"\bMILITARY\b",
    r"\bSTRIKE\b", r"\bMIDEAST\b", r"\bFED\b", r"\bINFLATION\b", r"\bCPI\b", r"\bPCE\b",
    r"\bRATE HIKE\b", r"\bRATE CUT\b", r"\bPOWELL\b", r"\bCENTRAL BANK\b", r"\bECB\b",
    r"\bBOJ\b", r"\bTREASURY\b", r"\bYIELD\b", r"\bSANCTION\b", r"\bRUSSIA\b", r"\bTAIWAN\b",
    r"\bTARIFF\b", r"\bTARIFFS\b", r"\bTRADE WAR\b", r"\bDEFICIT\b", r"\bG10\b", r"\bGEOPOLITICAL\b",
    r"\bBUYBACK\b", r"\bBUYBACKS\b", r"\bTWIST\b", r"\bTGA\b", r"\bDEBASEMENT\b", r"\bLIQUIDITY\b",
    r"\bDEBT CEILING\b", r"\bBESSENT\b", r"\bBOND\b", r"\bBONDS\b"
]
MACRO_REGEX = re.compile("|".join(MACRO_PATTERNS), re.IGNORECASE)

MICRO_PATTERNS = [
    r"\bGOLD\b", r"\bSILVER\b", r"\bBULLION\b", r"\bOUNCE\b", r"\bOUNCES\b", r"\bMETALS\b",
    r"\bPBOC\b", r"\bVAULT\b", r"\bRESERVE\b", r"\bRESERVES\b", r"\bETF\b", r"\bPRECIOUS METALS\b",
    r"\bSOVEREIGN BUYING\b", r"\bGAS\b", r"\bFUEL\b", r"\bFUELS\b", r"\bCOMMODITY\b",
    r"\bCOMMODITIES\b", r"\bSUPPLY SQUEEZE\b", r"\bINVENTORY\b", r"\bBARREL\b", r"\bOIL\b",
    r"\bCRUDE\b", r"\bBRENT\b", r"\$100\b", r"\bENERGY\b", r"\bPLATINUM\b", r"\bPALLADIUM\b"
]
MICRO_REGEX = re.compile("|".join(MICRO_PATTERNS), re.IGNORECASE)

RSS_SOURCES = [
    {
        "name": "Treasury & Macro Wire",
        "url": "https://news.google.com/rss/search?q=US+Treasury+Bessent+OR+Fed+OR+gold+buyback+when:2d&hl=en-US&gl=US&ceid=US:en",
        "default_category": "MACRO"
    },
    {
        "name": "Federal Reserve Press",
        "url": "https://www.federalreserve.gov/feeds/press_all.xml",
        "default_category": "CENTRAL_BANKS_FED"
    },
    {
        "name": "Yahoo Commodities",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F,CL=F,DX-Y.NYB,^TNX&region=US&lang=en-US",
        "default_category": "COMMODITIES_ENERGY"
    },
    {
        "name": "Yahoo Gold & Metals",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F,SI=F,PA=F,PL=F&region=US&lang=en-US",
        "default_category": "COMMODITIES_ENERGY"
    },
    {
        "name": "FXStreet Wire",
        "url": "https://www.fxstreet.com/rss/news",
        "default_category": "MACRO"
    },
    {
        "name": "CNBC World",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
        "default_category": "GEOPOLITICAL_GLOBAL"
    },
    {
        "name": "CNBC Economy",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
        "default_category": "CENTRAL_BANKS_FED"
    },
    {
        "name": "CNBC Energy & Commodities",
        "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19836768",
        "default_category": "COMMODITIES_ENERGY"
    },
    {
        "name": "Yahoo Market Wire",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC,^DJI,^IXIC&region=US&lang=en-US",
        "default_category": "OTHER"
    },
    {
        "name": "MarketWatch",
        "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "default_category": "MACRO_ECONOMIC_INDICATORS"
    }
]

EXCLUDED_NOISE_KEYWORDS = [
    "ROTH", "401K", "RETIREE", "ESTATE PLAN", "MORTGAGE RATE", "REFINANCE", "CREDIT CARD",
    "SOCIAL SECURITY", "TOO OLD FOR", "MY WIFE", "RETIREMENT SAVINGS", "MEDICARE", "INHERITANCE",
    "ROYALTY INTEREST", "DRILLING EXTENDS", "MINERALISATION", "MINERALIZATION", "ASSAY RESULTS",
    "INTERCEPT", "PRIVATE PLACEMENT", "HERBAL DISPATCH", "TITAN MINERALS", "KRAKATOA RESOURCES",
    "CENTRUS ENERGY", "SM ENERGY", "BKV", "SELECT WATER SOLUTIONS", "PROFRAC", "STOCKS TRADE",
    "ZOPKHITO", "BLACKWATER MINE", "DYNASTY", "ACQUIRES OPTION", "ANNOUNCES CLOSING", "NON-BROKERED",
    "ANNUITY", "FOREVER PAYCHECK", "PAYS OFF MORTGAGE", "SAVINGS ACCOUNT", "BUY THIS DIP",
    "IRA", "EXECUTOR", "SIBLINGS", "OLDER PEOPLE LIKE ME", "SCAMMERS", "JIM CRAMER", "SOUTH PARK",
    "HALF MARATHON", "MARATHON", "SURGED 45%", "GROWTH INITIATIVES", "WHY SSR MINING", "SURGED"
]

MAX_EVENT_AGE_MINUTES = 720  # 12 hours hard cut-off for breaking live news

_ROTATION_COUNTER = 0


class LiveWorldEventsEngine:
    """
    Real-Time Institutional Live World Events Engine:
    Parses live multi-feed financial, central bank, commodity, and geopolitical news.
    Categorizes events into MACRO, MICRO, and OTHER without technical fluff.
    Rotates fresh news headlines across cycles.
    Includes automated continuous 30s background poller for sub-second 0ms instant reads.
    """
    _bg_started = False

    def __init__(self, cache_ttl_seconds: int = 30, enable_background_polling: bool = True):
        self.cache_ttl = cache_ttl_seconds
        self._mem_cache: List[Dict[str, Any]] = []
        self._mem_cache_ts: float = 0.0
        self._lock = threading.Lock()
        EVENTS_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

        if enable_background_polling and not LiveWorldEventsEngine._bg_started:
            LiveWorldEventsEngine._bg_started = True
            bg_t = threading.Thread(target=self._background_poller, daemon=True, name="LiveWorldEventsPoller")
            bg_t.start()

    def _background_poller(self):
        """Continuously polls global news feeds in the background every 30s."""
        time.sleep(2)
        while True:
            try:
                self.fetch_live_events(force_refresh=True)
            except Exception as _e:
                LOG.debug(f"Background news poller error: {_e}")
            time.sleep(30)

    def _categorize(self, title: str) -> str:
        if MACRO_REGEX.search(title):
            return "MACRO"
        elif MICRO_REGEX.search(title):
            return "MICRO"
        return "OTHER"

    def fetch_live_events(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Fetch live world events from memory cache, disk cache, or parallel RSS feeds."""
        now_ts = time.time()
        
        # 1. In-memory hot cache (0ms)
        if not force_refresh and self._mem_cache and (now_ts - self._mem_cache_ts < self.cache_ttl):
            return self._mem_cache

        # 2. Disk cache (<5ms)
        if not force_refresh and EVENTS_CACHE_FILE.exists():
            try:
                with open(EVENTS_CACHE_FILE, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    last_fetch = cache_data.get("updated_at_ts", 0)
                    if now_ts - last_fetch < self.cache_ttl:
                        raw_evs = cache_data.get("events", [])
                        valid_evs = []
                        for ev in raw_evs:
                            t = ev.get("title", "")
                            t_up = t.upper()
                            if any(kw in t_up for kw in EXCLUDED_NOISE_KEYWORDS):
                                continue
                            ev["category"] = self._categorize(t)
                            valid_evs.append(ev)
                        if valid_evs:
                            self._mem_cache = valid_evs
                            self._mem_cache_ts = last_fetch
                            return self._mem_cache
            except Exception as err:
                LOG.warning(f"Failed to read events cache: {err}")

        # 3. Fast parallel network fetch
        events = []
        seen_titles = set()
        timestamp_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        def _fetch_single_source(src):
            src_events = []
            try:
                req = urllib.request.Request(src["url"], headers=headers)
                xml_data = urllib.request.urlopen(req, timeout=2.5).read()
                root = ET.fromstring(xml_data)
                for item in root.findall(".//item")[:15]:
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    pub_elem = item.find("pubDate")
                    desc_elem = item.find("description")
                    if desc_elem is None:
                        desc_elem = item.find("summary")
                    
                    if title_elem is not None and title_elem.text:
                        raw_title = html.unescape(title_elem.text.strip())
                        for bad, good in [("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("\u2014", " - "), ("\u2013", "-")]:
                            raw_title = raw_title.replace(bad, good)
                        raw_title = raw_title.replace("&apos;", "'").replace("&#39;", "'").replace("&quot;", '"')
                        t_upper = raw_title.upper()
                        if any(kw in t_upper for kw in EXCLUDED_NOISE_KEYWORDS):
                            continue
                        cat = self._categorize(raw_title)
                        link = link_elem.text.strip() if (link_elem is not None and link_elem.text) else ""
                        pub_date = pub_elem.text.strip() if (pub_elem is not None and pub_elem.text) else timestamp_str
                        mins_ago = 30.0
                        if pub_elem is not None and pub_elem.text:
                            try:
                                p_dt = email.utils.parsedate_to_datetime(pub_elem.text.strip())
                                mins_ago = round(abs((now_utc - p_dt).total_seconds()) / 60.0, 1)
                            except Exception:
                                pass
                        if mins_ago > MAX_EVENT_AGE_MINUTES:
                            continue

                        # Extract and clean summary / description snippet
                        summary_snippet = ""
                        if desc_elem is not None and desc_elem.text:
                            raw_desc = html.unescape(desc_elem.text.strip())
                            # Remove HTML tags (e.g. <a href...>, <p>, <b>)
                            clean_desc = re.sub(r"<[^>]+>", " ", raw_desc)
                            clean_desc = re.sub(r"\s+", " ", clean_desc).strip()
                            for bad, good in [("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("\u2014", " - "), ("\u2013", "-")]:
                                clean_desc = clean_desc.replace(bad, good)
                            clean_desc = clean_desc.replace("&apos;", "'").replace("&#39;", "'").replace("&quot;", '"')
                            if len(clean_desc) > 140:
                                clean_desc = clean_desc[:137] + "..."
                            summary_snippet = clean_desc

                        src_events.append({
                            "title": raw_title,
                            "summary": summary_snippet,
                            "category": cat,
                            "source": src["name"],
                            "pub_date": pub_date,
                            "minutes_ago": mins_ago,
                            "link": link
                        })
            except Exception:
                pass
            return src_events

        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = executor.map(_fetch_single_source, RSS_SOURCES)
            for res_list in results:
                for ev in res_list:
                    t_low = ev["title"].lower()
                    if t_low not in seen_titles:
                        seen_titles.add(t_low)
                        events.append(ev)

        if events:
            # Sort by recency (most recent first)
            events.sort(key=lambda x: x.get("minutes_ago", 999.0))
            self._mem_cache = events
            self._mem_cache_ts = now_ts
            try:
                with open(EVENTS_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump({"updated_at": timestamp_str, "updated_at_ts": now_ts, "events_count": len(events), "events": events}, f, indent=2)
            except Exception:
                pass
        elif self._mem_cache:
            return self._mem_cache

        return events

    def get_classified_rotating_news(self, items_per_section: int = 3) -> Dict[str, Any]:
        """
        Returns rotating news headlines cleanly classified into MACRO, MICRO, and OTHER.
        Rotates headlines across calls so OpenCode receives fresh wire updates on every wake.
        Zero technical metrics, pure factual raw news.
        """
        global _ROTATION_COUNTER
        _ROTATION_COUNTER += 1

        all_events = self.fetch_live_events()
        if not all_events:
            return {
                "macro": [],
                "micro": [],
                "other": [],
                "formatted_box": "- News & Catalysts: No active wire headlines at this moment."
            }

        # Dynamically recalculate minutes_ago in real time against current UTC clock
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        fresh_events = []
        for ev in all_events:
            p_str = ev.get("pub_date")
            if p_str:
                try:
                    p_dt = email.utils.parsedate_to_datetime(p_str)
                    ev["minutes_ago"] = round(abs((now_utc - p_dt).total_seconds()) / 60.0, 1)
                except Exception:
                    pass
            if ev.get("minutes_ago", 0) <= MAX_EVENT_AGE_MINUTES:
                fresh_events.append(ev)

        # Sort fresh events strictly by recency
        fresh_events.sort(key=lambda x: x.get("minutes_ago", 999.0))

        macro_events = [e for e in fresh_events if e.get("category") == "MACRO"]
        micro_events = [e for e in fresh_events if e.get("category") == "MICRO"]
        other_events = [e for e in fresh_events if e.get("category") == "OTHER"]

        def _rotate_slice(lst, n):
            if not lst:
                return []
            if len(lst) <= n:
                return lst
            idx = (_ROTATION_COUNTER % (len(lst) - n + 1))
            return lst[idx:idx + n]

        sel_macro = _rotate_slice(macro_events, items_per_section)
        sel_micro = _rotate_slice(micro_events, items_per_section)
        sel_other = _rotate_slice(other_events, 2)

        lines = [
            "- NEWS & CATALYST INTELLIGENCE (90% Priority - Macro / Micro / Cross-Market):"
        ]

        def _format_event_line(item_dict):
            line = f'  * "{item_dict["title"]}" ({item_dict.get("minutes_ago", 0):.1f}m ago | {item_dict.get("source", "Wire")})'
            summary = item_dict.get("summary")
            if summary:
                line += f'\n    Context: "{summary}"'
            return line

        if sel_macro:
            lines.append("  [MACRO & GEOPOLITICAL]:")
            for m in sel_macro:
                lines.append(_format_event_line(m))

        if sel_micro:
            lines.append("  [MICRO & COMMODITY FLOW]:")
            for m in sel_micro:
                lines.append(_format_event_line(m))

        if sel_other:
            lines.append("  [OTHER & CROSS-MARKET]:")
            for o in sel_other:
                lines.append(_format_event_line(o))

        formatted_box = "\n".join(lines)

        return {
            "macro": sel_macro,
            "micro": sel_micro,
            "other": sel_other,
            "formatted_box": formatted_box,
            "all_events_count": len(all_events)
        }

    def get_formatted_summary(self, max_items: int = 5) -> str:
        """Returns rotating classified summary."""
        res = self.get_classified_rotating_news(items_per_section=max_items)
        return res.get("formatted_box", "")