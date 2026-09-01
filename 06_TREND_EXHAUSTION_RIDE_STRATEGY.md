# XAUUSD Trend-Exhaustion Ride (Run-Till-Exhaustion) — Continuation Strategy

> **Status:** Strategy playbook derived from a LIVE, active experiment (Ticket `#532804486`,
> exhaustion-ride SELL probe @ 4367.18, SL 4379, TP-cap 4334) within the London/NY-overlap session,
> operating a `4TF_STRONG_BEARISH_CONFLUENCE` tape. **Core principle: RIDE an aligned trend leg until
> delta/velocity EXHAUSTION confirms a reversal — NOT a tight scalp — using the 0.01-lot probe →
> 1.0-lot fill workflow.** This is the **6th strategy file**, complementing:
> - `01_MICRO_PROFIT_SCALPING_STRATEGY.md` (historical hold-to-tip archive)
> - `02_XAUUSD_CE_IN_DIRECTION_STRATEGY.md` (direction-agnostic CE entry)
> - `03_ASIAN_BEAR_TRAP_REVERSAL_STRATEGY.md` (session-discipline + rejection-continuation)
> - `03_SWEPT_LOW_REVERSAL_DELTA_CONFIRMED.md` (delta-confirmed reversal)
> - `04_RIDE_ALIGNED_VELOCITY_FAST_CAPTURE_STRATEGY.md` (fast-capture scalp)
> - `05_SPRING_INTO_SUPPLY_DELTA_QUANTIFIED.md` (supply spring)
>
> Non-controlling evidence — does not override `OPENCODE_MANDATES.md`, the canonical Agent rule & study
> mandate.

---

## 🎯 CORE OBJECTIVE

Take a **XAUUSD trade that rides an aligned trend leg to EXHAUSTION** — capturing the full move, with a
**trailing stop behind structural highs/lows** rather than a fixed tight scalp TP — using the operative
**0.01-lot probe → 1.0-lot fill** workflow to de-risk the initial read. The goal is NOT the ~$100 nearest-node
scalp of `04_`; it is the **larger continuation leg** that a strong 4TF-aligned, delta-confirmed trend
delivers before exhaustion.

> **⚠️ THE INSIGHT THAT BIRTHED THIS FILE (from the user's directive):**
> > "looking at the current live probe as it's showing long bearish for too long — can't we do these type of
> > trades where we run till exhaustion, not just a scalp?"
>
> The prior short (`532766078`) failed as a **scalp-with-tight-stop** — it was entered early into a
> counter-trend bounce (Asian Low sweep) and got whipsawed before the real down-leg resumed. The correction:
> **stop scalping the pullback; RIDE the confirmed trend leg and EXIT on exhaustion, not on a fixed TP.** Also
> paired with the standing directive: **"don't cut early with a 0.01 lot, then fill to 1.0 lot."**

---

## 🧭 THE 0.01 PROBE → 1.0 FILL WORKFLOW (the operative execution model)

1. **Probe 0.01 lot** at the nearest VALID trigger (evaluated with the full MCP suite) — NOT the unicorn
   perfect setup. Per user: **"Don't gate too much."** Be decisive; validate the nearest valid (not
   necessarily ideal) aligned trigger.
2. **Let the 0.01 probe run to exhaustion — do NOT cut it early.** The probe is the confirmation vehicle; a
   small early cut teaches nothing and abandons the trend leg on noise.
3. **Fill to 1.0 lot** at the CORRECT confirmation point — when the probe shows the trend is re-accelerating in
   the ride direction (aggressive directional delta restored + structural continuation), **not** a filled-to-exhaustion
   FVG. This is the single biggest edge over the failed `532766078`.
4. **Manage both lots under the SAME trail-to-exhaustion framework** (below) until an exhaustion exit signal fires.

> **🔑 THE HARD LESSON (from `532766078` and the `PROBE_FILL_M5_BEAR_FVG_BREAKDOWN` ULM pattern):**
> Filling to 1.0 on PRICE-BREAKDOWN ALONE (delta BALANCED) **into an exhausted ADR causes a whip-out**.
> The fill requires **BOTH structural continuation AND aggressive directional delta restoration** before scaling.
> Do NOT scale on price action alone when the delta is BALANCED.

---

## 🚦 THE RIDE-TO-EXHAUSTION ENTRY GATE (all must hold)

1. **Strong HTF alignment WITH the entry.** `4TF_STRONG_BEARISH_CONFLUENCE` (H4/H1/M15 bearish) = strongest
   short-ride bias. Avoid counter-trend anticipation.
2. **Confirmed directional delta** (recent 10-bar delta in the entry direction and **negative/positive pressure
   percentage**), ideally **no divergence** between price and CVD. Exhaustion/divergence at entry = do NOT enter;
   that is reversal fuel, not ride fuel.
3. **Price rejecting a structural FVG/CE in the ride direction** (e.g. M15 Bearish FVG CE rejection resuming
   the down-leg), with **tick velocity ≥ ~90 t/m** in the direction (velocity collapse = no ride).
4. **Not an exhausted-ADR chase.** If ADR is already deeply exhausted (>85% used), the ride-to-exhaustion
   window is narrow — prefer a fresh reaction off a structural level.

## 🚦 THE CONFIRMATION GATE — 1.0 vs 0.01 SIZING (hard rule; from `532841164` LOSS -$730)

> **The loss was a REPRODUCE misclassified as CONFIRMED.** I went 1.0 direct on an ANTICIPATION entry
> (4TF + negative delta + velocity, but NO printed FVG-rejection trigger). The bounce broke the CE instead of
> rejecting → -$730. If I'd probed 0.01, the failed rejection would've cost ~-$7. **The winning trade's edge
> was the FVG rejection PRINTING (confirmation); the loser lacked the print (anticipation).**

1. **CONFIRMED-TRIGGER entries (FVG rejection printed + resumption in motion) → may size 1.0 directly.**
2. **ANTICIPATION entries (confluence + delta, but trigger NOT yet printed) → MUST probe 0.01 first** and
   scale to 1.0 only when the trigger prints (price rejects the FVG CE and resumes the ride direction).
3. **A reproduce is never guaranteed** — the reproduce flag only entitles you to 1.0 when the trigger
   CONFIRMS at/after entry. Confluence (4TF/delta/velocity) does NOT override a broken structure: if the
   CE rejection fails (price closes through the CE), thesis is dead — exit at the CE failure, NOT at the
   wider SL.
4. **If in doubt about trigger state → 0.01.** The probe is the cheap way to learn which case you're in.

## 🔄 THE EXHAUSTION EXIT GATE (exit the ride when these confirm)

Exit on **EXHAUSTION**, not a fixed TP — but keep a protective cap:
- **Tick velocity collapse** (e.g. 287 t/m → <80 t/m) while the move stalls.
- **CVD divergence** — price prints the extreme but CVD stops confirming (delta exhaustion).
- **Delta sign flip** — 10-bar delta flips against the ride direction (accumulation/distribution reversing).
- **Order-book imbalance flipping** to the opposite (buyer-dominant for a short ride).
- **Structural reversal** — price closes back through the FVG CE / swept a fresh HTF low in the opposite
  direction... i.e. the trend leg structure breaks.

**Protective cap:** because this is not an endless ride, place a **TP-CAP** at the deepest reachable node
(e.g. the deepest fresh M5 Bull FVG / VA-low), and **trail the SL** behind each structural lower-low/higher-
high. The cap + trail define the boundary; exhaustion signals trigger the discretionary early exit.

---

## ✅ LIVE ACTIVE EXPERIMENT (Ticket `#532804486`)

| Field | Value |
|---|---|
| **Side** | SELL 0.01 (probe) |
| **Entry** | 4367.18 |
| **Current** | ~4367-4369 (near entry, consolidation) |
| **SL** | 4379.00 (above M15 Bear FVG top 4378.17) |
| **TP-CAP** | 4334.00 (deepest M5 Bull FVG) |
| **4TF** | H4(13.3) H1(23.1) M15(45.1) M5(70.2) → `4TF_STRONG_BEARISH_CONFLUENCE` |
| **CVD** | Cumulative -2367.7 (negative, bearish flow dominant) |
| **FVG** | M15 Bearish [4374.43-4378.17], CE 4376.3, PARTIALLY_FILLED — entry is below it, ride resuming |
| **Velocity** | ~217 t/m (high, move active) |
| **Scale plan** | Fill to 1.0 when bearish delta re-accelerates (10-bar delta strongly negative) + price stays below FVG CE, then trail |

> **Watch registered:** `RIDE_TO_EXHAUSTION` — scale to 1.0 only if bearish delta re-accelerates with price
> rejecting FVG CE 4376.3; trail behind each lower-high; exit on exhaustion (velocity collapse + CVD
> divergence + order-book flip), not a fixed scalp TP.

---

## 🚫 FAILURE TRAPS TO AVOID

- **The Exhaustion-Mistaken-As-Reversal Trap:** entering WITH the trend, then panicking out on the first
  counter-pullback (the `532776078` error). The trend leg needs room; only exhaustion signals justify exit.
- **Scaling on Price-Breakdown-Alone into Exhausted ADR** (the `PROBE_FILL_M5_BEAR_FVG_BREAKDOWN` trap):
  fill to 1.0 only when both structure AND directional delta confirm.
- **Scalping a Trend Leg:** a tight fixed TP on a strong trend leaves the main move on the table (the 
  `04_` velocity lesson — don't cap a confirmed trend at the nearest node).
- **Riding Through a Confirmed Exhaustion:** ignoring velocity collapse + CVD divergence + order-book flip
  and holding "hoping" the leg continues = the waterfall surrender. Exhaustion IS the exit.
- **Counter-Trend Ride:** riding AGAINST the HTF alignment (e.g. buying in a strong-bearish confluence).
  The ride edge comes from going WITH the dominant 4TF fuel.

---

## 📈 BASE-RATE / PRECEDENT SUPPORT

- **London/NY-overlap session** = peak institutional volume/momentum window — the best environment for a
  sustained trend leg (matches the live experiment timing).
- **Full 4TF confluence** = strongest rideable institutional alignment (H4/H1/M15 bearish confirmed in the
  live probe).
- **Deepening-Sweep-Liquidity-Vacuum & Deep-Exhaustion precedents** in ULM describe the continuation-
  to-exhaustion dynamic this strategy codifies.
- The `04_` velocity-ride win `532397864` (+$884) demonstrates the power of riding WITH dominant fuel to a
  structural extension rather than a tight scalp — this strategy formalizes that as **ride-to-exhaustion**.

---

## 📒 LIVE EVIDENCE LOG (progressive — appended each cycle)

| Ticket | Cycle | P/L | Price | Key finding / decision |
|---|---|---|---|---|
| 532766078 | — | **-$15.73** | 4369.23 | Prior scalp short entered early into counter-trend bounce → whipsaw, cut on momentum-divergence invalidation. **Birthed the ride-to-exhaustion correction** (`BEAR_TRAP_LIQUIDITY_GRAB_FAILURE` recorded). |
| 532804486 | 2522 | probe | 4367.18 | **EXHAUSTION-RIDE SELL 0.01 open.** 4TF strong bearish, CVD -2367, below M15 Bear FVG CE. Watch registered; scale to 1.0 on bearish-delta re-acceleration + structure; exit on exhaustion. |
| 532804486 | 2528 | -$2.18 | 4369.36 | Consolidating near entry; velocity 244 t/m; **hold (probe must run to exhaustion, do not cut early).** |
| 532804486 | 2536 | **-$4.99** | 4372.17 | Probe cut. Bearish delta FAILED to confirm — 10-bar delta +2486, CVD -2367→-1023 (buyer absorption), M15/M5 flipped bullish. **Per user correction, 0.01 probe-riding was the wrong model.** Did NOT scale on absorbing tape (`RIDE_TO_EXHAUSTION_FILL_GATE` recorded). |
| 532820222 | 2578→2616 | **+~$868** | exit 4360.00 | **✅ 1.0-LOT RIDE-WITH-TREND WIN (the VALIDATING trade).** Entry 4368.81 on M15 Bear FVG rejection + `4TF_STRONG_BEARISH_CONFLUENCE` resumption (the "right entry" — NOT a 0.01 probe ride). Rode peak +$1056 (4358.25), then trailed SL 4375.50→4360.00 on **velocity-collapse exhaustion** (258→9 t/m into M15 Bull FVG 4344-4354). Banked ~$868 (balance 98,728.24 → 99,596.19). `RIDE_TO_EXHAUSTION_1LOT_FVG_REJECTION` recorded. |
| 532841164 | 2638→2666 | open | 4357.68 | **REPRODUCE-VALIDATED-WIN: SELL 1.0 @ 4356.93, SL 4366.50, TP 4334.00** — re-entered the down-leg on 4TF strong bearish + 10-bar delta flipped negative (-1366) + high velocity. Bounce tested M5 EMA20 (4363) then faded back to entry; delta stayed negative (-1465 / CVD -1520) = sellers absorbing the bounce. **Held through adverse pullback (peak -$467) — no cut while 4TF bearish + delta negative + structure intact (per user: don't cut if still valid).** Riding to exhaustion; invalidation = close above M15 EMA20 4367 / delta flip positive. |
| 532841164 | 2678→2688 | **-$730** | exit 4364.23 | **❌ FAILED CE-REJECTION REPRODUCE (LOSS).** Tested M15 Bear FVG CE 4363.47; price initially rejected (delta -910 at CE) BUT then broke ABOVE the CE — M5 flipped **BULLISH** (first 4TF break), FVG footprint rotated up to [4374.43-4378.17]. Honored the pre-committed invalidation (close above CE = protect) and exited at 4364.23 before the wider SL. **LESSON: a reproduce is not guaranteed; 4TF alone does NOT override a broken structure — a failed CE rejection = thesis dead. Protect at the CE failure, not the wider SL.** `RIDE_TO_EXHAUSTION_1LOT_FAILED_CE_REJECTION` recorded. |

---

## ✅ VALIDATED LESSON (from the +$868 win — the correction this strategy formalizes)

1. **1.0 lot at the RIGHT entry beats 0.01 riding-and-holding.** The probe (`532804486`) was cut for -$4.99
   because the fill (directional delta confirmation) never materialized. The **1.0 lot (`532820222`) was entered
   at the confirmed structural trigger** (FVG rejection + 4TF resumption) and rode +$1056 → banked +$868. Do not
   park a small probe hoping it "runs"; wait for the right entry and go 1.0.
2. **Do NOT over-rely on the 10-bar delta as an entry gate.** Per user directive, a positive short-term delta
   during a bounce should NOT alone reject a trade when 4TF alignment, structure (FVG rejection), and location
   all favor the ride. The structure + HTF alignment are the primary drivers; delta was one voice, not the veto.
   (This corrects my earlier over-gating that skipped valid trend entries.)
3. **The non-delta exhaustion exit works: velocity collapse into a fresh structural FVG.** The +$868 was banked
   by trailing on tick-velocity collapse (258→9 t/m into the M15 Bull FVG) — the rider need not and should not
   rely on delta flip to exit. Use velocity + structure + order-book as independent exit signals.
4. **Bank on exhaustion, don't scalp early, don't give it all back.** Peak was +$1056; the trail captured $868 —
   protecting ~10 pts that a loose/no-trail hold would have surrendered into the reversal zone.

---

*Reference: `logs/pattern_reality_check.md`, `logs/unified_learning_memory.json`,
`logs/top4_reproducible_patterns.json`, `logs/full_desk_dossier.md`. Non-controlling; `OPENCODE_MANDATES.md`
remains canonical.*
