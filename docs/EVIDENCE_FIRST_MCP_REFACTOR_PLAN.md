# Alpha Evidence-First MCP Refactor and Decision Architecture Plan

## Status and purpose

This document is the implementation contract for the next Alpha architecture refactor.

The objective is not to build another signal engine, conviction engine, analyst desk, or pre-trade dossier that decides what the market means before the primary reasoner sees the evidence.

The target architecture is:

```text
LIVE / EXTERNAL DATA
        |
        v
DETERMINISTIC DATA + EVIDENCE SERVICES
        |
        v
FRESH MCP QUERIES ON DEMAND
        |
        v
ONE PRIMARY REASONER (OpenCode)
        |
        v
DETERMINISTIC SAFETY / BROKER VALIDATION
        |
        v
MT5 EXECUTION
```

OpenCode is the sole trade reasoning authority. Data services answer factual and deterministic questions. Safety services validate execution constraints. No intermediate component is allowed to silently replace reasoning with a conviction score, BUY/SELL recommendation, synthetic consensus, or stale precomputed thesis.

---

# 1. Branch state checked before this plan

The repository currently has these relevant branches:

- `main`
- `fix/agent-only-decision-authority`
- `fix/centralize-hardcoded-runtime-config`
- `codex/unified-learning-memory`

At the time of writing, `main` is ahead of the two small fix branches by additional commits, so neither fix branch should be blindly treated as the implementation base.

The two small branches contain changes that remain architecturally relevant:

## fix/agent-only-decision-authority

Focus:
- remove competing daemon-side trade authority
- make the Agent the decision authority
- adjust order-router and daemon semantics accordingly

## fix/centralize-hardcoded-runtime-config

Focus:
- centralize runtime constants
- reduce hard-coded configuration inside daemon/order-router paths

## codex/unified-learning-memory

This branch is substantially larger and contains a major amount of additional work, including:
- unified learning memory
- CVD engine
- decision snapshot recorder
- fair value gap module
- ledger decomposition
- librarian agent
- trade forensics
- expanded MCP server
- expanded sensors
- revised agent graph
- institutional strategy documents

It is not safe to assume this branch should be merged wholesale. It must be diff-audited against the evidence-first architecture because it may contain both valuable raw-data capabilities and additional competing reasoning layers.

### Required pre-refactor branch action

Before implementation starts:

1. Compare all three branches against current main at file level.
2. Extract useful deterministic capabilities.
3. Reject any change that introduces a second trade reasoner or hidden scoring authority.
4. Cherry-pick or manually port useful isolated changes rather than blindly merging diverged branches.
5. Re-run the full MCP inventory after branch reconciliation.

---

# 2. The core architectural rule

## Data services may answer

- What is the current price?
- What changed?
- When did it change?
- What was the event?
- What was actual versus forecast?
- What is the latest reported positioning?
- Where are objectively derived reference levels?
- What is the current account state?
- What historical observations match this query?

## Data services may calculate

- arithmetic
- deltas
- returns
- ranges
- percentiles
- timestamps and ages
- deterministic event detection
- risk and margin estimates
- objective reference levels
- volume/price statistics

## Data services must not decide

- BUY
- SELL
- bullish
- bearish
- conviction score
- consensus
- approved
- rejected
- good trade
- bad trade
- likely winner
- institutional thesis
- final destination

The primary reasoner decides meaning.

---

# 3. Current MCP audit

The existing MCP server contains these major categories.

## KEEP AND REFACTOR

### mcp_alpha_execute_trade

Keep as execution-only functionality.

Required changes:
- split preview from execution
- return current tick and timestamp used for execution
- return broker validation results
- remove any trade-quality judgment
- enforce explicit parameter validation
- record source and execution timestamps

New shape:

- mcp_alpha_preview_trade
- mcp_alpha_execute_trade

### mcp_alpha_update_position

Keep.

Refactor into explicit actions:
- move SL
- move TP
- break-even
- partial close
- full close

Return before/after values and execution timestamps.

### mcp_alpha_get_account_status

Keep but expand into:
- account state
- positions
- portfolio exposure
- portfolio risk

### mcp_alpha_get_live_world_events

Keep as an evidence source.

Requirements:
- published timestamp
- retrieval timestamp
- source
- source URL/identifier where available
- explicit failure instead of synthetic fallback
- category filtering remains acceptable

### Pattern and memory tools

Keep:
- record pattern observation
- record pattern outcome
- get book page
- search book
- get book index

Refactor memory so the Agent can retrieve relevant evidence rather than entire books.

---

# 4. Remove or retire current MCP abstractions

## REMOVE: mcp_alpha_get_symbol_conviction

Reason:
- a conviction score is already a judgment
- current implementation mixes live and non-live inputs
- current implementation includes hard-coded positioning values
- current implementation calculates indicator-derived conclusions before the reasoner sees raw evidence

Replace with factual evidence endpoints.

## REMOVE AS A DECISION TOOL: mcp_alpha_query_analyst_desk

Reason:
- creates a second reasoning layer
- can hide hard-coded macro assumptions
- can return synthesized conclusions rather than evidence
- duplicates reasoning that should belong to OpenCode

Useful underlying data collectors may survive as evidence providers.

## REMOVE OR RESTRICT: mcp_alpha_get_full_book

Reason:
- uncontrolled prompt bloat
- stale context
- anchoring bias
- encourages bulk context ingestion rather than targeted investigation

Use:
search -> inspect result -> retrieve relevant page or record.

## REBUILD: mcp_alpha_register_watch

The current API must not acknowledge a watch unless it has been persisted into the authoritative daemon watch/rule store and is actually being evaluated.

Replace with:
- mcp_alpha_create_watch
- mcp_alpha_list_watches
- mcp_alpha_get_watch
- mcp_alpha_update_watch
- mcp_alpha_cancel_watch

One authoritative persistent watch state only.

---

# 5. Non-negotiable truth and freshness contract

Every evidence MCP response must expose, where applicable:

```json
{
  "status": "SUCCESS | STALE | UNAVAILABLE | ERROR",
  "source": "provider identifier",
  "observed_at": "timestamp at which the underlying fact was true",
  "retrieved_at": "timestamp at which Alpha fetched it",
  "age_seconds": 0,
  "data": {}
}
```

Rules:

1. Never silently replace unavailable data with a constant.
2. Never label cached data as live.
3. Never generate synthetic fallback news as market evidence.
4. Never return positioning without report/release date.
5. Never return an event without its timestamp.
6. Never hide source age.
7. If a source fails, return UNAVAILABLE.
8. If cached data is beyond the endpoint freshness SLA, return STALE.
9. Reasoner-visible timestamps must be machine readable and human understandable.
10. All multi-source outputs must preserve per-source freshness.

Principle:

**NO DATA IS BETTER THAN FALSE DATA.**

---

# 6. New MCP evidence domains

# Domain A: Live market

## mcp_alpha_get_live_market(symbol)

Return:
- bid
- ask
- last where available
- spread absolute
- spread relative
- tick time
- server time
- source age

No trend or bias conclusion.

## mcp_alpha_get_bars(symbol, timeframe, count)

Return raw:
- timestamp
- open
- high
- low
- close
- tick volume / volume where available

No BUY/SELL interpretation.

## mcp_alpha_get_market_changes(symbol, windows)

Example windows:
- 1m
- 5m
- 15m
- 1h
- 4h
- 1d

Return:
- price delta
- percent delta
- high/low excursion
- realized range
- range percentile
- volume/tick-volume change
- movement speed statistics

This endpoint answers what changed, not what it means.

---

# Domain B: Reference levels and structure evidence

## mcp_alpha_get_reference_levels(symbol)

Return objectively derived levels:
- current day high/low
- previous day high/low
- weekly high/low
- monthly high/low
- session highs/lows
- other explicitly documented deterministic levels

## mcp_alpha_get_structure_events(symbol, timeframe, lookback)

Return detected facts such as:
- prior swing high broken
- prior swing low broken
- N-period high/low created
- prior session extreme traded through
- return back inside prior range
- range expansion
- retest event

Do not label the event bullish or bearish.

## mcp_alpha_get_structure_snapshot(symbol, timeframes)

Return compact factual state for multiple timeframes:
- latest OHLC
- recent extrema
- current range position
- event timestamps

This is optional convenience, not a thesis.

---

# Domain C: Liquidity and market map

Existing modules such as liquidity radar and institutional analytics must be audited and decomposed into evidence outputs.

## mcp_alpha_get_liquidity_map(symbol)

Return:
- recent swing highs/lows
- equal-high/equal-low candidates
- session extremes
- volume clusters where supported
- objectively detected gap/displacement zones
- reference prices

Every field must state whether it is:
- observed
- derived
- estimated

## mcp_alpha_get_liquidity_state(symbol)

Return factual/proxy metrics:
- spread
- current range
- range percentile
- volume percentile
- movement speed
- depth if a genuine depth source exists
- clearly labelled liquidity proxies

Never claim a liquidity vacuum as a conclusion.

---

# Domain D: Cross-asset evidence

For XAUUSD the initial core basket should support configurable instruments such as:
- XAUUSD
- DXY / USD proxy
- US 2Y yield
- US 10Y yield
- real yield proxy where available
- XAGUSD
- volatility/risk proxy
- configurable equity/risk assets

## mcp_alpha_get_cross_asset_state(symbol_or_basket)

Return latest values with individual timestamps.

## mcp_alpha_get_cross_asset_changes(basket, windows)

Return synchronized deltas across requested windows.

No fixed macro constants are allowed.

---

# Domain E: Macro and calendar

## mcp_alpha_get_macro_state(series)

Return each series with:
- value
- observation timestamp
- source
- retrieval timestamp
- age
- frequency

## mcp_alpha_get_economic_calendar(window)

Return:
- event
- country/currency
- impact
- scheduled time
- actual
- forecast
- previous
- revision
- release status

## mcp_alpha_get_event_surprise(event_id)

Deterministic calculations only:
- actual minus forecast
- revision
- immediate observed market reaction over configurable windows

The reasoner determines whether the surprise matters.

---

# Domain F: News and world events

## mcp_alpha_get_live_world_events

Retain and enforce the truth contract.

## mcp_alpha_search_market_news(query, since, filters)

Return:
- headline
- source
- publication timestamp
- retrieval timestamp
- URL/identifier
- short source-grounded snippet

## mcp_alpha_get_news_item(id)

Return source content or permitted extracted representation.

No fabricated fallback headlines.

---

# Domain G: Positioning and derivatives

This is one of the largest current evidence gaps.

## mcp_alpha_get_cot_positioning(symbol)

Return:
- report date
- release date
- data age
- managed money
- commercial positioning
- open interest
- weekly changes
- historical percentile
- methodology metadata

Hard-coded symbol dictionaries must be removed.

## mcp_alpha_get_futures_state(symbol)

Where data access exists:
- futures price
- volume
- open interest
- basis/term information
- timestamps

## mcp_alpha_get_options_state(symbol)

When a reliable source is integrated:
- implied volatility
- IV changes
- skew
- put/call measures
- open interest concentrations
- expiration concentrations

These are evidence, not squeeze predictions.

---

# Domain H: Account and portfolio

## mcp_alpha_get_account_state()

Return:
- balance
- equity
- margin
- free margin
- daily PnL
- monthly PnL where tracked
- current drawdown
- broker/account timestamp

## mcp_alpha_get_positions()

Return each position with:
- ticket
- symbol
- side
- volume
- entry
- current price
- SL
- TP
- unrealized PnL
- timestamps where available

## mcp_alpha_get_portfolio_risk()

Deterministically calculate:
- estimated open risk
- symbol exposure
- portfolio heat
- correlation group exposure where configured
- margin impact

No judgment about whether a new trade is good.

---

# Domain I: Memory and research

The memory system is useful but must remain evidence, not a vetoing brain.

## mcp_alpha_search_memory(query, filters)

Filters may include:
- symbol
- regime tags
- event type
- structure tags
- direction
- date range

## mcp_alpha_get_memory_record(id)

Return the exact relevant observation and outcome metadata.

## mcp_alpha_search_trade_history(filters)

Return comparable historical trades and actual outcomes.

Pattern counts may promote research priority but must never automatically approve or reject execution.

---

# Domain J: Dynamic watches

The Agent must be able to register future observation conditions that the actual daemon evaluates.

## mcp_alpha_create_watch

Return:
- watch id
- canonical persisted rule
- creation timestamp
- daemon acknowledgment

## mcp_alpha_list_watches

Return actual daemon-consumed state.

## mcp_alpha_get_watch(id)

Return current authoritative state.

## mcp_alpha_update_watch(id, ...)

Modify persisted rule.

## mcp_alpha_cancel_watch(id)

Remove/disable persisted rule.

No fake in-memory acknowledgements.

---

# Domain K: Execution

## mcp_alpha_preview_trade

Input:
- symbol
- side
- volume
- SL
- TP

Return:
- live bid/ask used
- spread
- estimated entry
- SL distance
- TP distance
- estimated monetary risk
- margin impact
- broker constraints
- validation failures

No trade-quality recommendation.

## mcp_alpha_execute_trade

Must execute exactly the validated parameters and return:
- order status
- ticket/order id
- fill price
- execution timestamp
- broker retcode
- error details

## Position management

Keep deterministic modification operations and prevent unsafe stop loosening where that rule is explicitly configured.

---

# 7. Current intelligence layers to decompose

The project currently contains multiple analyst/reasoning concepts. Their deterministic calculations may be valuable, but their decision authority must be removed.

Potential transformations:

```text
TechnicalAnalyst
    -> Market / Structure Evidence

FundamentalAnalyst
    -> Positioning / Fundamental Evidence

MacroNewsAnalyst
    -> Macro + News Evidence

Conviction / Consensus
    -> REMOVE

Bull/Bear Debate
    -> REMOVE AS EXECUTION AUTHORITY

Trader Agent
    -> REMOVE AS COMPETING TRADE REASONER

Risk calculations
    -> Deterministic Safety / Exposure Service
```

Do not delete useful parsers, collectors, calculations, or source adapters without first extracting reusable deterministic functions.

---

# 8. Data-source audit requirements

Before adding a new endpoint, audit every current source:

- MT5
- Granger
- OpenBB
- macro adapters
- economic calendar
- RSS/news crawler
- world events
- world market
- liquidity radar
- institutional analytics
- CVD engine
- pattern book
- trade journal
- unified learning memory
- decision snapshots
- futures/derivatives integrations

For each source document:

| Source | Data | Live/cached | Source timestamp | Retrieval timestamp | Failure mode | Synthetic fallback | MCP exposure |
|---|---|---|---|---|---|---|---|

Anything with a silent constant or fabricated fallback is a priority defect.

---

# 9. Dossier policy

The system must not precompute a complete market interpretation on a timer and present it as current truth.

A wake payload may contain only minimal trigger context:

```text
RING
time
symbol
rule/event that fired
event timestamp
current bid/ask at trigger
rule id
```

The reasoner then investigates on demand.

The reasoner must be able to compare:
- trigger-time state
- current state

This prevents acting on a market that has materially changed while the Agent was waking or reading.

Periodic streams may remain for operational awareness, but they must be explicitly labelled as background observations and cannot substitute for fresh queries before a trade.

---

# 10. Reasoner operating protocol

The Agent should not query every endpoint automatically.

The protocol is:

1. Receive trigger.
2. Read minimal trigger facts.
3. Query current live market.
4. Compare trigger state with current state.
5. Determine the uncertainty relevant to this decision.
6. Query only the evidence needed to resolve that uncertainty.
7. If considering execution, refresh live market and account/portfolio state immediately before preview.
8. Reason independently.
9. Preview trade.
10. Execute, wait, or reject.
11. If waiting for a condition, create an authoritative daemon watch.

The Agent is responsible for questions such as:
- What changed?
- Why might it matter?
- Who is vulnerable?
- Is positioning relevant?
- Is the market accepting or rejecting a move?
- What invalidates the thesis?
- Where could price travel?
- Is the asymmetry sufficient?

---

# 11. Safety boundary

Safety services may enforce:
- broker constraints
- malformed parameters
- invalid volume
- unavailable symbol
- stale price used for preview/execution
- account hard limits
- mandatory risk constraints explicitly configured as non-negotiable
- terminal/connection failure

Safety services must not silently replace the Agent's market thesis.

The order router is a validation boundary, not another strategist.

---

# 12. Full file-level implementation audit

Before coding, create a file inventory with one of:

- KEEP
- MODIFY
- DECOMPOSE
- RETIRE
- DELETE

Priority files include:

- mcp_server/alpha_mcp_server.py
- daemon/daemon_v2.py
- daemon/order_router.py
- tradingagents/agent_graph.py
- tradingagents/institutional_analytics.py
- tradingagents/liquidity_radar.py
- tradingagents/world_events.py
- tradingagents/world_market.py
- tradingagents/pattern_book.py
- tradingagents/trade_journal.py
- tradingagents/unified_learning_memory.py
- tradingagents/cvd_engine.py
- tradingagents/decision_snapshot_recorder.py
- sensors/granger_adapter.py
- sensors/openbb_macro_adapter.py
- sensors/global_news_crawler.py
- alpha_trading_desk.py
- config.py
- opencode.json

Legacy daemon and duplicate entrypoint files must also be explicitly classified.

No duplicate runtime authority should survive accidentally.

---

# 13. Implementation phases

## Phase 0: Branch reconciliation

- audit branch diffs
- preserve deterministic improvements
- reject competing decision layers
- establish one implementation branch

## Phase 1: Truth audit

- inspect every MCP response
- identify constants
- identify stale caches
- identify synthetic fallbacks
- identify missing timestamps

## Phase 2: MCP contract foundation

Implement a common response metadata layer:
- status
- source
- observed_at
- retrieved_at
- age_seconds
- data

## Phase 3: Replace conclusion endpoints

Retire:
- conviction score
- analyst desk decision synthesis
- fake watch registration
- unrestricted full-book retrieval

## Phase 4: Core live evidence

Implement:
- live market
- bars
- market changes
- reference levels
- structure events
- account state
- positions
- portfolio risk

## Phase 5: External evidence

Implement:
- cross-asset state/change
- macro state
- calendar
- event surprise
- news search

## Phase 6: Institutional/positioning evidence

Implement:
- COT with dates
- futures state
- derivatives/options where reliable
- liquidity map
- liquidity state
- CVD and other raw order-flow proxies after source validation

## Phase 7: Memory and learning integration

Expose:
- targeted memory search
- record retrieval
- comparable trade history
- outcome evidence

Do not turn memory into an automatic execution gate.

## Phase 8: Dynamic watch integration

Connect MCP watch CRUD directly to the authoritative daemon rule store.

## Phase 9: Execution hardening

Add:
- preview
- explicit validation
- timestamped execution
- deterministic broker checks

## Phase 10: End-to-end decision simulation

Test:

```text
trigger
 -> current market query
 -> targeted investigation
 -> evidence freshness checks
 -> independent reasoning
 -> preview
 -> execution or wait
 -> watch registration
```

---

# 14. Acceptance criteria

The refactor is not complete until all of the following are true:

1. No MCP tool returns a trade conviction score.
2. No MCP tool returns BUY/SELL as an intelligence conclusion.
3. No live-labelled endpoint uses a hidden constant.
4. Every external fact exposes source and freshness metadata.
5. A source failure is explicit.
6. OpenCode can query live evidence on demand.
7. OpenCode can compare trigger-time state with current state.
8. Dynamic watches are genuinely evaluated by the daemon.
9. Execution is preceded by a fresh preview/validation path.
10. Account and portfolio state can be queried fresh before execution.
11. Memory is searchable without bulk prompt injection.
12. One component only has trade reasoning authority.
13. The daemon does not independently decide trades.
14. The order router does not independently decide trade quality.
15. Legacy/duplicate runtime paths are explicitly retired or isolated.
16. Branch changes have been reconciled intentionally rather than merged blindly.

---

# 15. Target end state

```text
DATA SOURCES
    |
    v
FACTUAL / DETERMINISTIC SERVICES
    |
    v
FRESH MCP EVIDENCE API
    |
    +---- live market
    +---- market change
    +---- structure
    +---- liquidity evidence
    +---- cross asset
    +---- macro
    +---- calendar
    +---- news
    +---- positioning
    +---- portfolio
    +---- memory
    |
    v
ONE REASONER
(OpenCode)
    |
    v
PREVIEW + SAFETY VALIDATION
    |
    v
MT5
```

The system should become more capable not by pre-deciding more, but by giving the reasoner better access to fresh, timestamped, source-grounded evidence at the exact moment it needs to reason.
