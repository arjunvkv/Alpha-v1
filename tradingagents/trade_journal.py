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

    def get_journal_data(self) -> dict:
        try:
            if os.path.exists(JSON_JOURNAL_PATH):
                with open(JSON_JOURNAL_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as err:
            LOG.error(f"Failed to read trade journal json: {err}")
        return {"winning_trades": [], "lessons_learned": [], "self_correction_rules": []}

    def _render_markdown(self, data: dict):
        lines = []
        lines.append("# Persistent Self-Study Trade Memory Journal")
        lines.append("This persistent memory store records all closed trades, root cause lessons, and self-correction rules to prevent repeating mistakes.\n")
        lines.append("> ⚠️ **5-HIT REPEAT THRESHOLD MANDATE**: OpenCode CIO must NOT enforce or act on a self-correction rule or lesson from these buckets UNLESS the exact same pattern/lesson has been observed and repeated 5 or more times (>= 5 hits) from real live trade executions ('hit and learn'). Single or low-frequency occurrences (< 5 hits) are exploratory data, NOT mandatory system constraints.\n")

        lines.append("## 🏆 WINNING_TRADES_BUCKET (What Worked Well)")
        for item in data.get("winning_trades", []):
            lines.append(f"- **{item.get('symbol')} Ticket #{item.get('ticket')}** (PnL +${item.get('pnl'):.2f}): {item.get('lesson')}")
        lines.append("")

        lines.append("## ⚠️ LESSONS_LEARNED_BUCKET (What Went Wrong)")
        for item in data.get("lessons_learned", []):
            lines.append(f"- **{item.get('symbol')} Ticket #{item.get('ticket')}** (PnL ${item.get('pnl'):.2f}): {item.get('lesson')}")
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
