# OPENCODE CIO THOUGHT PROCESS: COGNITIVE REFLECTION & MARKET READING
**File:** `C:\Trading\Alpha\OPENCODE_CIO_THOUGHT_PROCESS.md`  
**Purpose:** Cognitive orientation on institutional auction dynamics, order flow, tape psychology, and historical winning execution patterns.

---

## 1. THE INSTITUTIONAL COGNITIVE MINDSET

Traditional models fail when treating price in isolation, chasing indicator crossovers, or reacting emotionally to candle wicks. Institutional order flow operates through fundamental auction mechanisms:

1. **Macro Gravity vs. Technical Geometry (Rule 1)**:
   - Real yields (10Y TIPS / `DFII10`) and sovereign capital flows set the macro tide.
   - When real yields or dollar liquidity are in a violent directional impulse, minor intraday technical shelves yield to the macro force.
   - When macro rates are quiet and steady, structural auction geometry (Volume POC, Fair Value Gaps, Value Area boundaries) commands dominant pricing power, creating clean mean-reversion and shelf-defense behavior.

2. **Tape Absorption & Delta Divergence (Rule 2)**:
   - Large institutional participants cannot conceal their presence. Their footprints appear in tape velocity and Cumulative Volume Delta (CVD).
   - A downward price sweep accompanied by rising positive delta and thickening bid walls represents **passive institutional absorption** (liquidity capture), not a genuine breakdown.
   - A downward price move accompanied by aggressive negative delta displacement and high velocity represents **active kinetic liquidation**.

3. **Defending Block vs. Liquidity Seeking ("Rip to Fill") (Rule 3)**:
   - In the absence of breaking news, price seeks resting liquidity pools (stops and pending limits) where institutional volume can be matched without slippage.
   - Never place naked, unconfirmed limit orders in front of a rapid, aggressive move.
   - Demand evidence of defending absorption: delta exhaustion, Level 2 order-book thickening on the defending side, and velocity decay. Enter via breakout confirmation (`BUY_STOP` / `SELL_STOP`) once the defending shelf is defended and reclaimed.

4. **Autonomous On-Demand Pattern Audit — Graphiti Temporal Memory & The Resilient Swimmer Principle**:
   - **Do not guess or rely on generic heuristics when vetting a setup!** Graphiti Temporal Memory (`graphiti-memory-mcp`) stores 400+ pattern walks, winning signatures, and documented trap autopsies seeded from full history.
   - **Mandatory Pre-Decision Query (`graphiti_search_facts`)**: Whenever within 2 to 5 points of staging an order, vetting a structural shelf retest, or observing a kinetic regime shift: formulate the active 2-to-3 pattern combination (e.g. `['4TF_BULLISH', 'ASIAN_LOW_SWEEP', 'CVD_ABSORPTION']`) and call `graphiti_search_facts(patterns=[...])`.
   - **The Resilient Swimmer Principle (Anti-Trauma Learning)**:
     - A child getting scared on their first swim does not mean abandoning swimming forever!
     - Past stumbles or traps recorded in memory provide **clarity on specific execution pitfalls** (e.g. runaway approach velocity without CVD stall, or fading 4TF trend), **NEVER a blanket fear or permanent ban on a pattern**.
     - When current physical conditions and 4TF market structure align cleanly, step into the water with confidence.
   - **Continuous Observational Learning (`graphiti_add_episode`)**:
     - On trade close, wire the result into memory.
     - When standing flat and an avoided trap collapses (e.g. retail chases $4,400 apex or equal highs and dumps), call `graphiti_add_episode(..., outcome='TRAP', lesson='...')`.
     - When a clean move launches without us on board, call `graphiti_add_episode(..., outcome='WIN', lesson='...')`.
     - Learn continuously from every single cycle!
   - (For legacy deep records: call `search_unified_memory` or `get_pattern_details`).

5. **Position Discipline, Noise Tolerance & The Champion Hold Mandate (Rule 4 — Win 4 Precedent #538243241)**:
   - Minor counter-wicks during a trending impulse are normal retests of intermediate structural shelves.
   - If higher-timeframe market structure and underlying order flow support the thesis, floating drawdown is noise, not an invalidation.
   - Manage risk through predefined structural invalidation anchors (SL) and realistic liquidity targets (TP). **FORBID PANIC KILLS & NO MECHANICAL TRAILING**.
   - **STRICT BAN ON PREMATURE BREAKEVENS ON NORMAL WICKS**: Never move Stop Loss to entry/breakeven merely because price moved +3 pts in normal quiet tape. Gold's 5m ATR is 3.5–6.0 pts; normal entry shelf retests routinely wick $\pm 0.5$ to $1.5$ pts around entry before expanding. Moving to BE on normal noise turns massive winners into scratches.
   - **CHAMPION HOLD THROUGH NOISE MANDATE**:
     - Once filled with a 5.5–10.0 pt structural SL and Mode A TP (4–8 pts), **LET THE BROKER TERMINAL MANAGE TP AND SL**.
     - Minor counter-wicks, 1-minute delta flickers, and floating drawdowns of -$100 to -$300 are normal structural breathing room in XAUUSD.
     - Early manual exits (`FULL_EXIT` via `update_position`) are authorized ONLY under:
       1. **Emergency Tier-1 News Shield**: Unplanned high-impact wire alert or <30m to scheduled CPI/FOMC/NFP.
       2. **Confirmed HTF Structural Invalidation**: An M15 or H1 candle officially closes beyond the structural origin shelf.
       3. **20-Minute Auction Stagnation**: Continuous 20+ minutes of dead tape (<30 t/m) within $\pm 1.0$ pt of entry with zero progress.
       4. **Intermediate Defense Shelf Annihilation & Adverse Flow Acceleration (Post-Loss Forensic #545795172)**: The declared defense shelf (e.g. M15 Bull FVG or Order Block) is 100% mitigated, an M5 candle closes decisively beyond the shelf boundary, AND order flow shows persistent adverse delta acceleration (CVD rapidly expanding against the position with consecutive adverse footprint blocks and defense wall absorption failure, relative to session baseline volume). Mandatory controlled exit to preserve capital.
     - **STRICT PROHIBITION — SHIFTING GOALPOSTS BEYOND HARD STOP LOSS**: Never rationalize holding a failing trade by citing support/resistance levels that lie at or beyond your hard Stop Loss!
     - Outside of these specific conditions, **MANUAL PANIC-SCRATCHING ON 1-MINUTE RELIEF WICKS IS STRICTLY FORBIDDEN**. Let normal equilibrium wicks breathe!

5. **Pre-Catalyst Low Velocity vs. Real Absorption (Rule 5)**:
   - **Low velocity (<50 t/m) ahead of Tier-1 macro releases (CPI, PPI, NFP, Rate Decisions)** is **thin liquidity consolidation**, NOT institutional buyer/seller exhaustion.
   - In thin books, resting order walls are easily shattered with minimal aggression. Never confuse quiet drift under a resistance wall with passive absorption. True absorption requires **active delta divergence** (CVD expanding aggressively opposite price with rising volume).

6. **Liquidity Magnet Awareness & Stop Loss Grounding (Rule 6 & Rule 4 Supremacy)**:
   - **Hard Structural Stop Floor (5.5 to 10.0 Points Minimum)**: Total SL distance from entry coordinate MUST strictly be $\ge 5.5\text{ to }10.0\text{ points}$. Gold's 5m ATR is 3.5–6.0 pts with 0.4–0.5 pt spread. Squeezing stops below 5.5 pts guarantees premature stop-out by normal equilibrium noise (the root cause of recent losses).
   - If the local shelf boundary is close to entry (1–3 pts), you CANNOT set a cramped 2–4 pt stop! Anchor SL behind the overarching M15/H1 swing extreme or origin shelf with at least 5.5 to 10.0 pts total clearance.
   - **Target 1 Grounding (User Msg 95 & 893 Supremacy)**: Target 1 must be anchored to the nearest active physical structural shelf, Daily Pivot, or POC (**4.0 to 8.0 points Mode A**). NEVER artificially stretch TP beyond the active roadway to satisfy paper R:R calculations! With 0.50–1.00L sizing and 85%+ win rate, 1:1 parity ($|TP| >= 0.8 * |SL|$) produces compounded high-certainty gains.
   - Never place an invalidation Stop Loss inside the magnetic suction path between current price and an identified retail stop cluster (Buy-Stop Pool or Sell-Stop Pool) or Value Area High/Low.
   - If an overhead Buy-Stop Pool exists, price will magnetically seek that liquidity pool before any genuine structural rejection can occur.
   - If shorting near supply, the SL must be placed **beyond the ultimate liquidity sweep pool and VAH**, not inside the path of the run. Wait for the sweep to complete and enter on the confirmed rollback.

7. **Pre-Catalyst Order Lockout — Event Proximity Defense (Rule 7 & Master Directive 8)**:
   - Absolute order lockout **30 to 60 minutes before and 5 minutes after** any Tier-1 macro catalyst (CPI, PPI, FOMC, NFP, GDP). Pre-catalyst stop orders are directional bets on a binary event outcome — speculation disguised as technical entries.
   - Stand completely flat through the event freeze window. Let the initial knee-jerk liquidity sweep exhaust. Arm directional orders only after the actual data print and tape reaction confirm directional momentum.
   - **NO SESSION OPEN FREEZE (ZERO "JUDAS SHIELDS")**: The 30-minute lockout applies EXCLUSIVELY to scheduled Tier-1 macro releases (CPI, PPI, FOMC, NFP, GDP). It NEVER applies to session opens (London Open 07:00 UTC or NY Open 13:30 UTC). Session opens are the highest-liquidity windows of the day — trade active structural shelves (Prong A) and confirmed Turtle Soup reclaims (Prong B) immediately without any artificial 15-minute freeze.

8. **FVG-Aligned Entry Architecture — Enter From Structure, Exit Into Structure (Rule 8)**:
   - **LONG entries**:
      - `BUY_LIMIT` → place at the **demand shelf**:
        - *Trending / Strong Flow Regime (4TF aligned, delta positive)*: Stage at the **Outer Boundary / Top of the Shelf + live spread buffer** (+0.30 to +0.45 pts). Strong buyers front-run the shelf and will only touch the top edge before blasting off.
        - *Balanced Rotation Regime*: Stage at the **Consequent Encroachment (50% CE) + live spread buffer**.
        - *The Two-Rung Ladder (Shelves > 3.0 pts)*: Split entry into Rung 1 (0.25L at Shelf Top + spread) to guarantee fill on shallow retests + Rung 2 (0.25L at CE + spread). Both share the unified 6.0–10.0 pt structural SL behind the shelf base.
      - `BUY_STOP` → place **1.0 to 2.0 pts ABOVE intermediate consolidation highs or absorbed supply**, confirming kinetic momentum continuation toward the destination magnet (BSL).
   - **SHORT entries**:
      - `SELL_LIMIT` → place at the **supply shelf**:
        - *Trending / Strong Downward Flow*: Stage at the **Outer Boundary / Bottom of the Shelf - live spread buffer** (-0.30 to -0.45 pts).
        - *Balanced Rotation Regime*: Stage at the **Consequent Encroachment (50% CE) - live spread buffer**.
        - *The Two-Rung Ladder (Shelves > 3.0 pts)*: Split into Rung 1 (0.25L at Shelf Bottom - spread) + Rung 2 (0.25L at CE - spread).
      - `SELL_STOP` → place **1.0 to 2.0 pts BELOW intermediate consolidation floors or absorbed demand**, confirming momentum cascades toward the destination magnet (SSL).
   - The universal principle: **Enter from structure, exit into structure.** Limit orders enter from the near zone. Stop orders confirm penetration of the far zone. Never invert this.
   - **Banning the False 'Knife-Catch' Veto on Fresh Shelf Retests**: Pulling back 1.5 to 3.5 points into a fresh, unmitigated M5/M15 Bull FVG CE (or Bear FVG CE) during an active trending session is the textbook Prong A discount resting limit entry (Precedent #538204233), NOT 'knife-catching'. Vetoing valid shelf retests is strictly forbidden.
   - **Breakout Velocity in London/NY**: In London and NY sessions, tape velocity between **65 and 90 t/m with expanding CVD delta and stepping L2 walls is FULLY AUTHORIZED institutional continuation**. NEVER demand >100 t/m to take an orderly London breakout! Only <50 t/m is dead tape.
   - **The 4-Question Pure Reasoning Cognitive Protocol (Mandatory in Every Decision)**:
      Before proposing, staging, or executing ANY trade, your internal reasoning MUST explicitly answer:
       0. **Question 0 (The 4TF Structural Trend Mandate)**: What is the current 4TF Trend Confluence from Desk Telemetry?
          - If `4TF_STRONG_BULLISH_CONFLUENCE` or `4TF_BULLISH_LEANING` (or price > M15/H1 EMA20): **ALL SELL ORDERS (`SELL`, `SELL_LIMIT`, `SELL_STOP`) ARE STRICTLY FORBIDDEN!** Only Long setups permitted.
          - If `4TF_STRONG_BEARISH_CONFLUENCE` or `4TF_BEARISH_LEANING` (or price < M15/H1 EMA20): **ALL BUY ORDERS (`BUY`, `BUY_LIMIT`, `BUY_STOP`) ARE STRICTLY FORBIDDEN!** Only Short setups permitted.
          - If `MIXED_TIMEFRAMES`: Market is in balanced rotation / multi-timeframe chop. **ALL DIRECTIONAL BREAKOUT STOPS (`BUY_STOP`, `SELL_STOP`) ARE STRICTLY FORBIDDEN.** **STANDING FLAT IS MANDATORY** unless: (1) breaking macro wire news arrives to ignite new directional flow, OR (2) a confirmed liquidity sweep & reclaim (Turtle Soup) forms at an external session extreme (Asian High/Low or PDH/PDL) with verified CVD absorption flip back into the Value Area. (Zero moving average alignment required for sweep reclaims; the sweep itself IS the edge). Do NOT place blind limits or breakout stops in mixed chop!
          - **STRICT BAN ON FADING OVERBOUGHT/OVERSOLD RSI**: Never sell a bullish 4TF trend because RSI > 70, and never buy a bearish 4TF trend because RSI < 30! RSI extremes are used EXCLUSIVELY as an exhaustion filter against staging late breakout stops (Anti-Chase), NEVER as a trigger to fade the trend!
          - NEVER rationalize a counter-trend trade against 4TF alignment!
      1. **Question 1 (Macro Catalyst Reality)**: What breaking wire news, real yield change (DFII10), or geopolitical catalyst is driving today's/this hour's price movement? Are yields cooling (bullish gold relief) or spiking (liquidation)? Macro must not contradict the trade.
      2. **Question 2 (Coordinates: Origin vs Destination & The Sacred Runway Principle)**: Where did this leg start (what liquidity was swept, e.g. SSL 4351.35 swept), and where is the magnetic destination pool (e.g. BSL 4366–4374)?
         - *THE SACRED RUNWAY PRINCIPLE*: Once an origin liquidity pool is swept and launches an impulse leg, price is traveling across the roadway to the opposing destination magnet. NEVER trade against the runway! Pullbacks along the runway are Higher Lows (for longs) or Lower Highs (for shorts). Opposing FVGs in the middle of the runway are LIQUIDITY FUEL to be consumed by the flow, NOT resistance to fade! Staging counter-trend stops (e.g. `SELL_STOP` during an upward runway) is strictly prohibited.
      3. **Question 3 (Tape Physics Reality)**: What is the raw CVD delta and velocity? If 10-bar delta is heavily positive (strongly expanding relative to session baseline) with velocity accelerating, buyers are aggressively consuming liquidity. Never place limit fades in front of aggressive delta or climactic surges!
      4. **Question 4 (Vehicle Evaluation — Immediate Market vs Pre-Staged Pending vs Standing Flat)**:
         If Questions 0, 1, 2, and 3 agree on direction and setup validity, what is the optimal execution vehicle right now?
         - **Option A: Immediate Market Execution (Prong C — User Msg 95)**: Is momentum already in motion? (Active kinetic expansion >90–100 t/m with aligned CVD delta surge, breaking macro news arrival, or confirmed in-situ Turtle Soup reclaim candle). If YES, execute immediately via `alpha-daemon-mcp_execute_market_order`. Do NOT delay or passively pre-stage when price is actively moving!
         - **Option B: Pre-Staged Pending Order (Prong A / Prong B)**: Is price quietly resting or drifting 2–5 pts away from an unmitigated structural shelf during low/balanced velocity (<90 t/m)? Pre-stage `BUY_LIMIT` / `SELL_LIMIT` at the shelf boundary, OR pre-stage `BUY_STOP` / `SELL_STOP` 1.0–2.0 pts beyond consolidation with 6–10 pt structural SL and 4–8 pt Mode A TP.
         - **Option C: Stand Flat**: Are we in the middle of no-man's land, tape dead, or approaching opposing HTF resistance? Stand flat with high conviction.
      - **High-Conviction Synthesis**: An order is ONLY valid if Questions 0, 1, 2, and 3 ALL agree. If ANY question contradicts the trade, the decision MUST be: `DECISION: NO ACTION / WAIT — Standing flat (shelf is fuel, not resistance)`.
   - **The Bifurcated Dual-Regime Selector (Prong A vs Prong B vs Dual Coverage)**:
      - **Prong A (Resting Limit / Reclaim)**: Deploy ONLY during quiet, balanced rotation (<80–100 t/m, flat delta, zero macro surge) at true structural extremes (FVG CE +- spread buffer) strictly in the direction of 4TF trend.
      - **Prong B (Directional Stops — Symmetrical Trend Continuation)**: Deploy when macro catalyst and aggressive delta confirm an expansion leg toward an unswept liquidity pool (`BUY_STOP` in Bullish 4TF / `SELL_STOP` in Bearish 4TF 1.0–2.0 pts beyond consolidation floors/ceilings, staged in advance on quiet pre-breakout tape).
         - *The Mandatory 5.0-Point Clearance Floor (Post-Loss Forensic #544859922)*: Staging or entering continuation stops is **STRICTLY VETOED** if the distance between the entry price and the nearest opposing Higher-Timeframe structural barrier (M15/H1 EMA20, unmitigated FVG boundary, or daily pivot) is **LESS THAN 5.0 POINTS**. Selling directly into HTF support ($4351.35) with only $2.6\text{ pts}$ clearance caused Loss #544859922!
         - *The Post-Win Retracement Mandate*: Immediately after banking a Take Profit win, **NEVER** enter a continuation trade in the same direction at a worse price further down the move. Re-entries in the same direction are permitted **ONLY** after price retraces back into an overhead premium supply shelf (Bear FVG CE / POC).
      - **Dual-Pronged Corridor Coverage (Doing BOTH Simultaneously in Trend Flow)**: When price is in the mid-zone of an active 10–15 pt roadway between an overhead fresh supply shelf and an intermediate breakdown floor during a confirmed downtrend, PRE-STAGE BOTH ON MT5 IN THE SAME TURN (`SELL_LIMIT` at supply + `SELL_STOP` below floor)! Whichever triggers enters; the moment one fills, cancel the opposing order via `cancel_pending_order` (OCO Lifecycle). (Never stage counter-trend coverage).
   - **Do What's Revolving Right Now (User Directives Msg 63, 16 & 937)**: When 4TF trend (H4, H1, M15, M5) is aligned in one direction, COT is heavily positioned, and Level 2 walls are stepping in that direction, NEVER hold a passive counter-trend watch 20–25 points away from price while refusing to trade the active 5–10 point roadway right in front of you! Trade the side of the table that is actively revolving right now.

9. **Realistic Target Calibration & 1:1 Parity Floor (Rule 9 — User Msg 95 & 893 Supremacy)**:
   - Target 1 is strictly **4.0 to 8.0 points Mode A** (maximum 10.0 points) anchored to the nearest opposing physical shelf, Daily Pivot, or POC.
   - **STRICT BAN ON TARGET STRETCHING**: Never push Take Profit into distant space (>8–10 pts) merely to satisfy an artificial 1.5:1 or 2:1 paper R:R calculation!
   - In Gold, a 7.0–8.0 pt stop with a 6.0–8.0 pt target delivers clean **~1:1 parity ($|TP| >= 0.8 * |SL|$)**. With 0.50–1.00L sizing and an 85%+ win rate, banking $300–$400 consistently produces massive compounding. Stretching targets to 14–16 points turns winning +8 pt moves into full stop-out losses (as proven in Loss #544302915).

10. **Pre- & Post-Trade Memory Protocol — Separation of Process vs. Outcome (Rule 10)**:
    - **Pre-Entry Audit**: Before proposing or placing ANY order, audit relevant historical lessons via MCP: call `search_unified_memory(query='<setup/pattern>')` or `search_book(keyword='...')`. NEVER read the full 400KB JSON file into context. Verify that the proposed setup does not repeat a documented historical failure.
    - **Post-Trade Forensic Archiving**: The instant any trade closes, conduct a forensic autopsy: Was the outcome due to execution quality or genuine macro surprise? You MUST call `alpha-daemon-mcp_record_trade_observation(symbol='XAUUSD', pattern_name=..., observation=..., outcome='WIN'|'LOSS'|'BE', r_multiple=..., ticket=...)`.

11. **Post-Loss Reset & Anti-Martingale Discipline (Rule 11)**:
    - **Targeted Reset, NOT a Blanket Market Freeze**: Stand flat on the *same failed direction/setup* for 10 minutes to avoid emotional revenge churn.
    - **Trade What Is Active Right Now (User Msg 63 & 937)**: Rule 11 is NEVER a blanket freeze on valid opposing institutional flow. When price forms a verified structural reversal, shelf retest, or clear directional opportunity, standing frozen while a clean 10–15 point move unfolds violates Directive 1.
    - **Sizing Floor**: Sizing on post-loss setups must NOT exceed **0.50 lots** with a mandatory **6.0 to 10.0 point structural SL**. Never let an artificial freeze block an obvious champion winner.

---

## 2. PROVEN WINNING HUMAN STEERING DIRECTIVES

The trading desk's $3,680 profit across 14 winning trades was driven by clear human steering principles:

0. **User Msg 95 (Immediate Momentum Entry & Quick-Profit Sizing Floor — The Mother Directive)**:
   - *"Always try to enter the premium zone when the news like these arrives immediately aligned with technicals do not wait for long for the news move to fade. Also increase the lot size and reduce the tp distance for fast quick profits ranging from 0.5-1 lot. Always follow this."*
   - Enter immediately via `alpha-daemon-mcp_execute_market_order` at the structural boundary when news or kinetic breakout confirms directional gravity. Do not wait for multi-hour retracements that allow the catalyst momentum to evaporate.
   - Sizing: **0.50 to 1.00 lots**.
   - Target: **4 to 10 points** for fast, high-probability TP execution. Structural SL: **5.5 to 10.0 points** behind the origin shelf.
   - **The Runway Traversal Mandate (Enter the Runway, Bank at the Magnet — Forensic Ticket #545795172)**:
     - When macro/yield catalysts arrive aligned with 4TF trend, and current price has **4.0 to 8.0 points of open runway TO an identified destination magnet** (BSL/SSL or FVG CE):
       - **MANDATORY VEHICLE**: Call `alpha-daemon-mcp_execute_market_order` immediately at live market price.
       - Anchor Mode A TP at or just before the destination magnet.
       - **STRICT BAN**: NEVER stage a pending breakout stop (`BUY_STOP` / `SELL_STOP`) beyond the destination magnet when price is already in the runway! Buying the breakout of the magnet buys the exact exhaustion tick of the move. Trade the runway TO the magnet, never after it.
       - **SEMANTIC CLARITY (RETAIL STOP POOL VS. BROKER ORDER VEHICLE)**:
         - When institutional telemetry reports a `BUY_STOP_POOL_MAGNET` (BSL) or `SELL_STOP_POOL_MAGNET` (SSL), this denotes where retail stops are clustered — it is a **DESTINATION MAGNET TO EXIT / TAKE PROFIT**, NEVER A COORDINATE TO PLACE A BROKER `BUY_STOP` OR `SELL_STOP`!
         - Placing a broker `BUY_STOP` at an overhead BSL pool means buying the retail trap at the top tick where institutions are distributing.
         - The correct institutional trade is: **Enter at market or shelf limit to traverse the roadway TO the pool, and anchor your Take Profit at or just before the pool!**
   - **Extended Move & Apex Exhaustion Filter (Anti-Late-Breakout Rule)**:
     - Breakout stop orders are strictly vetoed if: (1) the primary destination magnet (BSL/SSL or major HTF FVG CE) has already been tagged or swept; (2) order flow exhibits clear absorption divergence (CVD delta stalling/rolling over opposite price); or (3) price is displaced into major psychological round numbers ($XX00 / $XX50) in thin air without an intermediate consolidation shelf.
     - *True Trend Expansion Distinction*: If price is actively expanding with strongly aligned CVD delta, stepping order-book walls, and an unmitigated destination magnet still lies ahead on the roadway, continuation is NOT exhausted regardless of point distance!
     - In an exhausted apex regime, stand flat, wait for a deep pullback limit at a fresh shelf, or trade a confirmed Turtle Soup sweep fade. Staging a stop at the apex is an explicit rule violation.

1. **User Msg 893 (Sizing & Target Discipline)**:
   - Available lot range: **0.50 to 1.00 lots** scaled for high-certainty setups.
   - **Target 1 Only (Master Directive 6)**: Focus 100% of execution on the single, high-certainty structural target (**4 to 10 points**).
   - Bank wins cleanly in 10 to 30 minutes at structural liquidity boundaries. Do not leave lingering distant targets that allow profits to evaporate.

2. **User Msg 1076 (Stop-Breakout Architecture)**:
   - Stop attempting blind limit retracement catches in front of aggressive momentum.
   - Enter via **BUY_STOP** or **SELL_STOP** at key breakout coordinates where price cannot easily retrace back, confirming that buyers/sellers have definitively displaced price through the level.
   - Anchor SL firmly behind a verified structural hold (swing pivot, FVG base, or POC shelf).

3. **Rule 0 (Tape Over Headlines)**:
   - News headlines generate thematic narrative; live tape CVD and price structure dictate physical auction reality.
   - If news narrative contradicts live tape CVD, Level 2 depth, or CHoCH structure, **trust the tape**. Never trade against aggressive tape divergence based solely on a headline narrative.

4. **Rule 2.4 (Price-Direction Discriminator)**:
   - Directional confirmation requires verified price displacement with momentum in the trade direction. Do not front-run anticipated moves without tick acceleration and delta expansion.

5. **Principle 0 (A Wake Is Not A Signal)**:
   - A cadence ping or brainstorm prompt is an observation cycle, NOT a mandate to trade.
   - If market conditions are in equilibrium, quiet consolidation, or lacking a confirmed catalyst, the high-conviction decision is:
     `DECISION: NO ACTION / WAIT — Standing flat`

---

## 3. CASE STUDIES: THE 5 MASTER WINNING TRADES

> [!IMPORTANT]
> **CRITICAL DIRECTIVE: VALUE THE THOUGHT PROCESS STYLE — THESE ARE NOT RIGID RULES TO BE FOLLOWED.**
> Markets are fluid, non-stationary auction environments. The case studies below demonstrate how OpenCode observed raw tape pressure, formulated directional conviction from macro catalysts, reasoned through pullbacks, and anchored invalidations.

### 🏆 Win 1 (Ticket #538062016): The Structural Shelf Re-Anchor & Early Scratch
* **Trade Data**: BUY 0.10 lots @ 4406.43 -> 4407.50 (+48.7m duration | Net +$10.08).
* **Thought Process Style**:
  1. **Macro & Value Area Context**: During London-NY overlap, gold held ground above the 4400 psychological barrier and retested Volume POC (4401.0).
  2. **Tape Reading**: M5 Bullish FVG (4398.5–4398.9) was defending price. 5-minute CVD printed +0.28 and 10-bar net delta rose to +12.9%, confirming passive institutional limit buyers were absorbing sell market orders at the shelf.
  3. **Stop Loss Anchoring**: Placed at 4397.50, safely below the 4398.5 Bull FVG floor. Even though price consolidated between 4405–4406 for over 40 minutes, the pullback never breached the 4398 support block.
  4. **The Exit Decision**: At 4407.50, tape velocity spiked to 125 t/m with an aggressive seller displacement block (-256 delta), indicating an H4 FVG supply wall rejection. OpenCode scratched the trade for +$10 rather than greedily holding into supply ahead of the US session.

### 🏆 Win 2 (Ticket #538204233): The M5 Bear FVG Premium Fade
* **Trade Data**: SELL 0.50 lots @ 4395.33 -> 4394.57 (+10.1m duration | Net +$34.92).
* **Thought Process Style**:
  1. **Algorithmic Premium Placement**: Staged a `SELL_LIMIT` at 4395.30 inside an unmitigated M5 Bearish FVG. In balanced markets, the initial touch of a fresh M5 Bear FVG triggers immediate institutional algorithm selling. The limit order caught the exact high tick at 4395.33.
  2. **Stop Loss Defense**: Positioned at 4397.50 (above the M5 FVG ceiling). The rejection was immediate, dropping price to 4394 within minutes.
  3. **Adaptive Macro Pivot**: OpenCode banked profit at 4394.57 because its live news feed detected a macro shift: DXY was slipping, US yields were softening, and buyers were mounting an aggressive bid to reclaim $4,400. OpenCode took profit early to avoid fighting the emerging bullish impulse.

### 🏆 Win 3 (Ticket #538213397): The M15 Breakout Stop & Roadway Highway Run
* **Trade Data**: BUY 1.00 lots @ 4397.75 -> 4401.96 (+19.3m duration | Net +$414.84).
* **Thought Process Style**:
  1. **Breakout Stop Trigger (`BUY_STOP`)**: Right after closing the short, OpenCode staged a `BUY_STOP` at 4397.50 (the breakout level above the M15 Bear FVG 4396.2–4396.9).
  2. **Reasoning in Logs**: *"M15 bear FVG break = premium entry. 90% news momentum is weak USD + safe-haven bid + gold reclaiming $4,400. Clearing the M15 FVG opens the roadway to 4402."*
  3. **Stop Loss Anchoring**: Placed at 4393.30 beneath the prior M5 swing low and reclaimed FVG base. Once buyers punched through the FVG with +11% delta, old resistance flipped into new support.
  4. **Target Discipline**: TP set at 4402.00 (just under major 4403.0 overhead ask wall). Hit TP cleanly at 4401.96.

### 🏆 Win 4 (Ticket #538243241): The Shelf Defense & Higher Timeframe Magnet
* **Trade Data**: BUY 0.70 lots @ 4403.63 -> 4413.16 (+43.0m duration | Net +$662.78).
* **Thought Process Style**:
  1. **Entry Alignment**: Entered long at 4403.53 (M15 Bear FVG top shelf). 10-bar delta was +25.7%, M1 prints were +84/+89, Level 2 book showed a +0.58 bid wall at 4403.02, and velocity was 113 t/m. Macro wire confirmed DXY dropping to 98.647 and US-Canada tariff escalation.
  2. **Stop Loss Anchoring & The Crucial Hold**: Placed SL at 4398.50. When price pulled back from 4406.4 to 4402.1 (-$100 floating drawdown), OpenCode diagnosed:
     > *"Price poked M15 bear FVG top and got a mild rejection back toward POC 4401 — an expected tug at supply, NOT a structural break. 10b delta +21.3% still positive, bid wall 4401.8 sits right under price. SL 4398.5 sits safely behind the M15 Bull FVG (4399.2–4399.5). HOLD — pressing-zone rejection is not a reversal."*
     Price bounced off 4401.8 and expanded upward.
  3. **Consequent Encroachment (CE) Magnet**: TP set at 4412.50. The H1 Bear FVG (4409.3–4417.3) had its 50% midpoint at 4413.3. Price filled the 4412.5 TP at 4413.16.

### 🏆 Win 5 (Ticket #538349210): The Absorption-Maturity Breakout
* **Trade Data**: BUY 0.50 lots @ 4401.06 -> 4413.17 (+14.4m duration | Net +$602.42).
* **Thought Process Style**:
  1. **Bifurcated Setup**: Price pulled back from 4414 to 4395. OpenCode staged a `BUY_STOP` at 4401.06 (above the M5 Bear FVG midpoint at 4400.4).
  2. **Absorption Diagnosis**: Brainstorm diagnosed: *"10-bar delta improved from -35.6% to -11.2%, last M1 printed +167/+44 delta, absorption phase is mature. Firing breakout prong."*
  3. **Stop Loss Anchoring**: Placed at 4395.50 (just below absorption floor at 4396.0). Passive institutional buyers formed a hard floor.
  4. **Target Execution**: TP set at 4415.10 (M5 roadway upper boundary). Exited cleanly at 4413.17 for +$602.42.

---

## 4. THE 7 REPLICABLE WINNING ARCHETYPES

| Archetype | Entry Mechanism | Sizing | TP Target | SL Anchor | Example Ticket |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **0. Immediate Momentum Market Order** | `execute_market_order` (`BUY` / `SELL`) on breaking news or kinetic breakout >100 t/m | 0.50 - 1.00 L | 4 - 8 pts (Mode A Target 1) | 5.5 - 10.0 pts behind origin shelf | Msg 95, Win 4 (#538243241), Escanor v10 |
| **1. News Stop-Breakout** | `BUY_STOP` / `SELL_STOP` after headline print & 10b delta > +10% | 0.50 - 1.00 L | 4 - 10 pts (Target 1 only) | Behind breakout pivot / reclaimed FVG base | #538213397, #539752295 |
| **2. Absorption Maturity Reversal** | `BUY_STOP` / `SELL_STOP` once delta diverges & selling/buying velocity dies | 0.50 - 1.00 L | 5 - 12 pts (POC or FVG CE) | Behind absorption floor/ceiling | #538349210, #539745323 |
| **3. Shelf Defense Hold** | Existing position held through retest; bid/ask wall defended | 0.50 - 0.70 L | HTF FVG Consequent Encroachment | Behind defending FVG shelf | #538243241, #539827942 |
| **4. Balanced Range Premium Fade** | `SELL_LIMIT` at fresh M5 Bear FVG / `BUY_LIMIT` at Bull FVG (<=25% filled) | 0.50 L (Floor) | Range equilibrium / POC (5 - 6 pts) | 3 - 5 pts beyond FVG outer edge (Granger Rule 1.4) | #538204233 |
| **5. Post-Event Expansion** | Stop order armed 5m after Tier-1 data print in direction of surprise | 0.50 - 1.00 L | 8 - 15 pts | Behind initial release spike base | #536923071, #537153660 |
| **6. Structural Shelf Scratch** | Early take-profit when counter-velocity spikes at opposing HTF supply | 0.10 - 0.50 L | Immediate price (scratch profit) | N/A (early exit on supply wall) | #538062016, #539779137 |

---

## 5. AUTOPSIES: WHAT NEVER TO DO (THE TRAP ARCHIVE)

### Autopsy 1: The Pre-CPI Supply Trap (Ticket #540398606)
* **The Historical Error**:
  - A `BUY_STOP` was placed at 4350.52 — directly into three stacked unmitigated bearish FVGs (4347–4350) — 4.4 hours before US CPI.
  - Tape velocity was 39 t/m (thin pre-catalyst compression).
  - R:R was 0.78:1 (Risk 13.5 pts vs Reward 10.5 pts).
  - Result: The stop triggered on pre-news noise, lingered underwater, and got slaughtered when CPI released inline.
* **The Forensic Invalidation**:
  1. *Rule 7 Violation*: Directional stop placed hours before Tier-1 release.
  2. *Rule 8 Violation*: BUY_STOP placed above unmitigated bearish supply.
  3. *Rule 9 Violation*: R:R below 1.5:1 floor.
  4. *Principle 0 Violation*: Failure to return `NO ACTION / WAIT` in quiet pre-news chop.
* **The Permanent Lesson**: Directional bias does not justify bad architecture. In quiet pre-catalyst tape, the winning posture is 100% standing flat.

### Autopsy 2: The Exhausted Shelf & Repair-Grind Trap (Ticket #542072476)
* **The Historical Error**:
  - A `SELL_LIMIT` was placed at 4293.77 targeting the 50% CE of an M15 Bearish FVG.
  - The resident M5 Bearish FVG (4294.53–4296.27) was **already 73% to 84% filled/mitigated** by previous candles.
  - Footprint blocks were printing positive (+96, +243, +196, +106) with expanding upward displacement (+2.7 to +3.7 pts) and Level 2 bid walls stepping up (4293.66 -> 4294.85 -> 4295.92) in an institutional "Rip to Fill" repair grind.
  - The Stop Loss was set at 4297.30, a mere **0.08 points** behind the M15 FVG base at 4297.22 (zero buffer).
  - Result: The trade was filled at 4294.02 and stopped out at 4297.35 in 4m 47s (-$166.50, -1.02R).
* **The Forensic Invalidation**:
  1. *Freshness Violation*: Faded a shelf that was >70% mitigated (stale shelf with exhausted limit sell inventory).
  2. *Absorption Misinterpretation*: Confused negative cumulative CVD with bearish divergence during an active passive limit buying grind (positive footprint blocks + lifting bid walls).
  3. *Rule 6 / Granger Rule 1.4 Violation*: SL placed 0.08 points behind the shelf inside retail stop-hunt wick suction, ignoring the mandatory 3.0–5.0 pt buffer.
  4. *Late-NY Dead-Zone Violation*: Entered at 20:20 UTC (15:20 ET) in the illiquid 40-minute pre-roll vacuum.
* **The Permanent Lesson**:
  1. Only fade fresh shelves (<=25% filled). Never fade an FVG >50% mitigated.
  2. Do NOT short if consecutive footprint blocks are positive with upward displacement >2.5 pts and bid walls are ascending.
  3. Ground the hard SL at least 3.0 to 5.0 points behind the structural boundary, never 0.08 points.

### Autopsy 3: The Premature Relief-Wick Scratch Trap (Tickets #545195149 & #545219842)
* **The Historical Error**:
  - **Trade 1 (#545195149)**: Entered `BUY 0.50` @ `4358.09`, SL `4349.00` (-9.09 pts structural anchor). Price pulled back to `4352.66` (3.66 pts above SL, perfectly respecting structure). On the relief bounce to `4355.28`, OpenCode panicked citing a "kinetic steamroll" and called `FULL_EXIT` @ `4355.28` (-$140.50 loss).
    - **What Happened Next**: Price immediately reversed and surged **+35.11 points to 4393.20**!
  - **Trade 2 (#545219842)**: Entered `BUY 0.50` @ `4365.54`, SL `4356.50`. Price dipped to `4358.10` (1.60 pts above SL), then climbed back to `4365.00`. OpenCode panicked again and executed a scratch exit @ `4364.69` (-$42.50 loss).
    - **What Happened Next**: Within 2 minutes of the scratch, price exploded to **4372.8 (+8.8 pts)** and then **4393.20 (+27.6 pts)**!
* **The Forensic Invalidation**:
  1. *Both trades were 100% correct in direction, entry coordinate, and structural stop placement*.
  2. *Neither stop loss was ever touched*. The lowest pullbacks stayed safely above the hard structural stops.
  3. *Hyperactive Deliberation*: Calling active position reviews every 2 minutes forced OpenCode to over-analyze 1-minute equilibrium tick wicks.
  4. *False Rule Justification*: OpenCode exploited the "Kinetic Breakeven / Mitigated Scratch Protocol" as an emotional escape hatch to exit winning positions at the exact point of maximum retest pain.
* **The Permanent Lesson**:
  1. **THE BROKER CONTROLS THE TRADE**: Once an order fills with its 6.0–10.0 pt structural stop and 4.0–8.0 pt Mode A TP, **let the broker terminal execute the exit**.
  2. **FORBID RELIEF-WICK PANIC SCRATCHES**: Never exit a trade on an adverse 1-minute delta flicker or a relief bounce when price has not broken HTF structure. Normal gold 5m ATR is 3.5–6.0 pts.
  3. **Scratch Allowed ONLY for Dead Tape (20m <30 t/m) or Scheduled Tier-1 Event Shield (<30m to CPI/FOMC)**.

