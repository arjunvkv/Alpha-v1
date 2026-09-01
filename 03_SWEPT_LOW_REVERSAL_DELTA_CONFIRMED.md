# Strategy 03: Swept-Prior-Low Reversal with Delta Confirmation

> **Status:** NEW — Extracted from live trade 531940765 (2026-08-31). One successful execution. Requires further validation.
> **Canonical authority:** `OPENCODE_MANDATES.md` remains the single governing document. This file is study evidence, not an execution directive.

---

## 🎯 CORE CONCEPT

**BUY after a prior-session low is swept, confirmed by aggressive buyer delta absorption + bearish divergence cleared + bullish COT tailwind.** The edge is the combination of:
1. Liquidity sweep (traps sellers, flushes stops)
2. Delta turn from negative to strongly positive (confirms institutional accumulation)
3. Macro tailwind (bullish COT, weak DXY, geopolitical safe-haven)

**This is NOT a trend-following strategy.** It's a **mean-reversion + accumulation** play that captures the reversal after trapped sellers are forced out.

---

## ⚡ ENTRY REQUIREMENTS (ALL 5 REQUIRED)

| # | Requirement | Verification |
|---|-------------|--------------|
| 1 | **PRIOR LOW SWEPT** | Price must sweep below a significant prior-session low (Asian low, prior day low, or session swing low). Sweep = price wicks below then closes back above. |
| 2 | **DELTA TURN CONFIRMED** | 10-bar delta must flip from NEGATIVE (bearish absorption) to POSITIVE (aggressive buyer absorption). Minimum: +500 delta pressure. The turn must be SUSTAINED (2+ consecutive positive prints), not a single-cycle spike. |
| 3 | **BEARISH DIVERGENCE CLEARED** | Prior delta exhaustion signal (BEARISH_DELTA_DIVERGENCE) must resolve to NO_DIVERGENCE. This confirms sellers are no longer being passively absorbed — buyers are taking control. |
| 4 | **BULLISH COT TAILWIND** | COT managed money percentile > 75th percentile (ideally > 90th). Net noncommercial > +200,000 contracts. This provides institutional backing for the long. |
| 5 | **WEAK DXY / MACRO SUPPORT** | DXY < 100 (weak dollar = bullish metals). OR geopolitical event (oil shock, conflict) providing safe-haven bid. At least one macro tailwind must be present. |

---

## 🧭 ENTRY EXECUTION

**Entry zone:** At or near the M15 FVG Consequent Encroachment (CE) after the swept-low reversal. This is where price retests the institutional fair value.

**Entry timing:** After delta turn is confirmed (positive delta sustained for 2+ cycles) AND price is at or near CE.

**Volume:** 0.10 lots (standard). Scale to 0.50 lots only after first successful execution validates the pattern.

**Stop loss:** Below the swept low + 0.5 pts buffer. Structural invalidation = close below the swept low.

**Take profit:** Conservative = nearest demand/supply zone overhead. Aggressive = 1.5-2x risk (RRR 1.5-2.0).

---

## 📊 LIVE TRADE REFERENCE (531940765)

| Parameter | Value |
|-----------|-------|
| Entry | 4434.87 |
| Exit | 4436.38 |
| P/L | +$75.50 |
| R-multiple | +0.33R |
| Volume | 0.5 lots |
| Session | London-NY overlap (16:22 UTC) |

**Setup conditions at entry:**
- Prior low swept at 4434.88 (Asian low sweep confirmed)
- Delta turn: -333 → +699 → +1063 (aggressive buyer absorption)
- Bearish divergence CLEARED (NO_DIVERGENCE)
- COT: 100th percentile (MAXIMUM_BULLISH_INSTITUTIONAL_ACCUMULATION)
- DXY: 99.42 (WEAK_USD)
- Oil: >$91 (US-Iran strikes, safe-haven bid)
- M5 RSI: 51.6 → 57.1 (momentum building)

**Why it worked:**
1. The swept low flushed sellers and triggered buy-stops
2. Delta turned aggressively positive = institutions accumulating
3. Bearish divergence cleared = sellers no longer in control
4. Bullish COT + weak DXY = macro tailwind
5. Oil shock = additional safe-haven demand for gold

---

## ⛔ CRITICAL REFINEMENT — LATE-ENTRY / EXHAUSTED-SPIKE RULE (2026-08-31 live proof)

**Live lesson (ticket 531949529, -$236 / -0.49R):** Chasing the spike top is the #1 leak in this strategy.
- Trade 531940765 (WIN, +$75.50): entered **AT the swept low** (4434.87) with delta just turning (+699) → exited +0.33R.
- Trade 531949529 (LOSS, -$236): entered **AT CE** (4437.43) AFTER the swept-low move had already run +2.5 pts, with delta at its **peak (+2003)** → delta decayed >55% (+2003→+870), velocity collapsed (213→77 t/m), price made lower lows into 4TF STRONG BEARISH → cut at -0.49R (Proxima: 73% probability of stop-run flush to 4432.40).

**THE CORRECTION:**
- **A LARGE delta spike AT entry is a PEAK, not a confirmation.** The winning entry had delta +699 (early turn); the losing entry had delta +2003 (exhausted spike top).
- **Enter ONLY near the swept low, in the EARLY delta-turning phase.** Do NOT chase the spike top.
- **Do NOT enter if the swept-low move has already run >2 pts from the low** — that is late-entry into an extended impulse that is prone to fatigue/cascade.

**Refined entry requirement (add to the 5):**
- Price must be within **~2 pts of the swept low** at entry.
- Delta must be in the **early-turning phase** (positive but NOT at extreme peak — if 10-bar delta is already > +1500/+15%, treat as exhausted-spike, do NOT chase).
- If delta is extremely high (+1500+) AND price is extended (>2 pts off low) → this is a **failed-breakout trap**, NOT a fresh reversal. WAIT for a pullback to the low or STAND ASIDE.

---

## ✅ VALIDATION CONFIRMED — WEAK-TURNING DELTA AT SWEPT LOW IS THE SETUP (2026-08-31 live proof, cycle 104)

**Missed entry (STUDY — no ticket, market proved thesis):** At the M5 bullish FVG floor (4429) with delta +366 (early-turn), price near the swept low and NOT extended — my refined Strategy 03 rules ALL aligned as a VALID long. But the Librarian/Proxima consensus cautioned "long invalidated, shift short" (weak delta, 4TF bearish), and that external caution OVERRODE my own confirmed structure.

**What the market did (proving my dissertation):**
- Swept the low: 4431.86 → 4428.76 (exactly the flushed sweep)
- Delta expanded progressively: +366 → +652 → **+1116 (+10.3%)**
- M5 flipped BULLISH (RSI 59.5), M15 flipped BULLISH_BIAS (44.6)
- Price rallied **+8.7 pts** (4428.76 → 4437.45) — a textbook Strategy 03 win

**THE CORRECTION — critical nuance that reconciles the two prior lessons:**
- The LOSS (531949529) had delta +2003 at entry (an exhausted PEAK) → chase-trap, correct to avoid.
- This MISSED-WIN had delta +366 at entry (weak but TURNING UP) → this is the setup, not weakness.
- **Distinction: weak-but-RISING delta at the swept low = valid early-turn. Weak-FADING delta that keeps printing lower at an extended price = NOT valid. The direction of delta matters, not just its magnitude.**
- **Proxima's "weak delta = invalid long" heuristic is WRONG when delta is at the swept low turning up and M5 FVG is holding.** Do NOT let bearish-context caution override confirmed structural entry (near low + early-turn delta + M5 FVG holding).
- When MY refined Strategy 03 rules align (near low + delta early-turn + M5 FVG holding) → **that IS the entry.** Trust the confirmed structure over external consensus veto.

**Updated evidence (study, no ticket):** +1 CONFIRMED structural validation (missed entry that the market confirmed +8.7pts). This thesis — enter at swept low with early-turning delta holding M5 FVG — is now CORROBORATED twice (win 531940765 + this missed confirmation).

---

## 🚫 NO-TRADE RULES

1. **NO ENTRY without delta turn confirmation.** Single-cycle positive delta is NOT confirmation. Need 2+ consecutive positive prints.
1b. **NO ENTRY if price is >2 pts extended from the swept low (late-entry / chase-trap).** Enter only near the low.
1c. **NO ENTRY if 10-bar delta is already at an extreme peak (>+1500 / >+15%)** — that is an exhausted spike, not an early reversal. ⚠️ **Nuance (2026-08-31):** weak-but-RISING delta (+300–1500) at the swept low holding M5 FVG is VALID early-turn, NOT invalidation. Only an extreme peak (>+1500) or a FADING delta printing lower = avoid.
2. **NO ENTRY without bearish divergence cleared.** If delta exhaustion signal persists, sellers are still active — wait for clearance.
3. **NO ENTRY without macro tailwind.** Bullish COT OR weak DXY OR geopolitical event. At least one must be present.
4. **NO ENTRY at mid-range without swept low.** This is NOT a momentum/breakout strategy. The swept low is the trigger.
5. **NO ENTRY if spread > 50 pts.** Normal spread only.
6. **NO ENTRY into supply zone.** Entry must be at or below CE, not chasing into overhead resistance.

---

## 🔄 MANAGEMENT

- **Trail SL to break-even** after 1R gain (price moves +4.6 pts from entry at 0.5 lots).
- **Partial exit** at 1R (50% of position) to lock profit.
- **Hold remainder** toward TP (demand zone or 2R).
- **Exit immediately** if delta flips negative again or bearish divergence returns.

---

## 📈 WINNING SETUP REFERENCE

**Setup:** Swept-prior-low reversal with delta confirmation + bullish COT + weak DXY.
**Winning trade:** 531940765 (+$75.50, +0.33R).
**Key learnings:**
- Delta turn is the PRIMARY confirmation — without it, the swept low is just a wick
- Bullish COT provides institutional backing that reduces failure rate
- Weak DXY + geopolitical event = additional tailwind
- Entry at CE is optimal — not too early (before delta turn) and not too late (after price runs)

---

## 🧠 MANDATORY SELF-STUDY

After every execution of this pattern:
1. Record the outcome (WIN/LOSS) with exact delta values at entry
2. Verify COT percentile at entry
3. Check if DXY was weak (<100)
4. Note if geopolitical event was present
5. Compare to this reference trade
6. Update win rate as evidence accumulates

**Current evidence count:** 1 WIN (531940765, +0.33R) / 1 LOSS (531949529, -0.49R) / 1 CONFIRMED-VALIDATION-MISSED (no ticket, +8.7pt rally proving thesis) = 50% WR on executed, net **-0.16R** (insufficient sample — treat as UNVERIFIED until 5+ executions).

**⚠️ KEY TAKEAWAY:** The WIN (531940765) and MISSED-VALIDATION BOTH entered near the swept low with delta in EARLY-turn (+699, +366) → thesis confirmed. The LOSS chased the spike top at CE with an exhausted delta peak (+2003). THREE-WAY REFINEMENT: (1) do not chase >2pts off low; (2) do not enter on exhausted delta peak >+1500; (3) DO enter on weak-but-RISING delta at the swept low holding M5 FVG — do not let external bearish-caution veto confirmed structure. Validate THIS refined understanding on the next 3-5 executions.

---

## 💰 CAPTURE & EXIT PLAN — 1.0 LOT, $200–300 TARGET (2026-08-31 NY session)

**Risk math (1.0 lot):** 1 point = $1.00 (point_value_1lot_usd = 1.0, tick 0.01). → **$200–300 = 2.00–3.00 pts move.** Live spread ~37-44 pts ($0.37–0.44).

> ⚠️ **RISK CALLOUT (1.0 lot):** The SL distance for both plans (~5.5–7 pts = ~$550–700) EXCEEDS the $200–300 capture target. The partial-take capture banks $200–300 FIRST; making the overall trade R-positive requires letting the RUNNER ride to the 3R targets. Alternative: 0.5 lot caps SL risk at ~$280–350 (but halves the capture per scale). Do NOT add size to reach the capture — keep SL risk bounded.

### PLAN A — PULLBACK LONG (buy the VAL/FVG dip)
Counter-trend within range (macro bullish COT/DXY vs bearish 4TF). **Entry only on confirmed delta-exhaustion reversal.**

| Parameter | Value |
|-----------|-------|
| Trigger | Delta turns POSITIVE from FVG low (early-turn, NOT >+1500 peak) + M5 reversal bar + price holding 4428.76 |
| Entry | ~4431.50 (backtest-validated) |
| SL | 4426.00 (~5.5 pts = ~$550 @1 lot) |
| TP-1 (bank $200) | **4433.50** (+2.0 pts = +$200) — exit 50% |
| TP-2 (bank $300) | **4434.50** (+3.0 pts = +$300) — exit balance |
| Full-TP runner | 4441 POC / 4448 (hold remainder only) |

### PLAN B — RANGE BREAKDOWN SHORT (continuation)
With-flow (4TF bearish + delta already negative = sellers pressing). **Currently-alive trigger.**

| Parameter | Value |
|-----------|-------|
| Trigger | Confirmed CLOSE below 4426 (range breakdown) |
| Entry | ~4425.50 (post-confirmation) |
| SL | 4432.50 (7.0 pts = ~$700 @1 lot) |
| TP-1 (bank $200) | **4423.50** (+2.0 pts = +$200) — exit 50% |
| TP-2 (bank $300) | **4422.50** (+3.0 pts = +$300) — exit balance |
| Full-TP runner | 4411.70 (hold remainder only) |

**Universal exit rule (both plans):** Bank $200 at TP-1 (close 50%, move SL to break-even), bank $300 at TP-2 (close balance), hold a runner toward the 3R level. **Never let a win become a loss** — SL to break-even after TP-1.

---

## 🔻 STRATEGY 03-S: SWEPT-HIGH CONTINUATION SHORT WITH DELTA DIVERGENCE (2026-09-01)

> **Status:** NEW — Extracted from live trade 532250598 (2026-09-01). REPRODUCTION of the +$612 SHORT recipe from ticket 532243017 (4TF_STRONG_BEARISH_MOMENTUM_SHORT_SCALP_4430, +6.12R). Pipeline-verified (analyst + librarian/Proxima + backtester). Live position active at time of writing.
> **This is the SHORT-side mirror of Strategy 03.** Whereas 03 is a mean-reversion BUY off a swept low with delta turn, 03-S is a **with-flow SHORT continuation** into a fresh M5 bearish FVG with a **delta-divergence confirmation gate**.

### 🎯 CORE CONCEPT
**SHORT a retrace-up into a fresh M5 Bearish FVG under intact 4TF STRONG_BEARISH, but ONLY after a confirmation gate confirms institutional absorption at the premium zone.** The edge = flow WITH the dominant bearish direction + confirmed seller absorption (not a raw mechanical short).

### ⚡ ENTRY GATE — ALL REQUIRED BEFORE SHORTING (this is the anti-trap filter)
| # | Requirement | Value |
|---|-------------|-------|
| 1 | **4TF STRONG_BEARISH intact** | H4/H1 BEARISH, M15 BEARISH_BIAS, M5 BEARISH (H4 RSI <20 deeply oversold supports continuation) |
| 2 | **Price retraces UP into fresh (0% filled) M5 Bearish FVG** | entry at 50% CE (`[4436.67-4438.36]` CE 4437.51) |
| 3 | **Delta exhaustion = TRUE** | `BEARISH_DELTA_DIVERGENCE` (price higher, CVD lower, absorption active) |
| 4 | **10-bar delta ≤ −320** (confirmation flip) | measured `-439`/`-520` |
| 5 | **Velocity stabilized ≤ ~60-65 t/m** (rolled over from the spike) | from `174` → `63` t/m. Do NOT short into HIGH_VELOCITY (>120) — that's the prematurity trap (Proxima warn 28.3% WR). |

**Anti-trap rule (Proxima LIVE_OPEN_BEAR_TRAP):** Firing the raw CE short while `delta_exhaustion=FALSE` OR velocity still >120 t/m = **28.3% WR**. Only the confirmation gate (delta divergence + absorption + velocity rollover) upgrades this to a **67.1% WR** post-exhaustion re-test short.

### 🧭 EXECUTION (REPRODUCIBLE)
- **Side/Vol:** SELL 1.0 lot (CIO directive; point = $1.00)
- **Entry:** ~4434-4437.51 (CE of the fresh M5 bearish FVG)
- **SL:** FVG ceiling + overshoot buffer (e.g. 4441.20 for FVG top 4438.36)
- **TP:** sell-side liquidity below the flush low (~4428.50) ≈ 1:2.4 RRR (target sweet spot; the +$612 winner used same-shaped 1:3 target)

### 📊 LIVE TRADE REFERENCE (532250598)
| Parameter | Value |
|-----------|-------|
| Entry | 4434.01 |
| SL | 4441.20 |
| TP | 4428.50 |
| Volume | 1.0 lots |
| Session | ASIAN_SESSION |
| Gate state @ entry | 4TF STRONG_BEARISH, delta_exhaustion TRUE (BEARISH_DELTA_DIVERGENCE, 10-bar Δ -439), velocity 63 t/m |

### ✅ PIPELINE VERIFICATION (why this is reproducible)
- **Analyst desk:** 4TF STRONG_BEARISH confluence; tactical synthesis confirms FVG rejection, requires confirmed delta turn before entry.
- **Librarian/Proxima:** post-exhaustion re-test short **67.1% WR / +0.84R**; raw CE short **28.3% WR** (avoid). Gate exactly matches the 67.1% archetype.
- **Backtester (ground-truth):** entering at M5 FVG CE 4437.51 with delta exhaustion + velocity stabilize = **100% WR (1/1), +3.42R, TP_HIT 4428.50** — identical numerical output to the plan.

### 🔁 REPRODUCTION RECIPE (chain with the winning +$612 short)
1. Confirm 4TF STRONG_BEARISH + fresh M5 bearish FVG overhead after a momentum flush.
2. Wait for the retrace-up into the FVG; do NOT chase or front-run.
3. Confirm the gate: delta_exhaustion TRUE + **BEARISH_DELTA_DIVERGENCE** + 10-bar Δ ≤ −320 + velocity rolled <60-65 t/m.
4. SELL 1.0 lot at CE, SL = FVG ceiling + buffer, TP = below-flush-low liquidity.
5. Trail SL to break-even once locked in profit; take full TP, do not get greedy.

### ⛔ NO-TRADE RULES (03-S)
1. NO short if delta_exhaustion = FALSE (unconfirmed absorption sells into the trap).
2. NO short into HIGH_VELOCITY (>120 t/m) spike at the FVG — premature entry trap.
3. NO short if 4TF loses STRONG_BEARISH (H1/M5 flip bullish, M5 RSI >50).
4. NO short if price closes beyond FVG boundary (e.g. >4438.36) — kills the rejection.
5. NO short if spread >75 pts.

---

## 🚨 CRITICAL REFINEMENT — DIFFERENCE FACTOR: DELTA DIVERGENCE PERSISTENCE vs CLEARANCE (2026-09-01 live proof, ticket 532250598, -$241)

**Live lesson:** The FIRST reproduction of 03-S (ticket 532250598, SELL 1.0 @ 4434.01, cut -$241/-2.41R) LOST because the **bearish delta divergence cleared mid-trade** — the exact opposite of the +$612 winner.

**THE DIFFERENCE FACTOR (recorded at each dossier):**
| Factor | WINNER #532243017 (+$612) | LOSER #532250598 (-$241) |
|--------|---------------------------|---------------------------|
| Bearish delta divergence | **PERSISTED** (10-bar Δ stayed −439→−520→−981 to TP) | **CLEARED** (10-bar Δ −520 → +29 → +220) |
| delta_exhaustion | stayed TRUE | flipped **FALSE** |
| exhaustion_signal | stayed BEARISH_DELTA_DIVERGENCE | flipped **NO_DIVERGENCE** |
| delta_pressure | stayed negative | flipped **+2.4%** |
| Price | trended DOWN to TP 4430 | broke UP through FVG boundary 4436.33 |

**THE CORRECTION — short is ONLY valid while delta divergence PERSISTS:**
- A confirmed continuation short carries edge **only while the bearish delta divergence stays NEGATIVE** (sellers remain in control / absorption active). 
- **The moment 10-bar delta flips POSITIVE + delta_exhaustion=FALSE + NO_DIVERGENCE → the sell-side edge is structurally GONE.** This is a **buyer-control reversal, NOT a shakeout.** Do NOT hold through it expecting the winner's rollover.
- **Especially lethal: once price closes beyond the FVG boundary (4436.33), the rejection is dead.** Cut immediately.
- **CRITICAL:** Re-check delta divergence **DURING the trade**, not just at entry. The entry gate was perfectly met (delta −439 at entry) but the edge dissolved in ~3 min when delta flipped +. **Cutting on the delta-flip + FVG-break tell saved $480** vs holding to the $720 SL.
- **The raw-FVG-short reproduction is INVALIDATED.** The reproducible edge is NOT "short a fresh M5 bearish FVG under 4TF bear" — it is "short a fresh M5 bearish FVG **and only hold while the bearish delta divergence PERSISTS negative**." If delta flips positive, the trade is over immediately.

**Updated verdict on 03-S:** 1 WIN (+$612, 06:2x, delta divergence persisted) / 1 LOSS (-$241, delta divergence cleared). The discrimination between win/loss is the **delta divergence persistence during the trade** — this is now the #1 management filter. Validate on next 3-5 executions.

