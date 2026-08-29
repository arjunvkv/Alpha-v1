import os
import json
import logging
import datetime

LOG = logging.getLogger("alpha.trade_journal")

DOSSIER_DIR = r"C:\Trading\Alpha\logs"
JSON_JOURNAL_PATH = os.path.join(DOSSIER_DIR, "trade_journal_memory.json")
MD_JOURNAL_PATH = os.path.join(DOSSIER_DIR, "trade_journal_memory.md")

class TradeJournalMemory:
    """
    Self-Study Trade Memory Journal maintaining 3 persistent buckets:
    1. WINNING_TRADES_BUCKET: What worked well & high-conviction features to repeat.
    2. LESSONS_LEARNED_BUCKET: What went wrong & drawdown root causes.
    3. SELF_CORRECTION_RULES_BUCKET: Actionable rules to avoid past mistakes.
    """
    def __init__(self):
        os.makedirs(DOSSIER_DIR, exist_ok=True)
        self._ensure_journal()

    def _ensure_journal(self):
        if not os.path.exists(JSON_JOURNAL_PATH):
            initial_data = {
                "winning_trades": [
                    {"ticket": 528366541, "symbol": "XAGUSD", "pnl": 32.00, "lesson": "Bought near M5 Demand Zone with normal spread (43 pts). Quick profit target reached cleanly."}
                ],
                "lessons_learned": [
                    {"ticket": 528375334, "symbol": "XPTUSD", "pnl": -51.60, "lesson": "Entered XPTUSD while spread was in HIGH_SPIKE status (>500 pts). High spread ate initial margin capacity."}
                ],
                "self_correction_rules": [
                    "MANDATORY RULE 1: Never execute trades when live spread status is HIGH_SPIKE.",
                    "MANDATORY RULE 2: Target quick fixed $20-$30 USD micro-profit scalps and lock Break-Even at +$10 profit."
                ]
            }
            try:
                with open(JSON_JOURNAL_PATH, "w", encoding="utf-8") as f:
                    json.dump(initial_data, f, indent=2)
                self._render_markdown(initial_data)
            except Exception as err:
                LOG.error(f"Failed to initialize trade journal: {err}")

    def write_journal_memory(self):
        """Ensures the markdown trade journal file is fresh and rendered on disk."""
        data = self.get_journal_data()
        self._render_markdown(data)

    def record_closed_trade(self, ticket: int, symbol: str, side: str, pnl: float, entry_price: float, exit_price: float, reason: str = "") -> dict:
        """Records a closed trade, updates memory buckets, and re-renders markdown."""
        try:
            data = self.get_journal_data()
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if pnl >= 20.0:
                data["winning_trades"].append({
                    "timestamp": now_str,
                    "ticket": ticket,
                    "symbol": symbol,
                    "side": side,
                    "pnl": round(pnl, 2),
                    "lesson": f"SUCCESSFUL $20-$30 MICRO-SCALP: Closed at {exit_price} from {entry_price}. {reason}"
                })
            else:
                data["lessons_learned"].append({
                    "timestamp": now_str,
                    "ticket": ticket,
                    "symbol": symbol,
                    "side": side,
                    "pnl": round(pnl, 2),
                    "lesson": f"DRAWDOWN / LOSS ANALYSIS: Closed at {exit_price} from {entry_price} with PnL ${pnl:.2f}. Root Cause: {reason if reason else 'Market structural shift / spread expansion.'}"
                })
                # Add auto self-correction rule if loss occurred under high spread
                data["self_correction_rules"].append(f"MANDATORY CORRECTION ({symbol} #{ticket}): Audit entry market structure on {symbol} to ensure MTF alignment and normal spread before re-entering.")

            with open(JSON_JOURNAL_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            self._render_markdown(data)
            return data
        except Exception as err:
            LOG.error(f"Failed to record closed trade in journal: {err}")
            return {}

    def record_pattern_observation(self, symbol: str, pattern_name: str, observation: str) -> dict:
        """Records a research study observation / hypothetical setup pattern with incrementing hit count."""
        try:
            data = self.get_journal_data()
            if "research_study_patterns" not in data:
                data["research_study_patterns"] = []

            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            matched = False

            for item in data["research_study_patterns"]:
                if item.get("pattern_name", "").upper() == pattern_name.upper() and item.get("symbol", "").upper() == symbol.upper():
                    item["count"] = item.get("count", 1) + 1
                    item["last_observed"] = now_str
                    item["observation"] = observation
                    matched = True
                    break

            if not matched:
                data["research_study_patterns"].append({
                    "symbol": symbol.upper(),
                    "pattern_name": pattern_name.upper(),
                    "count": 1,
                    "observation": observation,
                    "first_observed": now_str,
                    "last_observed": now_str
                })

            with open(JSON_JOURNAL_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            self._render_markdown(data)
            return data
        except Exception as err:
            LOG.error(f"Failed to record pattern observation: {err}")
            return {}

    def get_journal_data(self) -> dict:
        try:
            if os.path.exists(JSON_JOURNAL_PATH):
                with open(JSON_JOURNAL_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as err:
            LOG.error(f"Failed to read trade journal json: {err}")
        return {"winning_trades": [], "lessons_learned": [], "self_correction_rules": [], "research_study_patterns": []}

    def _render_markdown(self, data: dict):
        lines = []
        lines.append("# Persistent Self-Study Trade Memory Journal")
        lines.append("This persistent memory store records all closed trades, root cause lessons, self-correction rules, and research study patterns.\n")
        lines.append("> ⚠️ **5-HIT REPEAT THRESHOLD MANDATE**: OpenCode CIO must NOT enforce or act on a self-correction rule or lesson from these buckets UNLESS the exact same pattern/lesson has been observed and repeated 5 or more times (>= 5 hits) from real live trade executions ('hit and learn'). Single or low-frequency occurrences (< 5 hits) are exploratory data, NOT mandatory system constraints.\n")

        lines.append("## 🏆 WINNING_TRADES_BUCKET (What Worked Well)")
        for item in data.get("winning_trades", []):
            lines.append(f"- **{item.get('symbol')} Ticket #{item.get('ticket')}** (PnL +${item.get('pnl'):.2f}): {item.get('lesson')}")
        lines.append("")

        lines.append("## ⚠️ LESSONS_LEARNED_BUCKET (What Went Wrong)")
        for item in data.get("lessons_learned", []):
            lines.append(f"- **{item.get('symbol')} Ticket #{item.get('ticket')}** (PnL ${item.get('pnl'):.2f}): {item.get('lesson')}")
        lines.append("")

        lines.append("## 💡 RESEARCH_STUDY_PATTERNS_BUCKET (Self-Study & Recurring Setups)")
        lines.append("Records observed market structure patterns, RSI momentum shifts, and hypothetical setup moves with hit counts (`count: N`).")
        lines.append("When a pattern hit count reaches **5 or more (count >= 5)**, OpenCode must use it for **FASTER ANALYSIS & HIGH-CONFIDENCE IMMEDIATE TRADE PLACEMENT**!\n")

        patterns = data.get("research_study_patterns", [])
        if not patterns:
            lines.append("- *No research study patterns recorded yet.*")
        for pat in patterns:
            cnt = pat.get("count", 1)
            conf_label = "HIGH CONVICTION (>= 5 HITS)" if cnt >= 5 else f"EXPLORATORY (Count: {cnt})"
            lines.append(f"- **[{pat.get('symbol')}] {pat.get('pattern_name')}** [{conf_label}]: {pat.get('observation')} (Last: {pat.get('last_observed')})")
        lines.append("")

        lines.append("## 🎯 SELF_CORRECTION_RULES_BUCKET (Mandatory Future Directives)")
        for rule in data.get("self_correction_rules", []):
            lines.append(f"- {rule}")
        lines.append("")

        try:
            with open(MD_JOURNAL_PATH, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception as err:
            LOG.error(f"Failed to render trade journal markdown: {err}")
