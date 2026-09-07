import json
from sensors.evidence_sources import FREDAdapter, GDELTAdapter, RSSRegistry, envelope, SUCCESS, UNAVAILABLE

class FakeHttp:
    def __init__(self, payloads):
        self.payloads=list(payloads)
    def get(self, url, timeout=10, headers=None):
        value=self.payloads.pop(0)
        if isinstance(value, Exception): raise value
        return value

def test_fred_without_key_uses_free_treasury_direct(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    # When no key is provided, official US Treasury Direct XML feed is used seamlessly
    result = FREDAdapter(api_key="").observations("DGS10", limit=2)
    assert result["status"] == SUCCESS
    assert result["source"] == "US_Department_of_Treasury_Direct"
    assert len(result["data"]["observations"]) > 0

def test_fred_unknown_series_without_key_returns_unavailable(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    result = FREDAdapter(api_key="").observations("UNKNOWN_SERIES_XYZ")
    assert result["status"] == UNAVAILABLE
    assert result["data"] == {}

def test_fred_vintage_request_preserves_observations():
    payload=json.dumps({"observations":[{"date":"2024-01-01","value":"4.00"}]}).encode()
    result=FREDAdapter(api_key="x", http=FakeHttp([payload])).observations("DGS10", vintage_date="2024-02-01")
    assert result["status"] == SUCCESS
    assert result["data"]["vintage_date"] == "2024-02-01"
    assert result["data"]["observations"][0]["value"] == "4.00"

def test_gdelt_adds_provenance(tmp_path):
    from tradingagents.evidence_state import EvidenceStateStore
    store = EvidenceStateStore(tmp_path / "state.json")
    payload=json.dumps({"articles":[{"url":"https://example.com/a","title":"Gold event","domain":"example.com","seendate":"20260101000000"}]}).encode()
    result=GDELTAdapter(http=FakeHttp([payload]), state_store=store).search("gold")
    item=result["data"]["items"][0]
    assert result["status"] == SUCCESS
    assert item["canonical_url"] == "https://example.com/a"
    assert item["news_id"]
    assert item["first_seen_at"] == item["retrieved_at"]
    assert item["discovered_via"] == "gdelt"
    assert item["published_at"] is None
    assert item["discovered_at"] == "20260101000000"

def test_rss_registry_adds_stable_provenance(tmp_path):
    from tradingagents.evidence_state import EvidenceStateStore
    store = EvidenceStateStore(tmp_path / "state.json")
    xml=b"<rss><channel><item><title>Headline</title><link>https://example.com/x#frag</link><pubDate>Tue, 01 Jan 2026 00:00:00 GMT</pubDate></item></channel></rss>"
    result=RSSRegistry({"test":{"url":"https://feed.test/rss"}}, http=FakeHttp([xml]), state_store=store).fetch()
    item=result["data"]["items"][0]
    assert result["status"] == SUCCESS
    assert item["canonical_url"] == "https://example.com/x"
    assert item["news_id"]
    assert item["discovered_via"] == "direct_rss"


def test_truth_envelope_never_invents_data():
    result=envelope(UNAVAILABLE, "test", error="offline")
    assert result["status"] == UNAVAILABLE
    assert result["data"] == {}

def test_gdelt_rate_limited_falls_back_to_live_stream(tmp_path):
    from tradingagents.evidence_state import EvidenceStateStore
    store = EvidenceStateStore(tmp_path / "state.json")
    rss_xml = b"""<rss version="2.0"><channel>
        <item>
            <title>Fed Interest Rates Hold Steady Ahead of Inflation Data - Reuters</title>
            <link>https://reuters.com/markets/rates-test</link>
            <pubDate>Mon, 07 Sep 2026 12:00:00 GMT</pubDate>
            <source url="https://reuters.com">Reuters</source>
        </item>
    </channel></rss>"""
    # Simulate GDELT raising 429 / timeout Exception, followed by live stream RSS response
    fake_http = FakeHttp([RuntimeError("HTTP Error 429: Too Many Requests"), rss_xml])
    GDELTAdapter._circuit_open_until = 0.0
    adapter = GDELTAdapter(http=fake_http, state_store=store)

    res = adapter.search("gold fed rates", max_records=5)
    assert res["status"] == SUCCESS
    assert "Live Market News" in res["source"]
    assert len(res["data"]["items"]) == 1
    item = res["data"]["items"][0]
    assert item["headline"] == "Fed Interest Rates Hold Steady Ahead of Inflation Data - Reuters"
    assert item["publisher"] == "Reuters"
    assert item["discovered_via"] == "live_news_rss"
    assert item["canonical_url"] == "https://reuters.com/markets/rates-test"
    assert item["published_at"] == "Mon, 07 Sep 2026 12:00:00 GMT"
    assert item["observed_at"] is not None

