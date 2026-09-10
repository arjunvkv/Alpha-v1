"""Persistent evidence and observation state.

Small, local JSON persistence with atomic replacement and cross-process file locking.
This module owns identity, first_seen timestamps, read state and watch lifecycle so restarts
cannot silently rewrite historical observation time or drop concurrent watches.
"""
from __future__ import annotations
import contextlib, hashlib, json, os, re, threading, time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import portalocker

def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def canonical_url(url: str) -> str:
    return (url or "").strip().split("#", 1)[0].rstrip("/")

class EvidenceStateStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else Path(__file__).resolve().parent.parent / "data" / "live" / "evidence_state.json"
        self.lock_path = self.path.with_name(f"{self.path.stem}.lock")
        self.lock = threading.RLock()

    @contextlib.contextmanager
    def _locked(self):
        with self.lock:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            with portalocker.Lock(str(self.lock_path), timeout=15):
                yield

    def _load(self):
        if not self.path.exists():
            return {"version": 1, "news": {}, "watches": {}}
        for attempt in range(5):
            try:
                content = self.path.read_text(encoding="utf-8")
                if not content.strip():
                    time.sleep(0.02 * (attempt + 1))
                    continue
                data = json.loads(content)
                return {"version": 1, "news": data.get("news", {}), "watches": data.get("watches", {})}
            except Exception:
                time.sleep(0.02 * (attempt + 1))
        return {"version": 1, "news": {}, "watches": {}}

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.parent / f"{self.path.stem}_{os.getpid()}_{threading.get_ident()}_{int(time.time()*1000)}.tmp"
        try:
            tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
            os.replace(tmp, self.path)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass

    def upsert_news(self, items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        now = utc_now(); out = []
        with self._locked():
            state = self._load()
            for item in items:
                row = dict(item)
                key = canonical_url(row.get("canonical_url") or row.get("link") or "")
                if not key:
                    seed = "|".join(str(row.get(k, "")) for k in ("source_id", "headline", "published_at"))
                    key = "hash:" + hashlib.sha256(seed.encode()).hexdigest()
                existing = state["news"].get(key)
                if existing:
                    row["first_seen_at"] = existing.get("first_seen_at") or now
                    row["read_count"] = existing.get("read_count", 0)
                    row["last_read_at"] = existing.get("last_read_at")
                else:
                    row["first_seen_at"] = row.get("first_seen_at") or now
                    row.setdefault("read_count", 0)
                    row.setdefault("last_read_at", None)
                row["canonical_url"] = key if not key.startswith("hash:") else row.get("canonical_url", "")
                row["last_retrieved_at"] = now
                state["news"][key] = row
                out.append(row)
            self._save(state)
        return out

    def mark_read(self, ids: Iterable[str]) -> List[Dict[str, Any]]:
        now = utc_now(); marked = []
        with self._locked():
            state = self._load()
            wanted = set(ids)
            for key, row in state["news"].items():
                if key in wanted or row.get("news_id") in wanted:
                    row["read_count"] = int(row.get("read_count", 0)) + 1
                    row["last_read_at"] = now
                    marked.append({"news_id": row.get("news_id"), "canonical_url": row.get("canonical_url"), "last_read_at": now, "read_count": row["read_count"]})
            self._save(state)
        return marked

    def upsert_watch(self, watch: Dict[str, Any]) -> Dict[str, Any]:
        now = utc_now(); row = dict(watch)
        watch_id = row.get("id") or row.get("watch_id")
        if not watch_id:
            seed = "|".join(str(row.get(k, "")) for k in ("symbol", "condition", "target_price", "direction"))
            watch_id = "watch_" + hashlib.sha256(seed.encode()).hexdigest()[:16]
        with self._locked():
            state = self._load(); old = state["watches"].get(watch_id, {})
            row["id"] = watch_id
            row["created_at"] = old.get("created_at") or row.get("created_at") or now
            row["updated_at"] = now
            row["status"] = row.get("status") or old.get("status") or "ACTIVE"
            row["observed_at"] = old.get("observed_at") or row.get("observed_at")
            row["triggered_at"] = old.get("triggered_at") or row.get("triggered_at")
            state["watches"][watch_id] = row
            self._save(state)
        return row

    def get_watches(self, symbol: str | None = None, include_closed: bool = True):
        with self._locked():
            rows = list(self._load()["watches"].values())
        if symbol:
            rows = [r for r in rows if str(r.get("symbol", "")).upper() == str(symbol).upper()]
        if not include_closed:
            # Include ACTIVE and un-cleared TRIGGERED watches so trigger states are auditable
            rows = [r for r in rows if r.get("status") in ("ACTIVE", "TRIGGERED")]
        return sorted(rows, key=lambda r: r.get("updated_at", ""), reverse=True)

    def update_watch(self, watch_id: str, **changes):
        with self._locked():
            state = self._load(); row = state["watches"].get(watch_id)
            if not row: return None
            row.update({k: v for k, v in changes.items() if v is not None})
            row["updated_at"] = utc_now()
            state["watches"][watch_id] = row
            self._save(state)
            return row

    def mark_watches_observed(self, watch_ids: Iterable[str], observed_at: str | None = None):
        ts = observed_at or utc_now(); changed = []
        with self._locked():
            state = self._load()
            for wid in set(watch_ids):
                row = state["watches"].get(wid)
                if row:
                    row["observed_at"] = ts; row["updated_at"] = ts; changed.append(row)
            self._save(state)
        return changed

    def cancel_watch(self, watch_id: str) -> Optional[Dict[str, Any]]:
        return self.update_watch(watch_id, status="CANCELLED")

    def clear_completed_watches(self, symbol: str | None = None) -> int:
        cleared = 0
        with self._locked():
            state = self._load()
            new_watches = {}
            for wid, row in state["watches"].items():
                if symbol and str(row.get("symbol", "")).upper() != str(symbol).upper():
                    new_watches[wid] = row
                    continue
                if row.get("status") in ("TRIGGERED", "CANCELLED"):
                    cleared += 1
                else:
                    new_watches[wid] = row
            state["watches"] = new_watches
            self._save(state)
        return cleared
