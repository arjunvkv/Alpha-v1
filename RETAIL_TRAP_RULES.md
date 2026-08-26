# Alpha — Retail Trap Detection & High-Conviction Entry Rules
# Version: 1.0 — 2026-08-21
# Purpose: Prevent falling into retail traps. Only take institutional-grade setups.
# These rules override ALL other signals. If a trap is detected, DO NOT ENTER.

---

## CORE PRINCIPLE

**Retail traders think in "levels" and "indicators." Institutions think in "liquidity" and "positioning."**

A trade is NOT high-conviction because price is at a level and an indicator agrees.
A trade IS high-conviction when institutional flow confirms, traps are absent, and the math works.

**If you can explain the trade in one sentence to a retail trader and they'd agree — it is probably a trap.**

---

## PART 1: RETRAL TRAP CATALOG

### TRAP 1: The Resistance/Support Bounce Trap (MOST COMMON)

**Pattern:** Price approaches a "known" level (BB_Upper, SMA200, round number). Retail sees this as a natural reversal point and enters counter-trend.

**Why it fails:** Institutions KNOW retail sees these levels. They:
- Absorb retail counter-trend orders (providing liquidity for their own positions)
- Push through the level to trigger retail stops
- Reverse after retail has been flushed out — OR continue through, trapping shorts

**Example:** XAUUSD at $4603 approaching BB_Upper $4608.
- Retail thinks: "At resistance, overbought, gold extended 14.3% — SHORT it"
- Institutional reality: If accumulating, they ABSORB retail shorts here, then push through $4608

**Detection:** Price within 0.5% of a "known" level AND no institutional confirmation of reversal → TRAP ZONE.

---

### TRAP 2: The Breakout Chase Trap

**Pattern:** Price pokes above resistance. Retail sees "breakout!" and goes long immediately.

**Why it fails:** First-touch breakouts fail 60-70% of the time. Institutions:
- Push price just above the level to trigger buy stops (liquidity grab)
- Absorb retail buy orders
- Reverse and dump, trapping breakout chasers

**Valid breakout requires ALL of:**
- Daily CLOSE above the level (not just a wick/poke)
- Volume confirmation (>1.5x average for the time period)
- Retest of the broken level that holds as new support

**Detection:** Price just broke a level for the first time + no daily close confirmation + no volume spike → BREAKOUT TRAP.

---

### TRAP 3: The Indicator Confluence Trap

**Pattern:** Multiple indicators "agree" — RSI overbought, at BB_Upper, near resistance, MACD crossing down. Retail sees "triple/quadruple confirmation."

**Why it fails:** These indicators ALL measure the SAME underlying thing: "price is high." They are NOT independent signals. It's like asking 5 people looking at the same photograph if they see the same thing.

**Count unique DATA SOURCES, not indicators:**

| Signals that are ONE source (price derivatives) | Signals that are INDEPENDENT sources |
|---|---|
| RSI | COT positioning (CFTC) |
| Bollinger Bands | ETF flows (shares x NAV) |
| Stochastic | Yield curve / US10Y trend |
| MACD | DXY trend |
| Moving average crossovers | VIX regime |
| Volume (price-adjacent) | Commodity fundamentals (supply/demand) |
| Candlestick patterns | Options put/call ratio |

**Rule:** "Confluence" from 3 indicators that are all price-derived = ONE signal, not three.
Real confluence requires at least 2 independent data sources.

---

### TRAP 4: The News Spike Chase Trap

**Pattern:** News releases → price spikes in one direction → retail chases the spike.

**Why it fails:** "Buy the rumor, sell the news." Institutions accumulate BEFORE the news, then use the news spike to DISTRIBUTE (sell into retail buying).

**Detection:**
- Entering within 30 minutes of major news → TRAP
- Entering in the DIRECTION of a spike that already moved >1% → TRAP (you're buying after the move)
- Exception: If COT and institutional flow ALREADY supported the direction before news, and news confirms → not a trap

---

### TRAP 5: The Round Number Cluster Trap

**Pattern:** Price near psychological level ($4500, $4600, $5000). Retail clusters orders around round numbers.

**Why it fails:** Institutions know where retail clusters stops and limit orders. They push price to the cluster to grab liquidity, then reverse.

**Detection:** If the ONLY reason a level matters is that it's a round number → TRAP.
Round numbers need STRUCTURAL confirmation (previous high/low, volume profile, COT level) to be valid entry zones.

---

### TRAP 6: The Momentum Fade Trap (COUNTER-TREND)

**Pattern:** "Gold is up 14% in 20 days — it's overbought, time to short." Retail fades strong trends.

**Why it fails:** Trends persist longer than retail expects. Institutions are riding the trend and will squeeze counter-trend positions. "The market can stay irrational longer than you can stay solvent."

**Detection:**
- Strong trending market (>10% move in <30 days) + retail trying to fade it → TRAP
- Only fade a trend if: (A) COT shows institutional positioning shifting, (B) regime change detected, (C) clear rejection structure (not just "it's gone up a lot")

---

## PART 2: HIGH-CONVICTION ENTRY CRITERIA (ALL REQUIRED)

A trade is HIGH CONVICTION only when ALL of the following are true:

### 1. TRAP ABSENCE (GATE 0 — First Check)
Run the full trap scan from Part 1. If ANY trap is detected → **DO NOT ENTER. Period.**

### 2. INSTITUTIONAL ALIGNMENT (REQUIRED)
**Sources:** COT positioning (Granger L2), ETF flows (Granger L2)
- COT net long increasing → confirms LONG
- COT net short increasing → confirms SHORT
- COT at extreme (>90th percentile) → potential contrarian setup, NOT continuation
- If COT data is stale (>2 weeks) → reduce conviction by 2 points

### 3. MULTI-SOURCE CONFLUENCE (REQUIRED)
At least 3 INDEPENDENT data sources must align:
- **Fundamental:** Regime (BULLISH/BEARISH), yield trend, DXY trend
- **Positioning:** COT, ETF flows, options sentiment
- **Price Structure:** Break of structure, liquidity sweep, volume profile levels
- **Cross-Asset:** DXY-gold inverse, yields-metals inverse, VIX-equity inverse

**Rule:** Two indicators from the SAME source (RSI + BB = both price-derived) counts as ONE source.

### 4. STRUCTURE CONFIRMATION (REQUIRED)
Price must have DONE something at the level, not just APPROACHED it:
- **Rejection candle:** Wick through level + close back = institutional absorption
- **Breakout + retest:** Close above level → pullback → holds as new support → enter
- **Liquidity sweep:** Spike through level to grab stops → immediate reversal → enter in reversal direction

**NEVER enter on "approaching" alone.** The daemon triggers on proximity. The AI must wait for price ACTION at the level.

### 5. REGIME ALIGNMENT (REQUIRED)
Trade must align with the current macro regime:
- **BULLISH_METALS** → prefer LONG
- **BEARISH_METALS** → prefer SHORT
- **MIXED** → reduce position size 50% OR wait for regime clarity
- If regime shifted in last 24h → DO NOT ENTER (wait for stabilization)

### 6. RISK:REWARD >= 2:1 (REQUIRED)
- Entry, stop, and target must be at STRUCTURAL levels (not arbitrary percentages)
- Stop: at the level where, if hit, the thesis is INVALIDATED
- Target: at the next structural level (not a guess)
- Position size: (Account x 2% risk) / (Entry - Stop in $)

### 7. TIME QUALITY (REQUIRED)
- XAUUSD/XAGUSD: Prefer 13:00-21:00 UTC (NY session)
- Avoid first 30 minutes of session open (manipulation window)
- Avoid Friday 20:00-24:00 UTC (weekend gap risk)
- Asian session: reduce size 50% (thin books, wider spreads)

---

## PART 3: DECISION MATRIX (APPLY TO EVERY TRIGGER)

```
FOR EVERY ZONE_APPROACH TRIGGER:

STEP 1: TRAP SCAN
  Is price within 0.5% of a known level?           → TRAP 1 check
  Did price just break a level for the first time?   → TRAP 2 check
  Are all "confirming" indicators price-derived?     → TRAP 3 check
  Is there news within 30min or a recent spike?      → TRAP 4 check
  Is the only "level" a round number?                → TRAP 5 check
  Is the market in a strong trend being faded?        → TRAP 6 check

  IF ANY TRAP DETECTED → WAIT. Do not proceed.

STEP 2: ACTION AT LEVEL (not approach)
  Has price actually DONE something at the level?
  - Rejected with a clear candle? → Proceed to Step 3
  - Broke through and retested?  → Proceed to Step 3
  - Just approaching / grinding?  → WAIT. No action on approach.

STEP 3: INSTITUTIONAL CHECK
  COT positioning supports this direction?    → Yes / No / Unknown
  ETF flows support this direction?           → Yes / No / Unknown
  At least 1 YES required. Both unknown → reduce conviction.

STEP 4: MULTI-SOURCE CONFLUENCE
  Count independent aligned sources (from Part 2.3).
  Need >= 3. List them explicitly in reasoning.

STEP 5: REGIME CHECK
  Current regime supports this direction?     → Yes / Mixed / No
  Regime shifted in last 24h?                 → If yes, WAIT

STEP 6: RISK:REWARD
  Calculate R:R with structural stop and target.
  Must be >= 2:1. Calculate position size.

STEP 7: FINAL GATE
  ALL criteria met? → ENTER (write action.json)
  ANY criterion failed? → WAIT (explain which one)
```

---

## PART 4: CURRENT APPLICATION (XAUUSD, 2026-08-21)

**Applying the rules to the ongoing XAUUSD zone_approach triggers:**

| Check | Result | Verdict |
|---|---|---|
| TRAP 1 (Resistance bounce) | Price at BB_Upper $4608 — textbook retail resistance short | TRAP DETECTED |
| TRAP 3 (Indicator confluence) | BB_Upper + overbought + extended 14.3%/20d = all price-derived | TRAP DETECTED |
| TRAP 6 (Momentum fade) | Gold +14.3%/20d = strong trend, retail trying to short resistance | TRAP DETECTED |
| Structure confirmation | Price APPROACHING, not rejecting or breaking | NOT CONFIRMED |
| Institutional alignment | COT bullish metals, but no shift signal | NEUTRAL |
| Regime | MIXED | NO DIRECTIONAL BIAS |
| R:R | Cannot calculate without structure confirmation | NOT CALCULABLE |

**CONCLUSION: 3 traps detected + no structure confirmation + mixed regime = WAIT**

**Valid entry conditions:**
- LONG: Daily CLOSE > $4608 + volume + retest holds → confirms breakout (not trap)
- LONG: Pullback to SMA200 $4495 + regime still bullish + COT aligned → value entry
- SHORT: Only if COT shifts bearish + regime flips + clear rejection structure at $4608

---

## PART 5: WHAT CHANGES NOW

Before these rules, the AI decision was:
> "Price near level → analyze indicators → if aligned → consider entering"

After these rules, the AI decision is:
> "Price near level → TRAP SCAN → if trap detected → WAIT regardless of indicators → if no trap → require structure confirmation + institutional alignment + 3 independent sources → THEN enter"

**The fundamental shift:** Proximity to a zone is a WARNING, not an opportunity. It means "retail is watching this level — be careful." Action requires STRUCTURE (what price did at the level) not PROXIMITY (how close price is to the level).
