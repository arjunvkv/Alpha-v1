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

### 2. NON-RETAIL ENTRY CRITERIA (Mandatory — All 5 Must Pass)
**DO NOT enter based on retail levels alone. Retail levels are WATCH ZONES, not entry triggers.**

| # | Filter | Requirement | Why |
|---|---|---|---|
| 1 | **Spread** | ≤45 pts (NORMAL) | Institutions are ready for business |
| 2 | **Velocity** | Spike from baseline | Institutions are active |
| 3 | **Price Confirmation** | Holds above demand zone (BUY) or below supply zone (SELL) | Institutions are defending the level |
| 4 | **Sweep + Reversal** | If sweep occurred, price must return inside range | Institutions trapped retail, now reversing |
| 5 | **Analyst Desk** | Multi-source synthesis confirms direction | Fundamentals align |

### 3. Retail Trap Avoidance Rules
- **NEVER buy just because price hit demand zone** — wait for velocity spike + price holding above zone
- **NEVER sell just because price hit supply zone** — wait for velocity spike + price holding below zone
- **NEVER enter during ELEVATED spread** — institutions are wide, they don't want retail entering
- **NEVER enter on sweep alone** — wait for reversal confirmation (price back inside range)
- **NEVER use fixed TP if supply zone is closer** — dynamic TP based on zone distance

### 4. Proven Reproducible Winning Setups (`WINNING_TRADES_BUCKET`)
- **Setup 1 (Bullish Reversal Sweep)**: BUY Gold at Asian Low Demand Support AFTER sweep + reversal confirmation, targeting next supply zone.
- **Setup 2 (Bearish Liquidation Pullback)**: SELL Gold on M15/M5 Bearish Pullbacks AFTER velocity spike + price holding below supply.
- **Setup 3 (Resistance Breakout)**: BUY Gold on 3-TF Bullish Breakouts above M5 Resistance AFTER spread compression + volume confirmation.

### 5. Rapid Risk & Exit Management
- **Immediate Lock-In**: Set Take-Profit ($TP$) at **+$15.00 USD profit** or nearest supply zone (whichever is closer).
- **Strict SL Safety Latch**: Stop Loss ($SL$) is hard-capped at **-$5.00 USD**.
- **Micro Holding Time**: 1 to 3 minutes horizon.
- **Breakeven**: Move SL to breakeven after +$5.00 (1R) if velocity remains elevated.

---

## 🧠 MANDATORY SELF-STUDY & LESSON INTEGRATION
- Reference **[`logs/trade_journal_memory.md`](file:///C:/Trading/Alpha/logs/trade_journal_memory.md)** before executing.
- Avoid past mistakes recorded in the `LESSONS_LEARNED_BUCKET`.
- Repeat winning patterns stored in the `WINNING_TRADES_BUCKET`.

---

## 🚫 MANDATORY GAPS TO FILL (Priority Order)
1. **Volume Delta** — compute from MT5 ticks to know IF institutions are buying or selling
2. **VWAP** — replace retail pivot points with institutional benchmark
3. **Dynamic TP** — target supply/demand zones, not fixed $15
4. **Sweep Reversal Confirmation** — add "price back inside range" check to sweep label
5. **FuturesBench COT API** — replace stale weekly COT with real API data
