import os
import json
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

LOG = logging.getLogger("alpha.pattern_book")

BOOK_DIR = r"C:\Trading\Alpha\logs\pattern_book"
BOOK_META_PATH = os.path.join(BOOK_DIR, "book_metadata.json")
BOOK_INDEX_PATH = os.path.join(BOOK_DIR, "book_index.md")

MAX_ENTRIES_PER_PAGE = 50
MAX_PAGES = 100

class PatternBookManager:
    """
    100-Page Structured Institutional Memory Book:
    - 100 pages maximum capacity (up to 5,000 entries).
    - Exactly 50 entries / lines per page (~2,200 tokens).
    - Automatically rolls over to Page N+1 when current page reaches 50 entries.
    - Provides fast search, page retrieval, index inspection, and full book compilation.
    """
    def __init__(self, book_dir: str = BOOK_DIR):
        self.book_dir = book_dir
        os.makedirs(self.book_dir, exist_ok=True)
        self._ensure_book()

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
                f"# 📖 ALPHA INSTITUTIONAL PATTERN BOOK — PAGE {page_num:03d} / {MAX_PAGES}\n"
                f"Created: {now_str} | Capacity: {MAX_ENTRIES_PER_PAGE} Entries\n"
                f"Mandate: Patterns with count >= 5 trigger high-conviction immediate execution.\n"
                f"--------------------------------------------------------------------------------\n\n"
            )
            with open(page_path, "w", encoding="utf-8") as f:
                f.write(content)

    def _render_index(self, meta: Dict[str, Any]):
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        active_p = meta.get("active_page", 1)
        tot = meta.get("total_entries", 0)
        
        lines = [
            f"# 📚 100-PAGE INSTITUTIONAL PATTERN BOOK INDEX",
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
            status = "🟢 ACTIVE" if p == active_p else "🔒 FULL"
            p_file = f"page_{p:03d}.md"
            p_link = f"[{p_file}](file:///C:/Trading/Alpha/logs/pattern_book/{p_file})"
            lines.append(f"| **Page {p:03d}** | {status} | {cnt} / {MAX_ENTRIES_PER_PAGE} | {cnt/MAX_ENTRIES_PER_PAGE*100:.0f}% | {p_link} |")

        lines.extend([
            f"",
            f"---",
            f"### 🔍 Retrieval & Search Navigation:",
            f"- Use `mcp_alpha_get_book_page(page_number)` to read any specific page.",
            f"- Use `mcp_alpha_search_book(query)` to find patterns across all 100 pages.",
            f"- Use `mcp_alpha_get_book_index()` to inspect the table of contents.",
            f"- Use `mcp_alpha_get_full_book()` to read the entire compiled pattern library."
        ])

        try:
            with open(BOOK_INDEX_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception as e:
            LOG.error(f"Error rendering book index: {e}")

    def record_pattern(self, symbol: str, pattern_name: str, observation: str) -> Dict[str, Any]:
        """
        Record or increment hit count of an institutional pattern observation.
        Auto-paginates when active page reaches MAX_ENTRIES_PER_PAGE (100).
        """
        meta = self._get_metadata()
        active_page = meta.get("active_page", 1)
        sym = symbol.strip().upper()
        pname = pattern_name.strip().upper()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Step 1: Check if pattern already exists on ANY active/historical page
        for p in range(1, active_page + 1):
            page_path = self._get_page_filename(p)
            if os.path.exists(page_path):
                with open(page_path, "r", encoding="utf-8") as f:
                    content = f.read()

                target_tag = f"[{sym}] {pname}"
                if target_tag in content:
                    # Update hit count on this page
                    lines = content.splitlines()
                    new_lines = []
                    new_count = 1
                    for line in lines:
                        if target_tag in line:
                            # Extract count
                            import re
                            m = re.search(r"Count:\s*(\d+)", line)
                            if m:
                                new_count = int(m.group(1)) + 1
                            else:
                                new_count = 2
                            conviction_tag = "HIGH CONVICTION (>= 5 HITS)" if new_count >= 5 else f"EXPLORATORY (Count: {new_count})"
                            updated_entry = f"- **[{sym}] {pname}** [{conviction_tag}]: {observation} (Last: {now_str})"
                            new_lines.append(updated_entry)
                        else:
                            new_lines.append(line)

                    with open(page_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(new_lines) + "\n")

                    return {
                        "status": "UPDATED",
                        "page": p,
                        "symbol": sym,
                        "pattern_name": pname,
                        "count": new_count,
                        "conviction": "HIGH_CONVICTION" if new_count >= 5 else "EXPLORATORY",
                        "observation": observation
                    }

        # Step 2: New pattern — append to current active page
        pages_dict = meta.get("pages", {})
        active_p_info = pages_dict.setdefault(str(active_page), {"entries_count": 0})
        curr_entries = active_p_info.get("entries_count", 0)

        # Check if active page is full (>= 100)
        if curr_entries >= MAX_ENTRIES_PER_PAGE:
            if active_page < MAX_PAGES:
                active_page += 1
                meta["active_page"] = active_page
                pages_dict[str(active_page)] = {"entries_count": 0, "created_at": now_str}
                self._init_page(active_page)
                curr_entries = 0
            else:
                LOG.warning("Pattern book reached maximum 100-page capacity (10,000 entries).")

        page_path = self._get_page_filename(active_page)
        self._init_page(active_page)

        entry_line = f"- **[{sym}] {pname}** [EXPLORATORY (Count: 1)]: {observation} (Last: {now_str})\n"
        with open(page_path, "a", encoding="utf-8") as f:
            f.write(entry_line)

        # Update metadata
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
            "conviction": "EXPLORATORY",
            "observation": observation
        }

    def get_page(self, page_num: int = 1) -> Dict[str, Any]:
        """Retrieve full text and parsed entries for a specific page."""
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
        """Search across all pages in the book for keywords, symbol, or pattern names."""
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
        """Return the table of contents and stats for all 100 pages."""
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
        """Compile and return the entire book content across all pages."""
        meta = self._get_metadata()
        active_p = meta.get("active_page", 1)
        full_text = []
        for p in range(1, active_p + 1):
            page_path = self._get_page_filename(p)
            if os.path.exists(page_path):
                with open(page_path, "r", encoding="utf-8") as f:
                    full_text.append(f.read())
        return "\n\n".join(full_text)
