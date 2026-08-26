"""Alpha daemon package.

v2 layout (DAEMON_V2_SPEC.md):
- conditions.py    generic condition DSL evaluator
- rule_loader.py   alert_rules.json loader + validator
- ring_state.py    latch state store (ring_state.json)
- market_data.py   data providers (simulated + live MT5, lazy import)
- safety.py        always-on safety ring checks
- order_router.py  ORDER spec validation + routing to brain/executor
- wake_prompt.py   per-ring wake prompt builder
- daemon_v2.py     engine + poll loop + build_engine factory + entrypoint
- legacy_zone_watcher.py  retired v1 zone proximity watcher (reference only)
"""
