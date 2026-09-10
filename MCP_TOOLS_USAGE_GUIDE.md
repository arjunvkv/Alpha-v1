# ALPHA DESK MCP TOOLS: COMPLETE DIRECTORY & USAGE GUIDE

This document is the definitive operational reference for all tools exposed by the Alpha FastMCP server (`alpha-daemon-mcp`). OpenCode utilizes these atomic tools to gather live intelligence, inspect broker status, evaluate order-flow microstructure, manage universal watches, and execute trades.

---

## 1. Quick-Start Workflow: Autonomous Reasoning Cycle

Every OpenCode wake cycle should proceed through this disciplined sequence:
1. **Mandatory First Action (Step 0)**: `get_market_regime_context(symbol='XAUUSD')` to audit live broker quotes, spread, raw tick velocity, CVD ratio, 4m interval displacement, and real yields.
2. **Account & Inventory**: `get_account_status()` and `get_pending_orders()` to check balance, margin, open tickets, and staged orders.
3. **Microstructure & Institutional Geometry**: `get_live_microstructure()`, `get_fvg_matrix()`, and `get_full_institutional_profile()` to locate precise order-book walls, unmitigated FVGs, Point of Control (POC), and Value Area (VAH/VAL).
4. **Macro Economic Gravity**: `get_fred_observations()` for factual Federal Reserve real yields (e.g. `DFII10`) and nominal rates (`DGS10`).
5. **Targeted Narrative Research (Proxima MCP Only)**:
   * Real-time financial headlines and central bank statements are queried strictly through **Proxima MCP** (`proxima_ask_perplexity`, `proxima_deep_search`).
   * **Research Protocol**: Maximum 2 Perplexity queries per investigation. Use deep research / crawl tools for underlying factual transcripts and numbers.
   * **Strict Prohibition**: Strictly NO probability-seeking queries (e.g. "what is the probability gold rallies to 4400?"). Only query factual events, actual economic releases, and central bank quotes.
6. **Pre-Planned Order Placement**: `place_pending_order()` (`BUY_STOP` / `SELL_STOP` / `BUY_LIMIT` / `SELL_LIMIT`) for front-running expansions or staging at institutional shelves.
7. **Universal Watch Arming**: `register_watch()` to alert the daemon if price crosses critical thresholds or volatility spikes.

---

## 2. Market Microstructure & Physical Telemetry Tools

### `get_market_regime_context(symbol: str = "XAUUSD", force_refresh: bool = False)`
* **Purpose**: Fetches real-time physical broker reality and raw kinetic metrics.
* **Returns**:
  * Live broker bid/ask and spread in points.
  * Tick velocity (`tpm` - ticks per minute).
  * 5-minute Cumulative Volume Delta (CVD) and 10-bar delta ratio.
  * 4-minute price displacement and direction.
  * Point of Control (POC), Value Area High/Low (VAH/VAL), and auction air pockets.
  * Real yield levels (`DFII10`) and multi-asset deltas.
* **When to use**: Mandatory first call on every OpenCode wake.

### `get_live_microstructure(symbol: str = "XAUUSD")`
* **Purpose**: Inspects deep Level 2 book structure and tick-level tape dynamics.
* **Returns**:
  * Current spread in points (`0.1` pt resolution).
  * 1-minute and 5-minute tick velocity.
  * Complete raw CVD metrics: buy volume, sell volume, net delta, and delta velocity.
  * DOM order book imbalance ratio, bid walls, and ask walls.
  * Absorption vs. exhaustion detection.
* **When to use**: Right before sizing and staging orders to confirm whether institutions are absorbing or steamrolling.

### `get_fvg_matrix(symbol: str = "XAUUSD")`
* **Purpose**: Identifies unmitigated Fair Value Gaps across multiple timeframes (H4, H1, M15, M5).
* **Returns**:
  * List of bullish and bearish FVGs with top, bottom, and Consequent Encroachment (50% CE) price levels.
  * Fill percentages and touch counts.
* **When to use**: To pinpoint exact structural shelves and high-probability invalidation anchors.

### `get_full_institutional_profile(symbol: str = "XAUUSD")`
* **Purpose**: Provides institutional volume profile and VWAP distributions.
* **Returns**:
  * Point of Control (POC).
  * Value Area High (VAH 70%) and Value Area Low (VAL 70%).
  * VWAP center line with ±1σ, ±2σ standard deviation bands.
* **When to use**: To assess whether price is trading in value or exploring discovery imbalances.

### `get_measured_cvd(symbol: str = "XAUUSD")`
* **Purpose**: Detailed breakdown of cumulative volume delta across multiple lookbacks.
* **Returns**: Delta ratios, bar-by-bar delta shifts, and divergence indicators against price action.

---

## 3. Macroeconomic Yields & External Research

### `get_fred_observations(series_id: str, limit: int = 100, vintage_date: str = "")`
* **Purpose**: Direct access to factual Federal Reserve Economic Data (FRED).
* **Key Series IDs**:
  * `DFII10`: 10-Year Real Yield (TIPS yield) — primary macro gravity driver for gold.
  * `DGS10`: 10-Year Nominal Treasury Yield.
  * `DGS2`: 2-Year Treasury Yield.
  * `T10YIE`: 10-Year Breakeven Inflation Rate.
* **When to use**: When evaluating whether real rates provide tailwinds or headwinds for gold pricing.

> [!IMPORTANT]
> **Zero RSS / Scraped News in Alpha MCP**:
> To eliminate retail news hallucinations, all RSS scrapers and GDELT discovery tools have been removed from Alpha MCP.
> All external narrative and breaking news research must be conducted via **Proxima MCP**:
> - Limit to **maximum 2 Perplexity queries** per session.
> - Query strictly for hard economic figures and official releases.
> - Never ask probabilistic questions.

---

## 4. Account, Inventory & Execution Tools

### `get_account_status()`
* **Purpose**: Reads live FTMO MetaTrader 5 account metrics.
* **Returns**: Balance, Equity, Free Margin, Margin Level %, Floating PnL, and Open Position Count.
* **When to use**: Before placing any order to verify margin safety and daily drawdown headroom.

### `get_pending_orders(symbol: str = "ALL")`
* **Purpose**: Lists all active pending orders on the broker book.
* **Returns**: Order ticket, symbol, order type (`BUY_LIMIT`, `SELL_LIMIT`, `BUY_STOP`, `SELL_STOP`), volume, price, current market distance, SL, and TP.
* **When to use**: On every wake to audit resting orders and replace or cancel outdated setups.

### `place_pending_order(symbol: str, order_type: str, price: float, volume: float, sl_price: float, tp_price: float, tag: str = "")`
* **Purpose**: Stages pre-planned pending orders on the MT5 terminal.
* **Parameters**:
  * `symbol`: Usually "XAUUSD".
  * `order_type`: `"BUY_STOP"`, `"SELL_STOP"`, `"BUY_LIMIT"`, `"SELL_LIMIT"`.
  * `price`: Exact trigger entry coordinate.
  * `volume`: Lot size (0.10 to 1.00 lot scaled based on confidence).
  * `sl_price`: Mandatory structural invalidation level.
  * `tp_price`: Target profit level (aligned with structural liquidity pools).
  * `tag`: Optional descriptor string.
* **When to use**: For front-running breakouts or placing structural shelf limit orders.

### `execute_trade(symbol: str, side: str, volume: float, sl_price: float, tp_price: float, comment: str = "")`
* **Purpose**: Immediate market order execution at live bid/ask.
* **Parameters**: `side` ("BUY" or "SELL"), `volume` (0.10 to 1.00), `sl_price`, `tp_price`.
* **When to use**: Only when immediate market entry is justified by confirmed catalyst momentum.

### `cancel_pending_order(order_ticket: int = 0, symbol: str = "ALL")`
* **Purpose**: Cancels pending orders. Specify `order_ticket` to remove a single order, or set `symbol="XAUUSD"` to cancel all pending orders for that symbol.

### `update_position(ticket: int, action: str, params_json: str = "{}")`
* **Purpose**: Dynamically adjusts SL or TP on active open positions.
* **Parameters**:
  * `action`: `"MODIFY_SL"`, `"MODIFY_TP"`, `"CLOSE"`.
  * `params_json`: JSON string e.g. `{"sl": 4350.50, "tp": 4362.00}`.
* **When to use**: To advance SL to breakeven or reposition SL behind newly formed structural shelves.

### `get_mt5_deals_history(days: int = 30, symbol: str = "ALL", limit: int = 100, position_id: int = 0)`
* **Purpose**: Historical log of broker deal executions, slippage, and closed PnL.

---

## 5. Universal 500ms Watcher Management Tools

The background daemon scans active persistent watches every 500ms against live MT5 tick data. When a condition triggers, it wakes OpenCode immediately.

### `register_watch(symbol: str, condition_type: str, target_price: float, instruction: str, reason: str)`
* **Purpose**: Arms a persistent 500ms watch trigger in `evidence_state.json`.
* **Condition Types**:
  * `PRICE_CROSS_ABOVE`: Fires when ask/bid crosses above `target_price`.
  * `PRICE_CROSS_BELOW`: Fires when ask/bid crosses below `target_price`.
  * `PRICE_TOUCH`: Fires when price comes within spread tolerance of `target_price`.
  * `VELOCITY_SPIKE`: Fires when tick velocity surges.
  * `SPREAD_SPIKE`: Fires when broker spread widens abnormally.
* **Parameters**:
  * `instruction`: Specific action to evaluate upon trigger (e.g. "Execute BUY_STOP if CVD is positive").
  * `reason`: Structural context for the watch.
* **When to use**: To monitor structural breakout gates without needing to poll continuously.

### `get_active_watches(symbol: str = None, include_closed: bool = True)`
* **Purpose**: Inspects all currently registered, active, and triggered watches.

### `update_watch(watch_id: str, status: str = "", condition: str = "", instruction: str = "", target_price: float = None, reason: str = "")`
* **Purpose**: Updates an existing watch definition or adjusts its target level.

### `cancel_watch(watch_id: str)`
* **Purpose**: Disarms and cancels a registered watch by its unique ID.

### `clear_completed_watches(symbol: str = None)`
* **Purpose**: Purges `TRIGGERED` and `CANCELLED` watches from the persistent state file.

### `mark_watches_observed(watch_ids: list[str])`
* **Purpose**: Batch marks triggered watches as acknowledged by OpenCode.

### `mark_evidence_read(evidence_ids: list[str])`
* **Purpose**: Batch marks evidence items as processed.

---

## 6. Pattern Book & Research Memory Tools

### `search_book(keyword: str, symbol: str = None)`
* **Purpose**: Targeted search across Pattern Book setup records.

### `get_book_index()`
* **Purpose**: Complete index of institutional trade setups and playbooks.

### `get_book_page(page_id: str)`
* **Purpose**: Inspects deep execution guidelines for a specific setup pattern.

### `record_decision_snapshot(snapshot_json: str)`
* **Purpose**: Persists pre-decision context and rationale before trade staging.

### `record_trade_observation(observation_json: str)`
* **Purpose**: Records post-trade execution metrics and lessons learned.

### `record_pattern_observation(pattern_json: str)`
* **Purpose**: Adds an observed market microstructure pattern into persistent memory.

### `backtest_thesis(query: str, symbol: str = "XAUUSD", timeframe: str = "M5", bars: int = 60, offset: int = 0)`
* **Purpose**: Replays empirical bar history to validate edge before committing capital.
