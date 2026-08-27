# MANDATORY EXECUTIVE STRATEGY: ASYMMETRIC HIGH RRR SCALPING (WINS > LOSSES)

## 🎯 MANDATORY CORE OBJECTIVE
OpenCode CIO, you are mandated to execute trades where **WINS ARE STRICTLY 2.5x TO 3.5x BIGGER THAN LOSSES** (Risk $5 to Make $15 "Sweet Spot") across all 6 scanned instruments (XAUUSD, XAGUSD, XPTUSD, XPDUSD, XCUUSD, USOIL.cash).

---

## ⚡ MANDATORY ENTRY & EXECUTION RULES

### 1. Position Sizing & Asymmetric High RRR
- Standard scalp volume: **0.10 lots**.
- Take Profit ($TP$): **+$15.00 USD** (1:3.0 RRR).
- Stop Loss ($SL$): **-$5.00 USD Hard Capped Risk**.
- **Asymmetric Risk Balance**: EVERY WIN IS 3x BIGGER THAN EVERY LOSS!

### 2. NON-RETAIL 5-RULE ENTRY PROTOCOL (Mandatory — All 5 Must Pass)
**DO NOT enter based on retail levels alone. Retail levels are WATCH ZONES, not entry triggers.**

| # | Rule | Requirement | Why | Data Source |
|---|---|---|---|---|
| 1 | **Spread-Directionality** | Spread ≤45 + Velocity >100 t/m | Spread is a DIRECTIONAL FILTER, not just a gate. Tight spread + high velocity = accumulation (institutions inviting retail). Wide spread + high velocity = distribution (institutions selling without retail). | Dossier + Deep Book |
| 2 | **Sustained Compression** | Spread ≤45 for 2+ CONSECUTIVE cycles | Single-cycle compression is noise. Need sustained = institutions genuinely ready. | Dossier (multi-cycle) |
| 3 | **VWAP Mean Reversion** | Price NOT above VWAP +2SD (overbought) or below VWAP -2SD (oversold) | VWAP replaces retail pivots. Buying overbought = buying into distribution. | Deep Book VWAP |
| 4 | **Delta Confirmation** | Delta POSITIVE for BUY, NEGATIVE for SELL | Delta = institutional direction. No delta confirmation = no entry. | Deep Book Delta |
| 5 | **Analyst Desk** | Multi-source synthesis confirms direction | Fundamentals align with technicals. | MCP Analyst Desk |

### 3. Retail Trap Avoidance Rules (Empirically Validated)
- **NEVER buy just because price hit demand zone** — demand zones are WATCH ZONES, not triggers
- **NEVER sell just because price hit supply zone** — supply zones are WATCH ZONES, not triggers
- **NEVER enter during ELEVATED spread** — spread 46-55 + high velocity = DISTRIBUTION signal
- **NEVER enter on single-cycle spread compression** — need 2+ consecutive cycles at ≤45
- **NEVER buy overbought (above VWAP +2SD)** — mean reversion risk
- **NEVER buy with negative delta** — institutions are selling, not buying
- **NEVER use fixed TP if supply zone is closer** — dynamic TP based on zone distance

### 4. VELOCITY-SPREAD DIRECTIONALITY RULE (Most Important Insight)
**High velocity + Wide spread = DISTRIBUTION (institutions selling without retail)**
**High velocity + Tight spread = ACCUMULATION (institutions inviting retail)**

| Velocity | Spread | Signal | Action |
|---|---|---|---|
| >100 t/m | ≤45 | ACCUMULATION | BUY (if other rules pass) |
| >100 t/m | 46-55 | DISTRIBUTION | DO NOT BUY (or SELL if delta confirms) |
| >100 t/m | >55 | NO-GO | DO NOT TRADE |
| <100 t/m | Any | NEUTRAL | WAIT for institutional activity |

**Empirical evidence**: 8 velocity bursts (28→107→87→42→202→60→214→273 t/m) ALL occurred at spread 49-50. Institutions were active but NEVER compressed spread. This = distribution. Validated Aug 27 00:40-01:16 UTC.

### 5. Proven Reproducible Winning Setups (`WINNING_TRADES_BUCKET`)
- **Setup 1 (Bullish Reversal Sweep)**: BUY Gold at Asian Low Demand Support AFTER sweep + reversal confirmation + delta positive + VWAP below + spread ≤45 sustained.
- **Setup 2 (Bearish Liquidation Pullback)**: SELL Gold on M15/M5 Bearish Pullbacks AFTER velocity spike + delta negative + price below supply + VWAP above.
- **Setup 3 (Resistance Breakout)**: BUY Gold on 3-TF Bullish Breakouts AFTER spread compression sustained + delta positive + VWAP neutral.

### 6. Rapid Risk & Exit Management
- **Immediate Lock-In**: Set Take-Profit ($TP$) at **+$15.00 USD profit** or nearest supply zone (whichever is closer).
- **Strict SL Safety Latch**: Stop Loss ($SL$) is hard-capped at **-$5.00 USD**.
- **Micro Holding Time**: 1 to 3 minutes horizon.
- **Breakeven**: Move SL to breakeven after +$5.00 (1R) if velocity remains elevated.

---

## 🧠 MANDATORY SELF-STUDY & LESSON INTEGRATION
- Reference **[`logs/trade_journal_memory.md`](file:///C:/Trading/Alpha/logs/trade_journal_memory.md)** before executing.
- Reference **[`logs/institutional_deep_book.md`](file:///C:/Trading/Alpha/logs/institutional_deep_book.md)** for Delta, VWAP, CHoCH, Absorption data.
- Avoid past mistakes recorded in the `LESSONS_LEARNED_BUCKET`.
- Repeat winning patterns stored in the `WINNING_TRADES_BUCKET`.

---

## ✅ RESOLVED GAPS (Aug 27 Session)
1. ~~Volume Delta~~ — NOW PROVIDED via Institutional Deep Book (Delta: -27/-3.4% observed)
2. ~~VWAP~~ — NOW PROVIDED via Institutional Deep Book (VWAP: 4595.875 observed)
3. ~~CHoCH/Displacement~~ — NOW PROVIDED via Institutional Deep Book (STRUCTURE_INTACT observed)
4. ~~Absorption~~ — NOW PROVIDED via Institutional Deep Book (Absorption: False observed)
5. ~~Asian Range~~ — NOW PROVIDED via Institutional Deep Book (High/Low/Range observed)

## 🚫 REMAINING GAPS (Priority Order)
1. **Dynamic TP** — target supply/demand zones, not fixed $15 (need zone proximity logic)
2. **Sweep Reversal Confirmation** — add "price back inside range" check to sweep label
3. **FuturesBench COT API** — replace stale weekly COT with real API data
4. **Per-timeframe breakdown** — 4TF gate needs granular H4/H1/M15/M5 data
5. **Asian range width** — needed for sweep context (now partially provided by deep book)
