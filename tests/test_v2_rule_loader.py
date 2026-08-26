"""Daemon v2 rule loader + validator tests.

Unknown condition type must produce a LOUD load error (logged) and the rule
must be excluded from the active set - never silently skipped.
"""

import json

import pytest

from daemon.rule_loader import load_rules, validate_rules


def write_rules(tmp_path, doc):
    p = tmp_path / "alert_rules.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


VALID_RULE = {
    "id": "test-rule-1",
    "symbol": "XAUUSD",
    "kind": "entry",
    "direction": "long",
    "logic": "ALL",
    "conditions": [{"type": "price_above", "level": 100.0}],
    "ring_once": True,
    "expires_utc": None,
    "note": "test",
}


def valid_doc():
    return {
        "meta": {"version": 2, "updated_utc": "2026-08-22T00:00:00+00:00"},
        "safety": {"max_heat_pct": 6.0, "min_free_margin_pct": 20.0,
                   "terminal_silence_sec": 60},
        "rules": [dict(VALID_RULE)],
        "monitors": [],
    }


def test_valid_doc_loads_with_defaults(tmp_path):
    doc = valid_doc()
    # strip optional fields; loader must apply defaults
    del doc["rules"][0]["logic"]
    del doc["rules"][0]["ring_once"]
    res = load_rules(write_rules(tmp_path, doc))
    assert res.errors == []
    assert len(res.rules) == 1
    rule = res.rules[0]
    assert rule["logic"] == "ALL"
    assert rule["ring_once"] is True
    assert rule["kind"] == "entry"
    assert res.safety["max_heat_pct"] == 6.0


def test_unknown_condition_type_is_load_error_and_rule_excluded(tmp_path, caplog):
    doc = valid_doc()
    doc["rules"][0]["conditions"] = [
        {"type": "price_above", "level": 100.0},
        {"type": "moon_phase_gauge", "phase": "full"},
    ]
    with caplog.at_level("ERROR"):
        res = load_rules(write_rules(tmp_path, doc))
    assert res.rules == []  # excluded from active set
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err["rule_id"] == "test-rule-1"
    assert "unknown_condition_type" in err["error"]
    assert "moon_phase_gauge" in caplog.text
    assert any(r.levelname == "ERROR" for r in caplog.records)


def test_condition_without_type_key_is_error(tmp_path):
    doc = valid_doc()
    doc["rules"][0]["conditions"] = [{"level": 100.0}]
    res = load_rules(write_rules(tmp_path, doc))
    assert res.rules == []
    assert "missing_type" in res.errors[0]["error"]


def test_missing_rule_id_is_validation_error(tmp_path):
    doc = valid_doc()
    del doc["rules"][0]["id"]
    errs = validate_rules(doc)
    assert any("id" in e for e in errs)


def test_empty_conditions_is_validation_error(tmp_path):
    doc = valid_doc()
    doc["rules"][0]["conditions"] = []
    errs = validate_rules(doc)
    assert any("conditions" in e for e in errs)


def test_bad_logic_value_is_validation_error(tmp_path):
    doc = valid_doc()
    doc["rules"][0]["logic"] = "SOMETIMES"
    errs = validate_rules(doc)
    assert any("logic" in e for e in errs)


def test_bad_direction_value_is_validation_error(tmp_path):
    doc = valid_doc()
    doc["rules"][0]["direction"] = "sideways"
    errs = validate_rules(doc)
    assert any("direction" in e for e in errs)


def test_bad_expires_utc_is_validation_error(tmp_path):
    doc = valid_doc()
    doc["rules"][0]["expires_utc"] = "not-a-date"
    errs = validate_rules(doc)
    assert any("expires_utc" in e for e in errs)


def test_entry_rule_requires_symbol(tmp_path):
    doc = valid_doc()
    del doc["rules"][0]["symbol"]
    errs = validate_rules(doc)
    assert any("symbol" in e for e in errs)


def test_monitor_section_loads(tmp_path):
    doc = valid_doc()
    doc["monitors"].append({
        "id": "mon-template",
        "ticket_or_symbol": "",
        "kind": "monitor",
        "logic": "ANY",
        "conditions": [
            {"type": "position_exists", "symbol": None, "direction": None},
            {"type": "pnl_pct_below", "value": -0.5},
        ],
        "ring_once": True,
        "note": "template only",
    })
    res = load_rules(write_rules(tmp_path, doc))
    assert res.errors == []
    assert len(res.monitors) == 1
    assert res.monitors[0]["kind"] == "monitor"


def test_corrupt_json_file_raises_load_error(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{not json", encoding="utf-8")
    res = load_rules(p)
    assert res.rules == []
    assert len(res.errors) == 1
    assert "json" in res.errors[0]["error"].lower()


def test_missing_file_returns_error_not_crash(tmp_path):
    res = load_rules(tmp_path / "nope.json")
    assert res.rules == []
    assert len(res.errors) == 1


def test_utf8_content_roundtrip(tmp_path):
    doc = valid_doc()
    doc["rules"][0]["note"] = "ascii only note"
    path = write_rules(tmp_path, doc)
    raw = path.read_bytes()
    raw.decode("utf-8")  # must be valid utf-8
    res = load_rules(path)
    assert res.errors == []
