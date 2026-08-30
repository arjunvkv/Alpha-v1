"""Pre-Trade Decision Snapshot Recorder for Alpha Trading Desk.

Enforces Constitutional Mandate s4.137 (Separation of Process vs Outcome).
Records the complete market state, thesis, conviction, in-direction FVG fill%,
spread, contradictions count, and regime flag at the exact moment of trade decision.
"""

import os
import json
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, Optional

LOG = logging.getLogger("alpha.tradingagents.decision_recorder")
ALPHA_ROOT = Path(r"C:\Trading\Alpha")
SNAPSHOTS_LOG_PATH = ALPHA_ROOT / "logs" / "decision_snapshots.jsonl"

class PreTradeDecisionRecorder:
    """Persists pre-trade context and reasoning parameters for subsequent forensics."""

    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path or SNAPSHOTS_LOG_PATH
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def record_decision(
        self,
        symbol: str,
        side: str,
        conviction_score: float,
        in_direction_fvg_fill_pct: Optional[float] = None,
        spread_pts: int = 0,
        regime_flag: str = "NORMAL",
        contradictions_count: int = 0,
        notes: str = "",
        volume: float = 0.0,
        sl: float = 0.0,
        tp: float = 0.0
    ) -> Dict[str, Any]:
        """Saves a structured pre-trade decision snapshot."""
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
        
        snapshot = {
            "timestamp_utc": utc_now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "timestamp_ist": ist_now.strftime("%Y-%m-%d %H:%M:%S IST"),
            "symbol": symbol.strip().upper(),
            "side": side.strip().upper(),
            "volume": volume,
            "sl": sl,
            "tp": tp,
            "conviction_score": conviction_score,
            "in_direction_fvg_fill_pct": in_direction_fvg_fill_pct,
            "spread_pts": spread_pts,
            "regime_flag": regime_flag,
            "contradictions_count": contradictions_count,
            "notes": notes,
            "process_evaluated": True,
            "decision_authority": "OPENCODE_CIO_ONLY"
        }

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
            LOG.info(f"Recorded pre-trade decision snapshot for {symbol} {side} (Conviction: {conviction_score}, Fill: {in_direction_fvg_fill_pct}%)")
        except Exception as e:
            LOG.error(f"Failed to record pre-trade snapshot: {e}")

        return {
            "status": "RECORDED",
            "log_path": str(self.log_path),
            "snapshot": snapshot
        }
