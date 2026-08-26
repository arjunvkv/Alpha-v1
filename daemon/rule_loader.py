"""Alert-rules file loader + validator (DAEMON_V2_SPEC.md sections 3-4).

Unknown condition types are LOUD load errors and the offending rule is
excluded from the active set - never silently skipped.
"""

import json
import logging
from datetime import datetime

from daemon.conditions import KNOWN_CONDITION_TYPES

LOG = logging.getLogger("alpha.daemon.v2")

DEFAULT_SAFETY = {
    "max_heat_pct": 6.0,
    "min_free_margin_pct": 20.0,
    "terminal_silence_sec": 60,
}

RULE_DEFAULTS = {
    "logic": "ALL",
    "direction": "any",
    "ring_once": True,
    "expires_utc": None,
    "note": "",
}

VALID_LOGIC = {"ALL", "ANY"}
VALID_DIRECTION = {"long", "short", "any"}
VALID_KIND = {"entry", "monitor"}


class RuleSet:
    """Loaded rules document."""

    def __init__(self):
        self.rules = []
        self.monitors = []
        self.errors = []
        self.safety = dict(DEFAULT_SAFETY)


def _iso_ok(text):
    try:
        datetime.fromisoformat(str(text).replace("Z", "+00:00"))
        return True
    except (TypeError, ValueError):
        return False


def validate_rules(doc):
    """Return a flat list of human-readable validation error strings."""
    errors = []
    if not isinstance(doc, dict):
        return ["document must be a JSON object"]
    for section, expect_kind in (("rules", "entry"), ("monitors", "monitor")):
        items = doc.get(section)
        if items is None:
            continue
        if not isinstance(items, list):
            errors.append("%s must be a list" % section)
            continue
        for idx, rule in enumerate(items):
            tag = "%s[%d]" % (section, idx)
            if not isinstance(rule, dict):
                errors.append("%s must be an object" % tag)
                continue
            rid = rule.get("id")
            if not rid or not isinstance(rid, str):
                errors.append("%s: missing id" % tag)
            kind = rule.get("kind", expect_kind)
            if kind not in VALID_KIND:
                errors.append("%s: invalid kind '%s'" % (rid or tag, kind))
            if kind == "entry" and not rule.get("symbol"):
                errors.append("%s: entry rule requires symbol" % (rid or tag))
            if rule.get("logic", "ALL") not in VALID_LOGIC:
                errors.append("%s: invalid logic '%s'"
                              % (rid or tag, rule.get("logic")))
            direction = rule.get("direction", "any")
            if direction not in VALID_DIRECTION:
                errors.append("%s: invalid direction '%s'"
                              % (rid or tag, direction))
            expires = rule.get("expires_utc")
            if expires is not None and not _iso_ok(expires):
                errors.append("%s: invalid expires_utc '%s'"
                              % (rid or tag, expires))
            conds = rule.get("conditions")
            if not isinstance(conds, list) or not conds:
                errors.append("%s: empty conditions" % (rid or tag))
                continue
            for cidx, cond in enumerate(conds):
                if not isinstance(cond, dict):
                    errors.append("%s: condition %d not an object"
                                  % (rid or tag, cidx))
                    continue
                ctype = cond.get("type")
                if not ctype:
                    errors.append("%s: condition %d missing_type"
                                  % (rid or tag, cidx))
                elif ctype not in KNOWN_CONDITION_TYPES:
                    errors.append("%s: condition %d unknown_condition_type:"
                                  " %s" % (rid or tag, cidx, ctype))
    return errors


def _apply_defaults(rule, kind):
    out = dict(rule)
    for key, val in RULE_DEFAULTS.items():
        out.setdefault(key, val)
    out.setdefault("kind", kind)
    if out["logic"] not in VALID_LOGIC:
        out["logic"] = "ALL"
    if out["direction"] not in VALID_DIRECTION:
        out["direction"] = "any"
    return out


def load_rules(path):
    """Load + validate an alert-rules JSON file. Never raises."""
    res = RuleSet()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            doc = json.load(handle)
    except FileNotFoundError:
        res.errors.append({"rule_id": None,
                           "error": "file_not_found: %s" % path})
        LOG.error("rules file not found: %s", path)
        return res
    except json.JSONDecodeError as exc:
        res.errors.append({"rule_id": None,
                           "error": "invalid_json: %s" % exc})
        LOG.error("rules file is not valid JSON: %s (%s)", path, exc)
        return res
    except OSError as exc:
        res.errors.append({"rule_id": None,
                           "error": "unreadable_file: %s" % exc})
        LOG.error("rules file unreadable: %s (%s)", path, exc)
        return res

    safety_cfg = doc.get("safety") or {}
    if isinstance(safety_cfg, dict):
        for key, val in DEFAULT_SAFETY.items():
            res.safety[key] = safety_cfg.get(key, val)

    for err in validate_rules(doc):
        res.errors.append({"rule_id": None, "error": err})

    # Re-validate per-rule so exclusions carry the owning rule id.
    for section, kind in (("rules", "entry"), ("monitors", "monitor")):
        for rule in doc.get(section) or []:
            scoped = {"rules": [rule], "monitors": []}
            rule_errs = validate_rules(scoped)
            if kind == "monitor":
                scoped = {"rules": [], "monitors": [rule]}
                rule_errs = validate_rules(scoped)
            if rule_errs:
                for err in rule_errs:
                    res.errors.append({"rule_id": rule.get("id"),
                                       "error": err})
                    LOG.error("rule '%s' rejected: %s", rule.get("id"), err)
                continue
            (res.rules if section == "rules" else res.monitors).append(
                _apply_defaults(rule, kind))

    if res.errors:
        LOG.error("alert rules loaded with %d error(s); "
                  "%d rule(s) active", len(res.errors), len(res.rules))
    else:
        LOG.info("alert rules loaded clean: %d rule(s), %d monitor(s)",
                 len(res.rules), len(res.monitors))
    return res
