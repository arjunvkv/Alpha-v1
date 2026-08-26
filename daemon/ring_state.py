"""Ring state store (DAEMON_V2_SPEC.md section 5).

Append-only event log + fire-once latches + filled-ticket ledger, persisted
atomically as JSON. No .tmp litter survives a crash.
"""

import copy
import json
import os
import threading

DEFAULT_STATE = {"events": [], "latches": {}, "filled_tickets": []}
MAX_EVENTS = 1000


class RingStateStore:
    def __init__(self, path=None):
        # accept pathlib.Path or str uniformly
        self._lock = threading.Lock()
        self.path = path

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, value):
        # coerce Path->str so post-construction reassignment is safe too
        self._path = str(value) if value is not None else None

    # ------------------------------------------------------------- io ----
    def load(self):
        """Return persisted state merged over defaults. Never raises."""
        state = copy.deepcopy(DEFAULT_STATE)
        if not self.path or not os.path.exists(self.path):
            return state
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return state
        if isinstance(data, dict):
            for key, default in DEFAULT_STATE.items():
                value = data.get(key)
                if isinstance(value, type(default)):
                    state[key] = value
        return state

    def save(self, state):
        """Atomic persist: write .tmp then os.replace."""
        if not self.path:
            return
        with self._lock:
            tmp_path = self.path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2)
            os.replace(tmp_path, self.path)

    # --------------------------------------------------------- events ----
    def record(self, event):
        """Append one event dict, cap history, persist."""
        state = self.load()
        state["events"].append(event)
        if len(state["events"]) > MAX_EVENTS:
            state["events"] = state["events"][-MAX_EVENTS:]
        self.save(state)
        return event

    # -------------------------------------------------------- latches ----
    def latch(self, rule_id, kind):
        state = self.load()
        entry = state["latches"].get(rule_id) or {}
        entry.update({"kind": kind,
                      "fire_count": int(entry.get("fire_count") or 0) + 1})
        state["latches"][rule_id] = entry
        self.save(state)

    def unlatch(self, rule_id):
        state = self.load()
        if rule_id in state["latches"]:
            del state["latches"][rule_id]
            self.save(state)

    def is_latched(self, rule_id):
        return rule_id in self.load()["latches"]

    # ---------------------------------------------------------- fills ----
    def record_filled(self, rec):
        state = self.load()
        state["filled_tickets"].append(rec)
        self.save(state)
        return rec
