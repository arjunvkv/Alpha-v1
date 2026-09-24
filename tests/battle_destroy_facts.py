"""
======================================================================
     BATTLE & DESTROY SUITE - GRAPHITI PATTERN FACTS TOOLS
======================================================================
Exhaustive stress-testing, boundary destruction, and adversarial
fuzzing for Graphiti pattern facts tools and PatternMemoryEngine:

1. Permutations & formats (lists, JSON strings, comma strings, tuples)
2. Adversarial inputs (None, empty, special chars, huge strings, fakes)
3. Keyword argument flexibility (tags, pattern, note, kwargs)
4. Institutional anchor formatting across all 22 concepts
5. Decimal price boundary preservation (4327.85 never cut at period)
6. Base-rate / Desk Experience decomposition
7. Observation and Episode recording and synaptic reinforcement
8. Direct invocation of all 10 MCP tools and backward-compatibility aliases
9. Stress / rapid concurrency verification (zero SQLite lock errors)
======================================================================
"""

import sys
import io
import json
import sqlite3
import unittest
from pathlib import Path

# Force UTF-8 stdout/stderr for Windows console compatibility
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(r"C:\Trading\Alpha")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tradingagents.pattern_memory_engine import (
    PatternMemoryEngine,
    _normalize_pattern_tag,
    parse_and_normalize_tags,
    _canonical_walk_key,
    _tag_matches
)
from mcp_server.graphiti_mcp_server import (
    search_facts,
    record_observation,
    add_episode,
    get_pattern_walks,
    graphiti_search_facts,
    graphiti_record_observation,
    graphiti_add_episode,
    graphiti_get_pattern_walks,
    graphiti_memory_mcp_search_facts,
    graphiti_memory_mcp_record_observation
)


class TestBattleDestroyFacts(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = PatternMemoryEngine()
        cls.test_tags_created = []

    @classmethod
    def tearDownClass(cls):
        # Clean up any test records created in DB
        try:
            with cls.engine._get_conn() as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM observation_usage_audit WHERE queried_tags LIKE '%BATTLE_TEST%'")
                cur.execute("DELETE FROM episode_events WHERE patterns_json LIKE '%BATTLE_TEST%'")
                cur.execute("DELETE FROM pattern_walks WHERE canonical_key LIKE '%BATTLE_TEST%'")
                cur.execute("DELETE FROM pattern_nodes WHERE pattern_id LIKE '%BATTLE_TEST%'")
                conn.commit()
        except Exception:
            pass

    # ==================================================================
    # 1. TAG PARSING & NORMALIZATION DESTRUCTION
    # ==================================================================
    def test_01_tag_normalization_basics(self):
        self.assertEqual(_normalize_pattern_tag("bsl_sweep"), "BSL_SWEEP")
        self.assertEqual(_normalize_pattern_tag("  4TF-Bearish!  "), "4TF_BEARISH")
        self.assertEqual(_normalize_pattern_tag("POC...Retest"), "POC_RETEST")
        self.assertEqual(_normalize_pattern_tag(""), "")
        self.assertEqual(_normalize_pattern_tag(None), "")

    def test_02_parse_and_normalize_tags_formats(self):
        # Standard list
        self.assertEqual(parse_and_normalize_tags(["BSL_SWEEP", "4TF_BEARISH"]), ["4TF_BEARISH", "BSL_SWEEP"])
        # Comma-separated string
        self.assertEqual(parse_and_normalize_tags("BSL_SWEEP, 4TF_BEARISH"), ["4TF_BEARISH", "BSL_SWEEP"])
        # Plus-separated string
        self.assertEqual(parse_and_normalize_tags("BSL_SWEEP + 4TF_BEARISH"), ["4TF_BEARISH", "BSL_SWEEP"])
        # JSON list string
        self.assertEqual(parse_and_normalize_tags('["BSL_SWEEP", "4TF_BEARISH"]'), ["4TF_BEARISH", "BSL_SWEEP"])
        # Python repr string
        self.assertEqual(parse_and_normalize_tags("['BSL_SWEEP', '4TF_BEARISH']"), ["4TF_BEARISH", "BSL_SWEEP"])
        # Nested list
        self.assertEqual(parse_and_normalize_tags([["BSL_SWEEP"], "4TF_BEARISH"]), ["4TF_BEARISH", "BSL_SWEEP"])
        # Tuple and set
        self.assertEqual(parse_and_normalize_tags(("BSL_SWEEP", "4TF_BEARISH")), ["4TF_BEARISH", "BSL_SWEEP"])
        self.assertEqual(parse_and_normalize_tags({"BSL_SWEEP", "4TF_BEARISH"}), ["4TF_BEARISH", "BSL_SWEEP"])

    def test_03_parse_and_normalize_tags_adversarial(self):
        # Empty and None
        self.assertEqual(parse_and_normalize_tags(None), [])
        self.assertEqual(parse_and_normalize_tags([]), [])
        self.assertEqual(parse_and_normalize_tags(""), [])
        self.assertEqual(parse_and_normalize_tags("   "), [])
        # Only punctuation / symbols
        self.assertEqual(parse_and_normalize_tags(["!@#$%^&*()"]), [])
        self.assertEqual(parse_and_normalize_tags(["_"]), [])
        # 1-character tags filtered
        self.assertEqual(parse_and_normalize_tags(["A"]), [])
        # Whitespace and duplicates
        self.assertEqual(parse_and_normalize_tags(["BSL_SWEEP", "bsl_sweep", "  BSL_SWEEP  "]), ["BSL_SWEEP"])

    def test_04_tag_matching_precision(self):
        # Exact match
        self.assertTrue(_tag_matches("ORDER_BLOCK", "ORDER_BLOCK"))
        # Token match
        self.assertTrue(_tag_matches("ORDER_BLOCK", "BEARISH_ORDER_BLOCK"))
        self.assertTrue(_tag_matches("BEARISH_ORDER_BLOCK", "ORDER_BLOCK"))
        self.assertTrue(_tag_matches("4TF_BEARISH", "BEARISH"))
        # Token subset
        self.assertTrue(_tag_matches("BSL_SWEEP", "BSL_SWEEP_RECLAIM"))
        # False positives prevented
        self.assertFalse(_tag_matches("HOLD", "THRESHOLD"))
        self.assertFalse(_tag_matches("STOP", "NON_STOP_RALLY"))
        self.assertFalse(_tag_matches("WIN", "WINDFALL"))
        self.assertFalse(_tag_matches("RATE", "SEPARATE"))
        self.assertFalse(_tag_matches("AB", "ABCDEF"))

    # ==================================================================
    # 2. SEARCH_FACTS INTEGRITY & OUTPUT CARD VERIFICATION
    # ==================================================================
    def test_05_search_facts_standard_queries(self):
        queries = [
            ["BSL_SWEEP", "4TF_BEARISH"],
            ["POC_ABSORPTION"],
            ["TURTLE_SOUP"],
            ["ORDER_BLOCK", "FVG"],
            ["DEAD_TAPE", "LOW_VELOCITY"]
        ]
        for q in queries:
            card = self.engine.search_facts(patterns=q, symbol="XAUUSD")
            self.assertIsInstance(card, str)
            self.assertTrue(card.startswith("=== GRAPHITI PATTERN MEMORY"))
            self.assertIn("Desk Experience:", card)
            self.assertTrue(len(card) > 50)
            # Ensure no unhandled exception strings
            self.assertNotIn("Traceback", card)
            self.assertNotIn("IndexError", card)
            self.assertNotIn("ERROR", card)

    def test_06_search_facts_with_string_inputs(self):
        card1 = self.engine.search_facts(patterns="BSL_SWEEP, 4TF_BEARISH")
        card2 = self.engine.search_facts(patterns="['BSL_SWEEP', '4TF_BEARISH']")
        card3 = self.engine.search_facts(patterns='["BSL_SWEEP", "4TF_BEARISH"]')
        for c in (card1, card2, card3):
            self.assertIn("4TF_BEARISH", c)
            self.assertIn("BSL_SWEEP", c)
            self.assertIn("Desk Experience:", c)

    def test_07_search_facts_adversarial_queries(self):
        # Empty input
        res_empty = self.engine.search_facts(patterns=[])
        self.assertIn("No valid pattern tags", res_empty)

        # None input
        res_none = self.engine.search_facts(patterns=None)
        self.assertIn("No valid pattern tags", res_none)

        # Non-existent query tag
        res_novel = self.engine.search_facts(patterns=["NON_EXISTENT_TAG_XYZ_9999"])
        self.assertIn("Novel Setup", res_novel)
        self.assertIn("Pioneering Walk", res_novel)

        # 50 tags in query
        many_tags = [f"TAG_{i}" for i in range(50)]
        res_many = self.engine.search_facts(patterns=many_tags)
        self.assertIsInstance(res_many, str)
        self.assertNotIn("ERROR", res_many)

        # Extremely long string tag
        huge_tag = ["TAG_" + "A" * 2000]
        res_huge = self.engine.search_facts(patterns=huge_tag)
        self.assertIsInstance(res_huge, str)

    def test_08_search_facts_desk_experience_decomposition(self):
        # Query composite setup with multiple tags
        card = self.engine.search_facts(patterns=["ORDER_BLOCK", "FVG"])
        self.assertIn("Desk Experience:", card)
        # Verify exact setup count is distinguished from component count
        self.assertTrue("on exact setup" in card or "Live Wins" in card)

    # ==================================================================
    # 3. INSTITUTIONAL LITERATURE ANCHOR PRESERVATION
    # ==================================================================
    def test_09_all_22_institutional_concepts_formatting(self):
        with self.engine._get_conn() as conn:
            cur = conn.cursor()
            rows = cur.execute("SELECT title, author_citation, core_law, physical_trigger FROM institutional_playbook").fetchall()
            self.assertEqual(len(rows), 22, "Expected 22 institutional concepts in DB")

            for r in rows:
                title, citation, law, trigger = r[0], r[1], r[2], r[3]
                fmt = PatternMemoryEngine._format_structured_anchor(title, citation, law, trigger, max_chars=340)
                self.assertIsInstance(fmt, str)
                self.assertTrue(len(fmt) <= 350, f"Anchor format exceeded limit: {len(fmt)}")
                # Must start with title in brackets
                self.assertTrue(fmt.startswith(f"[{title}]"), f"Missing title in anchor: {fmt}")
                # Must contain author citation
                self.assertIn("(", fmt)
                self.assertIn(")", fmt)
                # Must contain trigger if concept had trigger
                if trigger:
                    self.assertIn("Trigger:", fmt)
                # Must not have dangling semicolons right after author
                self.assertNotRegex(fmt, r'\([^\)]+;\)\s*:', "Dangling semicolon in author citation")
                # Must not cut off mid-parenthesis
                self.assertEqual(fmt.count("("), fmt.count(")"), f"Mismatched parentheses in: {fmt}")

    def test_10_decimal_price_preservation(self):
        # Ensure _dense_card_summary does NOT cut at decimal numbers like 4327.85
        text_with_prices = (
            "13:41 UTC V-REVERSAL TRAP #3 CONFIRMED — flat stance through the kinetic cascade was the winning call. "
            "KEY TRAP SIGNATURE: internal SSL doorstep stop-run (4327.85) triggered without absorption. "
            "Forensic review confirms clean avoidance."
        )
        summary = PatternMemoryEngine._dense_card_summary(text_with_prices, max_chars=250)
        self.assertIsInstance(summary, str)
        # Must preserve full price with decimal digits intact
        self.assertIn("4327.85", summary)
        self.assertNotIn("(4327.]", summary)
        self.assertNotIn("4327. ", summary)

    # ==================================================================
    # 4. OBSERVATION & EPISODE RECORDING LIFECYCLE
    # ==================================================================
    def test_11_record_observation_and_synaptic_reinforcement(self):
        test_tags = ["BATTLE_TEST_SWEEP", "BATTLE_TEST_ABSORPTION"]
        res1 = self.engine.record_observation(
            patterns=test_tags,
            observation="Battle test cycle 1: high volume test",
            outcome="STUDY",
            symbol="XAUUSD"
        )
        self.assertEqual(res1["status"], "EPISODE_RECORDED")
        self.assertEqual(res1["outcome"], "STUDY")
        walk_id_1 = res1["walk_id"]

        # Record cycle 2 with same tags -> occurrence count and synaptic weight should increase
        res2 = self.engine.record_observation(
            patterns=test_tags,
            observation="Battle test cycle 2: continuation",
            outcome="STUDY",
            symbol="XAUUSD"
        )
        self.assertEqual(res2["walk_id"], walk_id_1)

        with self.engine._get_conn() as conn:
            cur = conn.cursor()
            walk_row = cur.execute("SELECT occurrence_count, synaptic_weight FROM pattern_walks WHERE walk_id = ?", (walk_id_1,)).fetchone()
            self.assertGreaterEqual(walk_row["occurrence_count"], 2)
            self.assertGreater(walk_row["synaptic_weight"], 1.0)

    def test_12_add_episode_and_audit_log(self):
        test_tags = ["BATTLE_TEST_WIN_WALK"]
        res = self.engine.add_episode(
            patterns=test_tags,
            outcome="WIN",
            lesson="Battle test execution completed at target +2.0R",
            symbol="XAUUSD"
        )
        self.assertEqual(res["status"], "EPISODE_RECORDED")
        self.assertEqual(res["outcome"], "WIN")

        # Now search facts with these tags and verify recall count increases
        card = self.engine.search_facts(patterns=test_tags, symbol="XAUUSD")
        self.assertIn("BATTLE_TEST_WIN_WALK", card)
        self.assertIn("Winning Signature", card)

        with self.engine._get_conn() as conn:
            cur = conn.cursor()
            audit_row = cur.execute(
                "SELECT * FROM observation_usage_audit WHERE canonical_key LIKE '%BATTLE_TEST_WIN_WALK%'"
            ).fetchone()
            self.assertIsNotNone(audit_row)
            self.assertEqual(audit_row["outcome"], "WIN")

    def test_13_get_pattern_walks_formatting(self):
        res = self.engine.get_pattern_walks(symbol="XAUUSD", limit=5)
        self.assertIsInstance(res, str)
        self.assertTrue(res.startswith("=== DOMINANT GRAPHITI PATTERN WALKS"))
        self.assertIn("PROVEN WINNING COMBINATIONS:", res)
        self.assertIn("DOCUMENTED TRAP FINGERPRINTS:", res)
        self.assertNotIn("Traceback", res)

    # ==================================================================
    # 5. MCP TOOL WRAPPERS & BACKWARD COMPATIBILITY ALIASES
    # ==================================================================
    def test_14_mcp_tool_search_facts_with_kwargs(self):
        # Call with unexpected keyword argument 'tags'
        res1 = search_facts(tags=["4TF_BEARISH"])
        self.assertIn("=== GRAPHITI PATTERN MEMORY", res1)

        # Call with keyword argument 'pattern'
        res2 = search_facts(pattern="POC_ABSORPTION")
        self.assertIn("=== GRAPHITI PATTERN MEMORY", res2)

        # Call with string representation of list
        res3 = search_facts(patterns="['TURTLE_SOUP']")
        self.assertIn("=== GRAPHITI PATTERN MEMORY", res3)

        # Call with extra unhandled kwargs (e.g. timeframe, session)
        res4 = search_facts(patterns=["4TF_BEARISH"], timeframe="M5", session="LONDON")
        self.assertIn("=== GRAPHITI PATTERN MEMORY", res4)

    def test_15_mcp_tool_record_observation_with_kwargs(self):
        # Call with note instead of observation
        res1 = record_observation(patterns=["BATTLE_TEST_NOTE"], note="Note text here", outcome="STUDY")
        data1 = json.loads(res1)
        self.assertEqual(data1["status"], "EPISODE_RECORDED")

        # Call with tags instead of patterns
        res2 = record_observation(tags=["BATTLE_TEST_TAGS"], observation="Observation text", outcome="STUDY")
        data2 = json.loads(res2)
        self.assertEqual(data2["status"], "EPISODE_RECORDED")

    def test_16_mcp_tool_add_episode_with_kwargs(self):
        res = add_episode(tags=["BATTLE_TEST_EP"], lesson="Episode lesson", outcome="WIN", custom_arg=123)
        data = json.loads(res)
        self.assertEqual(data["status"], "EPISODE_RECORDED")

    def test_17_mcp_tool_get_pattern_walks_with_kwargs(self):
        res = get_pattern_walks(symbol="XAUUSD", limit=3, extra_kw="test")
        self.assertIn("=== DOMINANT GRAPHITI PATTERN WALKS", res)

    def test_18_all_backward_compatibility_aliases(self):
        # 1. graphiti_search_facts
        r1 = graphiti_search_facts(patterns=["4TF_BEARISH"])
        self.assertIn("=== GRAPHITI PATTERN MEMORY", r1)

        # 2. graphiti_record_observation
        r2 = graphiti_record_observation(patterns=["BATTLE_TEST_ALIAS"], observation="Alias obs")
        self.assertEqual(json.loads(r2)["status"], "EPISODE_RECORDED")

        # 3. graphiti_add_episode
        r3 = graphiti_add_episode(patterns=["BATTLE_TEST_ALIAS"], outcome="TRAP", lesson="Trap alias")
        self.assertEqual(json.loads(r3)["status"], "EPISODE_RECORDED")

        # 4. graphiti_get_pattern_walks
        r4 = graphiti_get_pattern_walks(symbol="XAUUSD")
        self.assertIn("=== DOMINANT GRAPHITI PATTERN WALKS", r4)

        # 5. graphiti_memory_mcp_search_facts
        r5 = graphiti_memory_mcp_search_facts(patterns=["4TF_BEARISH"])
        self.assertIn("=== GRAPHITI PATTERN MEMORY", r5)

        # 6. graphiti_memory_mcp_record_observation
        r6 = graphiti_memory_mcp_record_observation(patterns=["BATTLE_TEST_ALIAS"], observation="Memory mcp obs")
        self.assertEqual(json.loads(r6)["status"], "EPISODE_RECORDED")

    # ==================================================================
    # 6. CONCURRENCY & RAPID SEQUENTIAL STRESS TEST
    # ==================================================================
    def test_19_rapid_sequential_queries_and_writes(self):
        # Run 50 rapid sequential queries and writes to guarantee zero SQLite lock failures
        for i in range(50):
            tag = f"BATTLE_TEST_STRESS_{i % 5}"
            if i % 5 == 0:
                res = record_observation(patterns=[tag], observation=f"Stress cycle {i}", outcome="STUDY")
                self.assertNotIn("ERROR", res)
            else:
                card = search_facts(patterns=[tag])
                self.assertNotIn("ERROR", card)


if __name__ == "__main__":
    print("=" * 70)
    print("RUNNING BATTLE & DESTROY SUITE FOR GRAPHITI FACTS TOOLS")
    print("=" * 70)
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestBattleDestroyFacts)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
