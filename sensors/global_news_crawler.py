"""Global Eyes News & Web Crawler for TradingAgents.

Combines RSS feed streams (finnews / MarketWatch / Kitco / WSJ / Reuters),
DuckDuckGo live web search, and Trafilatura web article text extraction.
"""

import logging
import re
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from sensors.evidence_sources import RSSRegistry

LOG = logging.getLogger("alpha.sensors.news")

class GlobalNewsCrawler:
    def __init__(self):
        self.rss_sources = {
            "kitco": "https://www.kitco.com/rss/gold.xml",
            "marketwatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
            "reuters_business": "https://www.reutersagency.com/feed/?best-topics=business-finance"
        }

    def fetch_rss_headlines(self, max_items: int = 15) -> List[Dict[str, str]]:
        """Fetch direct RSS evidence with publication/retrieval provenance.

        Compatibility returns the historical headline shape, while the underlying
        registry keeps canonical IDs and first-seen timestamps for persistence.
        """
        registry = RSSRegistry({name: {"url": url} for name, url in self.rss_sources.items()})
        result = registry.fetch(max_items=max_items)
        if result["status"] not in ("SUCCESS", "STALE"):
            LOG.debug("RSS registry unavailable: %s", result.get("error"))
            return []
        return [{
            "source": item["source_id"],
            "title": item["headline"],
            "link": item["canonical_url"],
            "pub_date": item.get("published_at") or "",
            "retrieved_at": item.get("retrieved_at"),
            "first_seen_at": item.get("first_seen_at"),
            "news_id": item.get("news_id"),
            "discovered_via": item.get("discovered_via"),
        } for item in result["data"]["items"][:max_items]]

    def search_live_web(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Live web search via DuckDuckGo search or truthful empty response."""
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                return [{"title": r.get("title", ""), "href": r.get("href", ""), "body": r.get("body", "")} for r in results]
        except Exception as err:
            LOG.debug(f"DuckDuckGo search unavailable for '{query}': {err}")
            return []

    def extract_article_text(self, url: str) -> str:
        """Extract noise-free text from web article using Trafilatura or standard fallback."""
        try:
            import trafilatura
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                result = trafilatura.extract(downloaded)
                if result:
                    return result
        except Exception as e:
            LOG.debug(f"Trafilatura extraction fallback for {url}: {e}")
        return "Cleaned article content unavailable; title and snippet used for sentiment analysis."
