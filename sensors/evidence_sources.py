"""Evidence-first free source adapters.

All adapters return the same truth contract. Optional sources never fabricate data
and callers can distinguish SUCCESS, STALE, UNAVAILABLE and ERROR.
"""
from __future__ import annotations
import hashlib, json, os, ssl, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from tradingagents.evidence_state import EvidenceStateStore

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
        try:
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
                return response.read()
        except Exception:
            ctx = ssl._create_unverified_context()
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
                return response.read()


class FREDAdapter:
    source = "FRED/ALFRED"
    base = "https://api.stlouisfed.org/fred"
    def __init__(self, api_key=None, http=None):
        self.api_key = api_key or os.getenv("FRED_API_KEY", "").strip()
        self.http = http or HttpJson()

    def _fetch_treasury_direct(self, series_id, limit=100, vintage_date=None):
        """Free fallback to official US Department of the Treasury XML feed (zero API key required)."""
        sid = (series_id or "DGS10").upper().strip()
        year = datetime.now(timezone.utc).year
        
        if sid == "T10YIE":
            nom = {x["date"]: float(x["value"]) for x in self._fetch_treasury_direct("DGS10", limit, vintage_date)}
            real = {x["date"]: float(x["value"]) for x in self._fetch_treasury_direct("DFII10", limit, vintage_date)}
            obs = []
            for dt, n_val in nom.items():
                if dt in real:
                    obs.append({"date": dt, "value": f"{(n_val - real[dt]):.2f}"})
            return obs

        is_real = sid in ("DFII10", "DFII5", "DFII20", "DFII30", "TC_10YEAR")
        data_type = "daily_treasury_real_yield_curve" if is_real else "daily_treasury_yield_curve"
        url = f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data={data_type}&field_tdr_date_value={year}"
        
        tag_map = {
            "DGS10": "BC_10YEAR",
            "DGS2": "BC_2YEAR",
            "DGS5": "BC_5YEAR",
            "DGS30": "BC_30YEAR",
            "DGS1": "BC_1YEAR",
            "DGS3MO": "BC_3MONTH",
            "DGS6MO": "BC_6MONTH",
            "DFII10": "TC_10YEAR",
            "DFII5": "TC_5YEAR",
            "DFII30": "TC_30YEAR",
        }
        if sid not in tag_map:
            return []
        tag_name = tag_map[sid]
        raw_xml = self.http.get(url)
        root = ET.fromstring(raw_xml)
        entries = root.findall("{http://www.w3.org/2005/Atom}entry")
        observations = []
        for entry in reversed(entries):
            content = entry.find("{http://www.w3.org/2005/Atom}content")
            if content is None: continue
            props = content.find("{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}properties")
            if props is None: continue
            val_elem = props.find(f"{{http://schemas.microsoft.com/ado/2007/08/dataservices}}{tag_name}")
            date_elem = props.find("{http://schemas.microsoft.com/ado/2007/08/dataservices}NEW_DATE")
            if val_elem is not None and val_elem.text and date_elem is not None and date_elem.text:
                dt = date_elem.text.split("T")[0]
                if vintage_date and dt > vintage_date:
                    continue
                observations.append({"date": dt, "value": val_elem.text})
                if len(observations) >= int(limit):
                    break
        return observations

    def observations(self, series_id, limit=100, vintage_date=None):
        retrieved = _iso()
        if self.api_key:
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
            except Exception:
                pass  # Fall through to US Treasury Direct free feed
        
        # Free source fallback: Official US Treasury Direct XML Feed (zero key required)
        try:
            observations = self._fetch_treasury_direct(series_id, limit, vintage_date)
            if observations:
                observed_at = observations[0].get("date")
                return envelope(SUCCESS, "US_Department_of_Treasury_Direct", {"series_id": series_id,
                                "vintage_date": vintage_date, "observations": observations,
                                "provenance": "Official US Department of the Treasury Direct XML Feed (Free)"},
                                observed_at=observed_at, retrieved_at=retrieved)
            return envelope(UNAVAILABLE, "US_Department_of_Treasury_Direct", retrieved_at=retrieved,
                            error=f"Series '{series_id}' not found on US Treasury Direct and FRED_API_KEY is not configured.")
        except Exception as exc:
            return envelope(ERROR, "US_Department_of_Treasury_Direct", retrieved_at=retrieved, error=str(exc))

class GDELTAdapter:
    source = "Original GDELT DOC 2.0"
    base = "https://api.gdeltproject.org/api/v2/doc/doc"
    def __init__(self, http=None, state_store=None):
        self.http = http or HttpJson()
        self.state_store = state_store or EvidenceStateStore()
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
            items = self.state_store.upsert_news(items) if items else []
            observed = items[0].get("published_at") if items else None
            return envelope(SUCCESS, self.source, {"items": items}, observed_at=observed, retrieved_at=retrieved)
        except Exception as exc:
            return envelope(ERROR, self.source, retrieved_at=retrieved, error=str(exc))

class RSSRegistry:
    """Direct public feeds with provenance. RSSHub routes are opt-in and self-host only."""
    def __init__(self, sources=None, http=None, state_store=None):
        self.http = http or HttpJson()
        self.state_store = state_store or EvidenceStateStore()
        if sources is not None:
            self.sources = sources
        else:
            config_path = Path(__file__).resolve().parent.parent / "config" / "evidence_sources.json"
            try:
                loaded = json.loads(config_path.read_text(encoding="utf-8"))
                self.sources = {k:v for k,v in loaded.get("sources", {}).items() if v.get("enabled", True)}
            except Exception:
                self.sources = {}
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
        items = self.state_store.upsert_news(items) if items else []
        status = SUCCESS if items else (ERROR if failures else UNAVAILABLE)
        latest_observed = next((item.get("observed_at") for item in items if item.get("observed_at")), None)
        return envelope(status, "Direct RSS/Atom registry",
                        {"items":items,"failures":failures}, observed_at=latest_observed, retrieved_at=retrieved,
                        error=None if items else "No RSS items available from configured sources.")

class CommonCrawlAdapter:
    source="Common Crawl Index"
    def __init__(self, http=None): self.http=http or HttpJson()
    def available_indexes(self):
        raw=self.http.get("https://index.commoncrawl.org/collinfo.json")
        return json.loads(raw.decode("utf-8"))
    def _resolve_index(self, index):
        if index and index != "latest":
            return index
        indexes=self.available_indexes()
        if not indexes:
            raise RuntimeError("No Common Crawl indexes available")
        return indexes[0].get("id") or indexes[0].get("name")
    def lookup(self, url, index="latest", limit=10):
        retrieved=_iso()
        try:
            index=self._resolve_index(index)
        except Exception as exc:
            return envelope(ERROR,self.source,retrieved_at=retrieved,error=f"index discovery failed: {exc}")
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
