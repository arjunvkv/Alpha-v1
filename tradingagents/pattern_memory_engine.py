"""
======================================================================
               ALPHA V1 - GRAPHITI PATTERN MEMORY ENGINE
======================================================================
Organic Associative Pattern Memory & Temporal Episode Knowledge Graph.
Inspired by Graphiti (Zep) & Letta Tiered Memory architecture.

Core Principles:
1. Biological "Baby Learning to Walk" model:
   - Repeated successful walks (co-occurring/sequential patterns) strengthen
     synaptic connection weight and gain higher recall prominence.
   - Stumbles / Traps are linked with their specific contextual pitfall.
   - Natural forgetting: Unrepeated one-off noise gently attenuates.
2. Continuous Observational Learning:
   - Learns from executed trades AND from observations while standing flat
     (avoided traps & missed clean moves).
3. The Resilient Swimmer Principle:
   - A past scare does NOT mean never swimming again.
   - Memories record the adverse condition that caused the stumble rather
     than blacklisting the pattern.
4. Zero Math Clutter:
   - Returns ultra-dense, clean text summaries (<100 tokens) for OpenCode.
   - Makes zero decisions and enforces zero gates; OpenCode remains the sole CIO.
======================================================================
"""

import os
import re
import json
import sqlite3
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = Path(r"C:\Trading\Alpha\logs\graphiti_pattern_memory.db")


def _normalize_pattern_tag(tag: str) -> str:
    """Canonical normalization for pattern tags: uppercase, alphanumeric + underscores."""
    t = str(tag or "").strip().upper()
    t = re.sub(r"[^A-Z0-9_]+", "_", t)
    t = re.sub(r"_+", "_", t).strip("_")
    return t


def _canonical_walk_key(patterns: List[str]) -> str:
    """Sort-invariant canonical key for pattern sets."""
    norm_tags = sorted(list(set(_normalize_pattern_tag(p) for p in patterns if p and str(p).strip())))
    return " + ".join(norm_tags)


class PatternMemoryEngine:
    """
    Local SQLite-backed Graphiti Temporal Pattern Memory Engine.
    Fast (<5ms), zero cloud dependencies, fully persistent.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            # Table 1: Pattern Nodes (Entities)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pattern_nodes (
                    pattern_id TEXT PRIMARY KEY,
                    canonical_name TEXT NOT NULL,
                    category TEXT DEFAULT 'STRUCTURAL',
                    occurrence_count INTEGER DEFAULT 1,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP
                )
            """)

            # Table 2: Pattern Walks (Episodes / Composite Sequences)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pattern_walks (
                    walk_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canonical_key TEXT NOT NULL,
                    patterns_json TEXT NOT NULL,
                    outcome TEXT NOT NULL,          -- 'WIN', 'TRAP', 'STUDY'
                    lesson TEXT DEFAULT '',
                    symbol TEXT DEFAULT 'XAUUSD',
                    occurrence_count INTEGER DEFAULT 1,
                    synaptic_weight REAL DEFAULT 1.0,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    created_at TIMESTAMP
                )
            """)

            # Table 3: Episode Events Log (Chronological Ingestion Audit)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episode_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    walk_id INTEGER,
                    symbol TEXT,
                    patterns_json TEXT,
                    outcome TEXT,
                    lesson TEXT,
                    source TEXT DEFAULT 'LIVE_OBSERVATION',
                    created_at TIMESTAMP,
                    FOREIGN KEY (walk_id) REFERENCES pattern_walks(walk_id)
                )
            """)

            # Indices for lightning-fast lookups
            conn.execute("CREATE INDEX IF NOT EXISTS idx_walks_key ON pattern_walks(canonical_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_walks_outcome ON pattern_walks(outcome)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_walks_weight ON pattern_walks(synaptic_weight DESC)")

    def add_episode(
        self,
        patterns: List[str],
        outcome: str,
        lesson: str = "",
        symbol: str = "XAUUSD",
        source: str = "LIVE_OBSERVATION"
    ) -> Dict[str, Any]:
        """
        Record a pattern walk episode (traded OR observed flat).
        Strengthens the synaptic weight of the walk and updates pattern nodes.
        """
        if not patterns or not isinstance(patterns, list):
            return {"status": "ERROR", "message": "Patterns list cannot be empty"}

        cleaned_patterns = [_normalize_pattern_tag(p) for p in patterns if p and str(p).strip()]
        if not cleaned_patterns:
            return {"status": "ERROR", "message": "No valid pattern tags found"}

        norm_outcome = str(outcome or "STUDY").strip().upper()
        if norm_outcome not in ("WIN", "TRAP", "STUDY"):
            norm_outcome = "WIN" if "WIN" in norm_outcome or "PROFIT" in norm_outcome else (
                "TRAP" if "TRAP" in norm_outcome or "LOSS" in norm_outcome else "STUDY"
            )

        now_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        canonical_key = _canonical_walk_key(cleaned_patterns)
        sym = str(symbol or "XAUUSD").strip().upper()
        clean_lesson = str(lesson or "").strip()

        with self._get_conn() as conn:
            cur = conn.cursor()

            # 1. Update pattern entity nodes
            for p_tag in cleaned_patterns:
                cur.execute("""
                    INSERT INTO pattern_nodes (pattern_id, canonical_name, occurrence_count, first_seen, last_seen)
                    VALUES (?, ?, 1, ?, ?)
                    ON CONFLICT(pattern_id) DO UPDATE SET
                        occurrence_count = occurrence_count + 1,
                        last_seen = ?
                """, (p_tag, p_tag, now_ts, now_ts, now_ts))

            # 2. Check if this exact walk + outcome already exists
            cur.execute("""
                SELECT walk_id, occurrence_count, synaptic_weight, lesson 
                FROM pattern_walks 
                WHERE canonical_key = ? AND outcome = ? AND symbol = ?
            """, (canonical_key, norm_outcome, sym))
            row = cur.fetchone()

            if row:
                walk_id = row["walk_id"]
                new_count = row["occurrence_count"] + 1
                # Synaptic reinforcement: Each repetition strengthens recall prominence
                new_weight = row["synaptic_weight"] + (1.0 if norm_outcome == "WIN" else 0.8)
                # Keep the newest lesson if provided, or retain past lesson
                updated_lesson = clean_lesson if clean_lesson else row["lesson"]

                cur.execute("""
                    UPDATE pattern_walks 
                    SET occurrence_count = ?, synaptic_weight = ?, lesson = ?, last_seen = ?
                    WHERE walk_id = ?
                """, (new_count, new_weight, updated_lesson, now_ts, walk_id))
            else:
                initial_weight = 1.2 if norm_outcome == "WIN" else 1.0
                cur.execute("""
                    INSERT INTO pattern_walks (
                        canonical_key, patterns_json, outcome, lesson, symbol, 
                        occurrence_count, synaptic_weight, first_seen, last_seen, created_at
                    ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                """, (
                    canonical_key,
                    json.dumps(cleaned_patterns),
                    norm_outcome,
                    clean_lesson,
                    sym,
                    initial_weight,
                    now_ts,
                    now_ts,
                    now_ts
                ))
                walk_id = cur.lastrowid

            # 3. Log event into history audit
            cur.execute("""
                INSERT INTO episode_events (walk_id, symbol, patterns_json, outcome, lesson, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (walk_id, sym, json.dumps(cleaned_patterns), norm_outcome, clean_lesson, source, now_ts))

        return {
            "status": "EPISODE_RECORDED",
            "walk_id": walk_id,
            "canonical_key": canonical_key,
            "outcome": norm_outcome,
            "patterns": cleaned_patterns,
            "lesson": clean_lesson
        }

    def search_facts(self, patterns: List[str], symbol: str = "XAUUSD", limit: int = 5) -> str:
        """
        Query memory for historical walks matching the queried pattern combination.
        Returns an ultra-dense, syntax-free text card (<100 tokens) for OpenCode.
        Incorporates the Resilient Swimmer Principle (contextual pitfall clarity, no blanket fear).
        """
        if not patterns or not isinstance(patterns, list):
            return "No patterns specified for Graphiti memory search."

        query_tags = [_normalize_pattern_tag(p) for p in patterns if p and str(p).strip()]
        if not query_tags:
            return "No valid pattern tags provided."

        sym = str(symbol or "XAUUSD").strip().upper()

        with self._get_conn() as conn:
            cur = conn.cursor()
            # Retrieve walks for this symbol, ordered by synaptic weight
            cur.execute("""
                SELECT walk_id, canonical_key, patterns_json, outcome, lesson, occurrence_count, synaptic_weight
                FROM pattern_walks
                WHERE symbol = ?
                ORDER BY synaptic_weight DESC
            """, (sym,))
            all_walks = cur.fetchall()

        if not all_walks:
            return f"=== GRAPHITI MEMORY: Zero recorded walks found for {sym} yet. ==="

        # Score matching walks by overlap count with query tags
        matched_wins = []
        matched_traps = []

        for w in all_walks:
            walk_pats = json.loads(w["patterns_json"])
            overlap = set(query_tags).intersection(set(walk_pats))
            if overlap:
                match_score = len(overlap) / max(len(query_tags), len(walk_pats))
                item = {
                    "walk_id": w["walk_id"],
                    "key": w["canonical_key"],
                    "patterns": walk_pats,
                    "outcome": w["outcome"],
                    "lesson": w["lesson"],
                    "count": w["occurrence_count"],
                    "weight": w["synaptic_weight"],
                    "overlap_count": len(overlap),
                    "match_score": match_score
                }
                if w["outcome"] == "WIN":
                    matched_wins.append(item)
                elif w["outcome"] == "TRAP":
                    matched_traps.append(item)

        # Sort by overlap count then synaptic weight
        matched_wins.sort(key=lambda x: (x["overlap_count"], x["weight"]), reverse=True)
        matched_traps.sort(key=lambda x: (x["overlap_count"], x["weight"]), reverse=True)

        if not matched_wins and not matched_traps:
            return (
                f"=== GRAPHITI PATTERN MEMORY ({sym}) ===\n"
                f"No previous walk matches combo: [{', '.join(query_tags)}].\n"
                f"Guidance: First encounter of this combination. Ground decision firmly in live 4TF trend and tape physics."
            )

        output_lines = [
            f"=== GRAPHITI PATTERN MEMORY: [{', '.join(query_tags)}] ({sym}) ==="
        ]

        total_wins = sum(x["count"] for x in matched_wins)
        total_traps = sum(x["count"] for x in matched_traps)
        output_lines.append(f"Recorded Experience: {total_wins} Winning Walks | {total_traps} Stumbles / Traps")

        # Summarize Top Winning Walk
        if matched_wins:
            top_w = matched_wins[0]
            w_lesson = f" - {top_w['lesson']}" if top_w['lesson'] else ""
            output_lines.append(
                f"- Winning Signature ({top_w['count']}x): [{top_w['key']}]{w_lesson}"
            )

        # Summarize Stumble / Trap Nuance (Resilient Swimmer Principle)
        if matched_traps:
            top_t = matched_traps[0]
            t_lesson = f" - Pitfall: {top_t['lesson']}" if top_t['lesson'] else ""
            output_lines.append(
                f"- Recorded Stumble ({top_t['count']}x): [{top_t['key']}]{t_lesson}"
            )
            output_lines.append(
                "- Resilient Swimmer Note: Do not fear the setup; avoid the specific pitfall above when technique aligns."
            )
        else:
            output_lines.append("- Zero trap stumbles recorded on this combination.")

        return "\n".join(output_lines)

    def get_pattern_walks(self, symbol: str = "XAUUSD", limit: int = 6) -> str:
        """
        Returns top dominant winning walks and trap walks for session recalibration during brainstorms.
        """
        sym = str(symbol or "XAUUSD").strip().upper()
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT canonical_key, outcome, lesson, occurrence_count, synaptic_weight
                FROM pattern_walks
                WHERE symbol = ? AND outcome = 'WIN'
                ORDER BY synaptic_weight DESC, occurrence_count DESC
                LIMIT ?
            """, (sym, limit))
            wins = cur.fetchall()

            cur.execute("""
                SELECT canonical_key, outcome, lesson, occurrence_count, synaptic_weight
                FROM pattern_walks
                WHERE symbol = ? AND outcome = 'TRAP'
                ORDER BY synaptic_weight DESC, occurrence_count DESC
                LIMIT ?
            """, (sym, limit))
            traps = cur.fetchall()

        if not wins and not traps:
            return f"No pattern walks recorded yet for {sym}."

        lines = [f"=== DOMINANT GRAPHITI PATTERN WALKS ({sym}) ==="]
        lines.append("PROVEN WINNING COMBINATIONS:")
        if wins:
            for w in wins:
                les = f" ({w['lesson']})" if w['lesson'] else ""
                lines.append(f"  [WIN] {w['occurrence_count']}x: [{w['canonical_key']}]{les}")
        else:
            lines.append("  (None recorded yet)")

        lines.append("DOCUMENTED TRAP FINGERPRINTS:")
        if traps:
            for t in traps:
                les = f" ({t['lesson']})" if t['lesson'] else ""
                lines.append(f"  [TRAP] {t['occurrence_count']}x: [{t['canonical_key']}]{les}")
        else:
            lines.append("  (None recorded yet)")

        return "\n".join(lines)

    def prune_decayed(self, decay_rate: float = 0.90, min_threshold: float = 0.20) -> str:
        """
        Gently attenuates stale unreinforced walks (Natural Forgetting).
        Walks with weight < min_threshold and occurrence_count <= 1 are cleaned up.
        """
        with self._get_conn() as conn:
            cur = conn.cursor()
            # Apply decay factor to all walks
            cur.execute("UPDATE pattern_walks SET synaptic_weight = synaptic_weight * ?", (decay_rate,))
            # Delete one-off anomalous noise below threshold
            cur.execute("DELETE FROM pattern_walks WHERE synaptic_weight < ? AND occurrence_count <= 1", (min_threshold,))
            deleted = cur.rowcount

        return f"Natural forgetting applied (decay factor: {decay_rate}). Pruned {deleted} stale one-off anomalies."
