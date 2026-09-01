# XAUUSD Ride-Aligned-Velocity + Nearest Fast-Capture — Micro-Momentum Scalping Strategy

> **Status:** Strategy playbook derived from a LIVE, **thrice-entered** fast-capture experiment
> (Tickets `#532338091` WIN, `#532339905` LOSS, `#532352006` SCRATCH) plus the full 138-trade forensic ledger
> + Proxima/ULM quantitative microstructure research. **Core principle: RIDE the velocity direction of MAXIMUM
> higher-timeframe alignment, and bank the NEAREST non-unicorn structural target FAST — WITHOUT GREED, WITHOUT
> over-management.** Net across the 3 experimental entries: `+75.90 −122 +7 = −$39.10`, but the experiment's
> real output is a now-validated, honest **conditional** edge: it wins on SUSTAINED negative-delta velocity and
> loses/scratches when that micro-fuel is absent (velocity-fade, wispy/instant-reverting delta).
> Non-controlling evidence — does not override `OPENCODE_MANDATES.md`, the canonical Agent rule & study mandate.
> This is the **4th strategy file**, complementing:
> - `01_MICRO_PROFIT_SCALPING_STRATEGY.md` (historical hold-to-tip archive)
> - `02_XAUUSD_CE_IN_DIRECTION_STRATEGY.md` (direction-agnostic CE entry)
> - `03_ASIAN_BEAR_TRAP_REVERSAL_STRATEGY.md` (session-discipline + rejection-continuation)

---

## 🎯 CORE OBJECTIVE

Take a **1-lot XAUUSD scalp** that **rides the velocity direction with the MOST higher-timeframe
(HTF) alignment**, entering on an aligned continuation/velocity read, and **exit at a NEAREST
non-unicorn structural target for a ~$100 fast-capture — NO greed, NO trailing-tightening, fast TP+exit.**

> **⚠️ RE-SCOPED TARGET (per CIO decision, post-experiment):** Target **~$100 wins** (a smaller, realistic,
> quickly-relevant fast-capture ≈ $1.0 move on 1.0 lot) instead of chasing ~$300. **Smaller, faster, bankable
> wins that avoid the velocity-fade surrender we just took on `#532339905`.** Combined with a hard
> **VELOCITY-GATE**: only trade/keep the ride while 5-min velocity is sustained in the direction
> (≥ ~90 t/m) and the tape is NOT printing counter-structure in the entry's way. When velocity raises,
> re-enter the experiment; when it collapses into chop, stand down.

> **⚠️ THE LESSON THAT BIRTHED THIS FILE (from Ticket #532323273 treatment):**
> We let a **+$436 winner** (6.4R) round-trip back to **~breakeven-minus** by trailing the SL to a
> razor-thin `4433.00` (0.02 above entry) in a chop-prone window. That taught the negative lesson:
> **when a winner prints a large profit, either (A) bank it at the profit peak outright, or (B) trail to a
> structural level with real room — NEVER lock to a razor-thin offset that guarantees a noise shakeout, and
> NEVER aim for a "unicorn" TP in a chop window.**
>
> The **positive lesson (the two wins below):** riding aligned velocity to a **nearest, non-greedy,
> structural** target with a **fixed fast TP + exit** (no trailing) captures the win cleanly and repeatably.

---

## ✅ THE THREE LIVE EXPERIMENTAL ENTRIES (Win / Loss / Scratch)

### Win #1 — Ticket `#532338091` (ride HTF-aligned velocity, nearest fast TP)
| Field | Value |
|---|---|
| **Setup** | SELL riding high velocity (`140 t/m`) downside with **H4+H1 BEARISH** alignment; entry at an **exhausted 72.7%-filled M5 bearish FVG** rejection zone |
| **Backtest (dir. confirm)** | **100% WR, 3.0R** short (entry `4435.44`, SL `4438.50`, TP `4432.26`) |
| **Nearest non-unicorn TP** | `4432.30` — top of the **M5 bullish-FVG liquidity pocket** `[4430.16-4432.64]` (real node, NOT a round number) |
| **SL** | `4438.50` — structural, above the FVG high `4438.47` |
| **Result** | **TP_HIT** — entry filled `4433.02` (lower than planned as price moved), exit `4432.30` = **+$75.90 net** (0.72R, no greed) |

### Loss #2 — Ticket `#532339905` (full 4TF alignment, VAL fast TP) — the honest counter-example
| Field | Value |
|---|---|
| **Setup** | SELL riding high velocity (`162 t/m`) downside with **FULL `4TF_STRONG_BEARISH_CONFLUENCE`** (H4/H1/M15/M5 all BEARISH); 10-bar delta `-1275.9`, pressure `-14.2%` |
| **Backtest (dir. confirm)** | **100% WR, 3.0R** short (entry `4429.48`, SL `4430.50`, TP `4426.42`) |
| **Nearest non-unicorn TP** | `4426.50` — **VAL pocket `4425.50-4426.80`** (Value-Area-Low shelf; proxima: 74.2% WR fast-capture vs 36.8% waterfall) |
| **SL** | `4432.50` — **TOO WIDE** relative to the ~$3 target (≈1.1R ratio underperformed vs the backtest's tight `4430.50`) |
| **Path** | -$56 → +$87 → +$11 → -$45 → -$64 → **closed -$122 on structural invalidation** |
| **Outcome** | **LOSS -$122.00 net (-1.22R)** |

### Scratch #3 — Ticket `#532352006` (velocity + wispy-negative delta; disciplined cut)
| Field | Value |
|---|---|
| **Setup** | SELL riding velocity (`129 t/m`) with **`4TF_STRONG_BEARISH_CONFLUENCE`**; price below VWAP (`BELOW_1SD`); delta turned `-23.5` (negative) |
| **Backtest (dir. confirm)** | **100% WR, +3.0R** short (London-open high-velocity → immediate non-unicorn liquidity pool) |
| **Nearest non-unicorn TP** | `4428.80` — nearest ~$100 fast-capture above the VAL `4427.49` (~$1.2 move, no greed) |
| **SL** | `4432.20` — too tight vs target (≈0.6R) |
| **Path** | Filled `4430.65` (adverse fill) → delta flipped `+92` (accumulation) within minutes → price pressed `4431.26` toward SL → **cut on structure** `4430.58` |
| **Outcome** | **SCRATCH +$7 net** (avoided a -$155 SL print) |

> **🔑 THE DISCIPLINED-CUT LESSON (from #3 `532352006`):** The micro-delta at entry (`-23.5`) was a **wispy
> negative** that instantly reverted to accumulation. When the **delta flips positive** (or price presses toward
> SL instead of the target) with a tight fast-capture TP, **cut on structure immediately** — a scratch/disciplined
> exit beats a large SL print. A faint barely-negative delta is NOT sufficient to ride.

### ⚠️ THE THREE-WAY CONTRAST — what actually decides the outcome

| Factor | Win #1 (`532338091`) | Loss #2 (`532339905`) | Scratch #3 (`532352006`) |
|---|---|---|---|
| **Velocity after entry** | Sustained → straight to TP in 1 bar | **Died to 13 t/m**; whipsawed 3× | Faded 129→~90, delta flipped to buy |
| **Delta** | Strong negative (`-1275.9` @ entry) | Strong negative (`-1275.9`) held | **Wispy `-23.5` → instantly `+92` (accumulation)** |
| **Counter-structure** | None | New bearish FVG above filled | Price pressed toward SL, not target |
| **SL** | Structural `4438.50` | Too wide `4432.50` | Too tight `4432.20` (≈0.6R) |
| **Result** | **+$75.90 TP_HIT** | **-$122 structural exit** | **+$7 disciplined cut** |

> **🔑 THE REFINED RULE (corrects the recipe):** riding aligned velocity to a nearest fast TP **wins ONLY while
> (a) velocity is SUSTAINED in the ride direction AND (b) a STRONG, confirmed NEGATIVE delta is holding**. It
> loses when the micro-fuel dies/fades into a counter-structure; it scratches when the delta was only *wispy* and
> reverted. If velocity collapses **or** delta flips positive **or** the tape prints a counter-FVG above a short —
> **CUT on that structural signal immediately**, do NOT wait for the VAL/SL. Do NOT hold a fading-momentum short
> through chop hoping it "finds" the target — that is the exact `532323273` + `ASIAN_SESSION_AVOID` failure context.
>
> **Add a velocity-gate:** only take/keep the ride while 5-min velocity is ≥ ~90 t/m in the direction. When it collapses below that into a chop window, exit on structure rather than hold the whip.
>
> **🔑 REFINED ENTRY (from `#532352006` scratch):** Do NOT enter on a *wispy* barely-negative delta (−23.5). Require a **STRONGER, confirmed initial negative delta (≤ −50, ideally toward −260)** that **holds for 1–2 bars** before entry. A faint negative that instantly reverts to accumulation = the velocity-fade trap; cut on structure the moment (a) delta flips positive OR (b) price presses toward SL instead of the target. With a tight fast-capture TP, a delta-reversal is grounds to cut immediately (a scratch beats a −155 SL print).

---

## 🧭 THE REPEATABLE FORMULA (the experiment's recipe)

1. **Find the MOST-aligned velocity direction.** The direction where the HIGHER timeframes align
   (H4+H1, or ideally all four H4/H1/M15/M5) AND the recent delta supports it.
   - Full `4TF_STRONG_BEARISH_CONFLUENCE` = strongest short bias.
   - Support with **recent 10-bar delta negative + negative delta pressure** (sellers in control).
   - **CRITICAL (post-#3): the negative delta must be STRONG (≤ −50, ideally toward −260) and HOLD for
     1–2 bars** — a wispy −20 to −30 that instantly reverts is NOT confirmable fuel; it is the velocity-fade
     trap and will flip to accumulation.
   - Confirm with **backtest only for directional confirmation** (never to set greed targets).
2. **Enter on aligned continuation / velocity** (ride it, don't chase a fresh reversal that hasn't triggered).
   - High velocity `>120 t/m` (velocity spike) in the aligned direction.
   - Avoid UNALIGNED entries (e.g. Asian chop against HTF).
3. **Target the NEAREST non-unicorn structural pocket**, NOT a round number, NOT a far "unicorn" TP:
   - Nearest M5 bullish-FVG liquidity pocket, **or** nearest **VAL (Value Area Low) shelf**, **or** nearest
     prior M15 swing low / equal-lows / resting-stop cluster.
   - **~$3.00 range on XAUUSD ≈ ~$300 on 1.0 lot.**
   - Proxima empirical: fast-capture to VAL ≈ **74.2% WR / +0.98R**, vs extended waterfall ≈ **36.8% WR / -0.12R**.
4. **Fast capture + exit — NO GREED, NO TRAILING-TIGHTENING.** Place a fixed TP at the nearest node and
   **let it fill and bank**. The whole point is to NOT over-stay and NOT get shaken out by a tight trail.

---

## 🚫 FAILURE TRAPS TO AVOID (from Proxima/ULM + our live lessons)

- **The Velocity-Extension/Waterfall Trap:** assuming an active velocity surge will "indefinitely" push through
  passive limit bids. As price reaches the VAL/liquidity node, algorithmic limit buyers absorb the selling,
  causing rapid 3–5 pt snap-back wicks that erase unbanked gains. → **Always book the nearest fast TP.**
- **Chasing a ≥60% filled FVG` (-10.83R trap)`:** entering into an already-fill-exhausted FVG as momentum chase.
  Enter on the aligned continuation read, not a late chase.
- **Trading AGAINST HTF alignment** (e.g. shorting when H4/H1 are bullish) — the velocity ride only has edge
  when riding WITH the most-aligned direction.
- **Razor-thin risk-free trailing in a chop window** (the `532323273` error) — either bank the peak outright
  or trail to a structural level with room; never a 0.02 offset.
- **The Wispy-Delta Trap (the `532352006` scratch):** entering on a barely-negative delta (−20 to −30) that
  instantly reverts to accumulation. Require a **confirmed strong negative delta (≤ −50, holds 1–2 bars)**.
- **"No directional backtest confirmation"** — always validate direction with the backtester first.

---

## 🔄 TWO-DIRECTIONAL FUEL-AGNOSTIC EXPANSION (cycle 568, per CIO "experiment both directions despite alignment")

> **The insight that motivated this:** in the `532352006` scratch, the *velocity* was high (129 t/m) but it was
> **buy-injected fuel** — the elevated tick rate was dominated by the aggressive BUY side, and my `-23.5` delta was
> just a weak echo of sellers (within minutes it flipped `+92`). The recipe was only looking at **sell-fuel**. The
> mirror image — a **confirmed POSITIVE-delta buy-injection** — is a symmetrically-tradeable ~$100 fast-capture.

**New rule:** ride the direction of **CONFIRMED directional fuel** (the delta sign is the true fuel, not the velocity
number alone and NOT the HTF alignment). Capture **BOTH directions** — buy-fuel long AND sell-fuel short — regardless
of 4TF alignment, provided the **nearest ~$100 node is actually within reach** (~$1-2 move).

The gate (both legs, symmetric):
| Leg | Velocity | Delta (confirmed, holds 1-2 bars) | Nearest ~$100 node |
|---|---|---|---|
| **BUY-fuel** | ≥ 90 t/m | ≥ **+50** (positive accumulation) | within ~$1-2 from structural support |
| **SELL-fuel** | ≥ 90 t/m | ≤ **−50** (negative sell-down) | within ~$1-2 from structural supply/rejection |

**Guardrails (counter-trend expansion is riskier, needs MORE discipline, not less):**
- **NEVER bottom-pick / top-pick counter-trend into a FAR node** — a nearest-node capture needs the target close.
  The cycle-568 BUY-fuel delta was strong (+667) but price was at range bottom, below VWAP, and the nearest upside
  node (4435.22) was $6 away = a counter-trend chase into the EXHAUSTED_FVG_TRAP. **Not a clean long.**
- Same confirmed-delta rule as the short leg: a wispy delta that instantly reverts is the velocity-fade trap in EITHER direction.
- Fast TP + exit both legs; **cut on structure** the moment the delta flips against the entry direction.

**Status:** experiment OPEN, both directional watches armed (see `logs/unified_learning_memory.json`
`TWO_DIRECTIONAL_FUEL_FAST_CAPTURE`). Not yet live-entered — neither leg has met the full gate (fuel + nearest node)
simultaneously so far.

---

## 🎯 TAKE-PROFIT & MANAGEMENT (the amended, corrected rules)

- **TP = NEAREST non-unicorn structural node** (M5 bullish-FVG liquidity pocket, VAL shelf, prior swing low),
  targeting a **~$100 fast-capture** (≈ $1.0 move on 1.0 lot) — **NO greed, fast TP + exit.**
- **⚡ STANDING RULE — VELOCITY-CALCULATED TP (per CIO "calculate TP based on velocity … surely hit to capture more"):**
  set the TP from the **sustained velocity magnitude**, targeting the point the current momentum will *actually reach*,
  NOT the minimal nearest node (which leaves money on the table, as on `#532362595` +$71.80 when velocity hit 162 t/m):
  - **Velocity-mapped downside impulse targets** (XAUUSD, net of ~45pt spread):
    - ~90–120 t/m → next VAL / breakdown shelf (~$1–2 ≈ $100–200)
    - ~120–160 t/m → velocity shelf +0.5 zone (e.g. `4424`, ~$3.5–4 ≈ $350–400)
    - **>160 t/m (confirmed strong directional delta, no divergence)** → backtest-validated full extension
      (e.g. `4420` / 3R objective, ~$5+ on 1.0 lot ≈ $500+)
  - **Key:** the velocity TP is still a **real structural shelf / backtest node**, not a round-number unicorn — it is
    the reachable continuation objective the momentum supports. Do NOT cap it at ~$100 when velocity is elevated.
  - Correlate with the measured 10-bar delta: only take the velocity-extended TP when the directional delta is
    **confirmed strong** (≤ −50 sell / ≥ +50 buy) with **no divergence** — else drop back to the nearest ~$100 node.
- **~$100 target, NO greed:** ONLY when velocity is moderate (~90–120 t/m) and the nearest node is close. When fuel
  (delta) + velocity are strong, use the velocity-calculated TP above — extension is disciplined, not greedy.
- **⚡ STANDING RULE — HARD-TP IS A $ DOLLAR TARGET, NOT A PRICE BAND (corrected on `#532392198` +$100):**
  when the directive is a "hard $X TP" (e.g. $100), translate it to a **price = entry ± (X_dollars / 10) for a
  1.0-lot XAUUSD** (1.0 lot = ~$10 per 1.0 point, so 10 points ≈ $100 gross). A "hard $100 TP" therefore sits
  ~10.0 pts from entry, NOT at some distant fixed band integer. Example: BUY @4419.64, hard $100 TP ⇒ `4429.60`
  (NOT `4431`, which was ~$1100 away and over-aimed). Setting a $100-intent as a $1100-away price means the order
  may never fill at the intended profit or hands the read to a manual close. **Always derive the TP price from the
  dollar target: TP_price = entry ± (target_dollars / 10).**
- **⚡⚡ STANDING RULE — COUNTER-TREND BUY ENTRY GATE (the REAL fix from `#532393819` -$211, refines the
  "hold-through-ebb" rule):** the hard-$100 TP conversion was correct engineering; the repeated BUY-leg losses
  (`#532389722` -$221, `#532393819` -$211) were **ENTRY-VALIDATION failures**, not TP failures. **Do NOT enter a
  counter-trend long on a strong-bearish tape unless ALL THREE confirm BEFORE entry:**
  1. **Structural low INTACT** — the support/sweep low is holding (NOT broken below entry).
  2. **Delta POSITIVE-inflecting** — recent 10-bar delta turning UP toward/above 0 (confirmed buy-fuel absorption,
     not merely "improving" while still strongly negative).
  3. **Displacement UP off support** — a higher-low displacement / reclaim above a structural level (e.g. the
     nearest FVG CE or prior low), NOT a resting-bid bottom-pick.
  - `#532393819` FAILED all three: entered @4419.45 on improving-but-still-negative delta while the `4418-4419` low
    IMMEDIATELY broke (→4417.73) into a 157→241 t/m selling burst. That was **bottom-picking into a breakdown**.
  - **"Hold through the ebb / do not cut on first drawdown" applies ONLY while the structural low+thesis HOLDS.**
    When the low BREAKS and selling re-bursts, the reversal is DEAD — cut on that structural invalidation
    immediately (do not hold to SL+breakdown).
  - **If the counter-trend BUY gate is NOT met (low broken, delta still deeply negative, no displacement up),
    STAND DOWN — do NOT force the retest.** A fresh M15/M5 FVG overhead + waterfall velocity = no long.
  - When the gate IS met, use the corrected hard-$100 TP (entry +10pts) and hold for it.
- **Fixed TP + fast exit — do NOT trail-tighten** into a fast-capture scalp. The SL alone defines downside.
- **Enter with the SL structural** (above the FVG high / micro displacement shelf / lower-1σ band). Prefer a
  **~1:1 RRR** (not a tight 0.6R) so a faint misread doesn't force an early scratch — the `532352006` SL `4432.20`
  was too tight relative to its `4428.80` TP.
- **Patience through entry noise:** a -$56 adverse wick at entry (0.16R) is NORMAL — do not panic-exit on
  the first drawdown if the SL is intact and alignment holds (validated twice).
- **CUT on micro-fuel loss (the disciplined rule):** if the **delta flips positive (accumulation)** OR
  velocity collapses (<~60 t/m) OR price presses toward the SL instead of the target **— exit on structure
  immediately**, do not wait for the SL. A scratch beats a large SL print.

---

## 📈 BASE-RATE SUPPORT (from 138-trade ledger + precedents)

- **London session (07-13 UTC)** ≈ 52.2% WR, +5.04R — the reliable window; avoid Asian 0%-WR chop for entries.
- **Full 4TF confluence** = strongest institutional alignment to ride.
- **Backtest on both live setups returned 100% WR / 3.0R** riding aligned velocity to a tight structural target.
- **Proxima fast-capture vs waterfall:** 74.2% / +0.98R vs 36.8% / -0.12R → **nearest fast TP beats greed.**

---

## 📒 LIVE EVIDENCE LOG (progressive — appended each cycle)

| Ticket | Cycle | P/L | Price | Key finding / decision |
|---|---|---|---|---|
| 532338091 | Entry | - | 4433.02 | SELL riding H4+H1 bearish velocity, exhausted FVG rejection; nearest fast TP 4432.30 |
| 532338091 | Close | **+$75.90** | 4432.30 | **TP_HIT** — banked nearest non-greedy target, fast exit. Validation #1 |
| 532339905 | Entry | -$56 | 4430.53 | SELL full-4TF velocity; entry noise into micro shelf; SL 4432.50 / TP 4426.50 |
| 532339905 | Cycle418 | -$12 | 4430.07 | Recovery — held through -$56 noise, did NOT panic-exit |
| 532339905 | Cycle424 | **+$87** | 4429.08 | In profit; holding to nearest VAL TP 4426.50, no trailing |
| 532339905 | Cycle436 | -$45 | 4430.40 | 2nd drawdown; velocity collapsed 13 t/m; flagged velocity-fade risk, kept SL |
| 532339905 | Cycle442 | **-$122** | 4431.17 | **STRUCTURAL EXIT** — new M5 bearish FVG `[4430.18-4432.64]` formed above & filled; cut on invalidation, did not hold whip. **LOSS validation #2** |
| 532352006 | Cycle536 | **+$7** | 4430.58 | **SCRATCH w/ disciplined EXIT** — entered on velocity 129 + delta -23.5, but delta immediately flipped positive (accumulation) & price pressed toward SL; cut on structure (+7 vs woulda -155 SL). **Turned 3rd entry into a scratch, not -$155. Lesson: require STRONGER, confirmed negative delta (≤-50, hold >1-2 bars), not a wispy -23.5** |
| 532362595 | Cycle604 | **+$71.80** | 4427.00 | **WIN at TP (SELL, 1.0 lot)** — first live test of TWO-DIRECTIONAL fuel-agnostic experiment SELL leg: confirmed sell-fuel (delta -452→-541, velocity 101→162 t/m, NO divergence, 4TF strong bearish). Supplied near TP 4427.00 filled 4427.00 for +$71.80 net. CIO requested raise TP by velocity (162 t/m) — arrived after fill; the velocity-justified 4424/4420 would have been ~$370-590. **Lesson: scale TP up with velocity when fuel confirmed.** |
| 532389722 | Cycle730 | **-$221.00** | 4420.0 | **BUY leg LOSS — process error (premature tight cut).** Entered 1.0 @ 4422.21 on 'good signs of improvement' (delta -854→-476, oversold RSI recovery, deep-sweep bear-trap). Price rolled back, velocity elevated-selling, sweep re-deepened. I cut at -$51/-221 on first drawdown instead of giving the reversal room to reach the ~$100 zone. Executed at 4420.0 (-$221). **LESSON: do NOT cut a counter-trend reversal buy on first drawdown if the structural low/SL is intact — give it room to reach the target ($100 zone).** |
| 532392198 | Cycle752 | **+$100.00** | manual | **BUY leg RETEST WIN — closed MANUALLY by CIO at +$100.** Entered 1.0 @ 4419.64 (SL 4416.50). My TP input (4431) was WRONG as a fixed price (~$1100 away = over-aim). CIO's 'hard $100 TP' = $100 PROFIT capture. Correct conversion for 1.0-lot XAUUSD: TP_price = entry ± dollars/10 → for +$100 from 4419.64 ⇒ ≈4429.60. CIO closed manually at +$100 = correct target. **VALIDATED: hard-TP directives are $ PROFIT targets, NOT fixed far price points.** Low 4418-4419 held; reversal ran to the $100 capture. |
| 532393819 | Cycle774 | **-$211.00** | 4417.34 | **BUY retest2 LOSS — entry-validation failure (the REAL fix).** Entered 1.0 @ 4419.45 (SL 4416.50, TP 4431.20 corrected-$100). The 4418-4419 low BROKE immediately (4417.73), ASIAN_LOW_SWEPT -9.95, velocity 157→241 t/m selling burst, fresh M15 bearish FVG overhead. Cut on structural invalidation -211. **LESSON: the -$211 AND -$221 were ENTRY gate failures (low not held + no positive-delta flip + no displacement up = bottom-picking into breakdown), NOT TP failures. Correct counter-trend BUY requires ALL THREE before entry; else STAND DOWN.** |
| 532397864 | Cycle816 | **+$883.83** | 4406.70 | **SELL-fuel ride WIN (TP_HIT, +$884 gross / +$883.83 net) — the CORRECT side to have taken sooner (per CIO 'why not sell').** Entered 1.0 @ 4415.54 WITH confirmed sell-fuel: recent delta -2208/-21.2% NO divergence, 4TF BEARISH_ALIGNED 0/4, fresh M15 bearish FVG [4423.12-4425.68] supply overhead, price in breakdown. Hard $100 TP 4406.70 (ask-derived). Price flew straight down 4415→4407 over ~4 cycles (velocity 258 t/m HIGH_INSTITUTIONAL_BURST, ASIAN_LOW_SWEPT -20.46, M5 RSI 29.8) → **TP_HIT 4406.70**. Balance 98358.86 → 99242.69 (+$883.83). **VALIDATION: riding WITH the dominant fuel beats fading it — the same tape that produced -$221/-$211 forced-buys produced +$884 riding the SELL.** |

---

*Reference: `logs/pattern_reality_check.md`, `logs/unified_learning_memory.json`, `logs/top4_reproducible_patterns.json`,
`logs/full_desk_dossier.md`. Live experimental entries: Win `#532338091` (+$75.90 TP_HIT), Loss `#532339905` (-$122
structural exit), Scratch `#532352006` (+$7 disciplined cut) — net `-$39.10` across the 3, refining the conditional
edge. All stats from the 138-trade forensic ledger + Proxima/ULM quantitative microstructure research. Non-controlling;
`OPENCODE_MANDATES.md` remains canonical.*
