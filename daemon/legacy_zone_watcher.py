"""Legacy zone watcher - extracted v1 reference (DAEMON_V2_SPEC.md s2).

Daemon v1 fused zone detection INTO the daemon process: proximity checks,
cooldowns and price-move gates fired zone_approach wakes directly. V2
retires that coupling - zones now live only inside AI-authored alert
rules, and this daemon executes conditions mechanically.

This module preserves the v1 ZoneWatcher logic as an importable reference
so future code can consult the old trigger semantics without resurrecting
them in the live loop. NOT imported by any v2 module.
"""

import json
import os
import time

ZONE_COOLDOWN_SEC = 1800        # per-zone re-trigger cooldown
PRICE_MOVE_THRESHOLD_PCT = 0.15 # min price movement between triggers


class ZoneWatcher:
    """V1 proximity watcher over data/live/zones.json."""

    def __init__(self, mt5_interface, zones_path):
        self.mt5 = mt5_interface
        self.zones_path = zones_path
        self._last_fire = {}   # "SYMBOL:TYPE" -> epoch ts

    # ----------------------------------------------------------- state ---
    def _load_zones(self):
        if not os.path.exists(self.zones_path):
            return {}
        try:
            with open(self.zones_path, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {}

    def update_zones(self):
        """Refresh zones.json from current chart objects / indicators."""
        raise NotImplementedError(
            "reference extraction only - see daemon.py history")

    # -------------------------------------------------------- triggers ---
    @staticmethod
    def _pct_move(a, b):
        if not b:
            return 0.0
        return abs(a - b) / abs(b) * 100.0

    def _should_fire_zone_trigger(self, symbol, zone_type, price):
        key = "%s:%s" % (symbol, zone_type)
        last = self._last_fire.get(key)
        now = time.time()
        if last is not None:
            if now - last < ZONE_COOLDOWN_SEC:
                return False, "cooldown"
            if self._pct_move(price, last) < PRICE_MOVE_THRESHOLD_PCT:
                return False, "no_price_movement"
        return True, ""
