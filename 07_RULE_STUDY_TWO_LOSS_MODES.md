# Rule Study 07: The Two Distinct Loss Modes — Process-Perfect Wrong-Side vs No-Anchor Process Failure

> **Status:** NEW — extracted 2026-09-08 from the session post-mortem (balance 99,546.78). Diagnostic reference;
> non-controlling evidence. `OPENCODE_MANDATES.md` and `OPENCODE_CIO_THOUGHT_PROCESS.md` remain canonical.
>
> **Relationship to existing files (avoid duplication):**
> - `OPENCODE_CIO_THOUGHT_PROCESS.md` = the 3 forensic case studies (false breakdown, stale headline, premature panic cut).
> - `05_SPRING_INTO_SUPPLY_DELTA_QUANTIFIED.md` = the spring-into-supply entry gate (delta flip + placement) backtest.
> - `07` (this) = **loss taxonomy** — separates the two *opposite* ways trades bleed and the correction for each.
>   Failure mode A and failure mode B are mirror images; conflating them produces wrong fixes.

---

## THE CORE INSIGHT

Today's losses (win rate ~50%, negative net) all trace to **two opposite, non-overlapping failure modes**.
A single "be more disciplined" remedy is useless — the modes demand opposite corrections.

| Mode | Failure type | Correct fix |
|------|--------------|-------------|
| **A — Process-perfect, structurally wrong-side** | Entry *selection* error; rigid SL/TP honored | Don't touch the management; fix the **pre-trade bias veto** (macro share + 4TF) |
| **B — No-anchor, discretionary exit** | Process *abandonment*; no structural SL/TP, manual exit | Fix the **mechanics**: no entry without pre-defined structural SL/TP; NEVER manual close |

---

## MODE A — PROCESS-PERFECT, STRUCTURALLY WRONG-SIDE

### The trade (ticket 537492861, 2026-09-08)
- **Setup:** Spring-reclaim BUY 0.30 @ 4403.19; trigger M5 close >4402.50 + positive measured 10-bar delta after PDL 4381 sweep. SL 4393.5 / TP 4425. — **-294.02** at SL.
- **What was RIGHT (do not "fix" this):** The full pre-execution audit ran (regime context, live micro, measured CVD +1107 positive, no divergence). Dual-prong staging was correct (limit 4400.5 + breakout watch). The invalidation rule fired on 4TF flip + massive counter-delta (-1013.9 10-bar, a **-2200 counter-delta swing** in ~3 min) and the SL executed instantly, **no panic, no rescue, no trailing**. That behavior is the goal-state — it produced exactly the planned -$291 risk.

### What was WRONG — the entry-bias veto that was suppressed
- **4TF was BEARISH-leaning at entry** (H4/H1/M15/M5 all bearish) — a spring BUY is counter-trend by construction.
- **Macro share ≥50%** (audit oscillated 44–73% MACRO_DIRECTIONAL_PRESSURE; DFII10 2.43%, +2.2σ = bearish ceiling). Per Thought Process §1: when real yields >2.40%, macro controls 50–70% of pricing and *technical support will be overrun*.
- **Tier-2 research explicitly flagged it** (Perplexity: "counter-trend long into rising yields… edge is to fade… expect 4410–4417 rejection"). It failed exactly there.
- The tape read (GEOPOLITICAL_SHOCK_DRIFT 44–63%) was **transient**; the authoritative audit was 50/50–73% macro. I acted on the transient share and overrode the structural one.

### Rule-state (Mode A)
**MODE_A_CALIBRATION: RECOGNIZE MACRO OVERHANG ASYMMETRY WITHOUT PROHIBITING TRADES.** When (a) macro-yield share ≥50% (DFII10 ≥2.40, z≥2.0) AND (b) 4TF is bearish-leaning:
- Recognize that upside moves into overhead supply (POC/VAH/M15 FVG) face strong fundamental resistance.
- Trend fades at resistance offer higher asymmetry; however, counter-trend demand setups (Wyckoff Springs, sweeps of PDL) remain completely valid.
- Manage risk cleanly: size according to setup conviction (e.g. 0.10–0.25 lots), anchor structural SL strictly behind the sweep wick, and target realistic structural liquidity rather than holding for unreasonable targets.
- Never freeze the desk or veto trade ideas: allow the CIO full freedom to trade both momentum expansions and value fades with accurate context.

---

## MODE B — NO-ANCHOR PROCESS FAILURE (DISCRETIONARY EXIT)

### The trades (ticket 537087480 + the morning divergence long)
- **ticket 537087480** — SELL 0.2 @ 4391.87, manual "OpenCode CIO Exit" @ 4397.99 after 1h30m. **-123.63**.
  MT5 record shows **SL 0.0 / TP 0.0** — the position entered with NO structural invalidation anchor.
- Morning divergence BUY (from session context) — bought a BULLISH_DELTA_DIVERGENCE long that was already flagged as a *weak signal*; exited on the flush. **-358 (approx).**

### What was WRONG
- **No pre-planned SL/TP** on entry → all management became discretionary.
- **Manual market close** on a temporary adverse move = the forbidden Panic Kill (Thought Process Play 3's old-failure pattern) even when the exit "felt" measured.
- Discretionary exits are price-chasers: they always fill on the weak side of the noise (worst-case fills).
- Resulting R is undefined because risk was undefined at entry.

### Rule-state (Mode B)
**MODE_B_RULE: NO ENTRY WITHOUT A PRE-DEFINED STRUCTURAL SL AND TP ON THE ORDER.** If SL/TP cannot be objectively placed (behind a shelf / at a liquidity target), the trade is NOT a trade — it is a guess. Manual market exits are STRICTLY FORBIDDEN for active trades except where an objective trigger (mode-A invalidation) has genuinely fired; when in doubt, the answer is leave the pre-set SL to do its job.

---

## THE ASYMMETRY THAT TURNED 50% WR NEGATIVE

| Metric | Winners | Losers |
|--------|---------|--------|
| Size | 0.10 | 0.20–0.30 |
| Anchoring | (win was a full 2h ride, TP structure coherent) | Mode A anchored, Mode B no anchor |
| Exit | Target-based | Manual / SL |

**Losers ran at 2–3x the size of winners.** R-multiples inverted: a 50% win rate with 3x loser size ≈ negative expectancy. Fix: risk-fixed sizing (0.10 probe → 0.20 confirmation → 0.30 only with ≥2 TF + macro alignment) — **size must be a function of alignment, not conviction** (s4.137).

---

## CHECKLIST BEFORE ANY ENTRY (post-mode study)

```
1. REGIME: authoritative get_market_regime_context — note macro-yield share. If ≥50% + DFII10≥2.40: macro provides tailwind for shorts; longs require structural demand confluence (sweep of PDL/VAL) with strictly defined structural SL.
2. 4TF: get_symbol_conviction — note HTF trend; trade with trend on pullbacks or responsive mean-reversion at proven exhaustion.
3. ANCHORS: define structural SL + TP on the ORDER before entry. If neither is objectively placable -> no trade.
4. SIZE: Dynamic sizing (0.10 to 1.00 lots) scaled to setup quality and confluence.
5. EXIT PLAN: the ONLY exits are (a) pre-set SL, (b) dynamic TP calibrated to structural liquidity, (c) mode-A invalidation on recorded objective triggers.
   Manual panic market close = forbidden.
```

---

*Reference: `get_mt5_deals_history` (2026-09-08, account 1514551285), decision snapshots 13:53/14:23, Pattern Book `SPRING_RECLAIM_POC` entry, `logs/decision_snapshots.jsonl`. Non-controlling; `OPENCODE_MANDATES.md` remains canonical.*