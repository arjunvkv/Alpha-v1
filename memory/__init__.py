"""
Alpha Memory — Decision records, mistakes, knowledge.

All persistence is JSON. No database.
Files:
    decisions.json — every decision, categorized
    mistakes.json  — rules extracted from errors (NEVER repeat)
    knowledge.json — bucket/regime stats, learned patterns
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger("alpha.memory")

MEMORY_DIR = Path(r"C:\Trading\Alpha\memory")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path, default):
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"Corrupt JSON at {path}: {e}. Starting fresh.")
    return default


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    tmp.replace(path)


class DecisionMemory:
    """Read/write interface for all Alpha memory files."""

    def __init__(self, memory_dir: Path = MEMORY_DIR):
        self.memory_dir = Path(memory_dir)
        self.decisions_file = self.memory_dir / "decisions.json"
        self.mistakes_file = self.memory_dir / "mistakes.json"
        self.knowledge_file = self.memory_dir / "knowledge.json"

    # ── Decisions ────────────────────────────────────────────────

    def record_decision(self, decision: dict) -> str:
        """Write a new decision. Returns decision ID."""
        decisions = _load_json(self.decisions_file, [])
        dec_id = f"TRD-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{len(decisions)+1:03d}"
        record = {
            "id": dec_id,
            "timestamp": _now(),
            "status": "open",
            **decision,
            "exit_price": None,
            "exit_time": None,
            "pnl": None,
            "r_multiple": None,
            "review": None,
            "lessons": None,
        }
        decisions.append(record)
        _save_json(self.decisions_file, decisions)
        log.info(f"Decision recorded: {dec_id} {decision.get('instrument')} "
                 f"{decision.get('direction')} conviction={decision.get('conviction')}")
        return dec_id

    def update_decision(self, decision_id: str, updates: dict) -> bool:
        decisions = _load_json(self.decisions_file, [])
        for d in decisions:
            if d["id"] == decision_id:
                d.update(updates)
                _save_json(self.decisions_file, decisions)
                return True
        log.warning(f"Decision not found: {decision_id}")
        return False

    def get_decision(self, decision_id: str) -> Optional[dict]:
        decisions = _load_json(self.decisions_file, [])
        for d in decisions:
            if d["id"] == decision_id:
                return d
        return None

    def find_open_by_ticket(self, ticket: int) -> Optional[dict]:
        """Find an open decision by its MT5 ticket."""
        decisions = _load_json(self.decisions_file, [])
        for d in decisions:
            if d.get("ticket") == ticket and d.get("status") == "open":
                return d
        return None

    def get_open_decisions(self) -> list:
        decisions = _load_json(self.decisions_file, [])
        return [d for d in decisions if d.get("status") == "open"]

    def get_closed_decisions(self, bucket=None, regime=None) -> list:
        decisions = _load_json(self.decisions_file, [])
        out = [d for d in decisions if d.get("status") == "closed"]
        if bucket:
            out = [d for d in out if d.get("bucket") == bucket]
        if regime:
            out = [d for d in out if d.get("regime_at_entry") == regime]
        return out

    # ── Mistakes ─────────────────────────────────────────────────

    def add_mistake(self, mistake: dict) -> str:
        mistakes = _load_json(self.mistakes_file, {})
        mid = f"M-{len(mistakes)+1:03d}"
        mistakes[mid] = {"date": _now()[:10], **mistake}
        _save_json(self.mistakes_file, mistakes)
        log.warning(f"MISTAKE RECORDED [{mid}]: {mistake.get('rule')}")
        return mid

    def get_mistakes(self) -> dict:
        return _load_json(self.mistakes_file, {})

    def check_mistakes(self, bucket: str, regime: str, instrument: str) -> list:
        """Return mistake rules that apply to a proposed trade."""
        violations = []
        for mid, m in self.get_mistakes().items():
            applies = (
                (m.get("bucket") in (None, bucket))
                and (m.get("regime") in (None, regime))
                and (m.get("instrument") in (None, instrument))
            )
            if applies:
                violations.append({"id": mid, **m})
        return violations

    # ── Knowledge ────────────────────────────────────────────────

    def add_knowledge(self, pattern: dict):
        knowledge = _load_json(self.knowledge_file, {"rules_learned": []})
        knowledge.setdefault("rules_learned", []).append({"date": _now()[:10], **pattern})
        _save_json(self.knowledge_file, knowledge)

    def get_knowledge(self) -> dict:
        return _load_json(self.knowledge_file, {"rules_learned": []})

    def update_bucket_stats(self, bucket: str, won: bool, r_multiple: float, regime: str):
        """Update running bucket statistics after a closed trade."""
        knowledge = _load_json(self.knowledge_file, {})
        buckets = knowledge.setdefault("buckets", {})
        stats = buckets.setdefault(bucket, {
            "total_trades": 0, "wins": 0, "losses": 0,
            "win_rate": 0.0, "avg_r_multiple": 0.0, "_r_sum": 0.0,
        })
        stats["total_trades"] += 1
        stats["_r_sum"] += r_multiple
        if won:
            stats["wins"] += 1
        else:
            stats["losses"] += 1
        n = stats["total_trades"]
        stats["win_rate"] = round(stats["wins"] / n, 3)
        stats["avg_r_multiple"] = round(stats["_r_sum"] / n, 2)
        del stats["_r_sum"]  # don't persist helper
        regimes = knowledge.setdefault("regimes", {})
        rstats = regimes.setdefault(regime, {"total_trades": 0, "wins": 0})
        rstats["total_trades"] += 1
        if won:
            rstats["wins"] += 1
        _save_json(self.knowledge_file, knowledge)
