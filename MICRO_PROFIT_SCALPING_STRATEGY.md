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

### 2. DIRECTIONAL SIGNAL: ACCUMULATION vs DISTRIBUTION (Corrected Hierarchy)
**VELOCITY is the PRIMARY gate. Spread is a PRECONDITION. Delta is the CONFIRMATION.**

**Gate Hierarchy (from strongest to weakest signal):**
1. **VELOCITY >100 t/m** = PRIMARY GATE — institutions are active (60% of velocity >100 cycles had positive delta)
2. **SPREAD ≤47** = PRECONDITION — spread in invitation zone (≤45 = strong, 46-47 = buffer requiring extra confirmation)
3. **DELTA >0** = CONFIRMATION — tells you which side institutions are on
4. **4TF ALIGNED** = STRUCTURAL — tells you if trend supports the trade
5. **COT BULLISH** = BACKGROUND — institutional positioning supports direction

| Velocity | Spread | Signal | Direction | Action |
|---|---|---|---|---|
| >100 t/m | ≤45 (GREEN) | ACCUMULATION | **BUY** | Full invitation — enter long if delta >0 |
| >100 t/m | 46-47 (BUFFER) | BORDERLINE | **CONDITIONAL BUY** | Enter ONLY if delta >0 AND 4TF aligned |
| >100 t/m | ≥48 (RED) | DISTRIBUTION | **SELL** or NONE | Institutions selling — do NOT buy |
| <100 t/m | Any | NEUTRAL | NONE | Wait for institutional activity |

**SPREAD BUFFER RULE:** Spread ≤47 is the effective gate. The 2-pt buffer (46-47) captures borderline cycles where institutions are compressing but haven't fully committed. These borderline cycles require STRONGER confirmation (velocity >100 + delta >0 + 4TF aligned ALL simultaneously).

### 3. BUY EXECUTION PROTOCOL (Accumulation Setups)
**Enter LONG ONLY when ALL 5 rules confirm accumulation:**

| # | Rule | Requirement |
|---|---|---|
| 1 | Spread-Directionality | Spread ≤45 + Velocity >100 t/m |
| 2 | Sustained Compression | Spread ≤45 for 2+ consecutive cycles |
| 3 | VWAP Mean Reversion | Price BELOW or AT VWAP (not overbought above +2SD) |
| 4 | Delta Confirmation | Delta POSITIVE (accumulation) |
| 5 | Analyst Desk | Multi-source synthesis confirms bullish direction |

**BUY Entry:** Market order when all 5 pass.
**BUY SL:** Below demand zone or Asian Low (whichever is closer), capped at -$5.00.
**BUY TP:** Nearest supply zone or VWAP upper band, targeted at +$15.00.
**BUY Breakeven:** Move SL to entry after +$5.00 (1R).

### 4. SELL EXECUTION PROTOCOL (Distribution Setups) ⚠️ NEW
**Enter SHORT ONLY when ALL 5 rules confirm distribution:**

| # | Rule | Requirement |
|---|---|---|
| 1 | Spread-Directionality | Spread 46-55 + Velocity >100 t/m (wide spread + high velocity = distribution) |
| 2 | Sustained Distribution | High velocity + wide spread for 2+ consecutive cycles |
| 3 | VWAP Mean Reversion | Price ABOVE VWAP +2SD (overbought, mean reversion imminent) |
| 4 | Delta Confirmation | Delta NEGATIVE (distribution / selling pressure) |
| 5 | Analyst Desk | Multi-source synthesis confirms bearish or neutral direction (no bullish veto) |

**SELL Entry:** Market order when all 5 pass.
**SELL SL:** Above supply zone or Asian High (whichever is closer), capped at -$5.00.
**SELL TP:** Nearest demand zone or VWAP lower band, targeted at +$15.00.
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

### 5B. TRAIL RECENT LOGS BEFORE ENTRY (Critical — Live Validated Aug 27)
**Don't wait for all 5 rules to align in a SINGLE future snapshot. The market picture NEVER repeats identically across cycles. The optimal entry is always in the PAST.**

When evaluating entry:
1. **Trail the last 2-3 cycles** — check if conditions WERE close to alignment at a BETTER PRICE.
2. **CRITICAL: Each cycle is unique.** The same snapshot NEVER repeats. Spread ≤45 in one cycle, velocity >100 in another, delta positive in another — these are SEPARATE events that may never align simultaneously.
3. **Entry rule: If 2 of the 3 key gates (spread ≤45, velocity >100, delta >0) passed across ANY of the last 2-3 cycles, and price is near VWAP/PP — that's the entry window.**
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
