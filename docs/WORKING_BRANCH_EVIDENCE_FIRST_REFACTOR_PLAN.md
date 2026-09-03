# Alpha Working-Branch Evidence-First Refactor Plan

## Scope

This plan applies specifically to the `codex/unified-learning-memory` branch.

It supersedes the earlier plan that treated much of Alpha's evidence infrastructure as missing. This branch already contains substantial work in market microstructure, CVD, FVG detection, institutional analytics, unified learning memory, trade forensics, ledger decomposition, decision snapshots, and backtesting support.

The objective is therefore not to rebuild those engines. The objective is to preserve their deterministic and factual capabilities while refactoring the MCP surface so OpenCode can reason from fresh evidence without competing decision layers.

## Target authority model

```
DATA SOURCES
  -> deterministic collectors and calculations
  -> fresh atomic MCP evidence
  -> OpenCode, sole market/trade reasoner
  -> deterministic preview and safety validation
  -> MT5 execution
```

No analyst desk, conviction score, consensus layer, bull/bear debate, trader sub-agent, or hidden scoring component may independently decide whether a trade should be taken.

# 1. Assets already implemented in this branch

Keep and build upon:

- `tradingagents/cvd_engine.py`
- `tradingagents/fair_value_gap.py`
- `tradingagents/unified_learning_memory.py`
- `tradingagents/librarian_agent.py`
- `tradingagents/trade_forensics.py`
- `tradingagents/ledger_decomposition.py`
- `tradingagents/decision_snapshot_recorder.py`
- existing institutional analytics calculations
- MT5 deal history and backtesting infrastructure
- existing world-event and news collectors, subject to truth auditing

Do not replace these systems with duplicate implementations.

# 2. Main architectural problem in the current branch

The branch has strong evidence engines but often exposes them through monolithic or opinionated MCP tools.

Current pattern:

```
raw data
 -> calculation
 -> analyst interpretation / conviction / posture
 -> OpenCode
```

Target:

```
raw data
 -> deterministic calculation
 -> timestamped evidence
 -> OpenCode reasons
```

The primary refactor is extraction and decomposition, not wholesale rebuilding.

# 3. MCP tools to retire as decision abstractions

## Retire `mcp_alpha_get_symbol_conviction`

Reason:
- compresses evidence into a judgment
- duplicates reasoning authority
- can mix live, stale, and derived assumptions
- hides the evidence OpenCode should inspect directly

Replace with atomic evidence queries.

## Retire `mcp_alpha_query_analyst_desk` as trade authority

Underlying deterministic collectors may survive.

The analyst desk must not produce the trade conclusion that OpenCode merely accepts.

## Retire unrestricted `mcp_alpha_get_full_book`

Reason:
- prompt bloat
- stale context
- anchoring
- unnecessary bulk retrieval

Use targeted search and record/page retrieval.

## Audit and reduce duplicate MCP aliases

Each capability should have one canonical MCP name unless aliases are required for backwards compatibility during migration.

# 4. Keep and refactor existing evidence engines

## CVD

Keep `cvd_engine.py` and `mcp_alpha_get_measured_cvd`.

Expose factual measurements such as:
- cumulative delta
- bar/window delta
- delta velocity
- divergence inputs
- source/methodology
- observed timestamp
- retrieval timestamp
- age

Do not return a final trade posture.

OpenCode decides whether the observed relationship between price and CVD implies absorption, divergence, exhaustion, continuation, or noise.

## Live microstructure

Keep `mcp_alpha_get_live_microstructure` and underlying collectors.

Preserve:
- spread
- tick velocity
- depth/order-book data when genuinely available
- raw imbalance
- raw CVD-related measurements
- timestamps

Remove or downgrade pre-interpreted market posture into explicitly documented deterministic event labels only.

## FVG

Keep `fair_value_gap.py` and `mcp_alpha_get_fvg_matrix`.

Preserve:
- timeframe
- gap boundaries
- consequent encroachment
- gap size
- fill percentage
- mitigation state
- source candle timestamp
- source provenance

FVG data is evidence, not a BUY/SELL instruction.

## Institutional analytics

Do not discard existing calculations.

Decompose the monolithic `mcp_alpha_get_full_institutional_profile` into smaller queries such as:
- volume profile
- POC/VAH/VAL
- VWAP state
- reference levels
- contract specifications
- cross-asset values

The existing bundled endpoint may remain temporarily for compatibility but must not be the preferred reasoner interface.

## Unified Learning Memory and Librarian

Keep both.

The Librarian must retrieve comparable observations, metadata, outcomes, sample sizes, and uncertainty.

It must not become a hidden trade reasoner.

Safe:
```
Find comparable historical situations and return evidence.
```

Unsafe:
```
Comparable history says BUY.
```

## Trade forensics and ledger decomposition

Keep.

Return historical evidence:
- sample size
- win/loss outcomes
- R distributions
- regime/session segmentation
- spread conditions
- FVG behavior
- other documented filters

Historical statistics must not automatically approve or reject execution.

## Decision snapshots

Keep and expand provenance.

Each decision snapshot should capture:
- trigger
- trigger timestamp
- evidence queries performed
- source timestamps
- retrieval timestamps
- freshness status
- facts returned
- reasoner's final thesis
- decision
- preview
- actual execution

# 5. Universal truth and freshness contract

Every external or time-sensitive MCP response must expose, where applicable:

```json
{
  "status": "SUCCESS | STALE | UNAVAILABLE | ERROR",
  "source": "provider or internal source",
  "observed_at": "when the underlying fact was true",
  "retrieved_at": "when Alpha obtained it",
  "age_seconds": 0,
  "data": {}
}
```

Rules:

1. Never silently replace unavailable data with a constant.
2. Never label cached data as live.
3. Never fabricate fallback news or events.
4. Never hide report/release dates for positioning.
5. Preserve per-source freshness in multi-source responses.
6. Return UNAVAILABLE when a source fails.
7. Return STALE when freshness exceeds the endpoint SLA.
8. Clearly distinguish observed, derived, proxy, and estimated values.

Principle:

NO DATA IS BETTER THAN FALSE DATA.

# 6. MCP surface to add or extract

## Live

### get_live_market(symbol)

Return:
- bid
- ask
- last where available
- spread
- tick/server timestamps
- source age

### get_bars(symbol, timeframe, count)

Return raw OHLCV/tick-volume records.

### get_market_changes(symbol, windows)

Return deterministic:
- price delta
- percentage delta
- high/low excursion
- realized range
- volume change
- movement speed

No directional conclusion.

## Structure

### get_reference_levels(symbol)

Return documented objective levels such as:
- current/previous day high-low
- weekly/monthly extremes
- session extremes

### get_structure_events(symbol, timeframe, lookback)

Return detected facts:
- prior swing broken
- new N-period high/low
- prior session extreme traded through
- return inside prior range
- range expansion
- retest

Do not label them bullish or bearish.

## Institutional

Extract existing calculations into atomic endpoints:
- get_volume_profile
- get_vwap_state
- get_contract_specs

## Cross-asset

### get_cross_asset_state(basket)

Return current values with individual timestamps.

### get_cross_asset_changes(basket, windows)

Return synchronized deterministic deltas.

## Macro

Add or expose clearly:
- get_macro_state
- get_economic_calendar
- get_event_surprise

Event surprise should calculate actual versus forecast and revisions, not decide their market meaning.

## News

Keep:
- get_live_world_events

Add:
- search_market_news
- get_news_item

All outputs require publication/source timestamps and explicit failure handling.

## Portfolio

Split account state into:
- get_account_state
- get_positions
- get_portfolio_risk

Portfolio risk is deterministic exposure/risk arithmetic, not trade-quality judgment.

# 7. Dynamic watches

The current persistence work is useful but must be verified against the actual daemon execution path.

Target:

```
OpenCode creates watch
 -> authoritative persisted rule
 -> daemon loads/evaluates rule
 -> trigger fires
 -> OpenCode wakes with trigger facts
```

Implement canonical CRUD:
- create_watch
- list_watches
- get_watch
- update_watch
- cancel_watch

A watch must never be acknowledged unless the daemon actually consumes the authoritative stored rule.

# 8. Execution hardening

Keep current execution functionality but separate:

- preview_trade
- execute_trade

Preview returns:
- current bid/ask
- spread
- estimated entry
- SL distance
- TP distance
- monetary risk
- margin impact
- broker constraints
- validation failures

Execution returns:
- order/ticket identifier
- fill price
- execution timestamp
- broker retcode
- error details

Do not silently invent risk-critical parameters.

Audit and remove defaults that automatically choose:
- volume
- stop loss
- take profit where explicit configuration is required

Missing mandatory parameters should produce a validation failure.

# 9. Competing agent graph refactor

Audit `tradingagents/agent_graph.py` component by component.

Keep:
- data retrieval
- deterministic indicator calculations
- market statistics
- source parsers
- factual transformations

Retire as trade authority:
- bull/bear debate
- consensus
- conviction
- trader sub-agent
- analyst opinion synthesis
- risk officer market opinion

Extract deterministic risk arithmetic into safety services.

Do not delete useful code before extracting reusable factual components.

# 10. OpenCode operating protocol

The current branch should not force every evaluation through every tool.

Replace mandatory giant-checklist behavior with:

1. Receive trigger.
2. Query current live market.
3. Compare trigger-time state with current state.
4. Identify the uncertainty relevant to the decision.
5. Query only evidence required to resolve that uncertainty.
6. Refresh live market and account/portfolio state immediately before preview.
7. Reason independently.
8. Preview.
9. Execute, wait, or reject.
10. If waiting on a condition, create an authoritative daemon watch.

Periodic background observations may exist but cannot substitute for fresh evidence before execution.

# 11. File-level audit

Classify every major file as:
- KEEP
- MODIFY
- DECOMPOSE
- RETIRE
- DELETE

Priority:

- mcp_server/alpha_mcp_server.py
- tradingagents/agent_graph.py
- tradingagents/cvd_engine.py
- tradingagents/fair_value_gap.py
- tradingagents/unified_learning_memory.py
- tradingagents/librarian_agent.py
- tradingagents/trade_forensics.py
- tradingagents/ledger_decomposition.py
- tradingagents/decision_snapshot_recorder.py
- tradingagents/institutional_analytics.py
- tradingagents/world_events.py
- tradingagents/world_market.py
- sensors/granger_adapter.py
- sensors/openbb_macro_adapter.py
- sensors/global_news_crawler.py
- daemon/daemon_v2.py
- daemon/order_router.py
- config.py
- opencode.json

Legacy and duplicate entry points must also be explicitly classified.

# 12. Implementation order

## Phase 1: Truth audit

Audit every current MCP endpoint for:
- hidden constants
- stale caches
- fabricated fallbacks
- missing timestamps
- duplicated authority
- synthetic conclusions

## Phase 2: Common response contract

Implement universal source/freshness metadata.

## Phase 3: Decompose existing monoliths

Split institutional profile and other large bundled responses into atomic evidence queries.

## Phase 4: Retire competing decision abstractions

Remove conviction and analyst-desk authority.

Refactor agent graph components that make trade conclusions.

## Phase 5: Fill true evidence gaps

Add:
- generic live market
- bars
- market changes
- reference levels
- structure events
- cross-asset changes
- explicit calendar/event surprise
- explicit news search
- portfolio risk

## Phase 6: Watch authority

Connect MCP watch CRUD to the actual daemon evaluator.

## Phase 7: Execution hardening

Implement preview-first execution and remove silent risk defaults.

## Phase 8: OpenCode protocol

Rewrite OpenCode instructions around dynamic uncertainty-driven investigation instead of mandatory full dossiers.

## Phase 9: End-to-end validation

Test:

```
trigger
 -> current market
 -> targeted evidence
 -> freshness checks
 -> independent reasoning
 -> preview
 -> execute / wait / reject
 -> authoritative watch if waiting
 -> decision snapshot
```

# 13. Acceptance criteria

The branch refactor is complete when:

1. Existing CVD, FVG, ULM, Librarian, forensics, ledger, and decision-snapshot assets are preserved where useful.
2. No MCP intelligence endpoint returns a conviction score as trade authority.
3. No analyst layer independently decides BUY/SELL.
4. OpenCode is the sole market/trade reasoner.
5. Every time-sensitive fact exposes source and freshness metadata.
6. No live-labelled endpoint hides constants or fabricated fallbacks.
7. Existing monolithic evidence bundles have atomic alternatives.
8. The Librarian retrieves evidence rather than making execution decisions.
9. Historical statistics remain evidence, not automatic trade approval.
10. Watches are actually evaluated by the authoritative daemon.
11. Execution does not silently invent volume or stop-loss risk.
12. A fresh preview path exists immediately before execution.
13. Current market can be compared with trigger-time state.
14. OpenCode is not forced to query every tool before every trade.
15. One runtime path owns each responsibility.

# Final target

The working branch should evolve from:

```
many strong data engines
 -> bundled dossiers
 -> analyst opinions
 -> conviction
 -> OpenCode
```

to:

```
many strong existing data engines
 -> fresh, atomic, timestamped evidence
 -> OpenCode independently reasons
 -> deterministic safety/preview
 -> MT5
```

The refactor should preserve the expensive infrastructure already built in this branch and remove only the layers that pre-decide what the evidence means.
