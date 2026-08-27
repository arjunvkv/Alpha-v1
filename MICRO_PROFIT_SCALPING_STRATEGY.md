# MANDATORY EXECUTIVE STRATEGY: BIDIRECTIONAL INSTITUTIONAL SCALPING

## 🎯 MANDATORY CORE OBJECTIVE
OpenCode CIO, you are mandated to execute trades in BOTH DIRECTIONS based on institutional flow. **BUY when institutions are accumulating. SELL when institutions are distributing.** Risk $5 / Make $15 "Sweet Spot" (1:3.0 RRR). 0.10 lots.

---

## ⚡ MANDATORY ENTRY & EXECUTION RULES

### 1. Position Sizing & Asymmetric RRR
- Standard scalp volume: **0.10 lots** (XAUUSD). Adjust for other instruments per contract specs.
- Take Profit: **+$15.00 USD** (or nearest zone, whichever is closer).
- Stop Loss: **-$5.00 USD Hard Capped**.
- **RRR**: EVERY WIN IS 3x BIGGER THAN EVERY LOSS.

### 2. DIRECTIONAL SIGNAL: SIMPLIFIED 5-GATE ENTRY (Corrected & Expanded Aug 27)
**VELOCITY is the PRIMARY gate. Spread is a PRECONDITION. Delta is CONFIRMATION. Price location prevents traps. Auxiliary signals (Momentum expansion, Intermarket GSR regime shift) provide supplementary confirmation.**

**5 MANDATORY GATES (all must pass for entry):**
1. **VELOCITY >100 t/m** = PRIMARY GATE — institutions are active (60% of velocity >100 cycles had positive delta)
2. **SPREAD ≤50** = PRECONDITION — spread in invitation zone (≤45 = GREEN, 46-50 = BUFFER needing velocity >100 + delta >0)
3. **DELTA >0 (or <0 for shorts)** = CONFIRMATION — tells you which side institutions are on (check deep book)
4. **NOT AT SESSION EXTREME** = TRAP GUARD — never buy at session high / supply zone or sell at session low / demand zone
5. **NOT OVERBOUGHT/OVERSOLD vs VWAP** = MEAN REVERSION GUARD — price must be <$30 above/below VWAP

**AUXILIARY EXPERIMENTAL SIGNALS (Enhance conviction & trigger faster analysis when active):**
- **Momentum Expansion Breakout:** MACD histogram > +10.0, RSI(14) > 45, and velocity > 100 t/m.
- **Intermarket GSR Regime Shift:** Gold-Silver Ratio (GSR) breaking < 65.0 or > 80.0 boundaries.

**NICE TO HAVE (add conviction, do NOT block entry):**
- 4TF BULLISH_ALIGNED or BULLISH_LEANING — increases win probability
- MACD histogram positive or turning up
- COT Maximum Bullish
- CIO Analyst Desk confirms bullish synthesis

| Velocity | Spread | Action |
|---|---|---|
| >100 t/m | ≤45 (GREEN) | **FULL INVITATION** — enter if delta >0 + not at session high + not overbought |
| >100 t/m | 46-50 (BUFFER) | **CONDITIONAL** — enter if ALL 5 gates pass |
| >100 t/m | >50 (RED) | **NO BUY** — spread too wide, institutions unclear |
| <100 t/m | Any | **WAIT** — no institutional activity |

**KEY LESSON LEARNED (Aug 27):** Spread ≤47 was too restrictive — blocked valid entries at spread 49-50 that reached +$40 profit. Spread ≤50 with velocity >100 + delta >0 is sufficient. 4TF is a conviction booster, NOT a blocking gate.

### 3. BUY EXECUTION PROTOCOL (Accumulation Setups)
**Enter LONG when ALL 5 HARD GATES pass:**

| # | Gate | Requirement | Blocking? |
|---|---|---|---|
| 1 | Velocity | >100 t/m | YES |
| 2 | Spread | ≤47 pts | YES |
| 3 | Delta | >0 (positive order flow from deep book) | YES |
| 4 | Not Session High | Price not at session high or supply zone | YES |
| 5 | Not Overbought | Price < $30 above VWAP | YES |

**BUY Entry:** Market order when all 5 gates pass.
**BUY SL:** Entry Price - 5 pts (MANDATORY, calculated at entry time). Entry 4621 = SL 4616.
**BUY TP:** Nearest supply zone or +$15.00 (whichever closer).
**BUY Breakeven:** Move SL to entry after +$5.00 (1R).

### 4. SELL EXECUTION PROTOCOL (Distribution Setups) ⚠️ NEW
**Enter SHORT when ALL 5 HARD GATES pass:**

| # | Gate | Requirement | Blocking? |
|---|---|---|---|
| 1 | Velocity | >100 t/m | YES |
| 2 | Spread | ≥46 pts (wide spread + high velocity = distribution) | YES |
| 3 | Delta | <0 (negative order flow / selling pressure) | YES |
| 4 | Not Session Low | Price not at session low or demand zone | YES |
| 5 | Not Oversold | Price > $30 below VWAP | YES |

**SELL Entry:** Market order when all 5 gates pass.
**SELL SL:** Entry Price + 5 pts (MANDATORY, calculated at entry time).
**SELL TP:** Nearest demand zone or +$15.00 (whichever closer).
**SELL Breakeven:** Move SL to entry after +$5.00 (1R).

### 5. Retail Trap Avoidance Rules (Empirically Validated)
- **NEVER buy just because price hit demand zone** — demand zones are WATCH ZONES, not triggers
- **NEVER sell just because price hit supply zone** — supply zones are WATCH ZONES, not triggers
- **NEVER buy during distribution** — wide spread + high velocity + negative delta = institutions selling
- **NEVER sell during accumulation** — tight spread + high velocity + positive delta = institutions buying
- **NEVER enter on single-cycle spread compression** — need 2+ consecutive cycles
- **NEVER buy overbought (above VWAP +2SD)** — mean reversion risk
- **NEVER sell oversold (below VWAP -2SD)** — mean reversion risk
- **NEVER ignore delta** — delta is the DIRECTIONAL confirmation
- **NEVER block on single 3-min snapshot** — a single data point is EXPLORATORY, not confirmation. When delta flips negative, TRAIL the next 1-2 cycles before confirming distribution vs reversal.
- **NEVER set SL wider than 5 pts from entry** — calculated at entry time. Entry 4641 = SL 4636. Period.
- **NEVER enter at session high/supply on first delta flip** — wait 1 cycle for confirmation or pullback.
- **NEVER trust delta divergence alone** — strong delta (+103) can coexist with falling price. Delta is one of 5 rules, not a standalone signal. Institutions accumulate while price drops (absorption). The 5-rule system exists because individual signals mislead.

### 5A. THREE-MINUTE DATA LAG RULE (Critical — Live Validated)
**A single 3-min snapshot is NOT enough to confirm a pattern.** The daemon delivers data every 3 minutes. Institutions can distribute for 1-2 cycles then reverse. Single snapshots create FALSE NEGATIVES.

**When delta flips negative (Rule 4 fails):**
1. **DO NOT immediately HOLD forever.** Instead, activate DELTA TRAILING.
2. **Trail delta over next 1-2 cycles:**
   - If delta IMPROVES over 2+ consecutive cycles (e.g. -31 → -25 → -15) = distribution winding down → potential BUY entry when delta flips positive
   - If delta WORSENS over 2+ consecutive cycles (e.g. -31 → -45 → -55) = distribution continuing → confirmed DO NOT BUY
   - If delta STALLS (e.g. -31 → -25 → -25) = distribution pausing → HOLD, wait for direction
3. **Entry only when delta trail confirms REVERSAL (flips positive) AND other rules align.**
4. **Single-cycle delta flip = exploratory data. Two-cycle delta trend = actionable signal.**

### 5C. DELTA COLLAPSE EXIT RULE (Critical — Live Validated Aug 27)
**When delta drops >50% in a single cycle, EXIT immediately even if still positive.**

- Delta +79 → +29 (-63% drop) = institutional withdrawal signal
- This is an EARLY EXIT signal, not a hold signal
- By the time delta turns negative, price has already dropped 5+ pts
- **Action:** If current delta is <50% of previous cycle's delta, close position at market
- Example: Previous delta +79, current delta +29 → EXIT (63% drop)

### 5D. REENTRY COOLDOWN RULE (Critical — Live Validated Aug 27)
**Never re-enter at the same price level within 3 cycles (9 minutes) of a stop-out.**

- Re-entering immediately at the same level is a REENTRY TRAP
- Institutions may be distributing at that level — the same setup that looked perfect may collapse
- **Action:** After a stop-out, wait for ONE of:
  - Price pulls back to a NEW demand level (different from entry)
  - 2-3 consecutive cycles of confirming data at the new level
  - London/NY session opens (volume returns)

### 5B. TRAIL RECENT LOGS BEFORE ENTRY (Critical — Live Validated Aug 27)
**Don't wait for all 5 gates to align in a SINGLE future snapshot. The market picture NEVER repeats identically across cycles. The optimal entry is always in the PAST.**

When evaluating entry:
1. **Trail the last 2-3 cycles** — check if conditions WERE close to alignment at a BETTER PRICE.
2. **CRITICAL: Each cycle is unique.** The same snapshot NEVER repeats. Spread ≤45 in one cycle, velocity >100 in another, delta positive in another — these are SEPARATE events that may never align simultaneously.
3. **Entry rule: If 2 of the 3 key gates (spread ≤47, velocity >100, delta >0) passed across ANY of the last 2-3 cycles, and price is near VWAP/PP and not at session high — that's the entry window.**
4. **Do NOT wait for all 3 gates in the same snapshot.** That will never happen. The alignment happens BETWEEN snapshots.
5. **If price has moved MORE THAN 5 pts from the best price in the trail, the window is CLOSED.** Do not enter at a worse price.
6. **The 3-min snapshot is a TRAILING indicator, not a leading one.** The optimal entry always happened 1-2 cycles ago. By the time you see perfect conditions, the price has moved.

### 6. Proven Reproducible Winning Setups (`WINNING_TRADES_BUCKET`)

**BUY SETUPS:**
- **Setup B1 (Accumulation Reversal)**: BUY at demand zone AFTER spread ≤45 sustained + delta positive + price below VWAP + velocity spike. TP: VWAP upper band or supply zone.
- **Setup B2 (Sweep Reversal BUY)**: BUY after Asian Low sweep + reversal confirmation + delta positive + spread ≤45. TP: Asian High or supply zone.

**SELL SETUPS:**
- **Setup S1 (Distribution Reversal)**: SELL at supply zone AFTER spread 46-55 + velocity >100 + delta negative + price above VWAP +2SD. TP: VWAP lower band or demand zone.
- **Setup S2 (Overbought Fade)**: SELL when price is above VWAP +2SD + delta negative + velocity elevated + spread 46-55. TP: VWAP mean (4596 observed).
- **Setup S3 (Asian High Rejection)**: SELL after price breaks above Asian High + immediately fails (wick rejection) + delta negative. TP: Asian Low or demand zone.

### 7. Rapid Risk & Exit Management
- **Immediate Lock-In**: Set TP at **+$15.00 USD** or nearest zone (whichever is closer).
- **Strict SL Safety Latch**: SL is hard-capped at **-$5.00 USD** (5 pts for 0.10 lots).
- **SL MUST BE CALCULATED AT ENTRY**: When placing the trade, SL = Entry Price - 5 pts (BUY) or Entry Price + 5 pts (SELL). NEVER set SL arbitrarily wide. If the entry is at 4641, SL = 4636. Period.
- **Micro Holding Time**: 1 to 3 minutes horizon.
- **Breakeven**: Move SL to breakeven after +$5.00 (1R) if institutional flow remains confirmed.
- **Trail Optional**: If price moves 2x TP distance, trail SL to +$10 lock.

### 7A. ENTRY TIMING AFTER DELTA FLIP (Critical — Live Validated Aug 27)
**Do NOT enter immediately on first delta flip signal.** The delta flip from negative to positive is the CONFIRMATION, but entry timing matters:
1. **When delta flips positive (e.g. -31 → +13):** This is the SIGNAL to prepare, not the entry trigger.
2. **Wait 1 cycle** — let delta confirm it's not a single-cycle bounce. If delta continues positive next cycle (+13 → +27), ENTER with:
   - SL = Entry Price - 5 pts (hard cap)
   - TP = Nearest supply zone or +$15 (whichever closer)
3. **If first flip is weak (< +10):** Wait for 2nd cycle confirmation. Weak flips can reverse.
4. **If first flip is strong (> +20):** Can enter immediately with tighter SL.
5. **NEVER enter at session highs** — if price is at supply zone + delta just flipped, wait for pullback to VWAP or PP for better entry.

---

## 🧠 MANDATORY SELF-STUDY & LESSON INTEGRATION
- Reference **[`logs/trade_journal_memory.md`](file:///C:/Trading/Alpha/logs/trade_journal_memory.md)** before executing.
- Reference **[`logs/institutional_deep_book.md`](file:///C:/Trading/Alpha/logs/institutional_deep_book.md)** for Delta, VWAP, CHoCH, Absorption, Asian Range data.
- Avoid past mistakes recorded in the `LESSONS_LEARNED_BUCKET`.
- Repeat winning patterns stored in the `WINNING_TRADES_BUCKET`.

---

## ✅ 100% RESOLVED GAPS (Complete Institutional Suite)
1. **Volume Delta & Cumulative Volume Delta (CVD)** — Live MT5 tick stream buyer vs seller pressure (`institutional_deep_book.md`)
2. **Institutional VWAP & ±1σ, ±2σ Bands** — Live typical price × volume distribution (`institutional_deep_book.md`)
3. **CHoCH & Structural Displacement** — Live fractal swing breaks with body displacement filter (`institutional_deep_book.md`)
4. **Institutional Absorption Filter** — High delta with compressed price action detection (`institutional_deep_book.md`)
5. **Asian Session Range & Sweep Reversal** — Exact 00:00-08:00 UTC High/Low and range re-entry confirmation (`institutional_deep_book.md`)
6. **Intraday Volume Profile (POC / VAH 70% / VAL 70%)** — 70% value area distribution (`institutional_deep_book.md`)
7. **Retail Stop Clusters & Liquidity Magnets** — Buy stop / sell stop liquidity pools (`institutional_deep_book.md`)
8. **FuturesBench CFTC COT API** — Official live CFTC open interest, net positions & 26w/52w COT Index (`institutional_deep_book.md`)
9. **Macro Treasury Yields & Squeezemetrics DIX/GEX** — 10Y/2Y curve spread, DXY, VIX, Dark Index & Gamma Exposure (`institutional_deep_book.md`)
10. **Dynamic Zone Proximity TP** — Bounded TP ($15-$40) scaled to nearest supply/demand zone distance (`institutional_deep_book.md`)
11. **Granular Per-Timeframe Breakdown** — H4, H1, M15, M5 specific EMAs, RSI, and Trend Biases (`institutional_deep_book.md`)
12. **Layer Conflict Resolution Rule** — For 1-3m micro-scalps, **Order Flow CVD & Intraday Price Action ALWAYS OVERRIDES Macro Fundamentals**. If Spread is 46-55, Velocity > 100 t/m, Delta is Negative, and Price > VWAP +2SD, execute SELL regardless of macro desk bullish lean.

---
*All institutional metrics updated continuously on every background scan cycle.*
