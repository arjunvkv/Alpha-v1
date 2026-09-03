"""Evidence-first free source adapters.

All adapters return the same truth contract. Optional sources never fabricate data
and callers can distinguish SUCCESS, STALE, UNAVAILABLE and ERROR.
"""
from __future__ import annotations
import hashlib, json, os, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

SUCCESS, STALE, UNAVAILABLE, ERROR = "SUCCESS", "STALE", "UNAVAILABLE", "ERROR"

def _now():
    return datetime.now(timezone.utc)

def _iso(value=None):
    value = value or _now()
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def _parse_observed(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        try:
            return parsedate_to_datetime(str(value)).astimezone(timezone.utc)
        except Exception:
            return None

def envelope(status, source, data=None, observed_at=None, retrieved_at=None, error=None, max_age_seconds=None):
    retrieved_at = retrieved_at or _iso()
    age = None
    if observed_at:
        observed = _parse_observed(observed_at)
        if observed is not None:
            age = max(0.0, (_now() - observed).total_seconds())
    if status == SUCCESS and max_age_seconds is not None and age is not None and age > max_age_seconds:
        status = STALE
    result = {"status": status, "source": source, "observed_at": observed_at,
              "retrieved_at": retrieved_at, "age_seconds": age, "data": data or {}}
    if error:
        result["error"] = error
    return result

class HttpJson:
    def get(self, url, timeout=10, headers=None):
        req = urllib.request.Request(url, headers={"User-Agent": "Alpha/1.0 evidence adapter", **(headers or {})})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read()

class FREDAdapter:
    source = "FRED/ALFRED"
    base = "https://api.stlouisfed.org/fred"
    def __init__(self, api_key=None, http=None):
        self.api_key = api_key or os.getenv("FRED_API_KEY", "").strip()
        self.http = http or HttpJson()
    def observations(self, series_id, limit=100, vintage_date=None):
        retrieved = _iso()
        if not self.api_key:
            return envelope(UNAVAILABLE, self.source, retrieved_at=retrieved,
                            error="FRED_API_KEY is not configured; source is optional and no fallback value was used.")
        params = {"series_id": series_id, "api_key": self.api_key, "file_type": "json",
                  "limit": int(limit), "sort_order": "desc"}
        if vintage_date:
            params["vintage_dates"] = vintage_date
        url = self.base + "/series/observations?" + urllib.parse.urlencode(params)
        try:
            payload = json.loads(self.http.get(url).decode("utf-8"))
            observations = payload.get("observations", [])
            observed_at = observations[0].get("date") if observations else None
            return envelope(SUCCESS, self.source, {"series_id": series_id,
                            "vintage_date": vintage_date, "observations": observations},
                            observed_at=observed_at, retrieved_at=retrieved)
        except Exception as exc:
            return envelope(ERROR, self.source, retrieved_at=retrieved, error=str(exc))

class GDELTAdapter:
    source = "Original GDELT DOC 2.0"
    base = "https://api.gdeltproject.org/api/v2/doc/doc"
    def __init__(self, http=None):
        self.http = http or HttpJson()
    def search(self, query, max_records=25, timespan=None):
        retrieved = _iso()
        params = {"query": query, "mode": "ArtList", "format": "json",
                  "maxrecords": max(1, min(int(max_records), 250))}
        if timespan:
            params["timespan"] = timespan
        try:
            raw = self.http.get(self.base + "?" + urllib.parse.urlencode(params))
            payload = json.loads(raw.decode("utf-8"))
            articles = payload.get("articles", [])
            items = []
            for article in articles:
                url = article.get("url", "")
                title = article.get("title", "")
                published = article.get("date")
                discovered_at = article.get("seendate")
                canonical = url.split("#", 1)[0]
                items.append({"news_id": hashlib.sha256((canonical or title).encode("utf-8")).hexdigest()[:24],
                              "canonical_url": canonical, "source_id": "gdelt",
                              "publisher": article.get("domain"),
                              "headline": title, "published_at": published,
                              "discovered_at": discovered_at, "retrieved_at": retrieved, "first_seen_at": retrieved,
                              "discovered_via": "gdelt", "language": article.get("language"),
                              "data": article})
            observed = items[0].get("published_at") if items else None
            return envelope(SUCCESS, self.source, {"items": items}, observed_at=observed, retrieved_at=retrieved)
        except Exception as exc:
            return envelope(ERROR, self.source, retrieved_at=retrieved, error=str(exc))

class RSSRegistry:
    """Direct public feeds with provenance. RSSHub routes are opt-in and self-host only."""
    def __init__(self, sources=None, http=None):
        self.http = http or HttpJson()
        self.sources = sources or {
            "kitco": {"url": "https://www.kitco.com/rss/gold.xml", "official_or_secondary": "secondary"},
            "marketwatch": {"url": "https://feeds.content.dowjones.io/public/rss/mw_topstories", "official_or_secondary": "secondary"},
            "reuters_business": {"url": "https://www.reutersagency.com/feed/?best-topics=business-finance", "official_or_secondary": "secondary"},
        }
    def fetch(self, max_items=20):
        retrieved = _iso(); items=[]; failures=[]
        for source_id, meta in self.sources.items():
            url = meta.get("url")
            if not url:
                continue
            try:
                raw = self.http.get(url)
                root = ET.fromstring(raw)
                count=0
                for node in root.findall(".//item"):
                    if count >= max_items: break
                    title=(node.findtext("title") or "").strip()
                    link=(node.findtext("link") or "").strip()
                    pub=(node.findtext("pubDate") or node.findtext("date") or "").strip()
                    if not title: continue
                    canonical=link.split("#",1)[0]
                    news_id=hashlib.sha256((canonical or source_id+"|"+title+"|"+pub).encode("utf-8")).hexdigest()[:24]
                    items.append({"news_id":news_id,"canonical_url":canonical,"source_id":source_id,
                                  "publisher":source_id,"headline":title,"published_at":pub or None,
                                  "observed_at": _iso(_parse_observed(pub)) if _parse_observed(pub) else None,
                                  "age_seconds": max(0.0, (_now() - _parse_observed(pub)).total_seconds()) if _parse_observed(pub) else None,
                                  "retrieved_at":retrieved,"first_seen_at":retrieved,
                                  "discovered_via":"direct_rss","freshness_state":SUCCESS,
                                  "official_or_secondary":meta.get("official_or_secondary","secondary")})
                    count+=1
            except Exception as exc:
                failures.append({"source_id":source_id,"error":str(exc)})
        status = SUCCESS if items else (ERROR if failures else UNAVAILABLE)
        latest_observed = next((item.get("observed_at") for item in items if item.get("observed_at")), None)
        return envelope(status, "Direct RSS/Atom registry",
                        {"items":items,"failures":failures}, observed_at=latest_observed, retrieved_at=retrieved,
                        error=None if items else "No RSS items available from configured sources.")

class CommonCrawlAdapter:
    source="Common Crawl Index"
    def __init__(self, http=None): self.http=http or HttpJson()
    def lookup(self, url, index="CC-MAIN-2026-30", limit=10):
        retrieved=_iso()
        endpoint=f"https://index.commoncrawl.org/{index}-index?"+urllib.parse.urlencode({"url":url,"output":"json","limit":int(limit)})
        try:
            raw=self.http.get(endpoint)
            lines=[json.loads(x) for x in raw.decode("utf-8").splitlines() if x.strip()]
            return envelope(SUCCESS,self.source,{"url":url,"index":index,"captures":lines},retrieved_at=retrieved)
        except Exception as exc:
            return envelope(ERROR,self.source,retrieved_at=retrieved,error=str(exc))

def capability_snapshot():
    return {"FRED/ALFRED": {"required":False,"state": SUCCESS if os.getenv("FRED_API_KEY") else UNAVAILABLE,
                             "on_demand":True,"reason": None if os.getenv("FRED_API_KEY") else "FRED_API_KEY not configured"},
            "Original GDELT": {"required":False,"state":SUCCESS,"on_demand":True},
            "Direct RSS/Atom": {"required":False,"state":SUCCESS,"on_demand":True},
            "RSSHub": {"required":False,"state":UNAVAILABLE,"on_demand":True,"reason":"self-hosted endpoint not configured"},
            "Common Crawl": {"required":False,"state":SUCCESS,"on_demand":True}}
