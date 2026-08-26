# Alpha-v1

Autonomous 24/7 Multi-Agent Quantitative Trading Desk & OpenCode CIO Brain Integration.

## 🚀 Features

- **5-Agent Local LLM Desk**:
  - `TechnicalAnalyst`: M15 RSI, MACD, and Ask/Bid tick posture.
  - `MultiTimeframeAnalyst`: H1, M15, M5 trend alignment matrix.
  - `OrderBlockEngine`: Daily Pivots ($PP, S_1, R_1$), Supply & Demand Order Block zones.
  - `COT/FundamentalAnalyst`: CFTC Managed Money positioning percentiles.
  - `Macro/NewsAnalyst` & `NewsShield`: DXY, VIX, RSS news & 30-min high-impact news freeze guard.
  - `BullBearDebater`: Bull vs Bear debate, RETAIL_TRAP_RULES audit, and conviction scoring ($0.0 - 10.0$).
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
