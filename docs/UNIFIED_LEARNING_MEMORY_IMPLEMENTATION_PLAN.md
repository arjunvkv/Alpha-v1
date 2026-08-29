# Unified Learning Memory Implementation Plan

## Objective
Replace overlapping Trade Journal and Pattern Book learning semantics with one canonical Unified Learning Memory while preserving every historical learning record. The Agent remains the sole trading decision-maker. Learning can require study but cannot force BUY, SELL, WAIT, approval, denial, or a no-trade outcome.

## Core Architecture
The canonical runtime learning store contains:
- Experiences: full trade/decision context, direction taken, execution details, outcomes, winners, losses, mistakes, lessons, and self-corrections.
- Patterns: normalized recurring phenomena linked to underlying experiences with unlimited evidence accumulation.
- Provenance: original source, original identifiers, and preserved historical payload/context.

Existing Trade Journal and Pattern Book files remain as source/archive data. Runtime learning retrieval is unified.

## Data Preservation
Migration is non-destructive. Preserve all available:
- market and decision context
- direction taken (BUY/SELL/WAIT when available)
- thesis and reasoning
- supporting and contradictory evidence
- execution fields, tickets, prices, PnL and R values
- winners, losses, lessons, mistakes and self-corrections
- research observations and pattern descriptions
- counts, statuses and existing timestamps
- original historical wording

No timestamp expansion, timezone conversion, aging, decay, or new timestamp fields are introduced.

## Pattern Evidence
Remove the hard 5-hit threshold and all future threshold-driven promotion semantics.
Patterns accumulate evidence indefinitely:
- occurrence_count is unbounded
- counts are based on unique underlying evidence where identifiers are available
- overlapping legacy sources are linked/deduplicated without destroying provenance
- historical legacy count/status remain preserved as historical metadata

Pattern state is descriptive only: ACTIVE, UNDER_REVIEW, REFINED, RETIRED. No pattern state blocks a trade.

## Historical Directives
Historical strings such as MANDATORY CORRECTION, NEVER DO X, or HIGH CONVICTION remain preserved as historical learning. They are not executable directives or gates in the new interpretation.

## Agent Authority
When relevant learning exists, the Agent must:
1. retrieve it,
2. study it,
3. compare it with current context,
4. consider supporting and contradictory evidence,
5. identify relevant past mistakes and lessons,
6. explain material differences when rejecting relevant precedent,
7. independently decide BUY, SELL, WAIT, or another valid action.

Only the study/reasoning process is required. The learning system never makes the trading decision.

## MCP
Do not add MCP tools. Keep the existing tool count and names. Existing learning-related MCP tools are refactored internally to read/write the canonical unified learning memory and return coherent learning context.

Learning-related veto/block/approval/denial/no-trade semantics are removed from learning responses. Descriptive fields such as relevant_learning, supporting_evidence, contradictory_evidence, repeated_mistake, historical_lesson and review_required may be returned.

## Migration
1. Read existing Trade Journal and Pattern Book data.
2. Normalize into experiences and patterns.
3. Preserve source provenance and original payload/context.
4. Link overlapping records.
5. Avoid duplicate occurrence inflation.
6. Write the canonical unified store.
7. Validate every source record is represented.
8. Switch runtime learning access to the unified store.
9. Keep old source files untouched as archive/source data.

## Verification
Add tests/checks for:
- source record preservation
- context preservation
- unlimited evidence accumulation
- removal of the 5-hit behavioral threshold
- direction preservation when available
- no learning-derived trade veto
- one canonical runtime learning view
- non-destructive migration and provenance

A migration report must expose source coverage, migrated counts, linked overlaps and unmapped records.

## Implementation Boundary
Changes are made on a non-main branch. They are committed but not merged to main until explicit confirmation.


## Implementation Status
Implemented on branch `codex/unified-learning-memory` and intentionally not merged to `main`.
The branch introduces the canonical store, routes existing learning MCP calls to it without adding tools, removes future five-hit promotion semantics, preserves legacy files as migration sources/archive, and keeps learning as Agent-study evidence rather than trading authority.
