"""Global Eyes News & Web Crawler for TradingAgents.

Combines RSS feed streams (finnews / MarketWatch / Kitco / WSJ / Reuters),
DuckDuckGo live web search, and Trafilatura web article text extraction.
"""

import logging
import re
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Dict, Any

LOG = logging.getLogger("alpha.sensors.news")

class GlobalNewsCrawler:
    def __init__(self):
        self.rss_sources = {
            "kitco": "https://www.kitco.com/rss/gold.xml",
            "marketwatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
            "reuters_business": "https://www.reutersagency.com/feed/?best-topics=business-finance"
        }

    def fetch_rss_headlines(self, max_items: int = 15) -> List[Dict[str, str]]:
        """Fetch real-time headlines across global RSS news streams."""
        headlines = []
        for name, url in self.rss_sources.items():
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    xml_data = response.read()
                    root = ET.fromstring(xml_data)
                    for item in root.findall(".//item")[:max_items]:
                        title = item.findtext("title") or ""
                        link = item.findtext("link") or ""
                        pub_date = item.findtext("pubDate") or ""
                        clean_title = re.sub(r"<[^>]+>", "", title).strip()
                        if clean_title:
                            headlines.append({
                                "source": name,
                                "title": clean_title,
                                "link": link,
                                "pub_date": pub_date
                            })
            except Exception as e:
                LOG.debug(f"RSS fetch for {name} failed: {e}")
        if not headlines:
            # Explicitly empty list - NEVER fabricate synthetic news headlines
            LOG.debug("No live RSS headlines returned from external feeds.")
        return headlines

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
