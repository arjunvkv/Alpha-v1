import json
from tradingagents.evidence_state import EvidenceStateStore

def test_news_first_seen_survives_retrievals(tmp_path):
    store=EvidenceStateStore(tmp_path/"state.json")
    first=store.upsert_news([{"news_id":"n1","canonical_url":"https://example.com/a","headline":"A","first_seen_at":"2026-01-01T00:00:00Z"}])[0]
    second=store.upsert_news([{"news_id":"n1","canonical_url":"https://example.com/a#x","headline":"A2"}])[0]
    assert second["first_seen_at"] == first["first_seen_at"]

def test_batch_read_marks_multiple_items(tmp_path):
    store=EvidenceStateStore(tmp_path/"state.json")
    store.upsert_news([{"news_id":"a","canonical_url":"https://e/a"},{"news_id":"b","canonical_url":"https://e/b"}])
    marked=store.mark_read(["a","b"])
    assert len(marked)==2
    assert all(x["read_count"]==1 for x in marked)

def test_watch_lifecycle_survives_restart_and_batch_observe(tmp_path):
    path=tmp_path/"state.json"; store=EvidenceStateStore(path)
    w1=store.upsert_watch({"symbol":"XAUUSD","condition":"above 1"})
    w2=store.upsert_watch({"symbol":"XAGUSD","condition":"below 2"})
    restarted=EvidenceStateStore(path)
    changed=restarted.mark_watches_observed([w1["id"],w2["id"]])
    assert len(changed)==2
    assert all(w["observed_at"] for w in changed)
    assert len(restarted.get_watches())==2
