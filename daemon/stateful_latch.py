"""Stateful Discovery Latch for Intelligent Trading Daemon.

Tracks active trade theses on disk (data/live/discovery_state.json) and suppresses
identical 10-second repeat log chatter. Only emits events on NEW_THESIS or MATERIAL_SHIFT.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, List

ALPHA_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ALPHA_ROOT / "data" / "live" / "discovery_state.json"

LOG = logging.getLogger("alpha.daemon.latch")

class StatefulDiscoveryLatch:
    def __init__(self):
        self.state_file = STATE_FILE
        self._state: Dict[str, Any] = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        try:
            if self.state_file.exists():
                text = self.state_file.read_text(encoding="utf-8")
                return json.loads(text)
        except Exception as e:
            LOG.warning(f"Failed to load discovery state file: {e}")
        return {}

    def _save_state(self):
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2)
        except Exception as e:
            LOG.error(f"Failed to save discovery state: {e}")

    def evaluate_thesis(self, symbol: str, current_score: float, bull_points: List[str], bear_points: List[str]) -> Tuple[bool, str]:
        """Evaluates whether to emit a discovery event.

        Returns (should_emit, reason):
        - (True, "NEW_THESIS"): No active thesis exists for symbol.
        - (True, "MATERIAL_SHIFT"): Score shifted by >= 1.0 or new bear trap risk emerged.
        - (False, "LATCHED_ACTIVE"): Market state is unchanged; suppress duplicate chatter.
        """
        symbol_key = symbol.upper()
        active = self._state.get(symbol_key)

        if not active:
            # New thesis
            self._state[symbol_key] = {
                "score": current_score,
                "bull_points": bull_points,
                "bear_points": bear_points,
                "status": "ACTIVE"
            }
            self._save_state()
            return True, "NEW_THESIS"

        # Check material state shift
        last_score = active.get("score", 0.0)
        last_bear = active.get("bear_points", [])

        score_delta = abs(current_score - last_score)
        new_bear_risk = len(bear_points) > len(last_bear)

        if score_delta >= 1.0 or new_bear_risk:
            # Material shift
            self._state[symbol_key]["score"] = current_score
            self._state[symbol_key]["bull_points"] = bull_points
            self._state[symbol_key]["bear_points"] = bear_points
            self._save_state()
            return True, "MATERIAL_SHIFT"

        # State unchanged
        return False, "LATCHED_ACTIVE"

    def clear_thesis(self, symbol: str):
        """Clears active thesis when setup is invalidated or executed."""
        symbol_key = symbol.upper()
        if symbol_key in self._state:
            del self._state[symbol_key]
            self._save_state()
