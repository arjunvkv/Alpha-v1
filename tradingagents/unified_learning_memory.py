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

STATES = {"ACTIVE", "UNDER_REVIEW", "REFINED", "RETIRED"}


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
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            LOG.error("Failed to load unified learning memory: %s", exc)
            return self._empty()

    def _save(self, data: Dict[str, Any]) -> None:
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _new_experience_id(self, data: Dict[str, Any]) -> str:
        return f"experience_{len(data['experiences']) + 1:06d}"

    def _ensure_pattern(self, data: Dict[str, Any], symbol: str, pattern_name: str,
                        observation: str = "", source: str = "UNIFIED") -> Dict[str, Any]:
        key = _norm(symbol, pattern_name)
        patterns = data["patterns"]
        pat = patterns.get(key)
        if pat is None:
            pat = {
                "pattern_id": key,
                "symbol": (symbol or "").upper(),
                "pattern_name": pattern_name,
                "description": observation,
                "state": "ACTIVE",
                "occurrence_count": 0,
                "experience_ids": [],
                "observations": [],
                "outcomes": [],
                "provenance": {"sources": [source], "legacy_statuses": []}
            }
            patterns[key] = pat
        elif source not in pat["provenance"].setdefault("sources", []):
            pat["provenance"]["sources"].append(source)
        return pat

    def _add_observation(self, pat: Dict[str, Any], observation: str, source: str,
                         timestamp: Optional[str] = None,
                         evidence_id: Optional[str] = None) -> None:
        pat["observations"].append({
            "observation": observation,
            "source": source,
            "timestamp": timestamp,
            "evidence_id": evidence_id
        })
        pat["occurrence_count"] = len(pat["observations"])

    def migrate_legacy(self) -> Dict[str, Any]:
        data = self._load()
        migration = data.setdefault("migration", {})
        unmapped: List[Dict[str, Any]] = []

        if os.path.exists(LEGACY_JOURNAL_PATH) and not migration.get("sources", {}).get("trade_journal"):
            try:
                with open(LEGACY_JOURNAL_PATH, "r", encoding="utf-8") as f:
                    legacy = json.load(f)

                for bucket, kind in (("winning_trades", "WINNING_EXPERIENCE"),
                                     ("lessons_learned", "LOSING_EXPERIENCE")):
                    for idx, item in enumerate(legacy.get(bucket, [])):
                        exp_id = self._new_experience_id(data)
                        direction = item.get("side") or item.get("direction")
                        data["experiences"][exp_id] = {
                            "id": exp_id,
                            "type": kind,
                            "timestamp": item.get("timestamp"),
                            "direction_taken": direction,
                            "market_context": {"symbol": item.get("symbol")},
                            "execution": {
                                "ticket": item.get("ticket"),
                                "entry_price": item.get("entry_price"),
                                "exit_price": item.get("exit_price")
                            },
                            "outcome": {"pnl": item.get("pnl")},
                            "learning": {"lesson": item.get("lesson")},
                            "provenance": {
                                "original_source": "TRADE_JOURNAL",
                                "bucket": bucket,
                                "original_index": idx,
                                "original_payload": item
                            },
                            "pattern_links": []
                        }

                for idx, rule in enumerate(legacy.get("self_correction_rules", [])):
                    exp_id = self._new_experience_id(data)
                    data["experiences"][exp_id] = {
                        "id": exp_id,
                        "type": "SELF_CORRECTION",
                        "timestamp": None,
                        "direction_taken": None,
                        "market_context": {},
                        "execution": {},
                        "outcome": {},
                        "learning": {
                            "lesson": rule,
                            "interpretation": "HISTORICAL_LEARNING_NOT_EXECUTION_DIRECTIVE"
                        },
                        "provenance": {
                            "original_source": "TRADE_JOURNAL",
                            "bucket": "self_correction_rules",
                            "original_index": idx,
                            "original_payload": rule
                        },
                        "pattern_links": []
                    }

                for idx, item in enumerate(legacy.get("research_study_patterns", [])):
                    pat = self._ensure_pattern(data, item.get("symbol", ""), item.get("pattern_name", ""),
                                               item.get("observation", ""), "TRADE_JOURNAL")
                    legacy_count = int(item.get("count", 1) or 1)
                    for n in range(legacy_count):
                        self._add_observation(
                            pat,
                            item.get("observation", ""),
                            "TRADE_JOURNAL",
                            item.get("last_observed") if n == legacy_count - 1 else item.get("first_observed"),
                            f"legacy_trade_journal_pattern:{idx}:{n}"
                        )
                    pat["provenance"].setdefault("legacy_statuses", []).append({
                        "source": "TRADE_JOURNAL",
                        "legacy_count": legacy_count,
                        "first_observed": item.get("first_observed"),
                        "last_observed": item.get("last_observed")
                    })
                migration.setdefault("sources", {})["trade_journal"] = True
            except Exception as exc:
                LOG.exception("Trade journal migration failed: %s", exc)
                unmapped.append({"source": "trade_journal", "error": str(exc)})

        if os.path.isdir(LEGACY_BOOK_DIR) and not migration.get("sources", {}).get("pattern_book"):
            try:
                outcomes = {}
                if os.path.exists(LEGACY_OUTCOMES_PATH):
                    with open(LEGACY_OUTCOMES_PATH, "r", encoding="utf-8") as f:
                        outcomes = json.load(f)

                line_re = re.compile(r"^-\s*\*\*\[([A-Z0-9]+)\]\s*([^\]]+?)\*\*\s*\[(.*?)\]:\s*(.*)$")
                for filename in sorted(os.listdir(LEGACY_BOOK_DIR)):
                    if not re.match(r"page_\d+\.md$", filename):
                        continue
                    with open(os.path.join(LEGACY_BOOK_DIR, filename), "r", encoding="utf-8") as f:
                        for line_no, line in enumerate(f, 1):
                            m = line_re.match(line.strip())
                            if not m:
                                continue
                            symbol, name, tag, rest = m.groups()
                            count_m = re.search(r"Count:\s*(\d+)", tag)
                            count = int(count_m.group(1)) if count_m else 1
                            last_m = re.search(r"\(Last:\s*([^)]*)\)", rest)
                            last_ts = last_m.group(1).strip() if last_m else None
                            obs = re.sub(r"\(Outcomes:\s*\d+\)", "", rest)
                            obs = re.sub(r"\(Last:\s*[^)]*\)", "", obs).strip(" :")
                            pat = self._ensure_pattern(data, symbol, name, obs, "PATTERN_BOOK")
                            # Do not overwrite/erase legacy evidence; preserve every legacy hit.
                            for n in range(count):
                                self._add_observation(
                                    pat, obs, "PATTERN_BOOK",
                                    last_ts if n == count - 1 else None,
                                    f"legacy_pattern_book:{filename}:{line_no}:{n}"
                                )
                            key = _norm(symbol, name)
                            for outcome in outcomes.get(key, []):
                                pat["outcomes"].append({
                                    **outcome,
                                    "source": "PATTERN_BOOK"
                                })
                            pat["provenance"].setdefault("legacy_statuses", []).append({
                                "source": "PATTERN_BOOK",
                                "legacy_tag": tag,
                                "legacy_count": count,
                                "file": filename,
                                "line": line_no
                            })
                migration.setdefault("sources", {})["pattern_book"] = True
            except Exception as exc:
                LOG.exception("Pattern book migration failed: %s", exc)
                unmapped.append({"source": "pattern_book", "error": str(exc)})

        migration["migrated_at"] = migration.get("migrated_at") or _now()
        migration["unmapped_records"] = unmapped
        self._save(data)
        return self.migration_report(data)

    def migration_report(self, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        data = data or self._load()
        return {
            "status": "SUCCESS",
            "canonical_store": self.path,
            "experiences": len(data.get("experiences", {})),
            "patterns": len(data.get("patterns", {})),
            "sources": data.get("migration", {}).get("sources", {}),
            "unmapped_records": data.get("migration", {}).get("unmapped_records", [])
        }

    def record_experience(self, *, ticket: Optional[int], symbol: str, direction_taken: Optional[str],
                          pnl: Optional[float], entry_price: Optional[float],
                          exit_price: Optional[float], lesson: str = "",
                          reason: str = "", timestamp: Optional[str] = None) -> Dict[str, Any]:
        data = self._load()
        exp_id = self._new_experience_id(data)
        pnl_value = float(pnl) if pnl is not None else None
        kind = "WINNING_EXPERIENCE" if pnl_value is not None and pnl_value >= 20.0 else "LOSING_EXPERIENCE"
        data["experiences"][exp_id] = {
            "id": exp_id,
            "type": kind,
            "timestamp": timestamp or _now(),
            "direction_taken": direction_taken,
            "market_context": {"symbol": symbol},
            "execution": {
                "ticket": ticket,
                "entry_price": entry_price,
                "exit_price": exit_price
            },
            "outcome": {"pnl": pnl_value},
            "learning": {
                "lesson": lesson,
                "reason": reason
            },
            "provenance": {"original_source": "UNIFIED_RUNTIME"},
            "pattern_links": []
        }
        self._save(data)
        return data["experiences"][exp_id]

    def record_pattern(self, symbol: str, pattern_name: str, observation: str,
                       outcome: Optional[str] = None, ticket: Optional[str] = None,
                       r_value: Optional[float] = None) -> Dict[str, Any]:
        data = self._load()
        pat = self._ensure_pattern(data, symbol, pattern_name, observation, "UNIFIED_RUNTIME")
        evidence_id = f"runtime:{len(pat['observations']) + 1}"
        self._add_observation(pat, observation, "UNIFIED_RUNTIME", _now(), evidence_id)
        if outcome is not None:
            try:
                rv = float(r_value) if r_value is not None else None
            except (TypeError, ValueError):
                rv = None
            pat["outcomes"].append({
                "outcome": outcome,
                "ticket": ticket,
                "r_value": rv,
                "ts": _now(),
                "source": "UNIFIED_RUNTIME",
                "evidence_id": evidence_id
            })
        self._save(data)
        return self._pattern_response(pat, "UPDATED")

    def attach_outcome(self, symbol: str, pattern_name: str, outcome: str,
                       ticket: Optional[str] = None, r_value: Optional[float] = None) -> Dict[str, Any]:
        data = self._load()
        key = _norm(symbol, pattern_name)
        pat = data["patterns"].get(key)
        if pat is None:
            return {"status": "NO_MATCHING_PATTERN", "symbol": symbol.upper(), "pattern_name": pattern_name}
        try:
            rv = float(r_value) if r_value is not None else None
        except (TypeError, ValueError):
            rv = None
        pat["outcomes"].append({
            "outcome": outcome,
            "ticket": ticket,
            "r_value": rv,
            "ts": _now(),
            "source": "UNIFIED_RUNTIME"
        })
        self._save(data)
        return self._pattern_response(pat, "OUTCOME_ATTACHED")

    def _pattern_response(self, pat: Dict[str, Any], status: str) -> Dict[str, Any]:
        return {
            "status": status,
            "symbol": pat["symbol"],
            "pattern_name": pat["pattern_name"],
            "count": pat["occurrence_count"],
            "state": pat.get("state", "ACTIVE"),
            "outcomes_recorded": len(pat.get("outcomes", [])),
            "review_required": True,
            "decision_authority": "AGENT_ONLY",
            "observation": pat.get("description", "")
        }

    def get_pattern(self, symbol: str, pattern_name: str) -> Optional[Dict[str, Any]]:
        return self._load()["patterns"].get(_norm(symbol, pattern_name))

    def search(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        q = (query or "").lower()
        results = []
        for pat in self._load()["patterns"].values():
            hay = " ".join([
                str(pat.get("symbol", "")),
                str(pat.get("pattern_name", "")),
                str(pat.get("description", "")),
                json.dumps(pat.get("observations", []), ensure_ascii=False)
            ]).lower()
            if q in hay:
                results.append(self._pattern_response(pat, "MATCH"))
                if len(results) >= max_results:
                    break
        return {"status": "SUCCESS", "query": query, "results": results, "count": len(results)}

    def all_patterns(self) -> List[Dict[str, Any]]:
        return list(self._load()["patterns"].values())

    def validation_summary(self) -> Dict[str, Any]:
        patterns = []
        for pat in self.all_patterns():
            outcomes = pat.get("outcomes", [])
            wins = sum(1 for x in outcomes if isinstance(x.get("r_value"), (int, float)) and x["r_value"] > 0)
            losses = sum(1 for x in outcomes if isinstance(x.get("r_value"), (int, float)) and x["r_value"] <= 0)
            patterns.append({
                "symbol": pat["symbol"],
                "pattern_name": pat["pattern_name"],
                "count": pat["occurrence_count"],
                "state": pat.get("state", "ACTIVE"),
                "outcomes_recorded": len(outcomes),
                "wins": wins,
                "losses": losses,
                "review_required": True,
                "decision_authority": "AGENT_ONLY"
            })
        return {"status": "SUCCESS", "patterns": patterns, "total_patterns": len(patterns)}


    def get_page(self, page_number: int = 1, page_size: int = 50) -> Dict[str, Any]:
        patterns = self.all_patterns()
        start = max(0, (int(page_number) - 1) * page_size)
        page = patterns[start:start + page_size]
        return {
            "status": "SUCCESS",
            "page": int(page_number),
            "entries": page,
            "entries_count": len(page),
            "total_entries": len(patterns),
            "canonical_store": self.path,
            "review_required": True,
            "decision_authority": "AGENT_ONLY"
        }

    def get_index(self) -> Dict[str, Any]:
        patterns = self.all_patterns()
        return {
            "status": "SUCCESS",
            "canonical_store": self.path,
            "total_patterns": len(patterns),
            "total_experiences": len(self._load().get("experiences", {})),
            "pattern_states": sorted(STATES),
            "unlimited_evidence": True,
            "review_required": True,
            "decision_authority": "AGENT_ONLY"
        }

    def get_full(self) -> str:
        data = self._load()
        return json.dumps({
            "canonical_store": self.path,
            "experiences": data.get("experiences", {}),
            "patterns": data.get("patterns", {}),
            "migration": data.get("migration", {}),
            "review_required": True,
            "decision_authority": "AGENT_ONLY"
        }, indent=2, ensure_ascii=False)
