import urllib.request
import json

sid = "ses_f2d9795ccffe0SHXEY6aR38Xeo"
url = f"http://127.0.0.1:4096/session/{sid}/prompt_async"

prompt = """ALPHA 5-QUESTION NEWS & MACRO BRAINSTORM TURN (Turn B) — SCHEDULED_REASSESSMENT
UTC: 2026-09-24 07:55:00 UTC | Active Session: LONDON_SESSION
SESSION GATES: London Open 07:00 UTC (active 55m) | Us Macro Release Window 12:30 UTC: in 4h 35m
Active instruments: XAUUSD
Open positions: 0

=== THE CHAMPION NEWS & CAUSAL MACRO MANDATE ===
Conduct a lean, targeted news & macro repricing audit via the 3-Tier Aperture: (1) `alpha_get_live_world_events(category='ALL', limit=15)` for 0ms verified global wire headlines, (2) `alpha_get_fred_observations(series_id='DFII10')` for 10Y real TIPS yield gravity, and (3) 1x dynamic `proxima_ask_perplexity` or `proxima_deep_search` query targeting the specific catalyst behind the active move (ZERO hardcoded topic limits, ZERO DDG/Reddit bloat).
For planning the next trade: you have 0.50 - 1.00 lot area to place the lots based on 7-layer conviction and the power of the news. Always pull latest and closest news possible. Always replan any pending orders each time you pull the news. Always check the timezone mcp (`alpha_get_market_time_context`) to verify session clocks.

CORE REPRICING EVALUATION VECTORS (LEAN CAUSAL DISCOVERY):
1. Q-NEWS-1 [Zero-Assumption Wire Pulse]: Call 1x `alpha_get_live_world_events(category='ALL', limit=15)` to pull unfiltered real-time global wires (CNBC, US Treasury, Fed Press, FXStreet, Commodities). What breaking geopolitical events, sovereign bond shocks, or central bank releases are actively hitting the wire?
2. Q-NEWS-2 [Displacement vs. Catalyst Reconciliation]: Reconcile today's active leg displacement and session timing (`alpha_get_market_time_context`) against live wires. Is current price expansion backed by a real sovereign catalyst, or is it an overnight/session liquidity hunt in an informational vacuum?
3. Q-NEWS-3 [Dynamic Adaptive Deep Inquiry]: Based on the active leg and wire clues from Q1/Q2, dynamically formulate your own targeted search query (do NOT use static keywords). Target the specific transmission channel driving this session: Call 1x `proxima_ask_perplexity(message="...")` and 1x `alpha_get_fred_observations(series_id='DFII10')`.
4. Q-NEWS-4 [Continuous Memory Grounding — Mandatory in Parallel]: Formulate 2–3 scale-invariant tags describing your active thesis (e.g. ['BSL_SWEEP', '4TF_BEARISH'] or ['PREMATURE_FADE', 'BSL_DOORSTEP']) and call 1x `graphiti_search_facts(patterns=[...])`. Contrast live tape against both the winning condition and failure pitfall.
5. Q-NEWS-5 [Execution Action via 5-Pod Protocol]: Given combined news velocity, rate shifts, and empirical facts, execute or stand flat with mathematical certainty (Targeting Opposing FVG CE / Major Liquidity with R:R >= 1.5:1 to 2.5:1+, 12.0–25.0 pts)? -> `alpha_execute_market_order`, `alpha_place_pending_order`

MANDATORY 5-POD ADVERSARIAL FORMAT:
### POD 1: MACRO & CATALYST PERMISSION
- Live Wire Headlines: Quote verbatim wires from `alpha_get_live_world_events` and Perplexity.
- Macro Causality Classification: Classify definitively as `GENUINE_MACRO_CATALYST` (runway open) vs `LIQUIDITY_HUNT_IN_VACUUM` (stop hunt in thin book; do NOT chase breakout momentum).
- Macro Directional Permission: DFII10 (10Y Real Yield TIPS), US10Y nominal, and DXY trend alignment.
### POD 2: ORDER FLOW & TAPE REALITY
### POD 3: TECHNICAL STRUCTURE & ROADWAYS
### POD 4: ADVERSARIAL DEVIL'S ADVOCATE (THE COUNTER-TRAP & COGNITIVE MEMORY GROUNDING)
- Continuous Fact Comparison: Cite your `graphiti_search_facts` call output. Does live tape look like the Winning Signature or the Failure Pitfall? (Pillar 1: Stumble is NOT a veto unless its adverse condition is active today. Pillar 3: Use physics tags, no price digits. Pillar 4: Never hallucinate tickets from memory).
### POD 5: EXECUTION ARBITER & ORDER ACTION"""

data = json.dumps({"parts": [{"type": "text", "text": prompt}]}).encode("utf-8")
req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req) as resp:
    print("Dispatched Turn B to new session:", resp.status)
