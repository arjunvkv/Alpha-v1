# Alpha-v1

Autonomous 24/7 Multi-Agent Quantitative Trading Desk & OpenCode CIO Brain Integration.

## 🚀 Features

- **5-Agent Local LLM Desk**:
  - `TechnicalAnalyst`: Pure Market Structure, 4-TF Confluence (H4/H1/M15/M5), and Order Flow Velocity.
  - `MultiTimeframeAnalyst`: H1, M15, M5 trend alignment matrix.
  - `OrderBlockEngine`: Daily Pivots ($PP, S_1, R_1$), Supply & Demand Order Block zones.
  - `COT/FundamentalAnalyst`: CFTC Managed Money positioning percentiles.
  - `Macro/NewsAnalyst` & `NewsShield`: DXY, VIX, RSS news & 15-min high-impact news freeze guard.
  - `BullBearDebater`: Bull vs Bear debate, Institutional Risk audit, and conviction scoring ($0.0 - 10.0$).
  - `RiskOfficer`: Max 6.0% account heat limit, dynamic lot sizing, and past mistake memory audit.

- **Resilient OpenCode CIO Communication Engine**:
  - `is_opencode_idle()` Idle-State Latch guaranteeing zero prompt stacking or interruptions.
  - 100% continuous multi-agent dialogue logging to `live_story.log`.
  - FastMCP tool execution via `mcp_alpha_update_position` and `mcp_alpha_execute_trade`.

## 🛠️ Setup & Execution

```bash
# Start 24/7 Background Trading Daemon
python -u alpha_trading_desk.py run
```


## Agent decision authority

Alpha separates evidence from decisions.

- The Agent is the only trading decision-maker: BUY, SELL, WAIT, HOLD,
  CLOSE, REDUCE, REVERSE, timing, setup interpretation and conviction.
- Memory, Pattern Book, repeatability, promotion, watchlists, scores and
  historical outcomes are advisory evidence only.
- The daemon may observe and wake the Agent, but may not convert evidence
  into a trade-quality gate.
- Execution validates malformed actions and physical/broker executability;
  it must not silently replace an Agent ORDER with WAIT because of a learned
  pattern, score, repeatability threshold, R:R threshold, or historical loss.
- Novel setups are allowed. They are recorded as new evidence so the Agent
  can learn from their eventual outcomes.

Authority flow:

`market → record → learn → evidence → Agent decision → execution`

Never:

`market → learn/gate → pass/fail → automatic no trade`
