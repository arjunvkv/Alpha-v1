import json
from sensors.evidence_sources import FREDAdapter, GDELTAdapter, RSSRegistry, envelope, SUCCESS, UNAVAILABLE

class FakeHttp:
    def __init__(self, payloads):
        self.payloads=list(payloads)
    def get(self, url, timeout=10, headers=None):
        value=self.payloads.pop(0)
        if isinstance(value, Exception): raise value
        return value

def test_fred_without_key_never_fabricates_value(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    result=FREDAdapter(api_key="").observations("DGS10")
    assert result["status"] == UNAVAILABLE
    assert result["data"] == {}
    assert "fallback" in result["error"].lower()

def test_fred_vintage_request_preserves_observations():
    payload=json.dumps({"observations":[{"date":"2024-01-01","value":"4.00"}]}).encode()
    result=FREDAdapter(api_key="x", http=FakeHttp([payload])).observations("DGS10", vintage_date="2024-02-01")
    assert result["status"] == SUCCESS
    assert result["data"]["vintage_date"] == "2024-02-01"
    assert result["data"]["observations"][0]["value"] == "4.00"

def test_gdelt_adds_provenance():
    payload=json.dumps({"articles":[{"url":"https://example.com/a","title":"Gold event","domain":"example.com","seendate":"20260101000000"}]}).encode()
    result=GDELTAdapter(http=FakeHttp([payload])).search("gold")
    item=result["data"]["items"][0]
    assert result["status"] == SUCCESS
    assert item["canonical_url"] == "https://example.com/a"
    assert item["news_id"]
    assert item["first_seen_at"] == item["retrieved_at"]
    assert item["discovered_via"] == "gdelt"
    assert item["published_at"] is None
    assert item["discovered_at"] == "20260101000000"

def test_rss_registry_adds_stable_provenance():
    xml=b"<rss><channel><item><title>Headline</title><link>https://example.com/x#frag</link><pubDate>Tue, 01 Jan 2026 00:00:00 GMT</pubDate></item></channel></rss>"
    result=RSSRegistry({"test":{"url":"https://feed.test/rss"}}, http=FakeHttp([xml])).fetch()
    item=result["data"]["items"][0]
    assert result["status"] == SUCCESS
    assert item["canonical_url"] == "https://example.com/x"
    assert item["news_id"]
    assert item["discovered_via"] == "direct_rss"

def test_truth_envelope_never_invents_data():
    result=envelope(UNAVAILABLE, "test", error="offline")
    assert result["status"] == UNAVAILABLE
    assert result["data"] == {}
