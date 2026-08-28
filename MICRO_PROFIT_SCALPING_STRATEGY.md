# MANDATORY EXECUTIVE STRATEGY: CONFIRMED-SWEEP HOLD-TO-TIP

> **This IS the strategy** — replaces the old $15-cap / $5-SL / 1-3-min micro-profit framework.
> The winning trade (XAUUSD BUY @ 4582.19 → ~4611 tip) validated the model: it did NOT cap at a fixed
> profit and did NOT grab +$5 breakeven — it LET a confirmed institutional expansion run to the
> supply/buy-stop-magnet tip and banked a large result. **There is no fixed dollar target.** The profit is
> whatever the market delivers when you ride confirmed institutional flow to the magnet and exit on
> exhaustion. The edge is **selectivity + riding the confirmation to the tip**, not trading frequency
> and not a forced dollar number.

## 🎯 CORE OBJECTIVE
Execute **directional institutional-flow trades**: **BUY when institutions accumulate at a REJECTED liquidity sweep at a structural Demand floor; HOLD through the confirmed expansion to the Supply/magnet tip; exit on exhaustion; then HOLD FLAT.** Volume 0.10 lots. Let the move **breathe and run** — do not cap it early, and do not force a specific target.

---

## ⚡ ENTRY — CONFIRMED DEEP-SWEEP REVERSAL (ALL 5 required)

| # | Confirmation | Requirement |
|---|---|---|
| 1 | **STRUCTURAL ZONE** | Entry at the Demand floor (NOT mid-range). A deep liquidity sweep (ASIAN_LOW / sell-stop grab) must be **in progress AT the zone**. |
| 2 | **SWEEP REJECTION** | The sweep is **REJECTED** — CHoCH + strong displacement candle confirms buyers absorbed the stops. NOT merely touched, NOT still flushing. |
| 3 | **VELOCITY (PRIMARY)** | **>100 t/m HIGH_INSTITUTIONAL_BURST** and **SUSTAINED** (not a 1-cycle blip). |
| 4 | **MOMENTUM (CONFIRMING)** | RSI **rising** + MACD hist **expanding** through the move. Momentum must be **CONFIRMING, not fading**. |
| 5 | **FUNDAMENTALS** | COT STRONG + Macro FAVORABLE (analyst desk synthesis, zero veto patterns). |

**Winning reference (process, not target):** Demand floor **4574.67–4575.02** (Asian-low sweep) → BUY 4582.19. Velocity 200–261 t/m; RSI 49→54; MACD hist **+15→+27 rising**; fundamentals COT 82.4% + Macro FAVORABLE. Held to the supply/buy-stop tip **4611–4612 (POC 4609.75)**. Result: large win. **The +$ figure was an outcome of the process — it is not the goal.**

**Entry verification (mandatory, from live deep book):**
- Delta **>0** (positive order flow / accumulation) ✓
- Spread **≤45 NORMAL** ✓
- Not at session high / not entering into the supply zone ✓
- Price **≤$30 from VWAP** (near equilibrium / below VWAP) ✓
- 4TF at least BULLISH_LEANING (conviction booster, not hard gate)

---

## 🧭 MANAGEMENT — HOLD TO THE TIP, LET IT BREATHE

- **HOLD through the expansion to the Supply / buy-stop-magnet tip.** **Do NOT cap at a fixed dollar amount. Do NOT grab +$5 breakeven while momentum is still confirming.** Do NOT cut a winning trade too early just because it has a little profit on the board — give it room to breathe and run (the thesis may reverse, go positive, and then keep expanding).
- **Check for decay/fatigue every cycle.** The ONLY exit triggers:
  - **Exhaustion signature** — velocity collapse AND/OR a complex-wide BULL_TRAP / ASIAN_HIGH_SWEPT flag AT the magnet.
  - Confirmed structural rejection at the supply tip.
- **DISTINGUISH CONFIRMING vs FADING:**
  - **Confirming** (RSI/MACD/velocity all RISING) → HOLD. Let institutions drive it.
  - **Fading** (MACD histogram DECLINING, RSI rolling, velocity dropping) → protection mode: bank the profit that exists rather than ride a fade.
- Engines always on for the peak: **frequently analyze decays/symptoms.** Get the early signal and bank at max — do not let a trade decline from its top; but also do not force an arbitrary top.

---

## 🔒 EXIT & POST-EXIT DISCIPLINE (mandatory)

- **Exit** on the exhaustion signature at the magnet (velocity collapse + trap flag). Capture the tip.
- **After harvesting: STAY FLAT.** Do **NOT** re-chase the just-harvested magnet. Do **NOT** counter-short on a BULL_TRAP/ASIAN_HIGH_SWEPT flag alone (needs a confirmed delta/BOS roll, not just a flag).
- **Re-entry ONLY** on the NEXT **rejected deep sweep at a FRESH Demand zone** with the full confirmation stack. Do not round-trip the same zone repeatedly.

---

## 🚫 RETRAP / NO-TRADE RULES (the leak sources — reject these)

- **NEVER enter mid-range on velocity alone.** Velocity says institutions are ACTIVE, not which way. Velocity without a Demand-floor / zone touch = zero execution (the -$94 / -$50 / -$42 bleed source).
- **NEVER buy a sweep still flushing** (no CHoCH/displacement rejection yet). Wait for absorption.
- **NEVER chase long into supply / a just-harvested magnet.**
- **NEVER short a BULL_TRAP flag without a confirmed downside roll.**
- **NEVER treat a single-cycle (3-min) snapshot as confirmation** — trail 2+ cycles (**single-cycle = exploratory; two-cycle trend = actionable**).
- **NEVER enter on a FADING MACD** at mid-range — the recurring fade-velocity trap.
- **NEVER set SL arbitrarily wide.** Verify point value / contract multiplier from the live deep book BEFORE entry. SL sized to the structural zone; TP is the supply/magnet tip (dollar value = whatever the run gives).
- **NEVER trust delta divergence alone** — one confirmation in the stack, not a standalone signal.

---

## 📊 WINNING SETUP REFERENCE
**Setup:** Buy the rejected Asian-low/sell-stop sweep at the Demand floor → hold the confirming expansion → exit at the supply/buy-stop magnet on velocity exhaustion → stay flat. Validated on a large win (count 1/5 → binding at 5, tracking as `CONFIRMED_SWEEP_REVERSAL_HOLD_TO_TIP`).
**Anti-pattern (avoid):** aggressive mid-range velocity entries without zone rejection → -$94 / -$50 / -$42.

---

## 🧠 MANDATORY SELF-STUDY & LESSON INTEGRATION
- Reference **[`logs/trade_journal_memory.md`](file:///C:/Trading/Alpha/logs/trade_journal_memory.md)** before executing.
- Reference **[`logs/institutional_deep_book.md`](file:///C:/Trading/Alpha/logs/institutional_deep_book.md)** for Delta, VWAP, CHoCH, Absorption, Asian Range, POC/liquidity magnets.
- Reference **`logs/opencode_rule.md` §0** for the codified Hold-to-Tip rule.
- Avoid past mistakes in `LESSONS_LEARNED_BUCKET`; repeat the confirmed-sweep hold-to-tip setup.

---

## ✅ INSTITUTIONAL DATA SUITE (LIVE — for the confirmation stack)
1. **Volume Delta / CVD** — buyer vs seller pressure (gate confirmation)
2. **Institutional VWAP & ±1σ/±2σ** — mean-reversion guard
3. **CHoCH & Structural Displacement** — sweep-rejection confirmation
4. **Institutional Absorption** — stop-absorption detection
5. **Asian Session Range & Sweep** — liquidity-sweep context
6. **Volume Profile (POC/VAH/VAL)** — value-area anchors
7. **Retail Stop Clusters & Liquidity Magnets** — the buy-stop/sell-stop pool = the TIP target
8. **FuturesBench CFTC COT** — institutional accumulation
9. **Macro Yields + DIX/GEX** — macro environment
10. **Dynamic Zone Proximity TP** — scaled to nearest magnet
11. **Granular 4-TF Breakdown** — confluence
12. **Layer Conflict Resolution** — order flow / price action overrides macro for these moves

---
*All institutional metrics updated continuously on every background scan cycle. Strategy = Selectivity + Ride confirmed flow to the tip + Stay flat after. There is NO fixed dollar target — let the market deliver.*
