# LIBRARIAN J-BATCH FIX SPEC — I1-I6 REGRESSION RESIDUALS
*Target file: `C:\Trading\Alpha\tradingagents\librarian_agent.py` (563 lines) + `C:\Trading\Alpha\mcp_server\alpha_mcp_server.py` (status emission, optional)*
*Author: OpenCode CIO · Date: 2026-08-30 · Repro queries all captured live — acceptance tests re-run by OpenCode after fix.*

> **RESEND #2 — 2026-08-30 02:04 UTC+?** Re-issued at user's request. Verification status of disk targets on re-issue: `librarian_agent.py` mtime 01:45:05 (pre-spec, J-fixes NOT applied), `alpha_mcp_server.py` mtime 01:28:52 (I-round only). Four targets below are unchanged from pre-J state. After this resend, expected diff must touch all four blocks before the 12-query battery can pass.

---

## J1 — Capability phrasings bypass orientation (I5-partial) — CONFIRMED

**Repro:** `ask_librarian("What can you do?", "XAUUSD")` → theme `Tactical Alignment Synthesis`, templated "Primary requirement: Enter on 50% CE tap…" (should be orientation reply).

**Root cause — `answer_query` line 395:**
```python
if len(clean_q) < 3 or clean_q.lower() in ["?", "??", "???", "hello", "hi", "hey", "help", "who are you", "what can you do", "test"]:
```
Exact-match against a fixed list, **no punctuation normalization** — `"What can you do?"` (with `?`) ≠ `"what can you do"`. Also `"how can you help"`, `"capabilities"`, `"what do you know"` all miss.

**Fix (minimal, safe):**
1. Normalize before match: `norm = " ".join(clean_q.lower().split()).strip("?.!,:;")` and/or strip terminal punctuation.
2. Replace exact-list with a **startswith-or-contains phrase set**: `["hello", "hi", "hey", "help", "who are you", "what can you do", "capabilit", "what do you know", "what are you", "test"]` — check `any(norm == p or norm.startswith(p) or p in norm for p in phrases)`.
3. Keep the `len < 3` catch.
4. Orientation reply unchanged (already correct — matched 0, no confabulation).

**Acceptance:** J1-repro + `"help"`, `"help me"`, `"what can you tell me"`, `"capabilities"` → theme `Librarian Orientation & Capabilities`, `matched_evidence_count 0`, empty `top_4_precedents`.

---

## J2 — Evidence-retrieval intent misrouted to invalidation boilerplate (I1-partial) — CONFIRMED

**Repro:** `ask_librarian("Show me the most recent losing XAUUSD trade and the reason it failed", "XAUUSD")` → theme `Structural Invalidation & Risk Boundary` (3-rule boilerplate). Ledger holds the ticket (e.g. 530998080, −$299.06 in ~101s) but the librarian never retrieves it.

**Root cause — `answer_query` line 444:** the invalidation branch `["INVALID", "STOP", "FAIL", "REVERS", "TRAP", "WRONG", "LOSS"]` matches `losing` (LOSS) + `failed` (FAIL) and hijacks the query. There is **no evidence-retrieval branch** anywhere.

**Fix (new branch, ordered BEFORE the invalidation branch ~line 444):**
1. Detect retrieval intent: tokens like `["LAST TRADE", "MOST RECENT", "RECENT", "SHOW ME", "LOSING TRADE", "LOST TRADE", "WINNING TRADE", "PRINT", "MY TRADES", "STATS (single-trade case)", "WHY IT"]` in `q_upper`.
2. Query `self.db.experiences` for `market_context.symbol == sym`, sort by record timestamp (prefer `outcome.close_time` / `execution.time` / record key if timestamped) **desc**, filter the requested polarity (loss: `outcome.pnl < 0` or `"LOSS" in outcome.outcome`; win: `pnl > 0`).
3. Answer with the top record: ticket number, symbol, PnL, R multiple if stored, duration if derivable, and stored post-mortem/reason text if present (`outcome` / `notes` fields), plus: *"Full forensics: call `get_trade_forensics(ticket=<n>)`."*
4. If none found, say so honestly: `"No <polarity> experience record on file for {sym}."`
5. Update the invalidation branch guard so pure risk queries still hit it (it must NOT match when retrieval tokens are present — put retrieval branch first and `elif`).

**Acceptance:** J2-repro → returns ticket 530998080 (or whatever the newest loss is), PnL, reason; `"most recent winning trade"` → newest win; `"last trade"` (no polarity) → newest regardless of outcome. No change to `"What are the exact invalidation rules for a long?"` (still 3-rule answer).

---

## J3 — Same pattern ID renders opposite trigger directions (theme-driven) — CONFIRMED

**Repro:** rank-1 `VELOCITY ACCELERATION THROUGH MAGNET CONFIRMS BREAKOUT` (same ID) renders `execution_trigger: "XAUUSD M5_BEAR_FVG mitigation with delta exhaustion"` under `"COT bullish but price falling — short the breakdown?"` but `"XAUUSD M5_BULL_FVG …"` under `"predict exact price"` / `"invalidation rules"`.

**Root cause — `answer_query` lines 517–521:**
```python
market_state = {
    "symbol": sym,
    "fvg_type": "M5_BEAR_FVG" if any(k in q_upper for k in ["SHORT", "BEAR", "SELL"]) else "M5_BULL_FVG",
    "sweep_status": "YEST_LOW_SWEPT" if any(k in q_upper for k in ["SWEEP", "LOW"]) else "IN_RANGE"
}
```
The **query text** decides the FVG type injected into the Top-4 renderer (`LibrarianTacticalClassifier.slot_top_4` line 330 fallback / `_format_cand` line 325 fallback `f"{symbol} {fvg_type} mitigation with delta exhaustion"`), so one pattern can display opposite triggers depending on query keywords. Same class of root cause as the fixed I1 template latch: *query-theme → market-state coupling*.

**Fix (minimal, direction-stable):**
1. Do **not** derive `fvg_type` from query keywords for the Top-4 render. Use a direction-neutral placeholder (`"NONE"`) or the symbol's actual live FVG from MT5 state when available (spread/CE real values preferred).
2. Prefer the pattern's **stored** `trigger_condition` verbatim for `execution_trigger` (line 325 `cand.get("trigger_condition") or <fallback>` already does this — only when stored trigger is missing does the fallback leak the query-derived fvg_type). Ensure the fallback string uses `"structural FVG/OB mitigation"` (direction-neutral) instead of `{fvg_type}`.
3. Same for `sweep_status`: default `"IN_RANGE"` unless real live state says otherwise.

**Acceptance:** J3-repro (contradiction query vs invalidation query) → same rank-1 pattern shows the SAME stored trigger string both times; no `M5_BEAR_FVG`/`M5_BULL_FVG` flip for an identical pattern ID.

---

## J4 — Proxima status flaps ONLINE↔OFFLINE_STANDBY by path — CONFIRMED

**Repro:** orientation queries → `proxima_status: "ONLINE"`; analytic queries → `"OFFLINE_STANDBY"`, same session, seconds apart.

**Root cause:** `answer_query` line 392 calls `check_health()` once (0.8 s timeout) and:
- orientation path (line 408) reports `"ONLINE" if proxima_online else "OFFLINE_STANDBY"` — a health ping, **never an actual query**;
- analytic path (lines 501–514) reports `ONLINE` only if `query_proxima_tools` actually returns content, else `OFFLINE_STANDBY` — but the same `proxima_online` flag was the gate; a health-ok then request-timeout yields `OFFLINE_STANDBY`. Result: path-dependent, flaky signal.

**Fix:**
1. **Single determination:** call `check_health()` once, store in one local, reuse everywhere; or better — determine status from the *actual* Proxima interaction outcome only.
2. **Honest semantics:** `proxima_status = "ONLINE"` only when a real `query_proxima_tools` call returned content in this request; `"OFFLINE_STANDBY"` for health-fail OR health-ok-but-timeout. For orientation (no Proxima call made), report `"STANDBY"` neutrally (or skip the field) instead of `"ONLINE"` — a readiness ping is not a live research result.
3. (Optional) synchronize with `alpha_mcp_server.py` line 534 status text if it re-derives status.

**Acceptance:** Across a 12-query battery, `proxima_status` is either consistently `OFFLINE_STANDBY` (Proxima Desktop down) with the honest "request timed out" synthesis, or consistently `ONLINE` (Desktop up) — never path-dependent flapping.

---

## Re-verification battery (run by OpenCode after agent applies fix)
Same 8 + different 4:
1. `"What is the win rate for XAUUSD?"` → 20/61 (I2 determinism)
2. `"What are the exact invalidation rules for a long?"` → 3-rule semantic (I1)
3. `"COT is MAXIMUM_BULLISH but price is falling hard today"` → real dip-vs-short logic + **trigger string stability** (J3)
4. `"Predict the exact price of XAUUSD at 3pm tomorrow"` → Prediction Refusal
5. `"What does the GSR ratio (67.07) and positive real yield imply?"` → intermix semantic
6. `"hello"` → orientation (I5)
7. `"what can you do?"` → orientation (J1)
8. `"capabilities"` / `"help me"` → orientation (J1)
9. `"Show me the most recent losing XAUUSD trade and the reason it failed"` → real ticket + PnL + reason (J2)
10. `"Show me the most recent winning XAUUSD trade"` → newest win (J2)
11. `"Any stored precedents or win rates for XAGUSD silver?"` → XAGUSD-only, observed>seeded (I3/I4)
12. `"Any stored precedents or levels for USOIL.cash?"` → zero gold numbers (I3)
Plus status consistency scan across all 12 (J4).