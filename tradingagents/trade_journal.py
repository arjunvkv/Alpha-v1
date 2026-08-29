import os
import json
import logging

from tradingagents.unified_learning_memory import DOSSIER_DIR, LEGACY_JOURNAL_PATH as JSON_JOURNAL_PATH, UnifiedLearningMemory

LOG = logging.getLogger("alpha.trade_journal")
MD_JOURNAL_PATH = os.path.join(DOSSIER_DIR, "trade_journal_memory.md")


class TradeJournalMemory:
    """Compatibility facade for Alpha's canonical Unified Learning Memory."""

    def __init__(self):
        os.makedirs(DOSSIER_DIR, exist_ok=True)
        self.memory = UnifiedLearningMemory()
        self.memory.migrate_legacy()
        self._ensure_journal()

    def _ensure_journal(self):
        if not os.path.exists(JSON_JOURNAL_PATH):
            initial_data = {
                "winning_trades": [{"ticket": 528366541, "symbol": "XAGUSD", "pnl": 32.00, "lesson": "Bought near M5 Demand Zone with normal spread (43 pts). Quick profit target reached cleanly."}],
                "lessons_learned": [{"ticket": 528375334, "symbol": "XPTUSD", "pnl": -51.60, "lesson": "Entered XPTUSD while spread was in HIGH_SPIKE status (>500 pts). High spread ate initial margin capacity."}],
                "self_correction_rules": [
                    "MANDATORY RULE 1: Never execute trades when live spread status is HIGH_SPIKE.",
                    "MANDATORY RULE 2: Target quick fixed micro-profit scalps and lock Break-Even at positive profit."
                ]
            }
            with open(JSON_JOURNAL_PATH, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, indent=2)
            self.memory.migrate_legacy()

    def write_journal_memory(self):
        self._render_markdown(self.get_journal_data())

    def record_closed_trade(self, ticket, symbol, side, pnl, entry_price, exit_price, reason=""):
        if pnl >= 20.0:
            lesson = "SUCCESSFUL MICRO-SCALP: Closed at {} from {}. {}".format(exit_price, entry_price, reason)
        else:
            lesson = "DRAWDOWN / LOSS ANALYSIS: Closed at {} from {} with PnL {}. Root Cause: {}".format(
                exit_price, entry_price, pnl,
                reason if reason else "Market structural shift / spread expansion."
            )
        self.memory.record_experience(
            ticket=ticket, symbol=symbol, direction_taken=side, pnl=pnl,
            entry_price=entry_price, exit_price=exit_price,
            lesson=lesson, reason=reason
        )
        data = self.get_journal_data()
        self._render_markdown(data)
        return data

    def record_pattern_observation(self, symbol, pattern_name, observation):
        self.memory.record_pattern(symbol, pattern_name, observation)
        data = self.get_journal_data()
        self._render_markdown(data)
        return data

    def get_journal_data(self):
        legacy = {"winning_trades": [], "lessons_learned": [], "self_correction_rules": [], "research_study_patterns": []}
        try:
            if os.path.exists(JSON_JOURNAL_PATH):
                with open(JSON_JOURNAL_PATH, "r", encoding="utf-8") as f:
                    legacy = json.load(f)
        except Exception as err:
            LOG.error("Failed to read trade journal json: %s", err)
        legacy["unified_memory"] = self.memory.migration_report()
        legacy["canonical_store"] = self.memory.path
        return legacy

    def _render_markdown(self, data):
        report = self.memory.migration_report()
        lines = [
            "# Persistent Self-Study Trade Memory Journal",
            "This file is a compatibility view. Canonical runtime learning is Unified Learning Memory.",
            "",
            "## Unified Learning",
            "- Canonical store: " + str(report["canonical_store"]),
            "- Experiences: " + str(report["experiences"]),
            "- Patterns: " + str(report["patterns"]),
            "- Pattern evidence accumulates without a 5-hit threshold.",
            "- Historical lessons and corrections are study evidence, not execution directives.",
            "- Direction taken is preserved when available.",
            "- The Agent is the sole trading decision-maker.",
            "",
            "## Legacy Historical Archive",
            "The original Trade Journal data remains preserved and is migrated non-destructively.",
            "",
            "### WINNING_TRADES_BUCKET"
        ]
        for item in data.get("winning_trades", []):
            lines.append("- {} Ticket #{}: {}".format(item.get("symbol"), item.get("ticket"), item.get("lesson")))
        lines.append("")
        lines.append("### LESSONS_LEARNED_BUCKET")
        for item in data.get("lessons_learned", []):
            lines.append("- {} Ticket #{}: {}".format(item.get("symbol"), item.get("ticket"), item.get("lesson")))
        lines.append("")
        lines.append("### SELF_CORRECTION_RULES_BUCKET")
        for rule in data.get("self_correction_rules", []):
            lines.append("- Historical learning: " + str(rule))
        lines.append("")
        try:
            with open(MD_JOURNAL_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception as err:
            LOG.error("Failed to render trade journal markdown: %s", err)
