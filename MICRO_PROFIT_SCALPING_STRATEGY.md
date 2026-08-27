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

### 2. DIRECTIONAL SIGNAL: ACCUMULATION vs DISTRIBUTION
**This is the CORE of the system. The spread-velocity combination tells you WHAT institutions are doing.**

| Velocity | Spread | Signal | Direction | Action |
|---|---|---|---|---|
| >100 t/m | ≤45 | ACCUMULATION | **BUY** | Institutions inviting retail — enter long |
| >100 t/m | 46-55 | DISTRIBUTION | **SELL** | Institutions selling without retail — enter short |
| >100 t/m | >55 | NO-GO | NONE | Too wide, no edge |
| <100 t/m | Any | NEUTRAL | NONE | Wait for institutional activity |

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
- **Strict SL Safety Latch**: SL is hard-capped at **-$5.00 USD**.
- **Micro Holding Time**: 1 to 3 minutes horizon.
- **Breakeven**: Move SL to breakeven after +$5.00 (1R) if institutional flow remains confirmed.
- **Trail Optional**: If price moves 2x TP distance, trail SL to +$10 lock.

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
