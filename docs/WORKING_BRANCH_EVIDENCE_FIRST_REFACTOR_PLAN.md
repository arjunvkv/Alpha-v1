# Alpha Working-Branch Evidence-First Refactor Plan

## Scope

This plan applies specifically to the `codex/unified-learning-memory` branch.

It supersedes the earlier plan that treated much of Alpha's evidence infrastructure as missing. This branch already contains substantial work in market microstructure, CVD, FVG detection, institutional analytics, unified learning memory, trade forensics, ledger decomposition, decision snapshots, and backtesting support.

The objective is not to rebuild those engines. Preserve their deterministic and factual capabilities while refactoring the MCP surface so OpenCode can reason from fresh evidence without competing decision layers.

## Target authority model

```
DATA SOURCES
  -> deterministic collectors and calculations
  -> persistent timestamped observations
  -> atomic MCP evidence when OpenCode requests it
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
- existing 2-minute observation/dossier scheduling and persistence infrastructure where it is a lightweight collector

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
 -> timestamped observation/evidence
 -> OpenCode decides what to read and what else to query
 -> OpenCode reasons
```

The primary refactor is extraction and decomposition, not wholesale rebuilding.

# 3. The dossier / 2-minute observation architecture

The existing dossier mechanism must not be replaced by another system-generated dossier builder.

There must be no service that repeatedly decides which evidence OpenCode needs, queries a large collection of sources, arranges a custom factual report, and hands that report to OpenCode for every reasoning cycle.

## Keep the 2-minute mechanism as a lightweight evidence-state updater

The recurring process should perform lightweight, already-available observation work and update persistent structured state.

It may maintain fresh observations such as:

- current and recent market prices/bars
- deterministic market changes
- objective structure/FVG state changes
- measured CVD and other already-built deterministic sensor outputs
- newly observed macro/news/event information
- active-watch and objective trigger state
- account/position observations where appropriate

Every observation must retain provenance and time.

Conceptually:

```
2-minute collector / observer
        ->
persistent structured evidence state
        ->
OpenCode reads the parts it needs
        +
OpenCode calls fresh MCP tools only when additional/current evidence is required
        ->
OpenCode reasons
```

## The system must not author a dossier for OpenCode

Do not add:

- `assemble_evidence_snapshot(...)`
- custom dossier construction for each reasoning cycle
- system-selected evidence bundles
- heavy periodic context packaging
- AI/system relevance selection before OpenCode reasons

OpenCode controls what it investigates.

The system's job is to collect, calculate, timestamp, persist, and expose evidence efficiently.

## OpenCode controls relevance

For one situation OpenCode may need:

- recent price state
- CVD
- FVG state
- newly observed events

For another it may need:

- current live market
- macro release details
- DXY/yield movement
- portfolio state

The system must not pre-arrange either combination.

OpenCode reads existing structured observations according to its own reasoning and calls atomic MCP endpoints for additional evidence.

## Staleness rules for the persistent state

The 2-minute evidence state is not live execution data.

Each observation must expose:

- value/data
- source
- observed_at
- retrieved_at
- age/freshness

OpenCode decides whether an existing observation is sufficiently current for the question it is answering.

Immediately before execution, current market and account/portfolio state must be refreshed through the appropriate live path rather than assumed from the periodic state.

# 4. MCP tools to retire as decision abstractions

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

Each capability should have one canonical MCP name unless aliases are required temporarily for backwards compatibility.

# 5. Keep and refactor existing evidence engines

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
- evidence reads and MCP queries performed
- source timestamps
- retrieval timestamps
- freshness status
- facts/observations used
- reasoner's final thesis
- decision
- preview
- actual execution

# 6. Universal truth and freshness contract

Every external or time-sensitive MCP response and persistent observation must expose, where applicable:

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
2. Never label cached or periodic data as live.
3. Never fabricate fallback news or events.
4. Never hide report/release dates for positioning.
5. Preserve per-source freshness in multi-source responses.
6. Return UNAVAILABLE when a source fails.
7. Return STALE when freshness exceeds the endpoint SLA.
8. Clearly distinguish observed, derived, proxy, and estimated values.

Principle:

NO DATA IS BETTER THAN FALSE DATA.

# 7. MCP surface to add or extract

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

# 8. Dynamic watches

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

# 9. Execution hardening

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

# 10. Competing agent graph refactor

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

# 11. OpenCode operating protocol

The current branch should not force every evaluation through every tool or through a heavy system-generated dossier.

Replace mandatory giant-checklist behavior with:

1. Receive a trigger or inspect the latest persistent observations.
2. Read the existing observations relevant to the current reasoning path.
3. Query current live market when current state matters.
4. Identify the uncertainty relevant to the decision.
5. Query only additional evidence required to resolve that uncertainty.
6. Refresh live market and account/portfolio state immediately before preview.
7. Reason independently.
8. Preview.
9. Execute, wait, or reject.
10. If waiting on a condition, create an authoritative daemon watch.

The 2-minute evidence state is a lightweight background observation layer. It does not decide which evidence should be assembled for OpenCode.

# 12. OpenCode questionnaire and instruction refactor

The OpenCode instructions must be rewritten to match this architecture. Replace the current fixed investigation checklist with a conditional, question-driven reasoning protocol.

OpenCode is the investigator. Persistent 2-minute observations provide available evidence; MCP tools provide additional or fresher facts. OpenCode decides what question to ask next.

## Core rules

Do not require:
- all-tool sweeps
- mandatory full-market dossiers
- fixed analyst checklists
- conviction or analyst conclusions as trade authority
- interpretation of missing evidence as confirmation
- treating periodic observations as live execution state

## Required reasoning loop

```
OBSERVE
 -> DEFINE THE ACTUAL DECISION
 -> IDENTIFY WHAT IS UNKNOWN
 -> ASK THE MOST VALUABLE NEXT QUESTION
 -> GET RELEVANT EVIDENCE
 -> UPDATE THE HYPOTHESIS
 -> REPEAT ONLY WHILE THE ANSWER CAN CHANGE THE DECISION
 -> EXECUTE / WAIT / NO TRADE
```

Stop investigating when further evidence is unlikely to materially change the action.

## Conditional questionnaire

### 1. What is happening now?
- What triggered this evaluation?
- What objective change or observation is present?
- How old is it?
- What is the current live market state?
- Has the market materially changed since the observation?

### 2. What is the actual decision?
Before searching broadly:
- Is there an actionable opportunity now?
- What scenario is being considered?
- What would invalidate it?
- What information is missing?

Do not search for confirmation before defining the uncertainty.

### 3. What is the most important unresolved question?
Examples:
- sweep or continuation?
- acceptance or rejection?
- flow confirmation or divergence?
- external event explanation?
- active move or exhaustion?
- sufficient structural room?
- portfolio/risk constraint?
- checkable assumption?

Select only the question that matters now.

### 4. Which evidence can answer it?
Use only relevant evidence:
- current market/changes
- bars
- reference levels/structure
- FVG
- CVD/microstructure
- macro/calendar/event surprise
- news
- cross-asset changes
- historical precedents
- account/portfolio risk

### 5. What changed after the answer?
After each material query:
- Was the uncertainty resolved?
- Was the scenario strengthened?
- Was it weakened or invalidated?
- Did a more important uncertainty appear?
- Can another query genuinely change the action?

## Mandatory pre-execution questions

Immediately before preview/execution:
1. Is the thesis still valid at current price?
2. Has price materially changed since the evidence was obtained?
3. Is the entry still structurally valid?
4. Is invalidation explicit and justified?
5. Is target explicit and justified?
6. Is volume/risk explicit?
7. Does current portfolio state permit the trade?
8. Does reward/risk remain acceptable at executable price?
9. Is critical evidence stale or unavailable?
10. Is WAIT better than execution now?

Refresh live market and account/portfolio state before preview.

## Contradiction handling

When a thesis forms, search for the strongest materially relevant disconfirming evidence. Do not run artificial bull/bear debates; resolve the contradiction most capable of changing the decision.

## Missing and stale evidence

- UNAVAILABLE is not bullish or bearish.
- STALE is not current.
- Missing confirmation is not confirmation.
- Failed sources must not create invented context.
- Incomplete evidence is acceptable only when missing evidence is not decision-critical.
- If a critical uncertainty cannot be resolved safely, choose WAIT or NO TRADE.

## Historical evidence

Use memory/forensics when historical comparison can answer a current uncertainty. Check:
- comparability
- sample size
- regime mismatch
- uncertainty

Historical outcomes are evidence, not direct signals.

## Watches

If a trade is not valid now but could become investigable after an objective event, define that event and create a daemon-backed watch.

Bad: `Watch until market looks bullish.`

Good: a precise, machine-evaluable price/time/structure condition.

A watch trigger starts a new reasoning cycle; the previous thesis is not automatically preserved.

## Decision outcomes

### EXECUTE
Only when thesis is current, critical uncertainty is resolved sufficiently, invalidation/target/risk are explicit, and live preview validates execution.

### WAIT
Use when a specific condition has not occurred, evidence is temporarily insufficient, or location is premature. State the exact reason and objective watch condition where possible.

### NO TRADE
Use when the scenario is invalidated, reward/risk is insufficient, contradictions remain material, risk constraints prohibit execution, or no clear edge remains.

## Instruction structure in opencode.json

Organize instructions around:
1. authority and role
2. evidence/freshness rules
3. persistent observation usage
4. dynamic questionnaire
5. hypothesis and contradiction handling
6. historical evidence
7. EXECUTE / WAIT / NO TRADE
8. pre-execution validation
9. watches
10. decision recording

Describe questions and decision gates, not a mandatory MCP tool sequence.

## Prompt-size and tool-efficiency rules

Require OpenCode to:
- read only relevant persistent observations
- prefer targeted MCP calls
- avoid repeating sufficiently fresh queries
- refresh only data whose age matters
- avoid full memory/book loads unless necessary
- avoid large context dumps
- stop when more evidence is unlikely to change the action

# 12A. Free-source evidence expansion

The refactor may add only sources genuinely usable without requiring a paid production upgrade for the planned capability.

## Macro and point-in-time research

Add a FRED/ALFRED evidence adapter for historical macro-series research, vintage-aware observations, revision-aware reconstruction, and point-in-time macro validation. The existing free live calendar feed remains available for scheduled/live calendar context.

## Whole-news architecture

Do not add a single commercial news API as the whole-news dependency.

### 1. Direct RSS/Atom source registry

Expand the current crawler into a source registry for public publisher and primary-source feeds. Each source should carry source_id, source_name, feed_url, feed_type, official_or_secondary, market_topics, instrument_relevance, poll_interval, publisher_timezone, and enabled.

Prefer direct feeds over intermediaries.

### 2. Original GDELT

Add Original GDELT as a global discovery and historical event/news-context source for global news discovery, geopolitical events, entity/topic searches, historical context, cross-language discovery, and comparable-event investigation.

GDELT discovery is evidence discovery, not final article authority. Preserve the discovered URL and retrieve the original publisher page when needed.

Do not make GDELT a mandatory call for every decision.

### 3. Self-hosted RSSHub fallback

Where a relevant source has no usable direct feed, support a self-hosted RSSHub route as a fallback.

Priority:

direct official/public RSS or Atom
-> direct publisher feed
-> self-hosted RSSHub route
-> GDELT discovery

Do not make a public shared RSSHub instance a production dependency.

### 4. Common Crawl historical recovery

Add Common Crawl only as an offline/on-demand historical evidence recovery path. Use it when a historical candidate URL or source page must be recovered and the original publisher/archive is unavailable.

Do not use Common Crawl as a live-news source or routine reasoning MCP.

## News provenance contract

Every persisted news item must be capable of carrying:

news_id, canonical_url, source_id, publisher, headline, summary_or_excerpt, published_at, retrieved_at, first_seen_at, discovered_via, language, instrument_tags, topic_tags, content_hash, duplicate_cluster_id, freshness_state.

first_seen_at means when Alpha first obtained the evidence, not the publisher publication timestamp.

Historical reasoning must distinguish publisher publication time, third-party ingestion/discovery time when available, Alpha retrieval time, and Alpha first-seen time.

## Explicitly rejected as architectural dependencies

Do not plan paid Trading Economics production capability, development-only NewsAPI access, quota-limited free tiers requiring paid access for the needed historical capability, commercial historical news archives, or paid order-flow feeds as required dependencies.

These may be reconsidered only after research demonstrates a concrete capability gap that the free architecture cannot fill.

# 12B. Source priority model

EXECUTION REALITY
MT5

LIVE MARKET / DERIVED EVIDENCE
MT5 + existing Alpha calculations

LIVE NEWS
direct RSS/Atom registry + existing crawler
-> self-hosted RSSHub fallback

GLOBAL / HISTORICAL NEWS CONTEXT
Original GDELT

HISTORICAL PAGE RECOVERY
Common Crawl on demand

MACRO HISTORY / VINTAGES
FRED / ALFRED

CRITICAL FACT VERIFICATION
original official source where relevant

No source should be queried merely because it exists. OpenCode selects a source only when the current unresolved question makes that evidence decision-relevant.

# 12C. Daemon and startup refactor

The existing daemon/startup flow must be refactored as part of the evidence-first architecture, but startup must remain lightweight.

The daemon must not build a trade dossier, crawl the news universe, fetch historical archives, calculate every market feature, or pre-answer the OpenCode questionnaire at startup.

## Startup responsibilities

Startup should perform only deterministic readiness work:

1. Load configuration and persistent daemon state.
2. Validate required local configuration and source registry structure.
3. Initialize and verify MT5 execution connectivity.
4. Subscribe/validate configured instruments required for daemon operation.
5. Register evidence adapters and their declared capabilities.
6. Restore persistent observation/watch state.
7. Start the lightweight trigger/watch loops.
8. Publish a structured startup capability snapshot.

Startup should not block on optional external evidence sources.

## Source lifecycle model

Every adapter must declare:

- required or optional
- startup validation level
- on-demand capability
- timeout
- freshness policy
- retry/backoff policy
- failure classification

Use explicit states:

READY
DEGRADED
UNAVAILABLE
ERROR

MT5/execution readiness is a required startup dependency.

External research/evidence sources such as FRED/ALFRED, GDELT, direct RSS feeds, RSSHub, and Common Crawl are optional evidence capabilities. Their temporary failure must not prevent the daemon from starting.

## Startup capability snapshot

After initialization, persist and expose a small structured snapshot containing:

daemon_started_at
daemon_version
config_version
mt5_state
instrument_states
adapter_states
enabled_capabilities
disabled_capabilities
startup_errors

Do not populate this snapshot with market conclusions, news summaries, calculated trade bias, or a prebuilt dossier.

## Lazy evidence initialization

Optional adapters should use lazy/on-demand initialization where practical:

OpenCode asks a question
-> MCP identifies the required capability
-> adapter validates availability if needed
-> evidence is retrieved
-> provenance and freshness are returned

Do not continuously preload external data merely to claim readiness.

## Trigger model

The daemon should remain responsible for cheap deterministic triggers and observation management, including:

- market/session transitions
- configured price or structure triggers
- observation due/expiry
- position/account state changes
- execution safety events

A trigger should wake or notify the investigation layer. It must not force the daemon to perform the entire reasoning investigation itself.

## Separation of responsibilities

Daemon:
- lifecycle
- MT5 connectivity
- observation/watch state
- cheap triggers
- scheduling
- persistence coordination

Evidence adapters:
- retrieve atomic evidence
- classify freshness and failure
- attach provenance

MCP:
- expose small question-answering capabilities

OpenCode:
- decide what question matters
- decide whether more evidence is needed
- reason about conflicting evidence
- decide execute / wait / no trade subject to deterministic execution safeguards

## Startup refactor acceptance criteria

1. A cold start reaches operational readiness without fetching a full dossier.
2. Optional evidence-source outages do not prevent daemon startup.
3. Required MT5/execution failures are explicit and prevent false readiness.
4. Startup output contains structured capability state rather than only free-form logs.
5. No fake fallback market values are inserted during startup.
6. No historical/news bulk fetch occurs during startup.
7. Restored watches preserve timestamps and state provenance.
8. Every daemon-owned trigger has a bounded cost and clear ownership.
9. OpenCode remains the reasoner; daemon startup does not precompute conclusions for it.
10. Restarting the daemon cannot silently erase first_seen, observed_at, or observation-state history.

# 13. File-level audit

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

The existing 2-minute dossier/observation implementation and every file participating in its scheduling, persistence, reading, and MCP exposure must be included explicitly in this audit.

Legacy and duplicate entry points must also be explicitly classified.

# 14. Implementation order

## Phase 1: Truth and dossier-path audit

Audit every current MCP endpoint and the complete 2-minute observation/dossier path for:

- hidden constants
- stale caches
- fabricated fallbacks
- missing timestamps
- duplicated authority
- synthetic conclusions
- heavy report construction
- system-selected evidence packaging
- whether OpenCode can read structured observations directly

## Phase 2: Common response and observation contract

Implement universal source/freshness metadata.

Ensure periodic observations and live queries remain distinguishable.

## Phase 3: Preserve and lighten the 2-minute path

Keep useful collection, deterministic sensing, persistence, and trigger work.

Remove:

- periodic market thesis generation
- BUY/SELL conclusions
- conviction scoring
- analyst consensus
- unnecessary heavy dossier formatting
- system-selected custom evidence bundles

The output is persistent structured evidence state, not a repeatedly authored report.

## Phase 4: Decompose existing monoliths

Split institutional profile and other large bundled responses into atomic evidence queries.

## Phase 5: Retire competing decision abstractions

Remove conviction and analyst-desk authority.

Refactor agent graph components that make trade conclusions.

## Phase 6: Fill true evidence gaps

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

## Phase 7: Watch authority

Connect MCP watch CRUD to the actual daemon evaluator.

## Phase 8: Execution hardening

Implement preview-first execution and remove silent risk defaults.

## Phase 9: OpenCode questionnaire and instruction rewrite

Rewrite `opencode.json` around the conditional question-driven investigation model in Section 12.

Replace fixed all-tool checklists with unresolved-question selection, targeted evidence, contradiction checks, decision gates, and explicit EXECUTE / WAIT / NO TRADE outcomes.

Do not require a system-generated dossier for each reasoning cycle.

## Phase 10: End-to-end validation

Test:

```
lightweight 2-minute observation
 -> persistent timestamped evidence state
 -> OpenCode reads what it considers relevant
 -> targeted fresh MCP evidence when needed
 -> freshness checks
 -> independent reasoning
 -> preview
 -> execute / wait / reject
 -> authoritative watch if waiting
 -> decision snapshot
```

# 15. Acceptance criteria

The branch refactor is complete when:

1. Existing CVD, FVG, ULM, Librarian, forensics, ledger, and decision-snapshot assets are preserved where useful.
2. The existing 2-minute mechanism performs lightweight observation/state updating rather than repeatedly authoring a market dossier.
3. No separate dossier builder decides what evidence OpenCode should receive for each reasoning cycle.
4. OpenCode determines what persistent observations to read and what additional MCP queries to make.
5. No MCP intelligence endpoint returns a conviction score as trade authority.
6. No analyst layer independently decides BUY/SELL.
7. OpenCode is the sole market/trade reasoner.
8. Every time-sensitive fact exposes source and freshness metadata.
9. No live-labelled endpoint hides constants or fabricated fallbacks.
10. Existing monolithic evidence bundles have atomic alternatives.
11. The Librarian retrieves evidence rather than making execution decisions.
12. Historical statistics remain evidence, not automatic trade approval.
13. Watches are actually evaluated by the authoritative daemon.
14. Execution does not silently invent volume or stop-loss risk.
15. A fresh preview path exists immediately before execution.
16. Current market can be compared with trigger-time or stored observation state.
17. OpenCode is not forced to query every tool or consume a heavy dossier before every trade.
18. One runtime path owns each responsibility.
19. `opencode.json` uses a conditional question-driven investigation protocol rather than a fixed MCP/tool checklist.
19A. New external evidence dependencies are restricted to the free-source architecture in Sections 12A–12B unless a later audit proves a concrete unmet capability.
20. OpenCode explicitly identifies the most important unresolved question before broadening evidence collection.
21. OpenCode performs materially relevant contradiction checks.
22. EXECUTE / WAIT / NO TRADE have explicit decision gates.
23. WAIT conditions are objective and can become daemon-backed watches.

# Final target

The working branch should evolve from:

```
many strong data engines
 -> bundled/periodic dossiers
 -> analyst opinions
 -> conviction
 -> OpenCode
```

to:

```
many strong existing data engines
 -> lightweight persistent timestamped observations
 -> OpenCode chooses what to read
 -> targeted fresh atomic MCP evidence when needed
 -> OpenCode independently reasons
 -> deterministic safety/preview
 -> MT5
```

The refactor preserves the expensive infrastructure already built in this branch, keeps the useful 2-minute collection path lightweight, and removes the layers that pre-decide what the evidence means or repeatedly decide how evidence should be packaged for the reasoner.
