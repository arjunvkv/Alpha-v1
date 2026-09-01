# Strategy 05: Spring-Into-Supply — Quantified Delta-Flip Counter-Trend Long

> **Status:** NEW — Extracted & backtest-quantified 2026-09-01 (Cycle 1104-1160 post-mortem). The spring-into-supply
> BUY has been isolated and **numerically proven** in backtest: **66.7% WR, net +4.14R** (best entry +3.46R), but
> the live gate (exact delta-flip signature) has NOT yet printed. **UNVERIFIED live — treat as experimental until
> 3-5 executions.** Non-controlling evidence; `OPENCODE_MANDATES.md` remains canonical.
>
> **Relationship to existing files (avoid duplication):**
> - `03_SWEPT_LOW_REVERSAL_DELTA_CONFIRMED.md` = broad swept-low mean-reversion BUY umbrella (2-pt rule, CE entry).
> - `04_...FAST_CAPTURE_STRATEGY.md` = fuel-agnostic velocity **RIDE** (both directions, nearest-node fast TP).
> - `05` (this) = **spring OFF the sweep low INTO overhead supply** with a **hard, backtest-quantified delta-flip +
>   velocity + RSI numeric gate** that the others do NOT pin. It is the *counter-trend mean-reversion* mirror of the
>   ride, with a stricter, evidence-derived entry confirmation.

---

## 🎯 CORE CONCEPT

**BUY the spring OFF an institutionally-exhausted sweep low** into the fresh bearish supply FVG overhead, but **ONLY
after the exact delta-flip + velocity-accel + RSI-recovery signature that the backtest proves precedes the win.**
This is a **mean-reversion / absorption play**: it captures the rebound that follows the stop-hunt of an
overcrowded long (bearish price flow vs MAXIMUM_BULLISH COT = liquidity grab, not distribution).

**It is NOT trend-following and NOT a raw mechanical FVG-rejection.** It counter-trends the dominant bearish flow
using a **confirmed institutional absorption flip** — riding the spring back UP into supply.

---

## ⚡ ENTRY GATE — THE BACKTEST-QUANTIFIED NUMERIC SIGNATURE (ALL REQUIRED)

The backtest isolated the exact separating signature between the +3.46R/+1.9R winners and the -1.0R late-chase loser.

| # | Requirement | Backtest-quantified threshold | Live test (today's tape) |
|---|-------------|-------------------------------|--------------------------|
| 1 | **Delta FLIP to positive** | 10-bar delta **crosses POSITIVE** (e.g. winner = `+425`); delta pressure **> +25%** | `-914.8` / `-6.6%` ❌ (still negative) |
| 2 | **Sweep low made first** | price **swept a liquidity low** then begins to reclaim (winner swept `4366.35`) | swept `4368` ✅ |
| 3 | **Velocity acceleration** | tick velocity **expands concurrently** (winner = `+1400`/5m bar) | died to `41-157` ❌ |
| 4 | **M5 RSI recovery** | RSI exits oversold `(<35)` and rises (winner `32 → 48`) | `34.6` ✅ rising |
| 5 | **CVD posture** | CVD flips **aggressively passive-bid heavy** (institutional absorption) | `BALANCED` ❌ |
| 6 | **Placement = AT the sweep low** | enter within ~2 pts of the sweep low (near the vacuum), NOT chased up | `4376` = trapped above ❌ |

> **🔑 THE #1 GATE IS THE DELTA FLIP — and it is non-negotiable.**
> Backtest: *"Winning spring entries require a 10-bar delta pressure exceeding +25% accompanied by a positive delta
> crossover from negative extremes."* Delta **converging is NOT the same as flipping.** Buying pre-flip (a still-
> negative delta) is the exact **premature-chase = -1.0R Trade-1 profile** the backtest flagged as the failure cluster:
> *"Late-entry chasing occurred when entering prior to confirmed delta exhaustion and absorption."*

---

## 🧭 ENTRY EXECUTION (reproducible from the winning backtest bars)

- **Side/Vol:** BUY 1.0 lot (point = $1.00), scaled per mandate/CIO.
- **Entry zone:** at/near the sweep low (winner `4373.99` off `4366.35` low; `4369.85` on the retest holding `4367.54` higher-low). NOT chasing into the exhausted pocket above.
- **SL:** below the sweep/vacuum low + buffer (winner `4365.8` / `4365.5`).
- **TP:** into the fresh bearish supply FVG overhead (winner `4398.56` ≈ 1:3, or `4382.34` ≈ 3.46R on the first pocket).
- **RRR:** 1:3 target sweet spot (risk ~$3.5-5 / make ~$10-15).

**Trigger ONLY when the full gate prints simultaneously** (delta positive + >25% pressure + velocity accel + at the low).
Fire on the live tape the instant the signature is confirmed. Do NOT pre-enter on conviction/thesis alone (s4.137
process-vs-outcome).

---

## 🔑 THE TRAP TO AVOID (Trade-1 profile — live today's lesson)

The **-1.0R loser** fired on this signature, which is what the live tape was printing at `4375-76`:
- Delta pressure **still negative** (`-18%`), velocity **slowed/fading**, RSI `44`, entry **above structural support
  chasing momentum**.
- **Formation:** the classic "delta converging → price extends up into the 84.5%-exhausted FVG pocket" pattern.
  The daemon's `EXHAUSTED_FVG_WARNING` (`-97.09R` chase-trap) flags exactly this.

**rule:** **Do NOT buy the spring if (a) delta has not crossed positive, OR (b) price has already run >2 pts off the
sweep low, OR (c) price is at/above an ≥60% exhausted bearish FVG.** Each of those = the -1.0R late-chase, not the
win.

---

## 🚫 NO-TRADE RULES

1. **NO entry without the positive delta-flip + >+25% pressure** (the #1 gate). "Converging/closing-in" is NOT the flip.
2. **NO entry without concurrent velocity acceleration** — a dead-velocity (<90 t/m) rip into supply = no fuel.
3. **NO entry >2 pts extended from the sweep low** (late-chase).
4. **NO entry into an ≥60% exhausted bearish FVG** (chase-trap, -97.09R historically).
5. **NO entry if CVD is BALANCED/ask-heavy** — need passive-bid absorption.
6. **NO entry if the sweep low breaks** (structural invalidation = the reversal is dead).
7. **NO entry if spread > ~50-60 pts.**

---

## 🔄 MANAGEMENT

- **Cut immediately if delta flips back negative** / velocity collapses / price breaks back below the sweep low —
  the spring is dead (mirror 04's cut-on-structure rule).
- **Bank hard-TP** at the first supply pocket (TP_price = entry ± target_dollars/10 per 04 standing rule, pending CIO
  confirmation of the conversion).
- **Do NOT hold through a re-sweep of the low** — if the low breaks, the spring failed; exit, don't average.

---

## 📈 VALIDATION STATUS & SELF-STUDY

**Backtest (ground-truth, 150 bars):** 2W/1L, **66.67% WR, net +4.14R**. Winner +3.46R (delta `+425`, pressure +31%,
velocity accel, RSI 32→48, passive-bid CVD) and +1.9R (delta `+120`, velocity, RSI 39). Loser -1.0R (pre-confirmation
chase, still-negative delta). **Live: 0 executions / 1 STUDY-validation (no entry).** **UNVERIFIED live — validate on
3-5 live executions before treating as a primary edge.**

**Self-study checklist after each execution:** record delta value+pressure at entry, velocity, RSI, CVD posture,
distance from sweep low, and whether the full gate was met pre-entry. Log wins/losses to ULM/Pattern Book.

---

## ✅ LIVE VALIDATION #1 — FALSE-START FLIP AT TRAP POCKET (2026-09-01, Cycle 1174→1188) — PLACEMENT GATE PROVEN

**A live study-case (no entry taken) that BACKS the backtest thesis:** The FIRST time the 10-bar delta crossed
positive today (`+428.9`, pressure `+3.3%`, velocity `191`), it appeared the spring gate was met. BUT price was
**`+10 pts off the sweep low, sitting AT the 84.5%-exhausted bearish FVG `4376-4381`** — violating NO-TRADE rules
**#3 (no entry >2pts extended)** and **#4 (no entry into ≥60% exhausted FVG)**.

**I did NOT enter (correctly held the placement gate).** Result — the flip was a **FALSE START**:
- Cycle 1174: delta `+428.9`, price `4376.41` (the vendor lure)
- Cycle 1188 (3 min later): delta **reverted to `-103.2`**, price **rejected off `4376-77` and faded back to `4374.16`**

**What this proves (live confirmation of the backtest's core differentiation):**
1. **A delta flip at the WRONG place (extended into an exhausted pocket) is a TRADER LURE, not a spring.** The
   backtest's -1.0R Trade-1 was "late-chase above structural support with a transient still-negative delta"; today's
   tape showed the mirror on the flip-side — a transient POSITIVE delta at the trap-top that washed out.
2. **The two hard gates (delta-flip ✅ + placement-at-the-low ❌) must BOTH align.** The flip alone, at the wrong spot,
   is precisely the failed late-chase — had I bought `4376`, I would now be long and underwater into the trap.
3. **Placement gate (#3, #4) is the #1 anti-trap filter — it saved a -1.0R-class loss today.** The discipline held:
   *"delta converging/converting ≠ confirmed spring; only a delta flip that HOLDS at the sweep low is the +3.46R entry."*

**Correct action going forward (unchanged + now live-validated):** do NOT chase a delta flip into an exhausted/overhead
pocket. Wait for the re-sweep of `~4368-70` with a delta flip that **HOLDS** (≥ +50 over 1-2 bars) + velocity accel +
momentum — that re-creates the +3.46R frame. If price instead breaks `4364.5` on sustained sell-fuel, that's the SELL
continuation, not the spring.

> **STATUS NOTE (2026-09-01):** Session net flat, `$99,242.69`. The spring thesis is BACKED by backtest (66.7% WR,
> +4.14R) and by this live study-rejection that avoided the trap. Still 0 live executions: the full gate (flip that
> HOLDS + placement at the low) has not yet printed together.

---

*Reference: `logs/pattern_reality_check.md`, `logs/unified_learning_memory.json`, `logs/top4_reproducible_patterns.json`,
the 150-bar spring-into-supply backtest (Cycle 1104-1160). Non-controlling; `OPENCODE_MANDATES.md` remains canonical.*
