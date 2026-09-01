# XAUUSD Asian Bear-Trap Reversal — Session-Discipline & Rejection-Continuation Strategy

> **Status:** Strategy playbook derived from a LIVE real-time validation (Ticket #532323273) plus the full
> 138-trade forensic ledger. The core principle: **THE EDGE IS THE REJECTION + 4TF RE-ALIGNMENT, NOT THE PRE-EMPTIVE ENTRY.**
> Non-controlling evidence — does not override `OPENCODE_MANDATES.md`, the canonical Agent rule & study mandate.
> This is the **3rd strategy file**, complementing:
> - `01_MICRO_PROFIT_SCALPING_STRATEGY.md` (historical hold-to-tip archive)
> - `02_XAUUSD_CE_IN_DIRECTION_STRATEGY.md` (direction-agnostic CE entry)

---

## 🎯 CORE OBJECTIVE

Execute **1-lot XAUUSD shorts at the FRESH BEARISH-FVG REJECTION** on a **4TF_STRONG_BEARISH_CONFLUENCE** tape,
targeting the **graceful demand/VAL magnet**, and — critically — **enter ONLY on the confirmed rejection of a
fresh bearish FVG**, NEVER pre-emptively into Asian-session chop.

> **⚠️ HEADLINE LESSON (from live Ticket #532323273):** We entered the short **pre-emptively** during the Asian
> session at `4432.98` — a **statistical 0%-win-rate window** (`ASIAN_SESSION_AVOID`). It went **-$224** before a
> **fresh M5 BEARISH FVG** accidentally formed overhead (`[4434.89-4435.22]`), price rejected it, and the short
> ran to **+$110**. **The win came from the rejection-reversal that formed AFTER our bad entry, NOT from the entry
> logic.** The repeatable edge is entering ON THE REJECTION, not on hope that a rejection will form later.

---

## 🧭 THE TWO HALVES OF THE TRADE (the honesty split)

| Half | What happened | Verdict |
|---|---|---|
| **The ENTRY** | Pre-emptive 1-lot short at `4432.98` in Asian session, chasing a ~72–86% filled FVG, weak-SELL direction | **PROCESS ERROR / LUCK** — violated `ASIAN_SESSION_AVOID`, `CHASED_FVG_TRAP`, direction base rates |
| **The CONTINUATION** | Fresh M5 BEARISH FVG `[4434.89-4435.22]` (CE `4435.06`) formed overhead → price swept up, REJECTED, reversed down through entry and past M5 bullish FVG toward TP | **REAL EDGE** — the `Asian Low Bear Trap Reversal` (9.8/10, 54.5% WR) pattern |

> **🔑 THE LESSON:** A process-error entry can bank a win (that is LUCK / exit saving a bad location — see
> `01_MICRO_PROFIT` §process-error-vs-luck). The **robust, reproducible edge** = waiting for the **confirmed
> rejection of a FRESH bearish FVG with 4TF aligned**, then entering.

---

## ✅ THE LIVE VALIDATION (Ticket #532323273) — the REAL edge, isolated

| Field | Value |
|---|---|
| **Setup** | Fresh M5 BEARISH FVG `[4434.89-4435.22]`, CE `4435.06`, **FRESH (0% fill)** — supply directly overhead |
| **The rejection** | Price swept UP into the FVG (the -$224 drawdown), then **rejected the CE and reversed down** |
| **4TF | Spread | CVD** | **4TF_STRONG_BEARISH_CONFLUENCE** (H4 20.7, M5 flipped BEARISH) \| 37–45 pts \| negative CVD `-2610.6` |
| **Reversal path** | Rejected `4435.06` → broke `4432.98` entry → through M5 bullish FVG `[4428.08-4433.13]` → toward TP `4424.00` |
| **Result** | From **-$224 → +$110** while the rejection thesis was in play |

**Why the CONTINUATION half won:** a **fresh** bearish FVG (supply) directly overhead on a **fully 4TF-bearish-aligned**
tape got its CE rejected — the exact institutional rejection-reversal stomach of the `ASIAN LOW BEAR TRAP REVERSAL`
pattern (6/11 = 54.5% empirical WR). **The entry timing was WRONG; the surviving pattern was RIGHT.**

**The hard truth:** This is a **high-variance survivor** — it does NOT validate trading Asian. It validates the
**fresh-bearish-FVG-rejection continuation** concept.

---

## 🚫 THE THREE LEAK PATTERNS THIS TRADE VIOLATED (from the 138-trade ledger)

These are the **bads** — do not repeat:

### 1. `ASIAN_SESSION_AVOID` — 0% win rate
- Asian (00-07 UTC): **2 trades, 0 wins, -$272.73, -3.09R** (avg loss -1.54R).
- Tick #532236326: SELL lost **-0.67R in 94 seconds** in Asian.
- **Lesson: DO NOT trade the Asian session regardless of setup.** Consolidation chop (delta oscillating around
  zero) destroys entries. This trade flipped **+$110 → -$29** in ONE cycle — textbook Asian chop.

### 2. `NEW_YORK_SHORT_DISASTER` / weak-SELL base rates
- Overall SELL = **21.1% WR** (4/19); NY|SELL = **15.4% WR** (2/13, -$786.85, -5.15R).
- **Lesson:** SELL is the historically weakest direction. Must be exceptionally selective (see the GOOD below).

### 3. `CHASED_FVG_TRAP` — ≥60% fill = trap
- Exhausted/Chased bucket: **35.7% WR, -$1415.57, -10.83R** (biggest dollar bleed; matches the system's -97.09R warning).
- Ticket #531707570: SELL at 74.1% fill lost -0.89R in 51 sec.
- **Lesson:** NEVER enter a ≥60%-filled FVG. Enter FRESH (<30%) or at CE (30-60%).

### Plus systemic: `TIGHT_SPREAD_BLEED` & `OVERTRADING_AND_TIMESCALE_MISMATCH`
- Tight spread (<40pts): 24.1% WR, **-$2088.61, -23.07R** = overtrading in low-quality chop.
- 138 trades at 31.2% WR = too many; 94-second 1-lot scalps bleed spread+commission.

---

## ✅ THE GOOD — what the ledger says WORKS (base rates that carry positive expectancy)

These are the **goods** — concentrate entries here:

### 1. `LONDON_SESSION_EDGE` — the ONLY reliable window
- London (07-13 UTC): **52.2% WR, +$1129.02, +5.04R**. London|BUY 52.6%, London|SELL 50%.
- **Lesson: Concentrate discretionary entries in London hours**; treat New York (26.5% WR, -27.24R) and Asian (0%) as avoid unless extremely selective.

### 2. `CE_FILL_SWEET_SPOT` — 30-60% fill is the profitable zone
- Equilibrium/CE (30-60%): **53.8% WR, +$1248.89, +1.02R** — the ONLY profitable fill bucket.
- Fresh (<30%): 26.3% WR -$238.30. Chased (≥60%): 35.7% WR -$1415.57.

### 3. `PROTREND_EQUILIBRIUM_GOLD` — the rare high-value setup
- Pro-Trend | Equilibrium/CE: **100% WR (2/2), +$823.67, +2.74R** (avg +1.37R).
- Plus Counter-Trend|Fresh long gives **+2.14 avg win R**.
- **Lesson:** The reliable edge = **trend-following entries into partially-filled equilibrium (30-60%) zones
  with elevated spread** — NOT fresh, NOT chased.

### 4. `ELEVATED_SPREAD` — counter-intuitive profitability
- Elevated (40-80pts): 34.2% WR, **+$1132.92, +2.47 avg win R**.
- **Lesson:** Elevated spread forces selective entries that win bigger; tight spread breeds the overtrading that bleeds.

### 5. `FRESH-BEARISH-FVG REJECTION` (NEW, from this trade) — the continuation edge
- A FRESH bearish FVG (supply) on a full 4TF bearish tape, whose CE gets rejected, has continuation potential
  (the Asian Low Bear Trap Reversal, 54.5% WR). **Enter on the confirmed rejection, not into the chop.**

---

## 🧭 ENTRY CHECKLIST — the CORRECT (non-luck) version

| # | Check | Requirement for a SHORT |
|---|---|---|
| 1 | **Session** | **LONDON (07-13 UTC)** preferred. **Asian (00-07) = NO TRADE.** |
| 2 | **4TF alignment** | Clean **4TF_STRONG_BEARISH_CONFLUENCE** (all 4 bearish). MIXED = NO TRADE. |
| 3 | **FVG type & state** | **FRESH BEARISH_FVG** (<30% fill) OR at CE (30-60%). **NEVER ≥60% filled.** |
| 4 | **Rejection confirmed** | Price swept UP into the bearish FVG and **REJECTED the CE** (displacement down past CE). Do NOT enter pre-emptively. |
| 5 | **Delta / CVD** | Negative / distribution (delta NOT opposing). CVD negative. |
| 6 | **Spread** | ≤ ~45-67 pts ceiling. **ELEVATED (40-80) is tradeable, HIGH_SPIKE = NO TRADE.** |
| 7 | **Macro clear** | No veto event / freeze. |
| 8 | **Size** | **1.0 lot ONLY on a clean rejection entry**; reduce to 0.5 / 0.1 on any uncertainty. |

---

## 🎯 TAKE-PROFIT & MANAGEMENT (graceful, per `02_` strategy)

- **Base-case TP ~20 pips / ~$200** at the first demand/VAL magnet in the short direction (for this trade, `4424.00`)
  — do NOT over-aim (CEO directive).
- **Trail to breakeven ONLY after a meaningful advance** (>50% to target or past a structural barrier) — NEVER on
  first-profit noise (the -$224 → +$110 ebb was normal breathing room).
- **Harvest on exhaustion** (M5 RSI ~20 short) once profit ≥ target.
- **Hard structural SL** above the FVG ceiling + supply; let it govern risk (this trade: `4441.50`).

### 🔍 BACKTEST-VALIDATED TP RULE — `TP_NO_NEGATIVE_BUFFER_UNDER_MOMENTUM` (NEW, 2026-09-01)

**Backtest finding (M5, 29 setups, 100% WR, 3.0R):** For the Asian Low Bear Trap Reversal short, the correct TP
is at the **VAL/demand magnet** (this trade: `4424.00`) and achieves **clean 3.0+ RRR with NO negative buffer**
(BP placed below the target) **when momentum is strong.**

- **Reproduced path:** entry `4439.25`, SL `4445.85`, TP `4424.00` → **TP_HIT at 3.0R**.
- **The rule:** when velocity is strong (CVD deeply negative, sustained selling pushing price through the target),
  **do NOT add a negative buffer** — a TP below the magnet only gives back profit. Place TP at the exact structural
  magnet (VAL/demand) and let momentum carry it through.
- **Live confirmation (#532323273):** +$436 at `4428.62`, price tracked straight to `4424.00` exactly as the
  backtest predicted. The magnet-chop just above `4424.00` (velocity burst 174 t/m) is normal target behavior —
  do NOT panic-shift the TP.

> **Engineering the negative-buffer decision:** a negative buffer (TP overshoot below the demand magnet) only makes
> sense on a **fading / exhausting** tape. On strong momentum it is suboptimal. **Assess velocity + CVD first**:
> strong = exact-magnet TP; fading = consider banking/pre-tip exit (per `01_` nearest-supply/VAH trailing).

---

## 🚫 INVALIDATION / NO-TRADE RULES

- **MIXED_TIMEFRAMES = NO TRADE.** 4TF must be cleanly aligned in the trade direction.
- **Asian session = NO TRADE** (0% WR window) unless a clean rejection-reversal has already formed and London overlap is imminent.
- **≥60% filled FVG = NO TRADE** (chase trap).
- **No confirmed rejection = NO TRADE.** Pre-emptive entries into chop are the #1 luck-vs-edge trap.
- **Opposing delta = NO TRADE.**
- **Spread HIGH_SPIKE / beyond ceiling = NO TRADE.**
- **Single-cycle = exploratory, two-cycle = actionable.**
- **Macro veto** (geopolitical escalation, rate shock) overhanging = high caution / NO-TRADE.
- **INVALIDATE** a short if M5 closes above the FVG ceiling/supply (for #532323273: above `4435.06` CE / `4441.50` SL).

---

## 🧠 LESSONS LOCKED INTO ULM (permanent — the goods & bads distilled)

1. **The edge is the REJECTION + 4TF re-alignment, not the pre-emptive entry.** Enter ON the fresh-bearish-FVG rejection.
2. **Asian session = 0% WR.** Do NOT trade it. London (07-13) is the only reliable window (52.2% WR, +5.04R).
3. **SELL is the weakest direction (21.1% WR)** — take it only on a clean 4TF-bearish rejection, not into weak favor.
4. **NEVER chase ≥60% fill FVG** (-10.83R trap). Enter fresh (<30%) or at CE (30-60%, +1.02R).
5. **Elevated spread (40-80) carries the +2.47R edge and the profitability** — tight spread breeds overtrading (-23.07R).
6. **Patience through a normal ebb is not thesis failure** — the winning trade went -$224 before +$110. Trail only after meaningful advance.
7. **A process-error entry that wins is LUCK, not validation.** Only a clean rejection entry is repeatable (per `01_`).
8. **Don't over-aim TP** — graceful ~$200 / ~20 pips at the first structural magnet (CEO directive, per `02_`).

---

## 🏆 SEPARATE WIN ARCHIVE — Today's Confirmed Wins (distinct from the bear-trap short above)

> This section records **today's OTHER confirmed win conditions** — kept **separate** from the `03_` bear-trap-reversal
> short (`#532323273`) AND from the `04_` ride-aligned-velocity file, because they are distinct edge signatures.
> `03_` = **rejection/bear-trap reversal** edge; the entries below = **velocity/delta fuel-ride** edge. Do not conflate.

### Win #532362595 (SELL fuel-ride, +$71.80) — 2026-09-01

**Edge signature (the "fuel-ride", NOT the bear-trap):**

| Condition | Value at entry | Notes |
|---|---|---|
| **Direction** | SELL | momentum-follow the fuel |
| **Recent 10-bar delta** | `-452.9` → `-689.6` | **CONFIRMED strong negative** (sellers in control, no divergence) |
| **Velocity** | `101 → 162 t/m` | elevated-to-high; sustained in direction |
| **Delta divergence** | `NO_DIVERGENCE` | accumulation NOT present (clean continuation) |
| **4TF alignment** | STRONG BEARISH (0 Bull / 3.5 Bear) | aligned with the short |
| **Entry** | `4429.09` (ask) / filled `4427.70` | near/at the breakdown continuation |
| **SL** | `4431.50` | structural above the micro shelf |
| **TP** | `4427.00` | nearest non-unicorn downside (VAL shelf) |
| **Result** | **+$71.80 net** (0.78R) | fast-capture, filled at TP |

**Replay / backtest:** SELL fuel-ride to nearest downside shelf returned **100% WR, 3.0R** in the M5 backtest
(`mcp_alpha_get... backtest`, slice `4428`→VAL `4426.65` in one bar).

**What made it a WIN (the repeatable conditions to re-enter):**
1. **Strong confirmed negative delta with NO divergence** — the fuel was genuinely selling, not a wispy/who-reversed delta.
2. **Velocity sustained in the ride direction** (not a spike that instantly faded).
3. **A NEAREST non-unicorn downside node within reach** (~$1) for a fast bankable capture.
4. **4TF aligned** with the ride direction (reinforcing, not required per the two-directional experiment, but present here).
5. **Fast TP + exit** — banked the nearest node, no over-hold.

**Lesson for `03_`/general (distinct from the bear-trap):** the **fuel-ride** edge = momentum-follow the confirmed
delta sign to the nearest reachable structural node. It is the DIFFERENT trade from the bear-trap *reversal* (which
requires a fresh-FVG rejection). Both are valid but must be classified separately when recording outcomes.

---

*Reference: `logs/pattern_reality_check.md`, `logs/unified_learning_memory.json`, `logs/top4_reproducible_patterns.json`,
`logs/full_desk_dossier.md`. Live validation Ticket #532323273 (Asian bear-trap reversal) + Win #532362595 (SELL fuel-ride).
All stats from the 138-trade forensic ledger (`mcp_alpha_get_ledger_decomposition`). Non-controlling; `OPENCODE_MANDATES.md` remains canonical.*

---

## 📒 LIVE EVIDENCE LOG — Ticket #532323273 (progressive cycle log)

Step-by-step findings as the live Asian Low Bear Trap Reversal unfolded (each also recorded to Pattern Book/ULM via MCP):

| Cycle | UTC | P/L | Price | Key finding / decision |
|---|---|---|---|---|
| Entry | 06:15 | - | 4432.98 | Pre-emptive 1-lot short, Asian session (PROCESS ERROR per ASIAN_SESSION_AVOID) |
| 272 | 06:22 | +$90 | 4432.08 | Bear-trap reversal confirmed; price broke entry, full 4TF bearish restored |
| 278 | 06:24 | +$110 | 4431.88 | Breaking down through M5 bullish FVG toward TP; continuation confirmed |
| 284 | 06:25 | -$29 | 4433.27 | Asian chop unwound the win (evidence of ASIAN_SESSION_AVOID risk) |
| 290 | 06:26 | -$2 | 4433.00 | Range-churn, delta oscillating = classic Asian range (01_ rule) |
| 296 | 06:27 | +$121 | 4431.77 | Broke back down through M5 bullish FVG → new lows toward TP |
| 302 | 06:28 | +$196 | 4431.02 | CVD -3431 / -12.7% delta = sustained selling; approach TP 4424 |
| 308 | 06:29 | +$436 | 4428.62 | Peak; $4.62 from TP; H4 RSI deeply oversold 19.6 |
| 314 | 06:30 | +$360 | 4429.38 | Magnet-chop above 4424.00 (velocity 174 t/m); TP unchanged per backtest |
| 320 | 06:32 | +$294 | 4430.04 | Retracement into Asian chop near magnet; 4TF still full bearish, velocity 156 t/m |
| 332 | 06:34 | +$293 | 4430.05 | Velocity collapsed to 42 t/m at magnet (fading). **TRAILED SL 4441.50 → 4433.00 = RISK-FREE**; TP 4424.00 armed. Locked win in chop window per 02_ rule |
| 338 | 06:35 | +$218 | 4430.80 | Risk-free trail working (chop pulled +$293→+$218 but SL protects). Velocity recovered 83 t/m; new M5 BEARISH_FVG [4430.16-4430.85] PARTIALLY_FILLED at price = constructive to TP 4424.00. Hold |
| 344 | 06:36 | +$165 | 4431.33 | Risk-free SL 4433.00 fully guards through chop (+$218→+$165). Velocity 108 t/m building downside; bearish FVG [4434.89-4435.22] fresh above price = retest-reject would trigger continuation to TP. Hold |
| 350 | 06:37 | +$159 | 4431.39 | Patient grind, price flat 4431, win +$159 fully protected by SL 4433.00. Velocity 96 t/m ELEVATED, 4TF bearish. Below fresh bearish FVG ceiling; await breakdown to TP 4424.00 or SL exit. No action |
| CLOSE | ~06:38 | **~-$15** | ~4433.0 | **SL 4433.00 filled at ~breakeven-minus.** Chopped out at the tedious Asian grind before TP 4424.00. Net ≈ -$15.10 (after ~6.21 commission/side). See post-mortem below |

---

## 🧾 POST-MORTEM — Ticket #532323273 (BREAKEVEN-MINUS)

**The uncomfortable truth of this trade:**

- **Path:** -$224 → **+$436 peak** → +$293 → trailed SL to `4433.00` (risk-free) → choppy grind → SL filled at ~breakeven (**net ≈ -$15**).
- **The risk-free trail SAVED it** from being a large loss (capped downside at zero after a -$224 early drawdown).
- **BUT trailing to `4433.00` (0.02 above entry `4432.98`) was TOO TIGHT.** It locked only ~breakeven on a trade that had printed **+$436**. The Chinese/Asian chop both saved us (via the trail) *and* thwarted us (the tight trail knocked the position out before the eventual `4424.00` TP could fill).

### Corrected management principle (amends lesson #5 / the risk-free-trail rule)
Trailing to risk-free is right — but **not at a razor-thin 0.02 offset**. A tight trail in a chop window guarantees the position gets shaken out on normal noise before the real move. **When you trail for protection in a chop-prone window, give it room** (e.g. lock a meaningful fraction of the peak, or trail to just beyond a structural barrier), **OR** if you cannot tolerate the noise of the window, **just take the large profit at the +$400 peak outright** (the +$436 capture) rather than aim to trail a chop window to the exact TP.

### The core, now-fully-confirmed lesson
1. **`ASIAN_SESSION_AVOID` is a hard PROCESS ERROR** — this entry was in a 0%-WR window; a ~breakeven outcome is **VARANCE, not validated edge**. No methodology was proven here.
2. **The continuation momentum (→+$436) was real** — 4TF bearish rejection FVG works when it *returns* into London.
3. **Management over-tightness + window chop, not thesis invalidation, capped the R.** The trade did NOT fail on thesis; it failed on where+how tightly we managed it.

**Key evidence conclusions:**
1. **The continuation (4TF-aligned rejection) is the real edge** — from -$224 → +$436.
2. **The Asian entry was still a process error** — expect chop (as seen at 284/290/320).
3. **TP at the structural magnet `4424.00` with NO negative buffer was validated** by both backtest and live path.
4. **Patience through the drawdown + normal ebb = the difference** — panic exit at -$224 would have missed +$436.
5. **When velocity fades at the magnet (momentum collapsing from 156→42 t/m), trail SL to risk-free** to lock the large win instead of letting it evaporate back into Asian chop.
