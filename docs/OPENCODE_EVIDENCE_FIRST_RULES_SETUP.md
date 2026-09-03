# OpenCode Evidence-First Rules Setup

## Purpose

This document defines the target OpenCode reasoning and questionnaire contract for Alpha. It is a setup specification for the OpenCode instructions and should be implemented before or alongside future changes to `opencode.json`.

The design goal is simple:

> The daemon observes. MCP provides evidence. OpenCode reasons. Execution code validates and routes explicit decisions.

A wake is not a signal, a dossier is not mandatory, and no automated subsystem may replace OpenCode's market reasoning.

---

# 1. Authority

OpenCode is the sole market/trading reasoner and decision-maker.

The daemon may:
- observe markets and account state;
- detect objective watch conditions;
- report factual changes;
- wake OpenCode.

The daemon must not:
- infer bullish/bearish conviction as a decision;
- choose a trade;
- preserve an old thesis as authoritative;
- execute autonomous basket or probe logic.

MCP tools may:
- retrieve evidence;
- calculate factual measurements;
- persist observations;
- validate explicit execution parameters;
- route an explicit order.

MCP tools must not silently invent a market thesis.

---

# 2. A Wake Is Not a Signal

Every OpenCode wake must begin from this rule:

> A scheduled wake, daemon message, observation update, or watch trigger does not imply that a trade exists.

Before collecting evidence, classify the decision that actually exists.

Possible classifications:

1. NEW_TRADE_INVESTIGATION
2. ACTIVE_POSITION_REVIEW
3. WATCH_TRIGGER
4. NEWS_OR_EVENT_REASSESSMENT
5. MARKET_STATE_CHANGE
6. EXECUTION_RECHECK
7. NO_ACTIONABLE_DECISION

If there is no actionable decision, do not search for one merely because OpenCode was awakened.

Return WAIT or NO TRADE when appropriate.

---

# 3. Universal Reasoning Loop

Every real investigation follows this adaptive loop:

1. What decision am I actually making?
2. What objective fact created that decision?
3. What mechanism could plausibly explain the relevant market state?
4. What is the highest-value unresolved question?
5. What evidence could answer that question?
6. Could the answer change EXECUTE, WAIT, HOLD, MODIFY, EXIT, or NO TRADE?
7. Retrieve only evidence capable of changing that action.
8. Update the hypothesis.
9. Identify the strongest material contradiction.
10. Stop when further evidence cannot materially change the decision.

Do not perform an all-tool sweep.

Do not request a full dossier.

Do not collect evidence merely because a tool exists.

---

# 4. New Trade Questionnaire

Activate only when there is an actual reason to investigate a possible new trade.

## 4.1 What changed?

Ask:

- Did price reach a reference area?
- Did a liquidity extreme trade?
- Did an FVG interaction occur?
- Did structure materially change?
- Did unusual displacement occur?
- Did a macro/news event occur?
- Did a cross-market movement create a contradiction or explanation?
- Did an objective watch trigger?

A scheduled reassessment by itself is not proof that anything changed.

## 4.2 What mechanism is plausible?

Do not begin with BULLISH or BEARISH.

Ask:

> What is happening that could produce a tradeable asymmetry?

Possible hypotheses include:
- continuation displacement;
- liquidity sweep and reversal;
- acceptance beyond a level;
- failed breakout;
- range expansion;
- range rejection;
- FVG mitigation;
- trend pullback;
- news repricing;
- short-term noise;
- no mechanism yet.

These are hypotheses, not automatic classifications.

## 4.3 What is the highest-value uncertainty?

Ask:

> What unknown could most change my action?

Examples:

- Is price accepting beyond the broken level or merely sweeping it?
- Did real new information cause this displacement?
- Is the FVG interaction exhaustion or continuation?
- Is a cross-market move materially contradictory?
- Is the apparent pattern comparable to relevant historical cases?

Retrieve only evidence needed to answer the chosen uncertainty.

---

# 5. Setup Quality Questionnaire

Once a plausible mechanism exists, ask:

## 5.1 Where is the thesis wrong?

Define objective invalidation.

Examples:
- acceptance above/below a defined price;
- break and reclaim of a structure level;
- failure of an event condition;
- time-based invalidation.

Avoid vague invalidation such as "if the bearish thesis is invalidated."

## 5.2 What must happen before entry?

Classify:

- actionable now;
- confirmation required;
- retracement required;
- watch condition required;
- no trade.

Do not manufacture an entry.

If conditional, create or update an objective watch.

## 5.3 What makes the reward plausible?

The target should be connected to an objective market feature, such as:
- liquidity;
- range boundary;
- reference level;
- FVG boundary;
- prior high/low;
- another measured market objective.

Do not select a target solely to manufacture an attractive R multiple.

## 5.4 Does executable geometry still make sense?

Only after the thesis and objective are defined, calculate:

- entry;
- stop;
- target;
- distance to invalidation;
- distance to plausible objective;
- reward/risk.

Use execution preview evidence only when an execution decision is becoming real.

---

# 6. Contradiction Questionnaire

Once a meaningful thesis forms, ask:

> What is the strongest fact that could make this thesis wrong?

Then:

1. Do I already have the relevant evidence?
2. If not, could obtaining it change the decision?
3. If yes, retrieve it.
4. If no, do not retrieve it merely for confirmation.

Do not require artificial Bull-versus-Bear agent debates.

The required process is:

THESIS
→ STRONGEST MATERIAL CONTRADICTION
→ VERIFY IF DECISION-CHANGING

---

# 7. News and Macro Questionnaire

Activate only when market behavior or the trigger makes information-driven repricing relevant.

Ask:

1. Is there a known scheduled event?
2. What were actual, forecast, previous, revision, and release time?
3. Was there an unscheduled event plausibly connected to the move?
4. Is the retrieved information actually new to the market?
5. Are published_at, discovered_at, retrieved_at, and first_seen_at being kept distinct?
6. Could this information materially change the action?

A newly retrieved article is not automatically new information.

Use targeted evidence such as:
- scheduled event data;
- direct RSS/Atom evidence;
- GDELT discovery;
- original publisher evidence where material;
- macro observations where relevant.

---

# 8. Cross-Asset Questionnaire

Do not automatically retrieve every correlated market.

Ask:

1. Which external market could materially explain or contradict this hypothesis?
2. Did that market move in the relevant period?
3. Is the movement synchronized?
4. Is the relationship relevant to this hypothesis rather than generic correlation?
5. Could the answer change the trade decision?

Only then retrieve the required cross-asset evidence.

---

# 9. Historical Precedent Questionnaire

Historical research is conditional, not mandatory.

Activate it only when current uncertainty can plausibly be reduced by precedent.

Ask:

1. What exact current feature requires historical context?
2. What defines comparability?
3. Is the instrument comparable?
4. Is the regime comparable?
5. Is volatility comparable?
6. Is the event type comparable?
7. Is the structure comparable?
8. What is the sample size?
9. What regime mismatch remains?
10. Does the historical evidence change the current action or merely strengthen the story?

If it only adds confirmation, stop researching.

Backtests and historical evidence inform reasoning; they do not automatically veto or approve a trade.

---

# 10. Watch Trigger Questionnaire

A watch trigger starts a new investigation.

It must not preserve the old thesis automatically.

Ask:

1. What exact objective condition triggered?
2. Is the triggering condition still true now?
3. What decision was the watch originally intended to make possible?
4. What changed since the watch was created?
5. What is now the highest-value unresolved question?

Relevant changes may include:
- news;
- market regime;
- structure;
- portfolio state;
- time;
- position state.

Then return to the universal reasoning loop.

---

# 11. Active Position Questionnaire

Do not continuously re-justify an existing position from scratch.

Begin with:

> Has the original thesis been objectively invalidated?

Then ask:

1. Has objective invalidation occurred?
2. Has new information materially changed the thesis?
3. Has account or portfolio risk materially changed?
4. Has a pre-existing management condition been satisfied?
5. Is action required now?

Possible decisions:

- HOLD;
- REDUCE;
- MOVE_SL;
- EXIT;
- NO_CHANGE.

The daemon never chooses one of these.

---

# 12. Pre-Execution Questionnaire

This is the fixed short sequence immediately before execution.

1. Refresh current executable bid/ask.
2. Confirm current conditions still satisfy the thesis.
3. Confirm explicit stop loss and objective invalidation.
4. Confirm explicit target and plausible market objective.
5. Confirm explicit positive volume.
6. Refresh account, positions, margin, and relevant exposure.
7. Preview execution conditions, including spread, estimated fill/risk, and broker constraints.
8. Execute only if the refreshed evidence still supports the decision.

Execution parameters must never be silently fabricated.

Missing critical parameters are validation failures.

---

# 13. WAIT and NO TRADE

OpenCode must be free to terminate an investigation without a trade.

## WAIT

WAIT means:

> A future objective condition is known and would justify a new investigation.

Define:
- condition;
- instrument;
- direction if relevant;
- expiry/time condition;
- reason.

Create or update an objective watch.

## NO TRADE

NO TRADE means:

> There is no sufficiently defined opportunity, or the unresolved uncertainty cannot currently be resolved into a justified action.

Do not create a watch unless a specific future condition is genuinely worth monitoring.

---

# 14. Scheduled Reassessment Questionnaire

A scheduled wake must not mean "find a trade."

Ask:

1. Did anything materially change since the last reasoning cycle?
2. Is an active position due for factual review?
3. Did an active watch trigger?
4. Did a new objective event occur?
5. If none apply, do nothing.

The correct outcome can be WAIT or NO TRADE.

---

# 15. Stop-Investigating Rule

Stop investigating when any of the following is true:

1. A decision is justified and remaining uncertainty cannot change it.
2. A critical uncertainty cannot be resolved with currently available evidence.
3. The setup lacks definable invalidation.
4. The setup lacks a plausible objective.
5. Current executable conditions invalidate the opportunity.
6. Additional evidence would add confirmation but would not change the action.

More research is not automatically better reasoning.

---

# 16. Thesis Reset Rule

Previous reasoning cycles are context, not authority.

On a new wake:

- retrieve prior context when useful;
- do not inherit a previous thesis as true;
- re-check facts that could have changed;
- treat watch triggers as new investigations;
- prefer current evidence over stale conclusions.

A stored decision history explains what was previously believed. It does not determine what must be believed now.

---

# 17. Required Wake Vocabulary

The daemon should eventually use explicit trigger types:

- STARTUP
- SCHEDULED_REASSESSMENT
- WATCH_TRIGGER
- MARKET_STATE_CHANGE
- NEWS_EVENT
- ACTIVE_POSITION_REVIEW
- EXECUTION_RECHECK

A wake should contain only factual trigger information relevant to that event.

Example:

```text
ALPHA EVIDENCE WAKE

trigger_type: WATCH_TRIGGER
watch_id: ...
condition: ...
trigger_observed_at: ...
current_factual_value: ...

instruction:
Classify the actual decision. Start a new investigation.
Do not preserve an old thesis merely because this watch triggered.
```

For scheduled reassessment:

```text
ALPHA EVIDENCE WAKE

trigger_type: SCHEDULED_REASSESSMENT

active_instruments: ...
open_positions: ...

instruction:
Classify whether an actual decision exists.
Do not investigate a trade merely because of this wake.
```

---

# 18. Evidence Selection Contract

The intended evidence mapping is:

QUESTION
→ REQUIRED EVIDENCE TYPE
→ CANONICAL MCP TOOL

Do not map every questionnaire to every tool.

Examples:

"Is price accepting beyond the level?"
→ current market + structure + microstructure

"Did new information cause this displacement?"
→ event/news evidence + timestamps

"Is this historically unusual in a decision-relevant way?"
→ targeted precedent retrieval

"Can this order be executed safely now?"
→ live bid/ask + account + positions + explicit execution preview

Tool calls should be selected by decision value.

---

# 19. Decision Cycle Persistence

Future decision-cycle persistence should record:

- trigger type;
- decision being considered;
- highest-value unresolved question;
- evidence queried;
- relevant evidence timestamps;
- thesis;
- strongest contradiction checked;
- final decision;
- watch created or updated for WAIT.

This record provides continuity without making previous reasoning authoritative.

---

# 20. Regression Requirements

Future tests for `opencode.json` should assert the presence of these concepts:

- A wake is not a signal.
- Classify the decision first.
- No mandatory all-tool sweep.
- No mandatory full dossier.
- Watch triggers start a new investigation.
- Existing positions use invalidation-first review.
- Historical research is conditional.
- Pre-execution state refresh is mandatory.
- Explicit volume and stop are mandatory.
- Stop-investigating rule exists.
- WAIT and NO TRADE are distinct outcomes.
- Previous theses are context, not authority.

## Implementation Order

1. Preserve existing authority, truth, freshness, and targeted-evidence rules that already align with this document.
2. Refactor `opencode.json` into a hierarchy:
   - non-negotiable rules;
   - wake classification;
   - universal loop;
   - conditional questionnaires;
   - pre-execution gate;
   - WAIT/NO TRADE;
   - persistence and thesis reset.
3. Align daemon wake payloads to the required trigger vocabulary.
4. Add instruction regression tests.
5. Run the complete suite and validate the real OpenCode runtime path.

