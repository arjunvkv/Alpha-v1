# ALPHA DESK MCP TOOLS: COMPLETE DIRECTORY & USAGE GUIDE

This document is the definitive operational reference for all tools exposed by the Alpha FastMCP server (`alpha-daemon-mcp`). OpenCode utilizes these atomic tools to gather live intelligence, inspect broker status, evaluate order-flow microstructure, manage universal watches, and execute trades.

---

## 1. Quick-Start Workflow: Autonomous Reasoning Cycle

Every OpenCode wake cycle should proceed through this disciplined sequence:
1. **Clock & Session Awareness**: `get_market_time_context()` to verify synchronized UTC, New York, and London trading hours.
2. **Account & Inventory**: `get_account_status()` and `get_pending_orders()` to check balance, margin, and staged orders.
3. **90% News & Macro Catalysts**: `get_direct_news()`, `search_market_news()`, `get_live_world_events()`, and `get_fred_observations()` to gather all wire drivers and real yields.
4. **10% Microstructure & Execution Coordinates**: `get_live_microstructure()`, `get_fvg_matrix()`, and `get_full_institutional_profile()` to locate precise entry shelves, invalidations (SL), and TP targets.
5. **Pre-Planned Order Placement**: `place_pending_order()` (`BUY_STOP` / `SELL_STOP`) for front-running expansions when the time is right.
6. **Universal Watch Arming**: `register_watch()` to alert the daemon if price crosses critical thresholds.

---

## 2. Market Microstructure & Physical Telemetry Tools

### `get_market_regime_context(symbol: str = "XAUUSD", force_refresh: bool = False)`
* **Purpose**: Fetches real-time physical broker reality and econometric variance metrics.
* **Returns**:
  * Live broker bid/ask and spread in points.
  * Tick velocity (`tpm` - ticks per minute).
  * 5-minute Cumulative Volume Delta (CVD) and 10-bar delta ratio.
  * 4-minute price displacement and direction.
  * Point of Control (POC), Value Area High/Low (VAH/VAL), and auction air pockets.
  * Real yield levels (`DFII10`) and multi-asset deltas.
* **When to use**: To get an instant snapshot of broker tape conditions.

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

### `get_symbol_conviction(symbol: str = "XAUUSD")`
* **Purpose**: Multi-timeframe trend alignment and institutional positioning.
* **Returns**: EMA alignments (H4/H1/M15/M5), RSI momentum regimes, and latest CFTC COT Managed Money net positioning.

---

## 3. News, Macro & World Intelligence Tools (90% Weight)

### `get_direct_news(max_items: int = 20)`
* **Purpose**: Retrieves the latest rotating wire news feeds ingested by the desk.
* **Returns**:
  * Classified news categories: `[MACRO & GEOPOLITICAL]`, `[MICRO & COMMODITY FLOW]`, `[OTHER & CROSS-MARKET]`.
  * Verbatim headlines, publication timestamps, and source URLs.
* **When to use**: Every analysis cycle to ensure no high-impact catalyst is missed.

### `search_market_news(query: str, max_records: int = 25, timespan: str = "")`
* **Purpose**: Performs semantic and keyword search across all scraped news archives.
* **Parameters**: `query` (e.g., "Fed rate cut", "PBOC gold reserves", "Iran Middle East conflict", "US CPI inflation").
* **When to use**: To drill into specific developing headlines or confirm macro policy statements.

### `get_live_world_events(category: str = "ALL")`
* **Purpose**: Tracks breaking geopolitical crises, central bank meetings, and sovereign announcements.
* **Parameters**: `category` ("ALL", "GEOPOLITICAL", "CENTRAL_BANK", "COMMODITIES").
* **When to use**: To monitor global flash events that drive sudden volume expansions.

### `get_fred_observations(series_id: str, limit: int = 100, vintage_date: str = "")`
* **Purpose**: Direct access to Federal Reserve Economic Data (FRED).
* **Key Series IDs**:
  * `DFII10`: 10-Year Real Yield (TIPS yield) — the primary macro gravity driver for gold.
  * `DGS10`: 10-Year Nominal Treasury Yield.
  * `DGS2`: 2-Year Treasury Yield.
* **When to use**: When evaluating whether bond yields provide tailwinds or headwinds for gold pricing.

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
  * `tp_price`: Target profit level (recommended below 12 points for high-probability front-running captures).
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

---

## 6. Time & Session Management

### `get_market_time_context(target_time: str = "", target_timezone: str = "America/New_York")`
* **Purpose**: Provides authoritative synchronized clocks across UTC, New York (ET), and London (BST).
* **Returns**: Active session name (e.g., `NEW_YORK_SESSION`, `LONDON_SESSION`, `ASIAN_SESSION`), active market overlaps, and minutes until session close.
* **When to use**: At the beginning of every turn to maintain absolute temporal alignment.

---

## 7. Research & Desk Validation

### `backtest_thesis(symbol: str, thesis: str, timeframe: str = "M5", bars: int = 500)`
* **Purpose**: Fast backtest of a quantitative thesis against recent bar data before taking high-risk action.

### `query_analyst_desk(query: str, symbol: str = "XAUUSD")`
* **Purpose**: Gathers consensus analysis from the Technical, Fundamental, Macro News, and Sentiment analyst sub-modules.
