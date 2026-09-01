# XAUUSD CE In-Direction — Direction-Agnostic Graceful TP Strategy

> **Status:** Live strategy playbook derived from TWO validated in-direction wins — +$234 (Ticket 531604293)
> and +$267 (Ticket 531632266, both 2026-08-31) — plus a corrected -$104 process-error loss (Ticket 531628003).
> The core principle: **TRADE THE EVIDENCE, NOT A FIXED DIRECTION.**
> Non-controlling evidence — does not override `OPENCODE_MANDATES.md`, the canonical Agent rule & study mandate.

---

## 🎯 CORE OBJECTIVE

Execute **1-lot XAUUSD trades at the M5 FVG Consequent Encroachment (CE) IN THE DIRECTION the live 4TF lean
and FVG type indicate** (Bullish FVG + bullish lean → LONG; Bearish FVG + bearish lean → SHORT), targeting a
**graceful, realistic profit zone** (~$200 / ~20 pips), and **NEVER over-aiming the TP.**

> **⚠️ CRITICAL CORRECTION (2026-08-31, -$104 loss):** **DO NOT fixate on a direction.**
> A long thesis is only valid while the tape is actually **bullish-leaning**. If the evidence flips bearish
> (M5 bearish rollover, negative delta, 4TF turns MIXED/not-bullish, macro veto), the long is **invalid —
> do NOT force it.** Let the evidence pick direction on every single setup.

> **🚫 CEO DIRECTIVE (2026-08-31, hard rule):** **Do NOT aim the TP for too much.** Place it at a
> **graceful / realistic level** (nearer structural magnet — prior swing high, round number, nearest supply/VAH)
> rather than the far edge of a move. A +$200-class scalp on 1 lot (~20 pips) is the base case.

---

## 🧭 DIRECTION-AGNOSTIC RULE (the core principle — applies to every entry)

| If the evidence shows... | Then trade... |
|---|---|
| **Bullish FVG** + **4TF bullish-leaning** (2-cycle confirmed) + delta **not strongly opposing** | **LONG** at the Bullish FVG CE (30–60% fill). Mildly-negative-but-*improving* delta is acceptable — buying returning. |
| **Bearish FVG** + **4TF bearish-leaning** (2-cycle confirmed) + delta **not strongly opposing** | **SHORT** at the Bearish FVG CE (30–60% fill). |
| 4TF **MIXED** / not cleanly leaning, OR delta **strongly opposing & deteriorating** the FVG direction, OR **macro veto** | **NO TRADE** (wait for a clean directional read) |

**The -$104 lesson (do not repeat):** I entered a LONG into an actually **bearish-leaning** tape (M5
BEARISH_BIAS, negative delta, 4TF MIXED, conviction LOW 4.6, Iran/rate-hike veto) purely because the 
strategy file was hardwired to "LONG." That is **direction fixation** and it is a **process error.**
A "don't over-wait for delta alignment" instruction refers to not over-fussing micro-delta **within a valid
directional setup** — it **never authorizes** forcing a long into a real bearish lean with negative delta.

> **🔑 KEY DELTA-NUANCE (from +$267 win #531632266):** "Delta aligns with direction" does NOT mean delta must
> be positive. The winning long entered with delta at **-6.4% but IMPROVING** (from -10.7%) inside a **2-cycle
> confirmed genuine bullish lean**. That is a buying-returning signal, not an opposing headwind. Over-waiting
> for delta to turn fully positive would have **missed the winner**. Distinguish this from the -$104 loss where
> delta was worsening into a MIXED/bearish tape. Rule: **strongly-opposing AND deteriorating delta = NO TRADE;
> mildly-opposing but improving delta within a genuine lean = tradeable.**

---

## ✅ THE VALIDATED WIN (Ticket 531604293) — LONG example

| Field | Value |
|---|---|
| **Setup** | M5 Bullish FVG `[4451.26–4453.38]`, CE `4452.32`, fill 30–60% (equilibrium) |
| **Entry** | BUY 1.0 lot @ `4457.30` (prox. FVG retest / backtest trigger matched `4455.96`) |
| **SL** | `4446.00` (below FVG floor `4451.26` + demand `4445.34`) |
| **Harvest** | `4459.64` (**+$234**) on M5 RSI ~80.7 deeply overbought |
| **4TF | Spread | CVD** | **BULLISH_LEANING** | 45 pts | BALANCED, no exhaustion divergence |

**Why it won:** the setup was **in-direction with a genuine bullish lean** — exactly what the direction-agnostic
rule requires. The mirror-image SHORT at a Bearish FVG CE with a genuine bearish lean carries the same logic.

---

## ✅ THE SECOND VALIDATED WIN (Ticket 531632266) — LONG example (delta-improving)

| Field | Value |
|---|---|
| **Setup** | M5 Bullish FVG CE `[4451.26–4453.38]` (equilibrium) — 2-CYCLE confirmed 4TF BULLISH_LEANING |
| **Entry** | BUY 1.0 lot @ `4455.81` |
| **SL** | `4448.00` (below FVG floor `4451.26`, above demand `4445.34`) |
| **Trail** | SL → breakeven `4455.81` at **+$174** (meaningful advance) |
| **Harvest** | Graceful TP `4458.50` (**+$267 net**) |
| **4TF \| Spread \| Delta** | **BULLISH_LEANING** (2 cycles) \| 45 pts \| **-6.4% but IMPROVING** (-10.7%→-6.4%, buying returning) |

**Why it won:** entered the validated CE at a **genuinely bullish-leaning** tape (not forced like the -$104).
The delta was slightly negative **but improving**, which the winning read correctly treated as buying-returning
rather than an opposing headwind — the exact nuance that separates this from the forced -$104 long.

---

## 🧭 ENTRY CHECKLIST (ALL must be true to take a trade — any direction)

| # | Check | Requirement |
|---|---|---|
| 1 | **4TF alignment** | Clean **BULLISH_LEANING** for a LONG or clean **BEARISH_LEANING** for a SHORT. **MIXED_TIMEFRAMES = NO TRADE.** |
| 2 | **Correct FVG type** | LONG → Bullish FVG. SHORT → Bearish FVG. Do NOT buy a Bullish FVG while the tape is bearish (and vice-versa). |
| 3 | **CE fill 30–60%** | Enter at equilibrium/CE (NOT chasing an exhausted ≥60% FVG). |
| 4 | **Delta aligns with direction** | LONG → delta not negative / absorbing. SHORT → delta not positive. **Opposing delta = NO TRADE.** |
| 5 | **Spread normal** | XAUUSD ≤ ~45–67 pts per live ceiling. ELEVATED/HIGH_SPIKE = NO TRADE. |
| 6 | **No exhaustion divergence** | CVD not showing exhaustion against the intended direction. |
| 7 | **Macro clear** | No veto macro event (geopolitical escalation, rate shock) overhanging the session. |

**Entry verification tool calls (MCP sequence — run on EVERY setup, both directions):**
1. `mcp_alpha_get_symbol_conviction` — 4TF alignment + EMA20/50 & RSI + FVG geometry + COT percentile
2. `mcp_alpha_get_fvg_matrix` / `mcp_alpha_get_full_institutional_profile` — FVG type + CE + POC/VAH/VAL/VWAP + demand/supply
3. `mcp_alpha_get_measured_cvd` — CVD posture, velocity, absorption, no-exhaustion confirmation (delta direction!)
4. `mcp_alpha_get_live_microstructure` — live spread (pts) + tick velocity + order-book imbalance
5. `mcp_alpha_query_analyst_desk` — 7-layer bull/bear synthesis for conviction
6. `mcp_alpha_get_live_world_events` — macro/geopolitical veto check (Iran-style escalation, rate shocks)

---

## 🎯 TAKE-PROFIT — THE GRACEFUL TP RULE (direction-independent)

**NEW DEFAULT: place TP at a graceful, realistic magnet, NOT a far target.**

- **Base case TP:** ~**20 pips / ~$200** on 1 lot, placed at the **first meaningful structure in the trade
  direction**: prior swing high/low, round number, nearest supply/VAH (long) or demand/VAL (short).
- **Do NOT extend the TP** to the far edge of the move "for the bonus."
- **Overbought / oversold = harvest signal:** M5 RSI **~80+ (long) / ~20- (short)** with profit at/above target
  → **harvest the win.** Do not hold for more.
- **Exceeded-target rule:** once profit ≥ intended ~$200, trail or exit; do not give back a real gain.

**Management sequence:**
1. HOLD through minor pullback noise while structure intact (FVG floor + demand below SL for a long; FVG ceiling + supply above SL for a short).
2. **Trail SL to breakeven** only after a **meaningful advance** (≈ +$80–+$100 / past a structural barrier) — NEVER on first-profit noise.
3. On exhaustion (M5 RSI ~80 / ~20) or profit ≥ target → **harvest at the graceful zone.**

---

## 🔍 THE COMPLETE MCP WORKFLOW (direction-agnostic)

### A. Pre-trade research & validation
| MCP tool | Purpose |
|---|---|
| `mcp_alpha_ask_librarian` | Quant expectancy / CE equilibrium edge + mirror-image bearish setups |
| `mcp_alpha_backtest_thesis` | Replay the exact FVG setup **in the live direction** before entry |
| `mcp_alpha_get_ledger_decomposition` | Confirm the profitable condition bucket (session × direction × CE × spread) |
| `mcp_alpha_get_trade_forensics` | Root-cause prior losses (counter-trend, direction fixation) |
| `mcp_alpha_query_analyst_desk` | 4TF directional consensus (bull OR bear) |

### B. Live entry-position
| MCP tool | Purpose |
|---|---|
| `mcp_alpha_get_account_status` | Confirm equity, margin, no conflicting positions before execution |
| `mcp_alpha_record_decision_snapshot` | Record pre-trade process context (with the direction + evidence used) |
| `mcp_alpha_register_watch` | Register the active thesis + invalidation with the Librarian |
| `mcp_alpha_execute_trade` | Place the 1-lot trade (side = evidence direction) with structural SL + graceful TP |

### C. Position management & closure
| MCP tool | Purpose |
|---|---|
| `mcp_alpha_get_account_status` | Monitor live PnL each cycle |
| `mcp_alpha_get_measured_cvd` | Confirm no exhaustion divergence while holding |
| `mcp_alpha_update_position` | `TRAIL_SL` to breakeven after meaningful advance → `FULL_EXIT` / harvest at graceful zone |
| `mcp_alpha_record_trade_observation` | Commit WIN/LOSS + lesson into Pattern Book & ULM |

---

## 🚫 INVALIDATION / NO-TRADE RULES (direction-agnostic)

- **MIXED_TIMEFRAMES = NO TRADE.** A long requires a genuine bullish lean; a short requires a genuine bearish lean. Do not force a side.
- **Opposing delta = NO TRADE.** Do not buy into negative delta, do not short into positive delta.
- **NO-TRADE** if spread elevated/spike beyond ceiling (execution safety latch).
- **NO-TRADE** on counter-trend into an exhausted ≥60% fill FVG without confirmed sweep + absorption + volume ≥1.5× the 20-bar average.
- **Macro veto:** geopolitical escalation (e.g. Iran strikes) or rate-shock repricing overhanging = NO-TRADE / high caution.
- **NO-TRADE** on a single-cycle snapshot — trail 2+ cycles; **single-cycle = exploratory, two-cycle = actionable.**
- **INVALIDATE** a long if M5 closes below the FVG floor/demand; a short if M5 closes above the FVG ceiling/supply.
- **DO NOT round-trip** the same FVG zone repeatedly after harvesting.

---

## 🧠 LESSONS LOCKED INTO ULM (permanent)

1. **Graceful TP > maximum TP.** Aim at a realistic magnet (~20 pips / ~$200), never a far stretch target.
2. **Direction-agnostic, not direction-fixated.** Trade the evidence: LONG only on bullish-lean FVG-CE; SHORT only on bearish-lean FVG-CE. MIXED 4TF or opposing delta = NO TRADE. **Never force a long just because there's a Bullish FVG** — the -$104 loss.
3. **In-direction is the edge** — but "direction" is defined by the live 4TF lean + FVG type + delta, re-evaluated on every setup.
4. **Trail to breakeven only after meaningful advance**, not on float noise.
5. **Harvest on exhaustion** (M5 RSI ~80 / ~20) once profit ≥ target.
6. **Structure-protection SL** — below FVG floor + demand (long) or above FVG ceiling + supply (short).

---

*Reference: `logs/pattern_reality_check.md`, `logs/unified_learning_memory.json`, `logs/full_desk_dossier.md`.
Validated WIN #531604293 (+$234, long on clean bullish lean). Corrected process-error LOSS #531628003 (-$104, forced long into bearish lean).
Non-controlling; `OPENCODE_MANDATES.md` remains canonical.*
