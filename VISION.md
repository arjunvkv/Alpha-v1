# ALPHA — Vision & Design Document

> **Read this before writing any code. If your code doesn't serve this vision, delete it.**

---

## The Idea

Alpha is an autonomous AI trading system. Not a dashboard. Not a signal service. A **trader** — one that perceives the market, judges opportunities, acts on conviction, and learns from every outcome.

The human is the **architect and approver**, not the operator. The system proposes trades, executes within risk limits, manages positions, and improves over time. The human reviews decisions, adjusts risk parameters, and steers the overall direction.

---

## What We're Building

```
Alpha = Granger (intelligence) + Brain (AI judgment) + Daemon (body) + MT5 (execution) + Memory (learning)
```

### The Body

| Part | Name | Role | Status |
|------|------|------|--------|
| Brain | AI (me, in Alethia v4 session) | Analysis, decisions, judgment | ✅ I am the brain |
| Body | `daemon/daemon.py` | Monitor, trigger, execute — the brain's body | ✅ Built & tested |
| Eyes | `granger/` | 7-layer market intelligence | ✅ Production ready |
| Lungs | `risk/` | Portfolio risk, position sizing, survival | BUILDING |
| Hands | `execution/` | MT5 bridge - enters/exits market | EXTRACT FROM DAEMON |
| Skeleton | `memory/` | Decisions, lessons, knowledge, journal | BUILDING |

### How the Brain Wakes Up

The daemon (body) runs continuously. When something matters, it sends a message into THIS session via `opencode run "<prompt>" -s ses_feee1399cffeIkkxcPfrsT1Uhq`. The AI wakes up with full context, analyzes, decides, and writes the action. The daemon executes it.

```
Daemon watches → Trigger detected → Sends message to this session
→ I wake up (full 3-day context preserved) → Analyze → Decide → Write action.json
→ Daemon executes via MT5 → Windows toast notification to user
```

### The Decision Cycle

```
PERCEIVE -> JUDGE -> ACT -> LEARN -> PERCEIVE -> ...
```

1. **PERCEIVE**: Monitor watches. Granger sees daily picture. Regime tracks real-time shifts.
2. **JUDGE**: Brain analyzes. Weighs evidence. Scores conviction. Checks mistakes.
3. **ACT**: Brain executes via MT5. Manages positions. Scales in/out.
4. **LEARN**: Every trade goes into a bucket. Patterns extracted. Mistakes recorded. Rules added.

---

## Core Principles

### 1. Event-Driven, Not Always-On

The brain (AI) does NOT run 24/7. The daemon (body) runs — it is lightweight, checks every 60 seconds, and fires triggers when something matters. The daemon sends a message into the AI session via `opencode run -s <session_id>`. The AI wakes up with full context, does its work, and goes back to sleep.

```
Sleep -> Daemon detects trigger -> Sends message to AI session
-> AI wakes (full context) -> Analyze -> Decide -> Write action
-> Daemon executes -> AI sleeps
```

This is efficient. The AI burns compute only when there is work to do. Verified working 2026-08-21.

### 2. I Am the Trader, Not a Dashboard

The system does not display charts and hope the human figures it out. I make decisions:

> "LONG Platinum at $1,852. Entry $1,850. Stop $1,835. Target: $1,920. Size: 0.2 lots (1.8% risk). Conviction: 8.5/10. Approve?"

The human receives a Windows toast notification showing what's happening. No intervention needed — the system is fully autonomous within risk limits.

### 3. Risk First, Always

Before ANY trade:
- Portfolio heat <= 6% total
- Single position <= 2% risk
- Correlation check (no two positions > 80% correlated at full size)
- Drawdown circuit breaker at -10% monthly
- No entries during high-impact news (NFP, FOMC, CPI within 60min)

If risk limits say no, the answer is no. Conviction does not override risk.

### 4. Learning Is Not Optional

Every trade produces a decision record. Every closed trade produces a review. Every review extracts at least one lesson. Mistakes go into `mistakes.json` and are NEVER repeated.

The system gets smarter with every trade. Not through model retraining - through **categorized experience**.

### 5. No Retail Indicators

The edge is NOT:
- EMA crossovers
- RSI divergences
- Pivot points
- VWAP bounces
- Fibonacci retracements
- MACD histogram

The edge IS:
- Granger 7-layer conviction scoring
- COT positioning extremes
- Options flow (P/C ratio, max pain)
- Macro regime classification
- Cross-asset correlation
- Real-time L2 order flow
- Institutional-grade risk management
- Learning from categorized experience

### 6. Simplicity Over Complexity

Every component must justify its existence. If a feature does not directly contribute to PERCEIVE -> JUDGE -> ACT -> LEARN, it does not belong.

No ML for the sake of ML. No dashboards for the sake of dashboards. No APIs for the sake of APIs. Only what is needed to trade well.

---

## Architecture

### Directory Structure

```
C:\Trading\Alpha\
├── daemon/                   <- The body (always running, never decides)
│   ├── daemon.py             <- ✅ Main daemon: monitor, trigger, execute
│   ├── WAKEUP_PROMPTS.md     <- ✅ 6 prompt templates for AI wake-up
│   └── TRIGGER_SCHEMA.md     <- ✅ JSON schema for triggers
│
├── brain/                    <- The trader (analysis + decisions)
│   ├── __init__.py
│   ├── analyzer.py           <- Pulls Granger, checks context, scores opportunities
│   ├── decision.py           <- Makes trade decisions, checks rules
│   ├── executor.py           <- Sends orders via MT5 bridge
│   ├── manager.py            <- Manages open positions (scale, trail, exit)
│   └── learner.py            <- Reviews closed trades, extracts lessons
│
├── granger/                  <- The eyes (7-layer market intelligence)
│   └── [symlink/copy of existing Granger code]
│
├── risk/                     <- The lungs (survival)
│   ├── __init__.py
│   ├── portfolio.py          <- Total heat, correlation, drawdown tracking
│   ├── sizing.py             <- Position sizing: conviction x ATR x account
│   └── limits.py             <- Hard limits, circuit breakers
│
├── execution/                <- The hands (MT5 bridge)
│   ├── __init__.py
│   ├── mt5_bridge.py         <- Extracted from Aletheia, cleaned up
│   └── order_manager.py      <- Order types, slippage, fill tracking
│
├── memory/                   <- The skeleton (learning)
│   ├── __init__.py
│   ├── decisions.json        <- Every decision, categorized
│   ├── knowledge.json        <- Learned patterns, what works
│   ├── mistakes.json         <- Rules extracted from errors (NEVER repeat)
│   ├── zones/                <- Active watch zones
│   └── journal/              <- Daily trade journals
│
├── data/                     <- Live data cache
│   ├── live/                 <- Real-time tick/bar cache
│   └── snapshots/            <- Daily Granger snapshots
│
├── logs/                     <- System logs
├── tests/                    <- Tests
├── config.py                 <- Single source of truth
├── main.py                   <- Entry point: start monitor
└── VISION.md                 <- This file
```

### Data Flow (Verified)

```
+-------------------------------------------------------------------+
|                    DAEMON (daemon/daemon.py)                       |
|                    Always running. Never decides.                   |
|                                                                    |
|  Fast (5s):  Check positions (trailing, time stops)               |
|  Medium (60s): Check regime (DXY/VIX), check zones               |
|  Slow (5min): Full portfolio scan                                  |
|  Daily: Pull Granger + full review                                 |
|                                                                    |
|  On trigger:                                                       |
|    1. Write data/live/trigger.json (full market context)          |
|    2. Send Windows toast notification                              |
|    3. opencode run "<prompt>" -s ses_feee1399cffeIkkxcPfrsT1Uhq  |
|    4. Wait for action.json                                         |
|    5. Execute via MT5                                               |
+-------------------------------+------------------------------------+
                                | opencode run -s <session>
                                | (message arrives in AI session)
                                v
+-------------------------------------------------------------------+
|                    AI (Alethia v4 session)                         |
|                    THE BRAIN. Makes every decision.                |
|                                                                    |
|  1. READ trigger.json — understand why I was woken                |
|  2. PULL Granger if stale (>6hrs since last update)              |
|  3. CHECK regime monitor (DXY/VIX real-time)                     |
|  4. CHECK risk limits (portfolio heat, correlation, drawdown)    |
|  5. CHECK mistakes.json (any rules violated?)                     |
|  6. ANALYZE: is thesis still valid at this zone?                  |
|  7. DECIDE: enter / adjust / exit / wait                         |
|  8. SIZE: conviction x ATR x account risk                        |
|  9. WRITE action.json for daemon to execute                       |
|  10. RECORD decision in decisions.json                            |
|  11. UPDATE zones (add new zones, remove hit zones)              |
|  12. SLEEP (back to daemon)                                       |
+-------------------------------------------------------------------+
```

### The Decision Buckets

Every trade is categorized into a bucket. Over time, the brain learns which buckets work in which regimes.

| Bucket | Description | Example |
|--------|------------|---------|
| `trend_continuation` | Riding an existing trend | Long Silver in bullish metals regime |
| `mean_reversion` | Buying dips in uptrends | Long Platinum at 34% range in uptrend |
| `breakout` | Entering on level break | Long Copper above $6.80 resistance |
| `regime_shift` | Trading a regime change | Long TLT when DXY breaks above 101 |
| `contrarian` | Against crowded positioning | Short Silver when COT > 95th percentile |
| `news_reaction` | Post-news move | Long Gold after dovish FOMC |
| `pairs` | Relative value | Long Silver/Short Gold ratio trade |
| `risk_off` | Defensive | Long TLT/Short equities in fear regime |

### The Learning Loop

```
Trade closes -> Review:
  1. What bucket? -> trend_continuation
  2. What regime? -> bullish_metals
  3. What conviction? -> 8.5
  4. What was the outcome? -> +1.5R
  5. What worked? -> Zone identification was precise
  6. What didn't? -> Entry could have been 0.3% lower
  7. Rule extracted? -> "In strong trends, zones are tighter - use 0.3% not 0.5%"
```

**mistakes.json grows over time. Every entry is a lesson learned the hard way:**

```json
{
  "M-001": {
    "date": "2026-08-22",
    "mistake": "Entered copper near 52w high with COT at 85th percentile",
    "rule": "NEVER enter when both range > 85% AND COT percentile > 80",
    "severity": "high",
    "bucket": "breakout",
    "regime": "bullish_metals"
  }
}
```

---

## Instruments

### Primary (Full Granger Coverage)
- Silver (XAGUSD) - highest conviction, DXY-beta play
- Gold (XAUUSD) - safe haven, macro hedge
- Platinum (XPTUSD) - mean reversion, supply story
- Copper (XCPUSD) - industrial cycle
- Palladium (XPDUSD) - automotive demand

### Secondary (via MT5)
- Crude Oil (WTI/Brent) - geopolitical risk
- Natural Gas - seasonal plays
- Major FX (EURUSD, USDJPY, GBPUSD) - DXY proxy trades
- Indices (SPX500, NASDAQ) - risk-on/off

### Available via MT5 (FTMO)
All instruments that FTMO offers on their CFD accounts. The system adapts - if Granger has a layer for it, use full intelligence. If not, use MT5 data + basic technicals.

---

## Triggers

The monitor fires alerts on these conditions:

| Trigger | Condition | Priority |
|---------|-----------|----------|
| `zone_approach` | Price within 0.5% of active zone | HIGH |
| `zone_break` | Price breaks through active zone | CRITICAL |
| `regime_shift` | DXY moves > 0.5% in 15min | HIGH |
| `vix_spike` | VIX crosses above 18 | HIGH |
| `yield_move` | 10Y moves > 5bps in 1hr | MEDIUM |
| `news_approach` | High-impact news in 30min | HIGH |
| `position_alert` | Open position within 0.3% of stop/target | CRITICAL |
| `daily_update` | 9:00 AM - Granger daily refresh | MEDIUM |
| `risk_breach` | Portfolio heat > 5% (approaching limit) | CRITICAL |
| `drawdown_alert` | Monthly drawdown > -7% (approaching -10% limit) | CRITICAL |

---

## What Granger Provides

Granger is the intelligence engine. It does not trade. It provides:

| Layer | What It Provides | How Brain Uses It |
|-------|-----------------|-------------------|
| L1 Prices | Current prices, 52w ranges, momentum | Entry/exit levels, range context |
| L2 Positioning | COT extremes, ETF flows | Contrarian signals, crowdedness check |
| L3 Macro | Yields, FX, VIX, FOMC calendar | Regime context, risk environment |
| L4 Sentiment | News sentiment per metal | Contrarian signals, overheated readings |
| L5 Fundamentals | Supply/demand, inventory proxies | Long-term thesis validation |
| L6 Technical | RSI, MACD, SMA, BB, ATR | Entry timing, stop/target levels |
| L7 Signals | Options flow, cross-asset, macro regime, yield curve | Conviction scoring, regime filter |

Brain scoring: Each layer contributes to a 1-10 conviction score. 8+ = trade. 6-7 = watch zone. <6 = no action.

---

## Risk Management

### Hard Limits (Never Override)

| Parameter | Limit | Action on Breach |
|-----------|-------|-----------------|
| Single position risk | <= 2% of account | Block new order |
| Portfolio heat (total open risk) | <= 6% | Block new orders |
| Correlation adjustment | If two positions > 80% corr, combined risk <= 3% | Reduce size |
| Monthly drawdown | -10% | Close all positions, stop trading |
| Daily loss limit | -3% | Stop trading for the day |
| Max open positions | 5 | Block new orders |
| News blackout | 60min before/after high-impact news | Block new entries |

### Position Sizing Formula

```
size_lots = (account_balance x risk_pct x conviction_multiplier) / (stop_distance x pip_value)

Where:
  risk_pct = 2% (base) x conviction_multiplier
  conviction_multiplier:
    6.0-6.9 -> 0.5x (half size)
    7.0-7.9 -> 0.75x
    8.0-8.9 -> 1.0x (full size)
    9.0-9.5 -> 1.25x
    9.6-10  -> 1.5x (max size, only for A+ setups)
  stop_distance = entry - stop (in pips)
  pip_value = instrument-specific (XAGUSD: $1/lot/pip, XAUUSD: $100/lot/pip, etc.)
```

### Drawdown Circuit Breaker

```
Monthly PnL:
  -5%  -> WARNING: reduce position sizes by 50%
  -7%  -> CRITICAL: no new positions, manage only
  -10% -> EMERGENCY: close all, stop trading, full review required
```

---

## Regime Monitor (Real-Time)

Tracks real-time shifts that could invalidate Granger's daily thesis:

| Signal | Source | Warning Threshold | Critical Threshold |
|--------|--------|------------------|-------------------|
| DXY | MT5 EURUSD inverse | > 0.3% move in 15min | > 0.5% move in 15min |
| VIX | yfinance | > 18 | > 22 |
| 10Y Yield | yfinance | > 5bps move in 1hr | > 10bps move in 1hr |
| Gold/Silver ratio | Computed | > 2% move in 1 day | > 5% move in 1 day |
| Correlation | Rolling 20d | Correlation drops below 0.5 | Correlation goes negative |

When a WARNING fires: reduce position sizes by 50%.
When a CRITICAL fires: close positions in that direction, wait for re-analysis.

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
- Project structure
- Config system
- Decision memory (JSON read/write)
- MT5 bridge extraction from Aletheia

### Phase 2: Monitor (Week 1-2)
- Price zone watcher
- Trigger system
- Economic calendar integration
- Console alert system

### Phase 3: Brain (Week 2-3)
- Granger integration
- Opportunity analyzer
- Decision maker (with rules checking)
- Position sizer

### Phase 4: Execution (Week 3)
- MT5 order execution
- Position management (scale, trail, exit)
- Slippage tracking

### Phase 5: Risk (Week 3-4)
- Portfolio heat tracker
- Correlation adjustment
- Drawdown circuit breaker
- News blackout

### Phase 6: Learning (Week 4)
- Post-trade review
- Lesson extraction
- Mistake recording
- Bucket performance tracking

### Phase 7: Integration (Week 4-5)
- End-to-end testing
- Paper trading
- Performance review
- Go-live preparation

---

## What Success Looks Like

After 3 months of operation:
1. 50+ trades in decision memory, categorized by bucket
2. 10+ rules in mistakes.json (lessons learned)
3. Win rate > 55% across all buckets
4. Average R:R > 1.5:1
5. Maximum drawdown < -8% (staying within limits)
6. Brain can identify A+ setups without human intervention
7. Human role is: review decisions, adjust risk, steer direction

---

## Files That Reference This Vision

- `PLAN.md` - Implementation plan (must align with this vision)
- `config.py` - All settings (must reflect these principles)
- `daemon/daemon.py` - The body (must follow trigger→AI→execute pattern)
- `daemon/WAKEUP_PROMPTS.md` - AI wake-up templates (must provide full context)
- `brain/decision.py` - Must check these rules before every trade
- `memory/mistakes.json` - Must grow with every lesson
- `risk/limits.py` - Must enforce these hard limits

**If any code contradicts this vision, the vision wins. Fix the code.**
