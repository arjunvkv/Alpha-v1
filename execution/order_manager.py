"""
Order Manager — order types, slippage tracking, fill quality.

Records every execution outcome to data/live/executions.json so
execution quality can be reviewed in post-trade analysis.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from config import LIVE_DATA_DIR, SLIPPAGE_TOLERANCE_PIPS

log = logging.getLogger("alpha.order_manager")

EXECUTIONS_FILE = LIVE_DATA_DIR / "executions.json"


class OrderManager:
    """Audit trail for all executions + slippage stats."""

    def __init__(self, executions_file: Path = EXECUTIONS_FILE):
        self.executions_file = Path(executions_file)

    def record_fill(self, decision_id: str, result: dict):
        """Append an execution record."""
        records = self._load()
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision_id": decision_id,
            **result,
            "within_tolerance": (result.get("slippage_pips", 99)
                                 <= SLIPPAGE_TOLERANCE_PIPS),
        }
        records.append(record)
        self._save(records)
        if not record["within_tolerance"]:
            log.warning(f"Slippage beyond tolerance: {result.get('slippage_pips')}p "
                        f"on {result.get('ticket')}")

    def get_stats(self, last_n: int = 50) -> dict:
        """Execution quality summary."""
        records = self._load()[-last_n:]
        if not records:
            return {"fills": 0}
        slips = [r.get("slippage_pips", 0) for r in records]
        return {
            "fills": len(records),
            "avg_slippage_pips": round(sum(slips) / len(slips), 2),
            "max_slippage_pips": max(slips),
            "within_tolerance_pct": round(
                sum(1 for r in records if r.get("within_tolerance")) / len(records) * 100, 1),
        }

    def _load(self) -> list:
        if self.executions_file.exists():
            try:
                with open(self.executions_file, encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                log.error("Corrupt executions.json — starting fresh")
        return []

    def _save(self, records: list):
        self.executions_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.executions_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, default=str)
        tmp.replace(self.executions_file)
