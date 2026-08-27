import os
import re
import json
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

LOG = logging.getLogger("alpha.pattern_book")

BOOK_DIR = r"C:\Trading\Alpha\logs\pattern_book"
BOOK_META_PATH = os.path.join(BOOK_DIR, "book_metadata.json")
BOOK_INDEX_PATH = os.path.join(BOOK_DIR, "book_index.md")
OUTCOMES_PATH = os.path.join(BOOK_DIR, "pattern_outcomes.json")

MAX_ENTRIES_PER_PAGE = 50
MAX_PAGES = 100


class PatternBookManager:
    """
    100-Page Structured Institutional Memory Book:
    - 100 pages maximum capacity (up to 5,000 entries).
    - Exactly 50 entries / lines per page.
    - Automatically rolls over to Page N+1 when current page reaches 50 entries.
    - Provides fast search, page retrieval, index inspection, and full book compilation.

    IMPORTANT (no hard gate): count >= 5 does NOT trigger automatic execution.
    It promotes a pattern to WATCHLIST/LEARNED status so the AGENT can evaluate it.
    Real learning requires recording trade OUTCOMES against each pattern
    (out-of-sample evidence), not repetition of narrative.
    """

    def __init__(self, book_dir: str = BOOK_DIR):
        self.book_dir = book_dir
        os.makedirs(self.book_dir, exist_ok=True)
        self._ensure_book()

    # ------------------------------------------------------------------
    # Key normalization — fixes the "count never accumulates" bug.
    # The LLM mints a new free-form name every cycle (e.g.
    # SCHEDULED_CYCLE_1544_REVIEW vs _1604_REVIEW); we strip volatile
    # tokens (digits, cycle/review markers) so the SAME phenomenon
    # matches and its hit count actually accumulates.
    # ------------------------------------------------------------------
    def _normalize_key(self, symbol: str, pattern_name: str) -> str:
        sym = symbol.strip().upper()
        key = pattern_name.strip().upper()
        key = re.sub(r"\d+", " ", key)            # drop cycle numbers / timestamps
        key = re.sub(r"[_\-]+", " ", key)         # underscores/hyphens -> space
        key = re.sub(r"[^A-Z ]", " ", key)        # keep A-Z and spaces only
        key = re.sub(r"\s+", " ", key).strip()    # collapse whitespace
        return f"{sym}|{key}"

    # ------------------------------------------------------------------
    # Outcome sidecar (decoupled from markdown so we never corrupt entries)
    # ------------------------------------------------------------------
    def _load_outcomes(self) -> Dict[str, List[Dict[str, Any]]]:
        if os.path.exists(OUTCOMES_PATH):
            try:
                with open(OUTCOMES_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                LOG.error(f"Error reading outcomes: {e}")
        return {}

    def _save_outcomes(self, data: Dict[str, List[Dict[str, Any]]]):
        try:
            with open(OUTCOMES_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            LOG.error(f"Error saving outcomes: {e}")

    def _record_outcome(self, key: str, outcome: str, ticket=None, r_value=None):
        data = self._load_outcomes()
        try:
            r_val = float(r_value) if r_value is not None else None
        except (TypeError, ValueError):
            r_val = None
        rec = {"outcome": outcome, "ticket": ticket,
               "r_value": r_val, "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        data.setdefault(key, []).append(rec)
        self._save_outcomes(data)

    def _outcome_count(self, key: str) -> int:
        return len(self._load_outcomes().get(key, []))

    # ------------------------------------------------------------------
    # Entry line parse / emit
    # ------------------------------------------------------------------
    def _parse_entry_line(self, line: str) -> Optional[Dict[str, Any]]:
        m = re.match(r"^-\s*\*\*\[([A-Z0-9]+)\]\s*([^\]]+?)\*\*\s*\[(.*?)\]:\s*(.*)$", line)
        if not m:
            return None
        sym = m.group(1)
        pname = m.group(2).strip()
        tag = m.group(3).strip()
        rest = m.group(4)
        outcomes_n = 0
        om = re.search(r"\(Outcomes:\s*(\d+)\)", rest)
        if om:
            outcomes_n = int(om.group(1))
        last_ts = ""
        lm = re.search(r"\(Last:\s*([^)]*)\)", rest)
        if lm:
            last_ts = lm.group(1).strip()
        obs = re.sub(r"\(Outcomes:\s*\d+\)", "", rest)
        obs = re.sub(r"\(Last:\s*[^)]*\)", "", obs)
        obs = obs.strip(" :")
        cnt = 1
        cm = re.search(r"Count:\s*(\d+)", tag)
        if cm:
            cnt = int(cm.group(1))
        return {"sym": sym, "pname": pname, "tag": tag, "obs": obs,
                "outcomes_n": outcomes_n, "last_ts": last_ts, "count": cnt}

    def _emit_entry_line(self, sym: str, pname: str, count: int, obs: str,
                         outcomes_n: int, last_ts: str) -> str:
        if count >= 5:
            tag = (f"WATCHLIST (>=5 HITS, {outcomes_n} outcomes logged — "
                   f"agent-evaluated, NO auto-execute)") if outcomes_n > 0 \
                else "WATCHLIST (>=5 HITS — awaiting outcome data, NO auto-execute)"
        else:
            tag = f"EXPLORATORY (Count: {count})"
        out_token = f"(Outcomes: {outcomes_n}) " if outcomes_n > 0 else ""
        return f"- **[{sym}] {pname}** [{tag}]: {obs} {out_token}(Last: {last_ts})"

    # ------------------------------------------------------------------
    # Filesystem helpers
    # ------------------------------------------------------------------
    def _get_page_filename(self, page_num: int) -> str:
        return os.path.join(self.book_dir, f"page_{page_num:03d}.md")

    def _ensure_book(self):
        if not os.path.exists(BOOK_META_PATH):
            initial_meta = {
                "title": "Alpha 100-Page Institutional Pattern & Memory Book",
                "max_pages": MAX_PAGES,
                "max_entries_per_page": MAX_ENTRIES_PER_PAGE,
                "active_page": 1,
                "total_entries": 0,
                "pages": {
                    "1": {"entries_count": 0, "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                }
            }
            self._save_metadata(initial_meta)
            self._init_page(1)
            self._render_index(initial_meta)

    def _get_metadata(self) -> Dict[str, Any]:
        if os.path.exists(BOOK_META_PATH):
            try:
                with open(BOOK_META_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                LOG.error(f"Error reading book metadata: {e}")
        return {
            "title": "Alpha 100-Page Institutional Pattern & Memory Book",
            "max_pages": MAX_PAGES,
            "max_entries_per_page": MAX_ENTRIES_PER_PAGE,
            "active_page": 1,
            "total_entries": 0,
            "pages": {"1": {"entries_count": 0}}
        }

    def _save_metadata(self, meta: Dict[str, Any]):
        try:
            with open(BOOK_META_PATH, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except Exception as e:
            LOG.error(f"Error saving book metadata: {e}")

    def _init_page(self, page_num: int):
        page_path = self._get_page_filename(page_num)
        if not os.path.exists(page_path):
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            content = (
                f"# ALPHA INSTITUTIONAL PATTERN BOOK — PAGE {page_num:03d} / {MAX_PAGES}\n"
                f"Created: {now_str} | Capacity: {MAX_ENTRIES_PER_PAGE} Entries\n"
                f"Mandate: count >= 5 promotes a pattern to WATCHLIST/LEARNED for the AGENT to evaluate "
                f"(NO auto-execution gate). Record trade OUTCOMES so the agent learns out-of-sample.\n"
                f"--------------------------------------------------------------------------------\n\n"
            )
            with open(page_path, "w", encoding="utf-8") as f:
                f.write(content)

    def _render_index(self, meta: Dict[str, Any]):
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        active_p = meta.get("active_page", 1)
        tot = meta.get("total_entries", 0)

        lines = [
            f"# 100-PAGE INSTITUTIONAL PATTERN BOOK INDEX",
            f"Last Updated: {now_str} | Active Page: Page {active_p:03d} / {MAX_PAGES} | Total Patterns Recorded: {tot}",
            f"",
            f"| Page # | Status | Entries Count | Capacity | File Link |",
            f"|---|---|---|---|---|"
        ]

        pages_dict = meta.get("pages", {})
        for p in range(1, active_p + 1):
            p_str = str(p)
            p_info = pages_dict.get(p_str, {})
            cnt = p_info.get("entries_count", 0)
            status = "ACTIVE" if p == active_p else "FULL"
            p_file = f"page_{p:03d}.md"
            p_link = f"[{p_file}](file:///C:/Trading/Alpha/logs/pattern_book/{p_file})"
            lines.append(f"| **Page {p:03d}** | {status} | {cnt} / {MAX_ENTRIES_PER_PAGE} | {cnt/MAX_ENTRIES_PER_PAGE*100:.0f}% | {p_link} |")

        lines.extend([
            f"",
            f"---",
            f"### Retrieval & Search Navigation:",
            f"- Use `mcp_alpha_get_book_page(page_number)` to read any specific page.",
            f"- Use `mcp_alpha_search_book(query)` to find patterns across all 100 pages.",
            f"- Use `mcp_alpha_get_book_index()` to inspect the table of contents.",
            f"- Use `mcp_alpha_get_full_book()` to read the entire compiled pattern library.",
            f"- Use `mcp_alpha_record_pattern_outcome(symbol, pattern_name, outcome, ticket, r_value)` to attach trade results."
        ])

        try:
            with open(BOOK_INDEX_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception as e:
            LOG.error(f"Error rendering book index: {e}")

    # ------------------------------------------------------------------
    # Core: record / increment
    # ------------------------------------------------------------------
    def record_pattern(self, symbol: str, pattern_name: str, observation: str,
                       outcome: str = None, ticket=None, r_value=None) -> Dict[str, Any]:
        """
        Record or increment a pattern observation. Matches by a DETERMINISTIC
        normalized key (instrument + de-noised name) so repeated phenomena
        accumulate instead of fragmenting into count:1 singletons.
        """
        meta = self._get_metadata()
        active_page = meta.get("active_page", 1)
        sym = symbol.strip().upper()
        pname = pattern_name.strip()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_key = self._normalize_key(symbol, pattern_name)

        if outcome is not None:
            self._record_outcome(new_key, outcome, ticket, r_value)

        # Step 1: find existing entry by normalized key on any page
        for p in range(1, active_page + 1):
            page_path = self._get_page_filename(p)
            if not os.path.exists(page_path):
                continue
            with open(page_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            matched_idx = -1
            matched_parsed = None
            for i, line in enumerate(lines):
                parsed = self._parse_entry_line(line)
                if parsed and self._normalize_key(parsed["sym"], parsed["pname"]) == new_key:
                    matched_idx = i
                    matched_parsed = parsed
                    break
            if matched_idx >= 0:
                new_count = matched_parsed["count"] + 1
                outcomes_n = self._outcome_count(new_key)
                updated = self._emit_entry_line(
                    sym, matched_parsed["pname"], new_count,
                    matched_parsed["obs"], outcomes_n, now_str)
                lines[matched_idx] = updated + "\n"
                with open(page_path, "w", encoding="utf-8") as f:
                    f.write("".join(lines))
                return {
                    "status": "UPDATED",
                    "page": p,
                    "symbol": sym,
                    "pattern_name": matched_parsed["pname"],
                    "count": new_count,
                    "validation": "WATCHLIST" if new_count >= 5 else "EXPLORATORY",
                    "outcomes_recorded": outcomes_n,
                    "observation": matched_parsed["obs"]
                }

        # Step 2: New pattern — append to current active page
        pages_dict = meta.get("pages", {})
        active_p_info = pages_dict.setdefault(str(active_page), {"entries_count": 0})
        curr_entries = active_p_info.get("entries_count", 0)

        if curr_entries >= MAX_ENTRIES_PER_PAGE:
            if active_page < MAX_PAGES:
                active_page += 1
                meta["active_page"] = active_page
                pages_dict[str(active_page)] = {"entries_count": 0, "created_at": now_str}
                self._init_page(active_page)
                curr_entries = 0
            else:
                LOG.warning("Pattern book reached maximum 100-page capacity (5,000 entries).")

        page_path = self._get_page_filename(active_page)
        self._init_page(active_page)

        outcomes_n = self._outcome_count(new_key)
        entry_line = self._emit_entry_line(sym, pname, 1, observation, outcomes_n, now_str) + "\n"
        with open(page_path, "a", encoding="utf-8") as f:
            f.write(entry_line)

        curr_entries += 1
        pages_dict[str(active_page)]["entries_count"] = curr_entries
        meta["total_entries"] = meta.get("total_entries", 0) + 1
        self._save_metadata(meta)
        self._render_index(meta)

        return {
            "status": "RECORDED_NEW",
            "page": active_page,
            "symbol": sym,
            "pattern_name": pname,
            "count": 1,
            "validation": "EXPLORATORY",
            "outcomes_recorded": outcomes_n,
            "observation": observation
        }

    def attach_outcome(self, symbol: str, pattern_name: str, outcome: str,
                      ticket=None, r_value=None) -> Dict[str, Any]:
        """Attach a trade outcome (PnL / R / ticket) to a pattern for learning."""
        new_key = self._normalize_key(symbol, pattern_name)
        self._record_outcome(new_key, outcome, ticket, r_value)
        outcomes_n = self._outcome_count(new_key)

        meta = self._get_metadata()
        active_page = meta.get("active_page", 1)
        for p in range(1, active_page + 1):
            page_path = self._get_page_filename(p)
            if not os.path.exists(page_path):
                continue
            with open(page_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for i, line in enumerate(lines):
                parsed = self._parse_entry_line(line)
                if parsed and self._normalize_key(parsed["sym"], parsed["pname"]) == new_key:
                    updated = self._emit_entry_line(
                        parsed["sym"], parsed["pname"], parsed["count"],
                        parsed["obs"], outcomes_n, parsed["last_ts"] or
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    lines[i] = updated + "\n"
                    with open(page_path, "w", encoding="utf-8") as f:
                        f.write("".join(lines))
                    return {"status": "OUTCOME_ATTACHED", "symbol": symbol.upper(),
                            "pattern_name": parsed["pname"], "outcomes_recorded": outcomes_n}
        return {"status": "NO_MATCHING_PATTERN", "symbol": symbol.upper(),
                "pattern_name": pattern_name, "outcomes_recorded": outcomes_n}

    def get_validation_summary(self) -> Dict[str, Any]:
        """Informational only (no gate). Surfaces WATCHLIST patterns + outcome stats
        so the agent can learn which patterns are actually validated."""
        meta = self._get_metadata()
        active_page = meta.get("active_page", 1)
        outcomes = self._load_outcomes()
        watchlist = []
        for p in range(1, active_page + 1):
            page_path = self._get_page_filename(p)
            if not os.path.exists(page_path):
                continue
            with open(page_path, "r", encoding="utf-8") as f:
                for line in f:
                    parsed = self._parse_entry_line(line)
                    if not parsed or parsed["count"] < 5:
                        continue
                    key = self._normalize_key(parsed["sym"], parsed["pname"])
                    recs = outcomes.get(key, [])
                    wins = sum(1 for r in recs if isinstance(r.get("r_value"), (int, float)) and r["r_value"] > 0)
                    losses = sum(1 for r in recs if isinstance(r.get("r_value"), (int, float)) and r["r_value"] <= 0)
                    watchlist.append({
                        "symbol": parsed["sym"],
                        "pattern_name": parsed["pname"],
                        "count": parsed["count"],
                        "outcomes_recorded": len(recs),
                        "wins": wins,
                        "losses": losses,
                    })
        return {"status": "SUCCESS", "watchlist_patterns": watchlist,
                "total_watchlist": len(watchlist)}

    def reindex_book(self) -> Dict[str, Any]:
        """Consolidate all existing entries by normalized key (remediates the
        current 200 count:1 fragments). Merges hit counts and preserves the
        earliest observation text. Outcomes JSON is already keyed by normalized
        key, so it remains valid."""
        meta = self._get_metadata()
        active_page = meta.get("active_page", 1)
        groups: Dict[str, Dict[str, Any]] = {}
        for p in range(1, active_page + 1):
            page_path = self._get_page_filename(p)
            if not os.path.exists(page_path):
                continue
            with open(page_path, "r", encoding="utf-8") as f:
                for line in f:
                    parsed = self._parse_entry_line(line)
                    if not parsed:
                        continue
                    key = self._normalize_key(parsed["sym"], parsed["pname"])
                    g = groups.setdefault(key, {
                        "sym": parsed["sym"], "pname": parsed["pname"],
                        "count": 0, "obs": parsed["obs"], "last_ts": parsed["last_ts"],
                        "first_ts": parsed["last_ts"], "outcomes_n": parsed["outcomes_n"]})
                    g["count"] += parsed["count"]
                    if parsed["last_ts"] > g["last_ts"]:
                        g["last_ts"] = parsed["last_ts"]

        consolidated = list(groups.values())
        # rewrite pages
        for p in range(1, active_page + 1):
            pp = self._get_page_filename(p)
            if os.path.exists(pp):
                os.remove(pp)
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_pages = {}
        page_no = 1
        self._init_page(page_no)
        lines_buff = [self._emit_entry_line(c["sym"], c["pname"], c["count"], c["obs"],
                                             c["outcomes_n"], c["last_ts"]) + "\n"
                     for c in consolidated]
        idx = 0
        page_meta = {}
        while idx < len(lines_buff):
            chunk = lines_buff[idx:idx + MAX_ENTRIES_PER_PAGE]
            page_path = self._get_page_filename(page_no)
            self._init_page(page_no)
            with open(page_path, "a", encoding="utf-8") as f:
                f.write("".join(chunk))
            page_meta[str(page_no)] = {"entries_count": len(chunk), "created_at": now_str}
            idx += MAX_ENTRIES_PER_PAGE
            page_no += 1

        new_meta = {
            "title": meta.get("title"),
            "max_pages": MAX_PAGES,
            "max_entries_per_page": MAX_ENTRIES_PER_PAGE,
            "active_page": page_no - 1,
            "total_entries": len(consolidated),
            "pages": page_meta,
            "reindexed_at": now_str,
            "note": "Consolidated by normalized key; prior 200 fragments merged."
        }
        self._save_metadata(new_meta)
        self._render_index(new_meta)
        return {"status": "REINDEXED", "before_entries": meta.get("total_entries"),
                "after_entries": len(consolidated), "pages": page_no - 1}

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------
    def get_page(self, page_num: int = 1) -> Dict[str, Any]:
        meta = self._get_metadata()
        active_p = meta.get("active_page", 1)
        if page_num < 1 or page_num > MAX_PAGES:
            return {"status": "ERROR", "error": f"Invalid page number {page_num}. Book range is 1 to {MAX_PAGES}."}

        page_path = self._get_page_filename(page_num)
        if not os.path.exists(page_path):
            return {"status": "EMPTY_PAGE", "page": page_num, "content": f"Page {page_num} is currently unwritten."}

        with open(page_path, "r", encoding="utf-8") as f:
            content = f.read()

        entries = [line for line in content.splitlines() if line.strip().startswith("- **[")]
        return {
            "status": "SUCCESS",
            "page": page_num,
            "is_active_page": (page_num == active_p),
            "total_entries_on_page": len(entries),
            "capacity": f"{len(entries)}/{MAX_ENTRIES_PER_PAGE}",
            "content": content
        }

    def search_book(self, query: str, max_results: int = 15) -> Dict[str, Any]:
        meta = self._get_metadata()
        active_page = meta.get("active_page", 1)
        q_lower = query.strip().lower()
        results = []

        for p in range(1, active_page + 1):
            page_path = self._get_page_filename(p)
            if os.path.exists(page_path):
                with open(page_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                for line_idx, line in enumerate(lines, 1):
                    if q_lower in line.lower() and line.strip().startswith("- **["):
                        results.append({
                            "page": p,
                            "line_number": line_idx,
                            "entry": line.strip(),
                            "page_link": f"file:///C:/Trading/Alpha/logs/pattern_book/page_{p:03d}.md#L{line_idx}"
                        })
                        if len(results) >= max_results:
                            break
            if len(results) >= max_results:
                break

        return {
            "status": "SUCCESS",
            "query": query,
            "matches_found": len(results),
            "results": results
        }

    def get_book_index(self) -> Dict[str, Any]:
        meta = self._get_metadata()
        active_p = meta.get("active_page", 1)
        pages_summary = []
        for p in range(1, active_p + 1):
            p_info = meta.get("pages", {}).get(str(p), {})
            cnt = p_info.get("entries_count", 0)
            pages_summary.append({
                "page": p,
                "status": "ACTIVE" if p == active_p else "FULL",
                "entries": cnt,
                "capacity": f"{cnt}/{MAX_ENTRIES_PER_PAGE}"
            })
        return {
            "status": "SUCCESS",
            "title": meta.get("title"),
            "max_pages": MAX_PAGES,
            "max_entries_per_page": MAX_ENTRIES_PER_PAGE,
            "active_page": active_p,
            "total_entries": meta.get("total_entries", 0),
            "pages": pages_summary
        }

    def get_full_book(self) -> str:
        meta = self._get_metadata()
        active_p = meta.get("active_page", 1)
        full_text = []
        for p in range(1, active_p + 1):
            page_path = self._get_page_filename(p)
            if os.path.exists(page_path):
                with open(page_path, "r", encoding="utf-8") as f:
                    full_text.append(f.read())
        return "\n\n".join(full_text)
