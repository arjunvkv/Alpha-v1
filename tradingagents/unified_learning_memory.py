import os
import re
import json
import logging
import datetime
from typing import Any, Dict, List, Optional

LOG = logging.getLogger("alpha.unified_learning_memory")

DOSSIER_DIR = r"C:\Trading\Alpha\logs"
UNIFIED_PATH = os.path.join(DOSSIER_DIR, "unified_learning_memory.json")
LEGACY_JOURNAL_PATH = os.path.join(DOSSIER_DIR, "trade_journal_memory.json")
LEGACY_BOOK_DIR = os.path.join(DOSSIER_DIR, "pattern_book")
LEGACY_OUTCOMES_PATH = os.path.join(LEGACY_BOOK_DIR, "pattern_outcomes.json")
REVIEW_STATE_PATH = os.path.join(DOSSIER_DIR, "agent_review_state.json")

STATES = {"ACTIVE", "UNDER_REVIEW", "REFINED", "RETIRED"}
LEARNING_REVIEW_SOURCES = (
    "Unified Learning Memory",
    "Pattern Book",
    "Historical Research",
    "Strategy Evidence Archive",
)

# Live evidence uses simple elapsed review intervals. Learning sources above never
# expire and are instead required in every explicit study cycle.
LIVE_REVIEW_SOURCES = {
    "Live Market State": 120,
    "Active Positions": 120,
    "Technical / Multi-Timeframe Detail": 240,
    "Intermarket Context": 600,
    "Macro / Calendar / World Events": 900,
}


def _now() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _norm(symbol: str, name: str) -> str:
    sym = (symbol or "").strip().upper()
    key = (name or "").strip().upper()
    key = re.sub(r"\d+", " ", key)
    key = re.sub(r"[_\-]+", " ", key)
    key = re.sub(r"[^A-Z ]", " ", key)
    key = re.sub(r"\s+", " ", key).strip()
    return f"{sym}|{key}"


class UnifiedLearningMemory:
    """Canonical learning store. Historical sources are imported non-destructively."""

    def __init__(self, path: str = UNIFIED_PATH):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._ensure()

    def _empty(self) -> Dict[str, Any]:
        return {
            "schema_version": 1,
            "title": "Alpha Unified Learning Memory",
            "experiences": {},
            "patterns": {},
            "migration": {
                "sources": {"trade_journal": False, "pattern_book": False},
                "migrated_at": None,
                "unmapped_records": []
            }
        }

    def _ensure(self) -> None:
        if not os.path.exists(self.path):
            self._save(self._empty())
            self.migrate_legacy()

    def _load(self) -> Dict[str, Any]:
        """Loads canonical learning store with concurrency retry and hard-fail on invalid JSON."""
        import time
        last_err = None
        for attempt in range(5):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not isinstance(data, dict) or "patterns" not in data:
                        raise ValueError("Store is not a valid UnifiedLearningMemory dictionary structure")
                    if isinstance(data.get("patterns"), list):
                        data["patterns"] = {p.get("pattern_id", str(i)): p for i, p in enumerate(data["patterns"]) if isinstance(p, dict)}
                    if isinstance(data.get("experiences"), list):
                        data["experiences"] = {e.get("experience_id", str(i)): e for i, e in enumerate(data["experiences"]) if isinstance(e, dict)}
                    return data
            except (PermissionError, OSError) as exc:
                last_err = exc
                time.sleep(0.05 * (attempt + 1))
            except Exception as exc:
                LOG.error(f"HARD-FAIL: Corrupted Unified Learning Memory store at {self.path}: {exc}")
                return {"_error": str(exc), "patterns": {}, "experiences": {}}
        
        LOG.error(f"HARD-FAIL: Could not open {self.path} after 5 retries: {last_err}")
        return {"_error": str(last_err), "patterns": {}, "experiences": {}}

    def _save(self, data: Dict[str, Any]) -> None:
        """Saves canonical learning store atomically via temp file replace."""
        import time
        if "_error" in data:
            LOG.error("Refusing to save corrupted data structure back to disk.")
            return

        tmp_path = self.path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomic rename with retry loop for Windows file locks
            for attempt in range(5):
                try:
                    os.replace(tmp_path, self.path)
                    break
                except (PermissionError, OSError):
                    time.sleep(0.05 * (attempt + 1))
            else:
                # Direct fallback write
                with open(self.path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
        except Exception as e:
            LOG.error(f"Failed saving unified learning memory: {e}")

    def _new_experience_id(self, data: Dict[str, Any]) -> str:
        return f"experience_{len(data['experiences']) + 1:06d}"

    def _ensure_pattern(self, data: Dict[str, Any], symbol: str, pattern_name: str,
                        observation: str = "", source: str = "UNIFIED") -> Dict[str, Any]:
        key = _norm(symbol, pattern_name)
        patterns = data["patterns"]
        pat = patterns.get(key)
        if pat is None:
            pat = {
                "pattern_id": key, "symbol": (symbol or "").upper(),
                "pattern_name": pattern_name, "description": observation,
                "state": "ACTIVE", "occurrence_count": 0,
                "experience_ids": [], "observations": [], "outcomes": [],
                "provenance": {"sources": [source], "legacy_statuses": []}
            }
            patterns[key] = pat
        elif source not in pat["provenance"].setdefault("sources", []):
            pat["provenance"]["sources"].append(source)
        return pat

    def _add_observation(self, pat: Dict[str, Any], observation: str, source: str,
                         timestamp: Optional[str] = None, evidence_id: Optional[str] = None) -> None:
        pat["observations"].append({"observation": observation, "source": source,
                                     "timestamp": timestamp, "evidence_id": evidence_id})
        pat["occurrence_count"] = len(pat["observations"])

    def reconcile_links(self) -> Dict[str, Any]:
        """Bidirectionally links trade experiences <-> patterns and tags evidence_provenance."""
        data = self._load()
        experiences = data.get("experiences", {})
        patterns = data.get("patterns", {})
        
        linked_exp_count = 0
        observed_patterns_count = 0

        # 1. Correlate experiences with patterns by symbol and trade direction/keywords
        for exp_id, exp in experiences.items():
            if not isinstance(exp, dict):
                continue
            ctx = exp.get("market_context", {})
            sym = str(ctx.get("symbol") or "").upper() if isinstance(ctx, dict) else ""
            direction = str(exp.get("direction_taken") or "").upper()
            ticket = exp.get("execution", {}).get("ticket") if isinstance(exp.get("execution"), dict) else None
            pnl = exp.get("outcome", {}).get("pnl", 0.0) if isinstance(exp.get("outcome"), dict) else 0.0
            is_win = float(pnl or 0.0) > 0.0

            matched_pat_keys = []
            for p_key, pat in patterns.items():
                if not isinstance(pat, dict):
                    continue
                p_sym = str(pat.get("symbol") or "").upper()
                p_name = str(pat.get("pattern_name") or pat.get("pattern_id") or "").upper()
                if (sym and p_sym == sym) or p_sym == "ALL":
                    if (direction and direction in p_name) or "SETUP" in p_name or "SWEEP" in p_name or "FVG" in p_name:
                        matched_pat_keys.append(p_key)
                        if exp_id not in pat.setdefault("experience_ids", []):
                            pat["experience_ids"].append(exp_id)
                        # Add linked outcome evidence if ticket is present
                        if ticket and not any(str(o.get("ticket")) == str(ticket) for o in pat.setdefault("outcomes", []) if isinstance(o, dict)):
                            pat["outcomes"].append({
                                "outcome": f"{'WIN' if is_win else 'LOSS'} (PnL ${pnl:+.2f})",
                                "ticket": str(ticket),
                                "r_value": round(float(pnl) / 15.0, 2) if pnl != 0 else 0.0,
                                "source": "EXPERIENCE_RECONCILIATION",
                                "ts": exp.get("timestamp") or _now()
                            })

            exp["pattern_links"] = matched_pat_keys
            if matched_pat_keys:
                linked_exp_count += 1

        # 2. Tag evidence_provenance on all patterns
        for p_key, pat in patterns.items():
            if not isinstance(pat, dict):
                continue
            has_linked_exps = len(pat.get("experience_ids", [])) > 0
            has_linked_tickets = any(bool(o.get("ticket")) for o in pat.get("outcomes", []))
            
            if has_linked_exps or has_linked_tickets:
                pat["evidence_provenance"] = "OBSERVED"
                observed_patterns_count += 1
            elif len(pat.get("outcomes", [])) > 0 or len(pat.get("observations", [])) > 0:
                pat["evidence_provenance"] = "SEEDED"
            else:
                pat["evidence_provenance"] = "ESTIMATED"

        self._save(data)
        LOG.info(f"Reconciled {linked_exp_count}/{len(experiences)} experiences to {len(patterns)} patterns ({observed_patterns_count} OBSERVED).")
        return {
            "patterns_count": len(patterns),
            "experiences_count": len(experiences),
            "linked_experiences_count": linked_exp_count,
            "observed_patterns_count": observed_patterns_count
        }

    def migrate_legacy(self) -> Dict[str, Any]:
        data = self._load(); migration = data.setdefault("migration", {}); migration.setdefault("sources", {})
        unmapped: List[Dict[str, Any]] = []
        if os.path.exists(LEGACY_JOURNAL_PATH) and not migration["sources"].get("trade_journal"):
            try:
                with open(LEGACY_JOURNAL_PATH, "r", encoding="utf-8") as f: legacy = json.load(f)
                for bucket, kind in (("winning_trades", "WINNING_EXPERIENCE"), ("lessons_learned", "LOSING_EXPERIENCE")):
                    for idx, item in enumerate(legacy.get(bucket, [])):
                        exp_id = self._new_experience_id(data); direction = item.get("side") or item.get("direction")
                        data["experiences"][exp_id] = {"id": exp_id, "type": kind, "timestamp": item.get("timestamp"),
                            "direction_taken": direction, "market_context": {"symbol": item.get("symbol")},
                            "execution": {"ticket": item.get("ticket"), "entry_price": item.get("entry_price"), "exit_price": item.get("exit_price")},
                            "outcome": {"pnl": item.get("pnl")}, "learning": {"lesson": item.get("lesson")},
                            "provenance": {"original_source": "TRADE_JOURNAL", "bucket": bucket, "original_index": idx, "original_payload": item}, "pattern_links": []}
                for idx, rule in enumerate(legacy.get("self_correction_rules", [])):
                    exp_id = self._new_experience_id(data)
                    data["experiences"][exp_id] = {"id": exp_id, "type": "SELF_CORRECTION", "timestamp": None,
                        "direction_taken": None, "market_context": {}, "execution": {}, "outcome": {},
                        "learning": {"lesson": rule, "interpretation": "HISTORICAL_LEARNING_NOT_EXECUTION_DIRECTIVE"},
                        "provenance": {"original_source": "TRADE_JOURNAL", "bucket": "self_correction_rules", "original_index": idx, "original_payload": rule}, "pattern_links": []}
                for idx, item in enumerate(legacy.get("research_study_patterns", [])):
                    pat = self._ensure_pattern(data, item.get("symbol", ""), item.get("pattern_name", ""), item.get("observation", ""), "TRADE_JOURNAL")
                    legacy_count = int(item.get("count", 1) or 1)
                    for n in range(legacy_count):
                        self._add_observation(pat, item.get("observation", ""), "TRADE_JOURNAL", item.get("last_observed") if n == legacy_count - 1 else item.get("first_observed"), f"legacy_trade_journal_pattern:{idx}:{n}")
                    pat["provenance"].setdefault("legacy_statuses", []).append({"source": "TRADE_JOURNAL", "legacy_count": legacy_count, "first_observed": item.get("first_observed"), "last_observed": item.get("last_observed")})
                migration["sources"]["trade_journal"] = True
            except Exception as exc:
                LOG.exception("Trade journal migration failed: %s", exc); unmapped.append({"source": "trade_journal", "error": str(exc)})
        if os.path.isdir(LEGACY_BOOK_DIR) and not migration["sources"].get("pattern_book"):
            try:
                outcomes = {}
                if os.path.exists(LEGACY_OUTCOMES_PATH):
                    with open(LEGACY_OUTCOMES_PATH, "r", encoding="utf-8") as f: outcomes = json.load(f)
                line_re = re.compile(r"^-\s*\*\*\[([A-Z0-9]+)\]\s*([^\]]+?)\*\*\s*\[(.*?)\]:\s*(.*)$")
                for filename in sorted(os.listdir(LEGACY_BOOK_DIR)):
                    if not re.match(r"page_\d+\.md$", filename): continue
                    with open(os.path.join(LEGACY_BOOK_DIR, filename), "r", encoding="utf-8") as f:
                        for line_no, line in enumerate(f, 1):
                            m = line_re.match(line.strip())
                            if not m: continue
                            symbol, name, tag, rest = m.groups(); count_m = re.search(r"Count:\s*(\d+)", tag)
                            count = int(count_m.group(1)) if count_m else 1
                            last_m = re.search(r"\(Last:\s*([^)]*)\)", rest); last_ts = last_m.group(1).strip() if last_m else None
                            obs = re.sub(r"\(Outcomes:\s*\d+\)", "", rest); obs = re.sub(r"\(Last:\s*[^)]*\)", "", obs).strip(" :")
                            pat = self._ensure_pattern(data, symbol, name, obs, "PATTERN_BOOK")
                            existing_ids = {x.get("evidence_id") for x in pat.get("observations", [])}
                            for n in range(count):
                                eid = f"legacy_pattern_book:{filename}:{line_no}:{n}"
                                if eid not in existing_ids: self._add_observation(pat, obs, "PATTERN_BOOK", last_ts if n == count - 1 else None, eid)
                            key = _norm(symbol, name)
                            existing_outcomes = {(x.get("ticket"), x.get("ts"), x.get("outcome"), x.get("r_value")) for x in pat["outcomes"]}
                            for outcome in outcomes.get(key, []):
                                marker = (outcome.get("ticket"), outcome.get("ts"), outcome.get("outcome"), outcome.get("r_value"))
                                if marker not in existing_outcomes: pat["outcomes"].append({**outcome, "source": "PATTERN_BOOK"})
                            pat["provenance"].setdefault("legacy_statuses", []).append({"source": "PATTERN_BOOK", "legacy_tag": tag, "legacy_count": count, "file": filename, "line": line_no})
                migration["sources"]["pattern_book"] = True
            except Exception as exc:
                LOG.exception("Pattern book migration failed: %s", exc); unmapped.append({"source": "pattern_book", "error": str(exc)})
        migration["migrated_at"] = migration.get("migrated_at") or _now(); migration["unmapped_records"] = unmapped
        self._save(data); return self.migration_report(data)

    def migration_report(self, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        data = data or self._load()
        return {"status": "SUCCESS", "canonical_store": self.path, "experiences": len(data.get("experiences", {})), "patterns": len(data.get("patterns", {})), "sources": data.get("migration", {}).get("sources", {}), "unmapped_records": data.get("migration", {}).get("unmapped_records", [])}

    def record_experience(self, *, ticket: Optional[int], symbol: str, direction_taken: Optional[str], pnl: Optional[float], entry_price: Optional[float], exit_price: Optional[float], r_multiple: Optional[float] = None, actual_risk_usd: Optional[float] = None, lesson: str = "", reason: str = "", timestamp: Optional[str] = None) -> Dict[str, Any]:
        data = self._load(); exp_id = self._new_experience_id(data); pnl_value = float(pnl) if pnl is not None else None
        kind = "WINNING_EXPERIENCE" if pnl_value is not None and pnl_value >= 20.0 else "LOSING_EXPERIENCE"
        data["experiences"][exp_id] = {"id": exp_id, "type": kind, "timestamp": timestamp or _now(), "direction_taken": direction_taken, "r_multiple": r_multiple, "r_value": r_multiple, "actual_risk_usd": actual_risk_usd, "market_context": {"symbol": symbol}, "execution": {"ticket": ticket, "entry_price": entry_price, "exit_price": exit_price}, "outcome": {"pnl": pnl_value, "r_multiple": r_multiple, "r_value": r_multiple, "actual_risk_usd": actual_risk_usd}, "learning": {"lesson": lesson, "reason": reason}, "provenance": {"original_source": "UNIFIED_RUNTIME"}, "pattern_links": []}
        self._save(data); return data["experiences"][exp_id]

    def record_pattern(self, symbol: str, pattern_name: str, observation: str, outcome: Optional[str] = None, ticket: Optional[str] = None, r_value: Optional[float] = None) -> Dict[str, Any]:
        data = self._load(); pat = self._ensure_pattern(data, symbol, pattern_name, observation, "UNIFIED_RUNTIME")
        evidence_id = f"runtime:{len(pat['observations']) + 1}"; self._add_observation(pat, observation, "UNIFIED_RUNTIME", _now(), evidence_id)
        if outcome is not None:
            try: rv = float(r_value) if r_value is not None else None
            except (TypeError, ValueError): rv = None
            pat["outcomes"].append({"outcome": outcome, "ticket": ticket, "r_value": rv, "ts": _now(), "source": "UNIFIED_RUNTIME", "evidence_id": evidence_id})
        self._save(data); return self._pattern_response(pat, "UPDATED")

    def attach_outcome(self, symbol: str, pattern_name: str, outcome: str, ticket: Optional[str] = None, r_value: Optional[float] = None) -> Dict[str, Any]:
        data = self._load(); key = _norm(symbol, pattern_name); pat = data["patterns"].get(key)
        if pat is None: return {"status": "NO_MATCHING_PATTERN", "symbol": symbol.upper(), "pattern_name": pattern_name}
        try: rv = float(r_value) if r_value is not None else None
        except (TypeError, ValueError): rv = None
        pat["outcomes"].append({"outcome": outcome, "ticket": ticket, "r_value": rv, "ts": _now(), "source": "UNIFIED_RUNTIME"})
        self._save(data); return self._pattern_response(pat, "OUTCOME_ATTACHED")

    def _pattern_response(self, pat: Dict[str, Any], status: str) -> Dict[str, Any]:
        return {"status": status, "symbol": pat["symbol"], "pattern_name": pat["pattern_name"], "count": pat["occurrence_count"], "state": pat.get("state", "ACTIVE"), "outcomes_recorded": len(pat.get("outcomes", [])), "review_required": True, "decision_authority": "AGENT_ONLY", "observation": pat.get("description", "")}

    def get_pattern(self, symbol: str, pattern_name: str) -> Optional[Dict[str, Any]]: return self._load()["patterns"].get(_norm(symbol, pattern_name))

    def search(self, query: str, max_results: int = 10, symbol: Optional[str] = None) -> Dict[str, Any]:
        data = self._load()
        patterns = data.get("patterns", {})
        raw_q = (query or "").strip()
        if not raw_q:
            return {"status": "SUCCESS", "query": query, "results": [], "count": 0}
        q_lower = raw_q.lower()
        compressed_query = re.sub(r"[^a-zA-Z0-9]", "", q_lower)
        tokens = [t for t in re.split(r"[\s_\-]+", q_lower) if t]
        
        sym_filter = None
        if symbol and str(symbol).strip().upper() not in ("", "NONE", "NULL", "ALL"):
            sym_filter = str(symbol).strip().upper()

        scored_results = []
        for pat in patterns.values():
            if not isinstance(pat, dict):
                continue
            p_sym = str(pat.get("symbol", "")).upper()
            if sym_filter and p_sym and p_sym != sym_filter and p_sym != "ALL":
                continue
            p_name = str(pat.get("pattern_name", "")).lower()
            p_id = str(pat.get("pattern_id", "")).lower()
            p_desc = str(pat.get("description", "")).lower()
            p_obs = json.dumps(pat.get("observations", []), ensure_ascii=False).lower()
            p_out = json.dumps(pat.get("outcomes", []), ensure_ascii=False).lower()
            
            hay = f"{p_sym} {p_name} {p_id} {p_desc} {p_obs} {p_out}"
            hay_compressed = re.sub(r"[^a-zA-Z0-9]", "", hay)
            
            score = 0
            if q_lower in hay:
                score += 100
            elif compressed_query and compressed_query in hay_compressed:
                score += 80
                
            name_corpus = f"{p_name} {p_id}"
            name_compressed = re.sub(r"[^a-zA-Z0-9]", "", name_corpus)
            matched_tokens = 0
            for t in tokens:
                if t in name_corpus:
                    score += 25
                    matched_tokens += 1
                elif t in name_compressed:
                    score += 20
                    matched_tokens += 1
                elif t in hay:
                    score += 8
                    matched_tokens += 1
                elif t in hay_compressed:
                    score += 5
                    matched_tokens += 1
            
            if tokens and matched_tokens == len(tokens):
                score += 30
                
            if score > 0:
                scored_results.append((score, matched_tokens, pat))
                
        scored_results.sort(key=lambda x: (x[0], x[1]), reverse=True)
        top_pats = [self._pattern_response(item[2], "MATCH") for item in scored_results[:max_results]]
        
        return {"status": "SUCCESS", "query": query, "symbol": sym_filter, "results": top_pats, "count": len(top_pats)}

    search_patterns = search
    get_full_book = lambda self: json.loads(self.get_full())

    def all_patterns(self) -> List[Dict[str, Any]]: return list(self._load()["patterns"].values())

    def validation_summary(self) -> Dict[str, Any]:
        patterns = []
        for pat in self.all_patterns():
            outcomes = pat.get("outcomes", [])
            wins = sum(1 for x in outcomes if isinstance(x.get("r_value"), (int, float)) and x["r_value"] > 0)
            losses = sum(1 for x in outcomes if isinstance(x.get("r_value"), (int, float)) and x["r_value"] <= 0)
            patterns.append({"symbol": pat["symbol"], "pattern_name": pat["pattern_name"], "count": pat["occurrence_count"], "state": pat.get("state", "ACTIVE"), "outcomes_recorded": len(outcomes), "wins": wins, "losses": losses, "review_required": True, "decision_authority": "AGENT_ONLY"})
        return {"status": "SUCCESS", "patterns": patterns, "total_patterns": len(patterns)}

    def _load_review_state(self) -> Dict[str, Any]:
        path = REVIEW_STATE_PATH
        if not os.path.exists(path): return {"cycle_id": 0, "learning_reads": {}}
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except Exception as exc:
            LOG.error("Failed to load Agent review state: %s", exc); return {"cycle_id": 0, "learning_reads": {}}

    def _save_review_state(self, state: Dict[str, Any]) -> None:
        tmp = REVIEW_STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f: json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp, REVIEW_STATE_PATH)

    def start_study_cycle(self) -> Dict[str, Any]:
        state = self._load_review_state(); state["cycle_id"] = int(state.get("cycle_id", 0)) + 1; state["cycle_started_at"] = _now()
        state["learning_reads"] = {name: None for name in LEARNING_REVIEW_SOURCES}
        self._save_review_state(state); return self.get_review_status()

    def mark_read(self, source: str, document_path: str = "") -> Dict[str, Any]:
        return self.mark_reads([source], document_paths={source: document_path} if document_path else {})

    def mark_reads(self, sources: List[str], document_paths: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Mark one or more evidence sources read in one acknowledgement."""
        state = self._load_review_state()
        document_paths = document_paths or {}
        marked, unknown = [], []
        read_at = _now()
        for source in sources:
            source = str(source or "").strip()
            if not source:
                continue
            document_path = document_paths.get(source, "")
            if source in LEARNING_REVIEW_SOURCES:
                state.setdefault("learning_reads", {})[source] = {
                    "read_at": read_at, "document_path": document_path,
                    "cycle_id": state.get("cycle_id", 0)
                }
                marked.append(source)
            elif source in LIVE_REVIEW_SOURCES:
                state.setdefault("live_reads", {})[source] = {
                    "read_at": read_at, "document_path": document_path
                }
                marked.append(source)
            else:
                unknown.append(source)
        self._save_review_state(state)
        result = self.get_review_status()
        result["marked_read"] = marked
        result["unknown_sources"] = unknown
        result["read_at"] = read_at
        return result

    def get_review_status(self) -> Dict[str, Any]:
        state = self._load_review_state(); learning = {}; live = {}
        for source in LEARNING_REVIEW_SOURCES:
            rec = state.get("learning_reads", {}).get(source)
            learning[source] = {
                "status": "READ_THIS_CYCLE" if isinstance(rec, dict) and rec.get("cycle_id") == state.get("cycle_id") else "READ_REQUIRED",
                "document_path": rec.get("document_path") if isinstance(rec, dict) else "",
                "read_at": rec.get("read_at") if isinstance(rec, dict) else None
            }
        now = datetime.datetime.now()
        for source, interval_seconds in LIVE_REVIEW_SOURCES.items():
            rec = state.get("live_reads", {}).get(source)
            status = "READ_REQUIRED"
            if isinstance(rec, dict) and rec.get("read_at"):
                try:
                    read_at = datetime.datetime.strptime(rec["read_at"], "%Y-%m-%d %H:%M:%S")
                    status = "READ_AGAIN_MANDATORY" if (now - read_at).total_seconds() >= interval_seconds else "READ_CURRENT"
                except Exception:
                    status = "READ_REQUIRED"
            live[source] = {
                "status": status,
                "review_interval_seconds": interval_seconds,
                "document_path": rec.get("document_path") if isinstance(rec, dict) else "",
                "read_at": rec.get("read_at") if isinstance(rec, dict) else None
            }
        return {
            "status": "SUCCESS",
            "cycle_id": state.get("cycle_id", 0),
            "cycle_started_at": state.get("cycle_started_at"),
            "learning": learning,
            "live": live,
            "learning_never_expires": True,
            "instruction": "Consult all mandatory learning sources during every study cycle. Learn from mistakes, corrections, contradictions and successful precedents; record meaningful learning even when no trade occurs."
        }

    def learning_cycle_complete(self) -> bool: return all(item["status"] == "READ_THIS_CYCLE" for item in self.get_review_status()["learning"].values())

    def get_page(self, page_number: int = 1, page_size: int = 50) -> Dict[str, Any]:
        patterns = self.all_patterns(); start = max(0, (int(page_number) - 1) * page_size); page = patterns[start:start + page_size]
        return {"status": "SUCCESS", "page": int(page_number), "entries": page, "entries_count": len(page), "total_entries": len(patterns), "canonical_store": self.path, "review_required": True, "decision_authority": "AGENT_ONLY"}

    def get_index(self) -> Dict[str, Any]:
        data = self._load()
        if "_error" in data:
            return {
                "status": "LOAD_ERROR",
                "canonical_store": self.path,
                "error": data["_error"],
                "total_patterns": 0,
                "total_experiences": 0,
                "message": "Unified Learning Memory store corrupted or unreadable"
            }
        patterns = list(data.get("patterns", {}).values())
        return {
            "status": "SUCCESS",
            "canonical_store": self.path,
            "total_patterns": len(patterns),
            "total_experiences": len(data.get("experiences", {})),
            "pattern_states": sorted(STATES),
            "unlimited_evidence": True,
            "review_required": True,
            "decision_authority": "AGENT_ONLY"
        }

    def get_full(self) -> str:
        data = self._load(); return json.dumps({"canonical_store": self.path, "experiences": data.get("experiences", {}), "patterns": data.get("patterns", {}), "migration": data.get("migration", {}), "review_required": True, "decision_authority": "AGENT_ONLY"}, indent=2, ensure_ascii=False)
