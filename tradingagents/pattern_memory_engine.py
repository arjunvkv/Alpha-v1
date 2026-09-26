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
import logging
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = Path(r"C:\Trading\Alpha\logs\graphiti_pattern_memory.db")
LOG = logging.getLogger("alpha.pattern_memory")


# Ephemeral noise patterns to reject completely
EPHEMERAL_NOISE = {
    "TURN_A", "TURN_B", "POST_WINDOW", "GATE_CLOSED", "SCHEDULED_REASSESSMENT",
    "VENDOR_ARTEFACT", "TAG_CLASSIFIER", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY",
    "UTC", "PILLAR4", "PROCESS_VIOLATION", "NO_OUTCOME_CLAIM", "SUBPOINT_DISPLACEMENT",
    "POST_CLOSE_GRIND", "PROVISIONAL_BREAK_RECLAIMED", "L2_PROXY_SERIES_NOT_ACCUMULATION",
    "FROZEN_TAPE_VENDOR_ARTEFACT", "CLOSE_APPROACH_LIQUIDITY_THINNING", "DEAD_WIRE_ZERO_CATALYST"
}

# Canonical synonym mapping to enforce 3-Vector Vocabulary
CANONICAL_SYNONYMS = {
    "4TF_BEARISH_LEANING": "4TF_BEARISH",
    "4TF_BULLISH_LEANING": "4TF_BULLISH",
    "4TF_STRONG_BEAR": "4TF_STRONG_BEARISH",
    "4TF_STRONG_BULL": "4TF_STRONG_BULLISH",
    "BSL_DOORSTEP": "BSL_SWEEP",
    "SSL_DOORSTEP": "SSL_SWEEP",
    "CVD_FLIP": "CVD_ABSORPTION",
    "DELTA_FLIP": "CVD_ABSORPTION",
    "BEAR_FVG": "BEARISH_FVG_SHELF",
    "BULL_FVG": "BULLISH_FVG_SHELF",
    "FVG_CE_MITIGATION": "FVG_CE_RETEST",
    "TURTLE_SOUP_RECLAIM": "TURTLE_SOUP",
    "PATTERN_A_RECLAIM": "PATTERN_A",
    "DAY_HIGH": "DAY_HIGH_SWEEP",
    "DAY_LOW": "DAY_LOW_SWEEP",
    "ASIAN_HIGH": "ASIAN_HIGH_SWEEP",
    "ASIAN_LOW": "ASIAN_LOW_SWEEP"
}


def _normalize_pattern_tag(tag: str) -> str:
    """Canonical normalization for pattern tags: uppercase, alphanumeric + underscores."""
    t = str(tag or "").strip().upper()
    t = re.sub(r"[^A-Z0-9_]+", "_", t)
    t = re.sub(r"_+", "_", t).strip("_")
    if t in EPHEMERAL_NOISE:
        return ""
    # Strip clock/timestamp patterns e.g. 20_56_UTC
    if re.search(r"\d{1,2}_\d{2}", t) or "UTC" in t:
        return ""
    return CANONICAL_SYNONYMS.get(t, t)


def parse_and_normalize_tags(p_input: Any) -> List[str]:
    """
    Robustly parses and normalizes pattern tags from any input format:
    - List of strings: ['TAG1', 'TAG2']
    - Comma-separated string: "TAG1, TAG2"
    - Plus-separated string: "TAG1 + TAG2"
    - JSON or Python list string: "['TAG1', 'TAG2']" or '["TAG1", "TAG2"]'
    - Single tag: "TAG1"
    Returns sorted unique normalized tags.
    """
    if p_input is None:
        return []
    
    raw_tags = []
    if isinstance(p_input, dict):
        # Extract from dict values or common keys like 'item', 'items', 'patterns', 'tags', 'values'
        for k in ("item", "items", "patterns", "tags", "values"):
            if k in p_input:
                return parse_and_normalize_tags(p_input[k])
        for v in p_input.values():
            raw_tags.extend(parse_and_normalize_tags(v))
    elif isinstance(p_input, (list, tuple, set)):
        for item in p_input:
            if isinstance(item, str) and ("," in item or "+" in item or "[" in item):
                raw_tags.extend(parse_and_normalize_tags(item))
            elif item:
                raw_tags.append(str(item))
    elif isinstance(p_input, str):
        s = p_input.strip()
        if (s.startswith("[") and s.endswith("]")) or (s.startswith("(") and s.endswith(")")):
            try:
                import ast
                parsed = ast.literal_eval(s)
                if isinstance(parsed, (list, tuple, set)):
                    return parse_and_normalize_tags(parsed)
            except Exception:
                pass
            try:
                parsed = json.loads(s)
                if isinstance(parsed, (list, tuple, set)):
                    return parse_and_normalize_tags(parsed)
            except Exception:
                pass
            s = s.strip("[]()").strip()
            
        if "," in s:
            raw_tags.extend(s.split(","))
        elif " + " in s:
            raw_tags.extend(s.split(" + "))
        elif "\n" in s:
            raw_tags.extend(s.split("\n"))
        elif s:
            raw_tags.append(s)
    else:
        raw_tags.append(str(p_input))

    cleaned = []
    for t in raw_tags:
        norm = _normalize_pattern_tag(t)
        if norm and len(norm) >= 2:
            cleaned.append(norm)

    return sorted(list(set(cleaned)))


def _canonical_walk_key(patterns: Any) -> str:
    """Sort-invariant canonical key for pattern sets."""
    norm_tags = parse_and_normalize_tags(patterns)
    return " + ".join(norm_tags)


def _tag_matches(q: str, p: str) -> bool:
    """Token-aware pattern tag matching that avoids false-positive substrings and negation traps."""
    if q == p:
        return True
    if len(q) < 3 or len(p) < 3:
        return False
    # Avoid matching negated antonyms (e.g. NON_STOP should not match STOP)
    if f"NON_{q}" in p or f"NON_{p}" in q:
        return False
    # Check token boundaries by underscore
    q_tokens = set(q.split("_"))
    p_tokens = set(p.split("_"))
    if q_tokens.issubset(p_tokens) or p_tokens.issubset(q_tokens):
        return True
    if p.startswith(q + "_") or p.endswith("_" + q) or ("_" + q + "_") in p:
        return True
    if q.startswith(p + "_") or q.endswith("_" + p) or ("_" + p + "_") in q:
        return True
    return False


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
                    recall_count INTEGER DEFAULT 0,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    last_recalled_at TIMESTAMP
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
                    recall_count INTEGER DEFAULT 0,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    last_recalled_at TIMESTAMP,
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

            # Table 4: Observation Usage & Retrieval Audit Log (Internal Audit Trail)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS observation_usage_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    walk_id INTEGER,
                    canonical_key TEXT,
                    outcome TEXT,
                    retrieval_type TEXT,
                    queried_tags TEXT,
                    lesson TEXT,
                    recalled_at TIMESTAMP,
                    FOREIGN KEY (walk_id) REFERENCES pattern_walks(walk_id)
                )
            """)

            # Dynamic migrations for existing databases
            try:
                walk_cols = [r["name"] for r in conn.execute("PRAGMA table_info(pattern_walks)").fetchall()]
                if "recall_count" not in walk_cols:
                    conn.execute("ALTER TABLE pattern_walks ADD COLUMN recall_count INTEGER DEFAULT 0")
                if "last_recalled_at" not in walk_cols:
                    conn.execute("ALTER TABLE pattern_walks ADD COLUMN last_recalled_at TIMESTAMP")
                if "source" not in walk_cols:
                    conn.execute("ALTER TABLE pattern_walks ADD COLUMN source TEXT DEFAULT 'LIVE_OBSERVATION'")

                node_cols = [r["name"] for r in conn.execute("PRAGMA table_info(pattern_nodes)").fetchall()]
                if "recall_count" not in node_cols:
                    conn.execute("ALTER TABLE pattern_nodes ADD COLUMN recall_count INTEGER DEFAULT 0")
                if "last_recalled_at" not in node_cols:
                    conn.execute("ALTER TABLE pattern_nodes ADD COLUMN last_recalled_at TIMESTAMP")
            except Exception as _mig_err:
                LOG.debug(f"DB column migration note: {_mig_err}")

            # Table 5: Institutional Playbook Knowledge Base (Decoupled Memory Tool)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS institutional_playbook (
                    concept_id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    author_citation TEXT NOT NULL,
                    core_law TEXT NOT NULL,
                    physical_trigger TEXT NOT NULL,
                    invalidation TEXT NOT NULL,
                    runway_behavior TEXT NOT NULL,
                    risk_guidance TEXT NOT NULL,
                    tags_json TEXT NOT NULL
                )
            """)

            # Indices for lightning-fast lookups
            conn.execute("CREATE INDEX IF NOT EXISTS idx_walks_key ON pattern_walks(canonical_key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_walks_outcome ON pattern_walks(outcome)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_walks_weight ON pattern_walks(synaptic_weight DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_walks_recall ON pattern_walks(recall_count DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_walk ON observation_usage_audit(walk_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON observation_usage_audit(recalled_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_playbook_cat ON institutional_playbook(category)")

            # Seed institutional playbook data into Graphiti graph
            self._seed_institutional_playbook(conn)

    def _seed_institutional_playbook(self, conn: sqlite3.Connection):
        """Seed the 22 institutional concepts into institutional_playbook, pattern_nodes, and pattern_walks."""
        try:
            from tradingagents.institutional_playbook_data import INSTITUTIONAL_CONCEPTS
            cur = conn.cursor()
            now_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

            for c in INSTITUTIONAL_CONCEPTS:
                tags_clean = [_normalize_pattern_tag(t) for t in c.get("tags", []) if t]
                tags_json = json.dumps(tags_clean)

                # 1. Update institutional_playbook table (full detailed reference card)
                cur.execute("""
                    INSERT OR REPLACE INTO institutional_playbook (
                        concept_id, category, title, author_citation,
                        core_law, physical_trigger, invalidation,
                        runway_behavior, risk_guidance, tags_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    c["concept_id"],
                    c["category"],
                    c["title"],
                    c["author_citation"],
                    c["core_law"],
                    c["physical_trigger"],
                    c["invalidation"],
                    c["runway_behavior"],
                    c["risk_guidance"],
                    tags_json
                ))

                # 2. Seed into pattern_nodes (Entity Nodes in Graphiti)
                for t in tags_clean:
                    cur.execute("""
                        INSERT INTO pattern_nodes (pattern_id, canonical_name, category, occurrence_count, first_seen, last_seen)
                        VALUES (?, ?, ?, 5, ?, ?)
                        ON CONFLICT(pattern_id) DO UPDATE SET
                            category = excluded.category,
                            last_seen = excluded.last_seen
                    """, (t, t, c["category"], now_ts, now_ts))

                # 3. Seed into pattern_walks (Canonical Institutional Anchor Walk in Graphiti)
                canon_key = _canonical_walk_key(tags_clean)
                lesson_text = f"[{c['title']}] ({c['author_citation']}) {c['core_law']} Trigger: {c['physical_trigger']}"

                existing = cur.execute(
                    "SELECT walk_id FROM pattern_walks WHERE canonical_key = ? AND source = 'INSTITUTIONAL_CANON'",
                    (canon_key,)
                ).fetchone()

                if existing:
                    cur.execute("""
                        UPDATE pattern_walks
                        SET patterns_json = ?, lesson = ?, synaptic_weight = 4.0, last_seen = ?
                        WHERE walk_id = ?
                    """, (tags_json, lesson_text, now_ts, existing["walk_id"]))
                else:
                    cur.execute("""
                        INSERT INTO pattern_walks (
                            canonical_key, patterns_json, outcome, lesson, symbol,
                            occurrence_count, synaptic_weight, source, first_seen, last_seen, created_at
                        ) VALUES (?, ?, 'WIN', ?, 'XAUUSD', 5, 4.0, 'INSTITUTIONAL_CANON', ?, ?, ?)
                    """, (canon_key, tags_json, lesson_text, now_ts, now_ts, now_ts))

            conn.commit()
        except Exception as e:
            LOG.error(f"Error seeding institutional playbook into Graphiti graph: {e}")

    def add_episode(
        self,
        patterns: Any,
        outcome: str,
        lesson: str = "",
        symbol: str = "XAUUSD",
        source: str = "LIVE_OBSERVATION"
    ) -> Dict[str, Any]:
        """
        Record a pattern walk episode (traded OR observed flat).
        Strengthens the synaptic weight of the walk and updates pattern nodes.
        """
        cleaned_patterns = parse_and_normalize_tags(patterns)
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
        
        # Clean lesson text from ephemeral diary artifacts
        clean_lesson = str(lesson or "").strip()
        if clean_lesson:
            clean_lesson = re.sub(r"Turn [AB][^,:]*[:,-]?", "", clean_lesson, flags=re.IGNORECASE)
            clean_lesson = re.sub(r"\d{1,2}:\d{2}(?::\d{2})?\s*(?:UTC)?", "", clean_lesson, flags=re.IGNORECASE)
            clean_lesson = re.sub(r"\b\d{5,6}\.?\d*\b", "", clean_lesson) # strip balance / ticket numbers
            clean_lesson = re.sub(r"\s+", " ", clean_lesson).strip(" ,;-")

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

    def record_observation(
        self,
        patterns: List[str],
        observation: str = "",
        outcome: str = "STUDY",
        symbol: str = "XAUUSD"
    ) -> Dict[str, Any]:
        """Record an active observation into Graphiti Temporal Memory (alias for add_episode)."""
        return self.add_episode(
            patterns=patterns,
            outcome=outcome,
            lesson=observation,
            symbol=symbol,
            source="LIVE_OBSERVATION"
        )

    @staticmethod
    def _dense_card_summary(text: str, max_chars: int = 380) -> str:
        """Compress forensic lessons into punchy, high-signal summaries while guaranteeing core rules/lessons are never cut mid-word or mid-sentence."""
        if not text:
            return ""
        t = " ".join(text.strip().split())
        if len(t) <= max_chars:
            return t
        
        # Check if there is an explicit punchline like 'Lesson:', 'KEY TRAP SIGNATURE:', 'Pitfall:', 'Trigger:', 'Confirms:', 'Rule'
        punchline = ""
        # Search for punchlines without prematurely stopping at decimal points in numbers (\d\.\d)
        punchline_match = re.search(r'(Lesson|KEY TRAP SIGNATURE|Pitfall|Trigger|Confirms|Rule \d+):?\s*(.+?)(?=(?:\.\s+[A-Z]|\.$|$))', t, re.IGNORECASE)
        if punchline_match:
            punchline_str = punchline_match.group(0).strip()
            if len(punchline_str) <= max_chars // 2:
                punchline = f" [{punchline_str}]"
        
        # Available room for lead context
        room = max_chars - len(punchline) - 5
        if room < 60:
            room = max_chars - 5
            punchline = ""
            
        lead = t[:room]
        # Look for sentence break: period followed by space and not preceded by digit (avoids breaking prices like 4327.85)
        sentence_breaks = [m.end() for m in re.finditer(r'(?<!\d)\.\s+', lead)]
        if sentence_breaks and sentence_breaks[-1] > 60:
            lead = lead[:sentence_breaks[-1]].rstrip()
        else:
            # Word boundary
            last_space = lead.rfind(" ")
            if last_space > 60:
                lead = lead[:last_space].rstrip() + "..."
            else:
                lead = lead.rstrip() + "..."
                
        return f"{lead}{punchline}"

    @staticmethod
    def _format_structured_anchor(title: str, citation: str, law: str, trigger: str, max_chars: int = 340) -> str:
        """Format an institutional concept from structured fields cleanly without fragile regexes."""
        y_m = re.search(r'\b(19\d\d|20\d\d)\b', citation)
        year = y_m.group(1) if y_m else ""
        first_part = citation.split(';')[0].split(',')[0].strip()
        first_part = re.sub(r'[\'\"\(].*?[\'\"]', '', first_part)
        first_part = re.sub(r'[\(\)]', '', first_part).strip()
        short_cit = f"{first_part} {year}".strip() if year and year not in first_part else first_part

        header = f"[{title}] ({short_cit}): "
        trig_str = f" Trigger: {trigger}" if trigger else ""

        full_text = f"{header}{law}{trig_str}"
        full_text = " ".join(full_text.strip().split())
        if len(full_text) <= max_chars:
            return full_text

        room_for_law = max_chars - len(header) - len(trig_str) - 3
        if room_for_law >= 60:
            law_cut = law[:room_for_law]
            sb = [m.end() for m in re.finditer(r'(?<!\d)\.\s+', law_cut)]
            if sb and sb[-1] > 40:
                law_cut = law_cut[:sb[-1]].rstrip()
            else:
                sp = law_cut.rfind(' ')
                if sp > 40:
                    law_cut = law_cut[:sp].rstrip() + "..."
                else:
                    law_cut = law_cut.rstrip() + "..."

            # Ensure no unclosed parentheses in truncated law
            if law_cut.count("(") > law_cut.count(")"):
                last_open = law_cut.rfind("(")
                if last_open > 30:
                    law_cut = law_cut[:last_open].rstrip() + "..."

            res = f"{header}{law_cut}{trig_str}"
            return " ".join(res.strip().split())
        else:
            res = full_text[:max_chars - 3]
            sp = res.rfind(' ')
            if sp > 100:
                res = res[:sp] + "..."
            if res.count("(") > res.count(")"):
                last_open = res.rfind("(")
                if last_open > 30:
                    res = res[:last_open].rstrip() + "..."
            return " ".join(res.strip().split())

    def _format_canon_anchor(self, canon_item: Dict[str, Any], max_chars: int = 340) -> str:
        """Format an institutional canon anchor directly from institutional_playbook table if available."""
        lesson_raw = canon_item.get("lesson", "")
        title_match = re.match(r'\[([^\]]+)\]', lesson_raw)
        title = title_match.group(1).strip() if title_match else ""
        
        row = None
        if title:
            try:
                with self._get_conn() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT title, author_citation, core_law, physical_trigger FROM institutional_playbook WHERE title = ?", (title,))
                    row = cur.fetchone()
            except Exception:
                row = None
                
        if row:
            return self._format_structured_anchor(row["title"], row["author_citation"], row["core_law"], row["physical_trigger"], max_chars=max_chars)
            
        return self._dense_card_summary(lesson_raw, max_chars=max_chars)

    def search_facts(self, patterns: Any, symbol: str = "XAUUSD", limit: int = 5) -> str:
        """
        Query memory for historical walks matching the queried pattern combination.
        Returns an ultra-dense, syntax-free text card (<100 tokens) for OpenCode.
        Incorporates the Resilient Swimmer Principle (contextual pitfall clarity, no blanket fear).
        """
        sym = str(symbol or "XAUUSD").strip().upper()
        query_tags = parse_and_normalize_tags(patterns)
        if not query_tags:
            return (
                f"=== GRAPHITI PATTERN MEMORY ({sym}) ===\n"
                f"Notice: No valid pattern tags provided. search_facts requires specific candidate setup tags (e.g. ['BSL_SWEEP', 'CVD_ABSORPTION'] or ['4TF_STRONG_BEARISH', 'FVG_SHELF']).\n"
                f"Provide 2-4 tags matching the active candidate setup to recall winning signatures and documented traps."
            )

        with self._get_conn() as conn:
            cur = conn.cursor()
            # Retrieve walks for this symbol, ordered by synaptic weight
            cur.execute("""
                SELECT walk_id, canonical_key, patterns_json, outcome, lesson, occurrence_count, synaptic_weight, COALESCE(source, 'LIVE_OBSERVATION') as source
                FROM pattern_walks
                WHERE symbol = ?
                ORDER BY synaptic_weight DESC
            """, (sym,))
            all_walks = cur.fetchall()

        if not all_walks:
            return f"=== GRAPHITI MEMORY: Zero recorded walks found for {sym} yet. ==="

        # Score matching walks by token-aware overlap with query tags
        matched_live_wins = []
        matched_live_traps = []
        matched_study = []
        matched_canon = []

        for w in all_walks:
            try:
                walk_pats = json.loads(w["patterns_json"])
            except Exception:
                continue
            overlap = set()
            for q in query_tags:
                for p in walk_pats:
                    if _tag_matches(q, p):
                        overlap.add(p)
            if overlap:
                match_score = len(overlap) / max(len(query_tags), len(walk_pats))
                item = {
                    "walk_id": w["walk_id"],
                    "key": w["canonical_key"],
                    "patterns": walk_pats,
                    "outcome": w["outcome"],
                    "lesson": w["lesson"] or "",
                    "count": w["occurrence_count"],
                    "weight": w["synaptic_weight"],
                    "source": w["source"],
                    "overlap_count": len(overlap),
                    "match_score": match_score
                }
                if w["source"] == "INSTITUTIONAL_CANON":
                    matched_canon.append(item)
                elif w["outcome"] == "WIN":
                    matched_live_wins.append(item)
                elif w["outcome"] == "TRAP":
                    matched_live_traps.append(item)
                elif w["outcome"] == "STUDY":
                    matched_study.append(item)

        # Sort by overlap count primary, synaptic weight + recency bonus secondary
        def _walk_rank(x):
            recency = min(1.0, (x.get("walk_id", 0) / 3000.0)) * 0.7
            return (x["overlap_count"], x["weight"] + recency)

        matched_live_wins.sort(key=_walk_rank, reverse=True)
        matched_live_traps.sort(key=_walk_rank, reverse=True)
        matched_canon.sort(key=_walk_rank, reverse=True)
        matched_study.sort(key=_walk_rank, reverse=True)

        if not matched_live_wins and not matched_live_traps and not matched_canon and not matched_study:
            return (
                f"=== GRAPHITI PATTERN MEMORY ({sym}) ===\n"
                f"No previous walk matches combo: [{', '.join(query_tags)}].\n"
                f"- Novel Setup: Zero prior live fills on this exact combination (Pioneering Walk).\n"
                f"- Guidance: Ground thesis strictly in 4TF alignment and physical tape absorption. If executing, use probe sizing (0.50L)."
            )

        output_lines = [
            f"=== GRAPHITI PATTERN MEMORY: [{', '.join(query_tags)}] ({sym}) ==="
        ]

        total_live_wins = sum(x["count"] for x in matched_live_wins)
        total_live_traps = sum(x["count"] for x in matched_live_traps)
        
        # Differentiate exact composite overlap vs loose component overlap
        exact_wins = [x for x in matched_live_wins if x["overlap_count"] >= len(query_tags)]
        exact_traps = [x for x in matched_live_traps if x["overlap_count"] >= len(query_tags)]
        
        if len(query_tags) > 1 and (exact_wins or exact_traps):
            ew_count = sum(x["count"] for x in exact_wins)
            et_count = sum(x["count"] for x in exact_traps)
            output_lines.append(
                f"Desk Experience: {ew_count} Live Wins | {et_count} Traps on exact setup ({total_live_wins}W | {total_live_traps}T across related components)"
            )
        else:
            output_lines.append(f"Desk Experience: {total_live_wins} Live Wins | {total_live_traps} Stumbles / Traps")

        # Contrast 1: Top Live Winning Walk (What made it win)
        if matched_live_wins:
            top_w = matched_live_wins[0]
            w_lesson = f" - Valid Trigger: {self._dense_card_summary(top_w['lesson'], 240)}" if top_w['lesson'] else ""
            output_lines.append(
                f"- Winning Signature ({top_w['count']}x): [{top_w['key']}]{w_lesson}"
            )

        # Contrast 2: Top Recorded Stumble / Pitfall (What broke it)
        if matched_live_traps:
            top_t = matched_live_traps[0]
            t_lesson = f" - Failure Pitfall: {self._dense_card_summary(top_t['lesson'], 240)}" if top_t['lesson'] else ""
            output_lines.append(
                f"- Recorded Stumble ({top_t['count']}x): [{top_t['key']}]{t_lesson}"
            )
            output_lines.append(
                "- Condition Test: A past stumble is NOT a veto. If the stumble's adverse condition is absent on live tape, setup is CLEARED."
            )
        elif not matched_live_wins and not matched_live_traps:
            # If no live trade fills, display recent study observations if present
            if matched_study and matched_study[0].get("lesson"):
                top_s = matched_study[0]
                s_note = f" - Recent Observation ({top_s['count']}x): {self._dense_card_summary(top_s['lesson'], 220)}"
                output_lines.append(f"- Live Desk Execution: Zero prior trade fills ({len(matched_study)} study cycles recorded).{s_note}")
            else:
                output_lines.append("- Live Desk Execution: Zero prior live fills on exact combination.")
        else:
            output_lines.append("- Clean Record: Zero stumbles recorded for this combination under proper execution.")

        # Institutional Literature Anchor (Foundational market auction law)
        if matched_canon:
            top_c = matched_canon[0]
            output_lines.append(
                f"- Institutional Literature Anchor: {self._format_canon_anchor(top_c, 340)}"
            )

        # --- INTERNAL AUDIT TRACKING (COMPLETELY INVISIBLE TO OPENCODE) ---
        # Increments internal recall_count for utilized walks/nodes and logs audit event
        try:
            now_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            recalled_walks = []
            if matched_live_wins:
                recalled_walks.append(matched_live_wins[0])
            if matched_live_traps:
                recalled_walks.append(matched_live_traps[0])
            if matched_canon:
                recalled_walks.append(matched_canon[0])
            for m in (matched_live_wins[1:] + matched_live_traps[1:] + matched_canon[1:]):
                if m["walk_id"] not in [r["walk_id"] for r in recalled_walks]:
                    recalled_walks.append(m)

            with self._get_conn() as conn:
                cur = conn.cursor()
                for rw in recalled_walks:
                    cur.execute("""
                        UPDATE pattern_walks 
                        SET recall_count = recall_count + 1, last_recalled_at = ?
                        WHERE walk_id = ?
                    """, (now_ts, rw["walk_id"]))
                    cur.execute("""
                        INSERT INTO observation_usage_audit (
                            walk_id, canonical_key, outcome, retrieval_type, queried_tags, lesson, recalled_at
                        ) VALUES (?, ?, ?, 'SEARCH_FACTS', ?, ?, ?)
                    """, (rw["walk_id"], rw["key"], rw["outcome"], json.dumps(query_tags), rw["lesson"], now_ts))

                for p_tag in query_tags:
                    cur.execute("""
                        UPDATE pattern_nodes
                        SET recall_count = recall_count + 1, last_recalled_at = ?
                        WHERE pattern_id = ?
                    """, (now_ts, p_tag))
        except Exception as _audit_err:
            LOG.debug(f"Audit counter increment error in search_facts: {_audit_err}")

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

        # --- INTERNAL AUDIT TRACKING (COMPLETELY INVISIBLE TO OPENCODE) ---
        try:
            now_ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            with self._get_conn() as conn:
                cur = conn.cursor()
                for w in wins:
                    cur.execute("""
                        UPDATE pattern_walks 
                        SET recall_count = recall_count + 1, last_recalled_at = ?
                        WHERE canonical_key = ? AND outcome = 'WIN' AND symbol = ?
                    """, (now_ts, w["canonical_key"], sym))
                    cur.execute("""
                        INSERT INTO observation_usage_audit (
                            walk_id, canonical_key, outcome, retrieval_type, queried_tags, lesson, recalled_at
                        ) VALUES (
                            (SELECT walk_id FROM pattern_walks WHERE canonical_key = ? AND outcome = 'WIN' AND symbol = ? LIMIT 1),
                            ?, 'WIN', 'GET_PATTERN_WALKS', '[]', ?, ?
                        )
                    """, (w["canonical_key"], sym, w["canonical_key"], w["lesson"], now_ts))

                for t in traps:
                    cur.execute("""
                        UPDATE pattern_walks 
                        SET recall_count = recall_count + 1, last_recalled_at = ?
                        WHERE canonical_key = ? AND outcome = 'TRAP' AND symbol = ?
                    """, (now_ts, t["canonical_key"], sym))
                    cur.execute("""
                        INSERT INTO observation_usage_audit (
                            walk_id, canonical_key, outcome, retrieval_type, queried_tags, lesson, recalled_at
                        ) VALUES (
                            (SELECT walk_id FROM pattern_walks WHERE canonical_key = ? AND outcome = 'TRAP' AND symbol = ? LIMIT 1),
                            ?, 'TRAP', 'GET_PATTERN_WALKS', '[]', ?, ?
                        )
                    """, (t["canonical_key"], sym, t["canonical_key"], t["lesson"], now_ts))
        except Exception as _audit_err:
            LOG.debug(f"Audit counter increment error in get_pattern_walks: {_audit_err}")

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

    def get_audit_usage_summary(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Internal audit inspection: returns pattern walks ordered by how often
        OpenCode has recalled / used them.
        """
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT walk_id, canonical_key, outcome, occurrence_count, recall_count, last_recalled_at, lesson
                FROM pattern_walks
                WHERE recall_count > 0
                ORDER BY recall_count DESC, last_recalled_at DESC
                LIMIT ?
            """, (limit,))
            return [dict(r) for r in cur.fetchall()]

    def get_recent_audit_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Internal audit log: returns recent observation retrieval events.
        """
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT audit_id, walk_id, canonical_key, outcome, retrieval_type, queried_tags, lesson, recalled_at
                FROM observation_usage_audit
                ORDER BY audit_id DESC
                LIMIT ?
            """, (limit,))
            return [dict(r) for r in cur.fetchall()]



