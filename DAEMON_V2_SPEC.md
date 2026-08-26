# DAEMON V2 SPEC - Generic Alert Engine + AI-Trader Contract

Status: APPROVED by user (5 decisions locked). This spec is the single source of truth
for the daemon v2 rewrite. Implementer MUST follow it exactly; deviations require a
written note in the final report.

## 1. Architecture Contract

- DAEMON = dumb alarm bell. It holds an AI-authored rule file, evaluates conditions
  quietly on a poll loop, and rings ONCE when a full condition-set fires. It NEVER
  generates its own trade ideas, zone pings, or crossing spam.
- AI = trader. On every ring the AI evaluates FROM SCRATCH: fresh Granger snapshot,
  live MT5 terminal data (bid/ask/spread/volume/positions), Proxima news sanity,
  retail-trap scan, 7 entry criteria. If thesis holds -> writes an ORDER to action.json.
  If market state changed materially between ring-fire and AI look -> veto with reason.
- After a fill the AI loads follow-up MONITOR rules into the same engine
  (trail-stop marks, partial-TP levels, exit triggers). Rings only when position
  needs attention.
- RETIRED: zone_approach triggers, level_crossing triggers, daily_scan wakes,
  whipsaw micro-crossing battles. None of these may fire in v2.

## 2. File Layout (all under C:\Trading\Alpha\data\live\)

- alert_rules.json   - AI-authored rules + monitors + safety config (new)
- action.json        - unchanged consumption path: decisions AND orders (existing)
- ring_state.json    - latch state: fired rule ids + timestamps + reset history (new)
- wake_prompt.txt    - REWRITTEN per-ring payload (replaces trigger-based prompt)
- processed_actions.jsonl - keep as-is (audit trail)
- suppressed_triggers.jsonl - retire; no longer written

All JSON files: write via .tmp then os.replace (atomic), encoding='utf-8' explicit,
ASCII-safe content only.

## 3. Rule Schema (alert_rules.json)

{
  "meta": {"version": 2, "updated_utc": "..."},
  "safety": {
    "max_heat_pct": 6.0,
    "min_free_margin_pct": 20.0,
    "terminal_silence_sec": 60
  },
  "rules": [
    {
      "id": "unique-string",
      "symbol": "XAUUSD",
      "kind": "entry",
      "direction": "long|short|any",
      "logic": "ALL|ANY",
      "conditions": [ {condition objects, see section 4} ],
      "ring_once": true,
      "expires_utc": null | "ISO8601",
      "note": "human-readable rationale"
    }
  ],
  "monitors": [
    {
      "id": "mon-...",
      "ticket_or_symbol": "...",
      "kind": "monitor",
      "logic": "ANY",
      "conditions": [ exit/attention predicates ],
      "ring_once": true,
      "note": "..."
    }
  ]
}

## 4. Condition DSL (generic evaluator)

Event predicates (edge-triggered, internal edge detection from poll ticks):
- price_cross_above  {"level": float}
- price_cross_below  {"level": float}

State predicates (level-triggered):
- price_above        {"level": float}
- price_below        {"level": float}
- daily_close_beyond {"level": float, "direction": "above"|"below"}
- volume_expansion   {"min_ratio": 1.5}            vs rolling 20-bar avg volume
- retest_hold        {"level": f, "tolerance_pct": 0.1, "bars": 3}
- indicator_state    {"name": "rsi"|"macd"|"ema", "params": {...}, "op": ">"|"<"|"cross_up"|"cross_down", "value": f}
- snapshot_field     {"path": "dotted.path.into.granger.snapshot", "op": ">"|"<"|"="|"in", "value": ...}
- time_window        {"start_utc": "HH:MM", "end_utc": "HH:MM"}
- spread_below       {"max_points": f}

Position/monitor predicates:
- position_exists    {"symbol": s, "direction": "long"|"short"|null}
- pnl_pct_below      {"value": -0.5}     (unrealized % move against)
- pnl_pct_above      {"value": 1.0}
- price_reached      {"level": f}

Unknown condition type -> rule marked invalid at load, logged, never silently skipped.

## 5. Safety Rings (always evaluated, independent of rules)

Fire immediately as priority rings regardless of latch state:
- open position hits/breaches its stop-loss
- account heat_pct > safety.max_heat_pct
- free_margin_pct < safety.min_free_margin_pct
- MT5 terminal silent > safety.terminal_silence_sec (disconnect guard)

Safety ring payloads use rule id "SAFETY_<NAME>" and are never latched off by AI reset
until the underlying condition clears.

## 6. Ring Protocol

- Poll loop every POLL_INTERVAL = 10 seconds.
- Evaluate: safety rings first, then monitors, then entry rules.
- On full logic-set true AND not currently latched AND not expired:
  append record to ring_state.json (rule_id, ts, market snapshot),
  write wake_prompt.txt with the RING PAYLOAD (section 7),
  print the existing wake banner so the AI gets invoked through the established
  channel, set latch if ring_once=true.
- Latch clears ONLY via AI action.json containing {"reset_rule_ids": [...]} or rule
  expiry. Re-fire of a latched rule is logged to ring_state.json as "suppressed_repeat"
  WITHOUT waking the AI.
- No other wake sources exist in v2.

## 7. Wake Prompt (per ring) must contain

- Ring id, kind (entry|monitor|safety), direction, triggering conditions with values
- Live market snapshot: symbol, bid, ask, spread, last, tick_volume, server time UTC
- Account: balance, equity, margin, free_margin, heat_pct, positions list
- Granger snapshot path + age_hours
- Explicit instruction block: evaluate FROM SCRATCH (Granger freshness check ->
  refresh if stale > 1h via orchestrator; MT5 terminal pull; Proxima news scrape;
  trap scan; 7 criteria); then either ORDER per section 8 or REJECT with written
  reason; include {"reset_rule_ids":[<fired id>]} in EVERY response so the latch
  clears deterministically.

## 8. Order Path (action.json)

AI response variants consumed by daemon:
- {"decision":"WAIT", ..., "reset_rule_ids":[...]}          -> non-executing, latch reset
- {"decision":"REJECT", "reason":"...", "reset_rule_ids":[...]} -> ring voided, latch reset
- {"decision":"ORDER", "symbol":..,"side":"buy"|"sell","volume":float,
   "sl":price,"tp":price,"rr":float,"reason":..,"timestamp":..,
   "reset_rule_ids":[...]}
       -> daemon validates (volume>0, sl+tp present, rr>=2.0 for entries,
          risk<=2pct equity), then routes to brain/executor.py order placement
          (MT5 market order). Fill result appended to processed_actions.jsonl.
       -> On confirmed fill daemon auto-inserts nothing itself; it logs the ticket
          into ring_state.json under "filled_tickets" so the AI can attach monitor
          rules on its next look.

Executor contract: reuse existing brain/executor.py functions; add thin wrapper
place_market_order(spec: dict) -> dict(result) if missing. DRY_RUN env var or config
flag must make ALL MT5 calls no-ops returning simulated success (for tests).

## 9. Sizing + Direction Policy (encoded in AI protocol, not daemon)

- Symbols: all available MT5 symbols + key commodities (seed XAUUSD XPTUSD XAGUSD XPDUSD).
- Direction: both long and short allowed; institutional alignment decided AT EVALUATION
  TIME from Granger layers, never baked into rules.
- Sizing: conviction x risk caps (max 2 pct equity per trade); entries only where
  structural R:R >= 2:1 is achievable (structural SL + structural TP).

## 10. Seed Rules (deliverable alert_rules.json)

Implementer seeds conservative starter set mirroring proven policy:
- xptusd-bb-breakout-long-v1: daily close above recalculated BB_Upper + volume
  expansion >= 1.5 + retest_hold(BB_Upper) -> ALL
- xauusd-bb-breakout-long-v1 / short mirror: same pattern on XAUUSD BB bands
- xagusd-sma200-reclaim-long-v1: close above SMA200 + retest hold
- xpdusd-range-watch-any-v1: ANY(price_cross_above recent high, price_cross_below
  recent low) placeholder pending institutional pull
- One monitor example attached to no ticket (template only).
Levels pulled from current zones.json values at implementation time; band values are
futures-based and accepted as-is.

## 11. Implementation Constraints (MANDATORY)

- Python 3.11, MetaTrader5 package, stdlib + existing project deps only.
- TDD: pytest unit tests per condition type with synthetic tick streams; integration
  test running the engine in DRY_RUN against simulated ticks asserting:
  ring fires once, latch suppresses repeats, reset via action.json works,
  ORDER validation enforces rr>=2 and rejects bad specs, safety ring fires on
  synthetic breach, zero MT5 calls made in DRY_RUN.
- Legacy behavior regression: prove v2 emits NO zone_approach/daily_scan wakes.
- Keep module importable (daemon.py exposes build_engine(config) pure factory for tests).
- ASCII-only source; encoding='utf-8' on all file IO; atomic .tmp+os.replace writes;
  never PowerShell redirects for JSON; logging format consistent with existing daemon.log.
- Do NOT touch Granger/ or Aletheia/ code. Do NOT delete old daemon code blindly:
  v2 replaces daemon.py main flow but legacy ZoneWatcher class may remain in a
  legacy_zone_watcher.py module (unused) for reference.

## 12. Definition of Done

1. pytest suite green (unit + DRY_RUN integration).
2. Daemon v2 starts against live MT5 demo terminal, loads seed alert_rules.json,
   logs one full evaluation cycle, stays healthy 60s, clean shutdown on SIGTERM/
   KeyboardInterrupt.
3. Injected test rule (price_above absurd level true-once) demonstrates real
   ring -> latch -> reset cycle in ring_state.json without placing any order.
4. Report: files changed, test output tail, health log tail, any deviations.
