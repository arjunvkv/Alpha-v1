"""Universal Deterministic Structural Backtesting Engine.

Executes physical, mathematically rigorous candle replay against real MT5 OHLCV data.
Zero lookahead bias, zero ghost fills, realistic intra-bar tracking, and broker-grade fill physics.
Supports both:
  1. Explicit Candidate Order Replay (direct testing of exact entry, SL, and TP coordinates)
  2. Quantitative Structural Archetype Scanning (FVGs, Order Blocks, Turtle Soup, Breakouts, Breakers, Pinbars)
"""

import math
from typing import List, Dict, Any, Optional

class StructuralEngine:
    """Master quantitative execution engine for structural backtesting."""

    def __init__(self):
        pass

    def run_simulation(self, candles: List[Dict[str, Any]], thesis_cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Runs complete deterministic replay across candles according to thesis configuration."""
        if not candles or len(candles) < 10:
            return {
                "thesis_summary": thesis_cfg.get("query", "Structural Backtest"),
                "total_setups_found": 0,
                "filled_trades": 0,
                "unfilled_setups": 0,
                "wins": 0,
                "losses": 0,
                "win_rate_pct": 0.0,
                "net_realized_r": 0.0,
                "profit_factor": 0.0,
                "trades": [],
                "failure_clusters": ["Insufficient historical candle sample size (minimum 10 bars required)."],
                "key_edge_takeaways": ["Provide at least 20-60 bars for statistically valid structural replay."]
            }

        setup_type = thesis_cfg.get("setup_type", "FVG_MITIGATION")
        direction = thesis_cfg.get("direction", "BOTH")

        # 1. Spot candidate setups
        candidate_setups = []
        if setup_type == "EXPLICIT_ORDER_REPLAY" or thesis_cfg.get("entry_price") is not None:
            candidate_setups = self._find_explicit_order_setups(candles, direction, thesis_cfg)
        elif setup_type == "FVG_MITIGATION":
            candidate_setups = self._find_fvg_setups(candles, direction, thesis_cfg)
        elif setup_type == "ORDER_BLOCK":
            candidate_setups = self._find_order_block_setups(candles, direction, thesis_cfg)
        elif setup_type == "BREAKER_BLOCK":
            candidate_setups = self._find_breaker_block_setups(candles, direction, thesis_cfg)
        elif setup_type == "REJECTION_WICK":
            candidate_setups = self._find_rejection_wick_setups(candles, direction, thesis_cfg)
        elif setup_type == "TURTLE_SOUP_SWEEP":
            candidate_setups = self._find_turtle_soup_setups(candles, direction, thesis_cfg)
        elif setup_type == "BREAKOUT_EXPANSION":
            candidate_setups = self._find_breakout_setups(candles, direction, thesis_cfg)
        elif setup_type == "TREND_EMA_PULLBACK":
            candidate_setups = self._find_ema_pullback_setups(candles, direction, thesis_cfg)
        else:
            candidate_setups = self._find_fvg_setups(candles, direction, thesis_cfg)

        # 2. Simulate physical fills and forward bar-by-bar progression
        executed_trades = []
        unfilled_count = 0
        max_fill_bars = thesis_cfg.get("max_fill_bars", 25)
        max_hold_bars = thesis_cfg.get("max_hold_bars", 35)
        trade_exit_bar = -1

        for setup in candidate_setups:
            form_idx = setup["formation_bar"]
            if form_idx <= trade_exit_bar:
                unfilled_count += 1
                continue
            form_idx = setup["formation_bar"]
            entry_style = setup["entry_style"]
            entry_price = setup["entry_price"]
            sl_price = setup["stop_loss"]
            tp_price = setup["take_profit"]
            is_long = setup["direction"] == "BULLISH"
            risk = setup["risk"]

            # Step 2A: Verify Real Physical Fill
            if setup.get("is_explicit"):
                # Explicit orders already verified by the candidate generator
                filled = True
                fill_idx = form_idx
                actual_fill_price = entry_price
                spread_pts = float(candles[fill_idx].get("spread_pts", 0.0))
                spread_cost_pts = round(spread_pts * 0.5, 2)
                if is_long:
                    actual_fill_price = round(actual_fill_price + spread_cost_pts, 2)
                else:
                    actual_fill_price = round(actual_fill_price - spread_cost_pts, 2)
                act_risk = risk
            else:
                filled = False
                fill_idx = -1
                actual_fill_price = entry_price

                if entry_style == "MARKET":
                    if form_idx + 1 < len(candles):
                        fill_idx = form_idx + 1
                        actual_fill_price = float(candles[fill_idx]["open"])
                        filled = True
                elif entry_style == "STOP":
                    for f in range(form_idx + 1, min(form_idx + 1 + max_fill_bars, len(candles))):
                        c = candles[f]
                        if is_long and float(c["high"]) >= entry_price:
                            filled = True
                            fill_idx = f
                            actual_fill_price = max(entry_price, float(c["open"])) if float(c["open"]) > entry_price else entry_price
                            break
                        elif not is_long and float(c["low"]) <= entry_price:
                            filled = True
                            fill_idx = f
                            actual_fill_price = min(entry_price, float(c["open"])) if float(c["open"]) < entry_price else entry_price
                            break
                else:
                    # Limit order: price MUST trade into or through the limit price
                    for f in range(form_idx + 1, min(form_idx + 1 + max_fill_bars, len(candles))):
                        c = candles[f]
                        if is_long:
                            if float(c["low"]) <= entry_price <= float(c["high"]):
                                filled = True
                                fill_idx = f
                                actual_fill_price = entry_price
                                break
                            elif float(c["high"]) < entry_price:
                                filled = True
                                fill_idx = f
                                actual_fill_price = float(c["open"])
                                break
                        else:
                            if float(c["low"]) <= entry_price <= float(c["high"]):
                                filled = True
                                fill_idx = f
                                actual_fill_price = entry_price
                                break
                            elif float(c["low"]) > entry_price:
                                filled = True
                                fill_idx = f
                                actual_fill_price = float(c["open"])
                                break

                if not filled or fill_idx < 0:
                    unfilled_count += 1
                    continue
                
                spread_pts = float(candles[fill_idx].get("spread_pts", 0.0))
                spread_cost_pts = round(spread_pts * 0.5, 2)
                if is_long:
                    actual_fill_price = round(actual_fill_price + spread_cost_pts, 2)
                else:
                    actual_fill_price = round(actual_fill_price - spread_cost_pts, 2)

                # Recalibrate actual risk and TP if fill slipped slightly (pattern setups only)
                act_risk = max(abs(actual_fill_price - sl_price), 1.0)
                if is_long:
                    tp_price = round(actual_fill_price + (act_risk * (setup["target_rr"])), 2)
                else:
                    tp_price = round(actual_fill_price - (act_risk * (setup["target_rr"])), 2)

            # Step 2B: Trace Forward Bars Post-Fill
            trade_resolved = False
            # Check intra-bar fill candle first
            fill_c = candles[fill_idx]
            f_low = float(fill_c["low"])
            f_high = float(fill_c["high"])
            f_open = float(fill_c["open"])
            f_close = float(fill_c["close"])

            sl_hit_fill = (f_low <= sl_price) if is_long else (f_high >= sl_price)
            tp_hit_fill = (f_high >= tp_price) if is_long else (f_low <= tp_price)

            if sl_hit_fill and tp_hit_fill:
                # Intra-bar ambiguity: assess conservatively based on close
                midpoint = (f_high + f_low) / 2.0
                open_dist_sl = abs(f_open - sl_price)
                open_dist_tp = abs(f_open - tp_price)
                
                if abs(f_open - midpoint) <= 1.0:
                    if (is_long and f_close > f_open) or (not is_long and f_close < f_open):
                        outcome = "TP_HIT"
                    else:
                        outcome = "SL_HIT"
                else:
                    if open_dist_tp < open_dist_sl:
                        outcome = "TP_HIT"
                    else:
                        outcome = "SL_HIT"

                if outcome == "TP_HIT":
                    realized_r = round(setup["target_rr"], 2)
                    exit_price = tp_price
                else:
                    realized_r = -1.0
                    exit_price = sl_price
                executed_trades.append({
                    "trade_id": len(executed_trades) + 1,
                    "setup_name": setup["name"],
                    "direction": setup["direction"],
                    "formation_bar": form_idx,
                    "formation_timestamp": candles[form_idx]["timestamp"],
                    "fill_bar": fill_idx,
                    "entry_timestamp": fill_c["timestamp"],
                    "entry_price": actual_fill_price,
                    "stop_loss": sl_price,
                    "take_profit": tp_price,
                    "exit_bar": fill_idx,
                    "exit_timestamp": fill_c["timestamp"],
                    "exit_price": exit_price,
                    "exit_reason": outcome,
                    "realized_r": realized_r,
                    "intra_bar_ambiguity": True,
                    "holding_bars": 0,
                    "analysis": f"{setup['name']} filled & resolved intra-bar at bar {fill_idx} ({exit_price}).",
                    "spread_cost_pts": spread_cost_pts
                })
                trade_resolved = True
                trade_exit_bar = fill_idx
            elif tp_hit_fill and not sl_hit_fill:
                realized_r = round(setup["target_rr"], 2)
                executed_trades.append({
                    "trade_id": len(executed_trades) + 1,
                    "setup_name": setup["name"],
                    "direction": setup["direction"],
                    "formation_bar": form_idx,
                    "formation_timestamp": candles[form_idx]["timestamp"],
                    "fill_bar": fill_idx,
                    "entry_timestamp": fill_c["timestamp"],
                    "entry_price": actual_fill_price,
                    "stop_loss": sl_price,
                    "take_profit": tp_price,
                    "exit_bar": fill_idx,
                    "exit_timestamp": fill_c["timestamp"],
                    "exit_price": tp_price,
                    "exit_reason": "TP_HIT",
                    "realized_r": realized_r,
                    "holding_bars": 0,
                    "analysis": f"{setup['name']} hit TP intra-bar on fill bar ({tp_price}).",
                    "spread_cost_pts": spread_cost_pts
                })
                trade_resolved = True
                trade_exit_bar = fill_idx
            elif sl_hit_fill and not tp_hit_fill:
                executed_trades.append({
                    "trade_id": len(executed_trades) + 1,
                    "setup_name": setup["name"],
                    "direction": setup["direction"],
                    "formation_bar": form_idx,
                    "formation_timestamp": candles[form_idx]["timestamp"],
                    "fill_bar": fill_idx,
                    "entry_timestamp": fill_c["timestamp"],
                    "entry_price": actual_fill_price,
                    "stop_loss": sl_price,
                    "take_profit": tp_price,
                    "exit_bar": fill_idx,
                    "exit_timestamp": fill_c["timestamp"],
                    "exit_price": sl_price,
                    "exit_reason": "SL_HIT",
                    "realized_r": -1.0,
                    "holding_bars": 0,
                    "analysis": f"{setup['name']} stopped out intra-bar on fill bar ({sl_price}).",
                    "spread_cost_pts": spread_cost_pts
                })
                trade_resolved = True
                trade_exit_bar = fill_idx

            # If not resolved on fill bar, step forward through subsequent bars
            if not trade_resolved:
                for step in range(fill_idx + 1, min(fill_idx + 1 + max_hold_bars, len(candles))):
                    fc = candles[step]
                    high = float(fc["high"])
                    low = float(fc["low"])
                    open_p = float(fc["open"])
                    close_p = float(fc["close"])

                    sl_hit = (low <= sl_price) if is_long else (high >= sl_price)
                    tp_hit = (high >= tp_price) if is_long else (low <= tp_price)

                    if sl_hit and tp_hit:
                        if is_long:
                            if close_p > open_p and open_p > sl_price:
                                outcome = "TP_HIT"
                                realized_r = round(setup["target_rr"], 2)
                                exit_price = tp_price
                            else:
                                outcome = "SL_HIT"
                                realized_r = -1.0
                                exit_price = sl_price
                        else:
                            if close_p < open_p and open_p < sl_price:
                                outcome = "TP_HIT"
                                realized_r = round(setup["target_rr"], 2)
                                exit_price = tp_price
                            else:
                                outcome = "SL_HIT"
                                realized_r = -1.0
                                exit_price = sl_price

                        executed_trades.append({
                            "trade_id": len(executed_trades) + 1,
                            "setup_name": setup["name"],
                            "direction": setup["direction"],
                            "formation_bar": form_idx,
                            "formation_timestamp": candles[form_idx]["timestamp"],
                            "fill_bar": fill_idx,
                            "entry_timestamp": candles[fill_idx]["timestamp"],
                            "entry_price": actual_fill_price,
                            "stop_loss": sl_price,
                            "take_profit": tp_price,
                            "exit_bar": step,
                            "exit_timestamp": fc["timestamp"],
                            "exit_price": exit_price,
                            "exit_reason": outcome,
                            "realized_r": realized_r,
                            "holding_bars": step - fill_idx,
                            "analysis": f"{setup['name']} filled at bar {fill_idx} ({actual_fill_price}). {outcome} resolved at bar {step} ({exit_price}).",
                    "spread_cost_pts": spread_cost_pts
                        })
                        trade_resolved = True
                        trade_exit_bar = step
                        break

                    elif sl_hit:
                        executed_trades.append({
                            "trade_id": len(executed_trades) + 1,
                            "setup_name": setup["name"],
                            "direction": setup["direction"],
                            "formation_bar": form_idx,
                            "formation_timestamp": candles[form_idx]["timestamp"],
                            "fill_bar": fill_idx,
                            "entry_timestamp": candles[fill_idx]["timestamp"],
                            "entry_price": actual_fill_price,
                            "stop_loss": sl_price,
                            "take_profit": tp_price,
                            "exit_bar": step,
                            "exit_timestamp": fc["timestamp"],
                            "exit_price": sl_price,
                            "exit_reason": "SL_HIT",
                            "realized_r": -1.0,
                            "holding_bars": step - fill_idx,
                            "analysis": f"{setup['name']} stopped out at {sl_price} on adverse pressure.",
                    "spread_cost_pts": spread_cost_pts
                        })
                        trade_resolved = True
                        trade_exit_bar = step
                        break

                    elif tp_hit:
                        realized_r = round(setup["target_rr"], 2)
                        executed_trades.append({
                            "trade_id": len(executed_trades) + 1,
                            "setup_name": setup["name"],
                            "direction": setup["direction"],
                            "formation_bar": form_idx,
                            "formation_timestamp": candles[form_idx]["timestamp"],
                            "fill_bar": fill_idx,
                            "entry_timestamp": candles[fill_idx]["timestamp"],
                            "entry_price": actual_fill_price,
                            "stop_loss": sl_price,
                            "take_profit": tp_price,
                            "exit_bar": step,
                            "exit_timestamp": fc["timestamp"],
                            "exit_price": tp_price,
                            "exit_reason": "TP_HIT",
                            "realized_r": realized_r,
                            "holding_bars": step - fill_idx,
                            "analysis": f"{setup['name']} hit asymmetric Take Profit target cleanly at {tp_price} (+{realized_r}R).",
                    "spread_cost_pts": spread_cost_pts
                        })
                        trade_resolved = True
                        trade_exit_bar = step
                        break

                # Step 2C: Mark-to-Market if trade did not hit SL or TP before window close
                if not trade_resolved:
                    last_c = candles[min(fill_idx + max_hold_bars, len(candles) - 1)]
                    last_close = float(last_c["close"])
                    mtm_pnl = (last_close - actual_fill_price) if is_long else (actual_fill_price - last_close)
                    mtm_r = round(mtm_pnl / act_risk, 2)
                    executed_trades.append({
                        "trade_id": len(executed_trades) + 1,
                        "setup_name": setup["name"],
                        "direction": setup["direction"],
                        "formation_bar": form_idx,
                        "formation_timestamp": candles[form_idx]["timestamp"],
                        "fill_bar": fill_idx,
                        "entry_timestamp": candles[fill_idx]["timestamp"],
                        "entry_price": actual_fill_price,
                        "stop_loss": sl_price,
                        "take_profit": tp_price,
                        "exit_bar": min(fill_idx + max_hold_bars, len(candles) - 1),
                        "exit_timestamp": last_c["timestamp"],
                        "exit_price": last_close,
                        "exit_reason": "WINDOW_EXPIRY_MTM",
                        "realized_r": mtm_r,
                        "holding_bars": min(fill_idx + max_hold_bars, len(candles) - 1) - fill_idx,
                        "analysis": f"{setup['name']} timed out after max hold window. Mark-to-market exit at {last_close} ({mtm_r}R).",
                    "spread_cost_pts": spread_cost_pts
                    })
                    trade_exit_bar = min(fill_idx + max_hold_bars, len(candles) - 1)

        # Step 3: Quantitative Statistical Aggregation
        resolved_trades = [t for t in executed_trades if t.get("exit_reason") != "WINDOW_EXPIRY_MTM"]
        mtm_trades = [t for t in executed_trades if t.get("exit_reason") == "WINDOW_EXPIRY_MTM"]
        wins = sum(1 for t in resolved_trades if t["realized_r"] > 0)
        losses = sum(1 for t in resolved_trades if t["realized_r"] < 0)
        total_resolved = len(resolved_trades)
        win_rate = round((wins / total_resolved * 100.0), 1) if total_resolved > 0 else 0.0
        net_r = round(sum(t["realized_r"] for t in resolved_trades), 2)
        
        mtm_exits = len(mtm_trades)
        mtm_avg_r = round(sum(t["realized_r"] for t in mtm_trades) / mtm_exits, 2) if mtm_exits > 0 else 0.0

        gross_win_r = sum(t["realized_r"] for t in resolved_trades if t["realized_r"] > 0)
        gross_loss_r = abs(sum(t["realized_r"] for t in resolved_trades if t["realized_r"] < 0))
        pf = round(gross_win_r / gross_loss_r, 2) if gross_loss_r > 0 else (99.0 if gross_win_r > 0 else 0.0)

        # Dynamic Edge Insights & Failure Clusters from REAL trades
        failure_clusters = []
        if losses > 0:
            loss_trades = [t for t in executed_trades if t["realized_r"] < 0]
            avg_holding = sum(t["holding_bars"] for t in loss_trades) / len(loss_trades)
            if avg_holding <= 3:
                failure_clusters.append("Immediate adverse momentum displacement through stop loss invalidation shelf.")
            else:
                failure_clusters.append("Extended consolidation chop gradually drifting beyond structural invalidation.")
            if unfilled_count > len(executed_trades):
                failure_clusters.append("Resting limit orders left unfilled due to aggressive runaway momentum.")
        elif wins > 0:
            failure_clusters.append(f"Zero losses recorded across {wins} winning fills in the sampled candle series.")
        elif len(executed_trades) > 0:
            failure_clusters.append("Zero trades resolved via SL or TP; all active positions timed out via mark-to-market window expiry.")
        else:
            failure_clusters.append("Zero physical order fills occurred within the sampled historical candle window.")

        key_takeaways = [
            f"Evaluated {len(candles)} historical bars. Found {len(candidate_setups)} valid setups ({len(executed_trades)} filled, {unfilled_count} unfilled).",
            f"Verified physical fill rate: {round(len(executed_trades) / max(1, len(candidate_setups)) * 100, 1)}%. Realized Profit Factor: {pf}.",
            f"Mathematical expectancy: {round(net_r / max(1, total_resolved), 2)}R per trade across resolved executions."
        ]

        return {
            "thesis_summary": thesis_cfg.get("query", setup_type),
            "setup_type": setup_type,
            "total_setups_found": len(candidate_setups),
            "filled_trades": len(executed_trades),
            "unfilled_setups": unfilled_count,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": win_rate,
            "net_realized_r": net_r,
            "profit_factor": pf,
            "mtm_exits": mtm_exits,
            "mtm_avg_r": mtm_avg_r,
            "sample_quality": {
                "n_resolved": total_resolved,
                "is_statistically_valid": total_resolved >= 5,
                "min_sample_warning": None if total_resolved >= 5 else f"Only {total_resolved} resolved trades. Minimum 5 required for statistical validity."
            },
            "trades": executed_trades,
            "failure_clusters": failure_clusters,
            "key_edge_takeaways": key_takeaways
        }

    # =========================================================================
    # DETECTOR 0: EXPLICIT CANDIDATE ORDER REPLAY
    # =========================================================================
    def _find_explicit_order_setups(self, candles: List[Dict[str, Any]], direction: str, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Replays explicit candidate order coordinates through historical candle series with broker-grade fill physics."""
        entry_price = cfg.get("entry_price")
        if entry_price is None:
            return []

        direction = cfg.get("direction", "BULLISH")
        is_long = direction == "BULLISH"
        entry_style = cfg.get("entry_style", "LIMIT")

        sl_price = cfg.get("sl_price")
        tp_price = cfg.get("tp_price")
        sl_points = cfg.get("sl_points")
        tp_points = cfg.get("tp_points")

        # Fallback buffers if not explicitly specified
        if sl_price is None:
            delta = sl_points if (sl_points and 1.0 <= sl_points <= 40.0) else 8.0
            sl_price = round(entry_price - delta, 2) if is_long else round(entry_price + delta, 2)

        if tp_price is None:
            delta = tp_points if (tp_points and 1.0 <= tp_points <= 150.0) else 16.0
            tp_price = round(entry_price + delta, 2) if is_long else round(entry_price - delta, 2)

        risk = max(round(abs(entry_price - sl_price), 2), 1.0)
        reward = max(round(abs(tp_price - entry_price), 2), 1.0)
        target_rr = round(reward / risk, 2)

        setups = []
        in_trade = False
        trade_exit_bar = -1

        for i in range(len(candles)):
            if in_trade and i <= trade_exit_bar:
                continue
            in_trade = False

            c = candles[i]
            prev_c = candles[i-1] if i > 0 else c

            filled = False
            fill_price = entry_price

            if entry_style == "MARKET":
                # Market order fills on first bar
                if i == 0 or i == 1:
                    filled = True
                    fill_price = float(c["open"])
            elif entry_style == "STOP":
                if is_long:
                    # BUY_STOP: Price pushes UP through entry from below
                    if (i == 0 and float(c["open"]) < entry_price and float(c["high"]) >= entry_price) or (i > 0 and float(prev_c["high"]) < entry_price and float(c["high"]) >= entry_price):
                        filled = True
                        fill_price = max(entry_price, float(c["open"])) if float(c["open"]) > entry_price else entry_price
                else:
                    # SELL_STOP: Price pushes DOWN through entry from above
                    if (i == 0 and float(c["open"]) > entry_price and float(c["low"]) <= entry_price) or (i > 0 and float(prev_c["low"]) > entry_price and float(c["low"]) <= entry_price):
                        filled = True
                        fill_price = min(entry_price, float(c["open"])) if float(c["open"]) < entry_price else entry_price
            else:
                # LIMIT order: Price trades into limit shelf
                if is_long:
                    # BUY_LIMIT: Price pulls down into entry from above
                    if (i == 0 and float(c["open"]) > entry_price and float(c["low"]) <= entry_price) or (i > 0 and float(prev_c["low"]) > entry_price and float(c["low"]) <= entry_price):
                        filled = True
                        fill_price = entry_price if float(c["low"]) <= entry_price <= float(c["high"]) else float(c["open"])
                else:
                    # SELL_LIMIT: Price pushes up into entry from below
                    if (i == 0 and float(c["open"]) < entry_price and float(c["high"]) >= entry_price) or (i > 0 and float(prev_c["high"]) < entry_price and float(c["high"]) >= entry_price):
                        filled = True
                        fill_price = entry_price if float(c["low"]) <= entry_price <= float(c["high"]) else float(c["open"])

            if filled:
                setup = {
                    "name": f"Explicit {direction} {entry_style} @ {entry_price}",
                    "direction": direction,
                    "formation_bar": i,
                    "entry_style": entry_style,
                    "entry_price": fill_price,
                    "stop_loss": sl_price,
                    "take_profit": tp_price,
                    "risk": risk,
                    "target_rr": target_rr,
                    "is_explicit": True
                }
                setups.append(setup)
                in_trade = True

                # Check forward to find when this trade terminates
                max_hold = cfg.get("max_hold_bars", 35)
                for f in range(i, min(i + max_hold, len(candles))):
                    fc = candles[f]
                    sl_hit = (float(fc["low"]) <= sl_price) if is_long else (float(fc["high"]) >= sl_price)
                    tp_hit = (float(fc["high"]) >= tp_price) if is_long else (float(fc["low"]) <= tp_price)
                    if sl_hit or tp_hit:
                        trade_exit_bar = f
                        break
                else:
                    trade_exit_bar = min(i + max_hold, len(candles) - 1)

        return setups

    # =========================================================================
    # DETECTOR 1: FAIR VALUE GAP (FVG)
    # =========================================================================
    def _find_fvg_setups(self, candles: List[Dict[str, Any]], direction: str, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        setups = []
        target_rr = cfg.get("target_rr", 2.0)
        raw_sl = cfg.get("sl_points")
        custom_sl = raw_sl if (raw_sl and 1.0 <= raw_sl <= 40.0) else None
        raw_tp = cfg.get("tp_points")
        custom_tp = raw_tp if (raw_tp and 1.0 <= raw_tp <= 120.0) else None

        for i in range(2, len(candles) - 1):
            c0, c1, c2 = candles[i-2], candles[i-1], candles[i]
            
            # Bullish FVG: c2.low > c0.high
            if direction in ["BULLISH", "BOTH"] and c2["low"] > c0["high"]:
                fvg_top = float(c2["low"])
                fvg_bot = float(c0["high"])
                gap_size = fvg_top - fvg_bot
                if gap_size >= 0.8:
                    fvg_ce = round((fvg_top + fvg_bot) / 2.0, 2)
                    sl = round(float(c1["low"]) - 1.2, 2) if not custom_sl else round(fvg_ce - custom_sl, 2)
                    sl = max(1.0, sl)
                    risk = max(round(fvg_ce - sl, 2), 1.5)
                    tp = round(fvg_ce + (risk * target_rr), 2) if not custom_tp else round(fvg_ce + custom_tp, 2)
                    setups.append({
                        "name": "Bullish FVG CE Mitigation",
                        "direction": "BULLISH",
                        "formation_bar": i,
                        "entry_style": cfg.get("entry_style", "LIMIT"),
                        "entry_price": fvg_ce,
                        "stop_loss": sl,
                        "take_profit": tp,
                        "risk": risk,
                        "target_rr": target_rr
                    })

            # Bearish FVG: c0.low > c2.high
            if direction in ["BEARISH", "BOTH"] and c0["low"] > c2["high"]:
                fvg_top = float(c0["low"])
                fvg_bot = float(c2["high"])
                gap_size = fvg_top - fvg_bot
                if gap_size >= 0.8:
                    fvg_ce = round((fvg_top + fvg_bot) / 2.0, 2)
                    sl = round(float(c1["high"]) + 1.2, 2) if not custom_sl else round(fvg_ce + custom_sl, 2)
                    sl = max(1.0, sl)
                    risk = max(round(sl - fvg_ce, 2), 1.5)
                    tp = round(fvg_ce - (risk * target_rr), 2) if not custom_tp else round(fvg_ce - custom_tp, 2)
                    tp = max(1.0, tp)
                    setups.append({
                        "name": "Bearish FVG CE Mitigation",
                        "direction": "BEARISH",
                        "formation_bar": i,
                        "entry_style": cfg.get("entry_style", "LIMIT"),
                        "entry_price": fvg_ce,
                        "stop_loss": sl,
                        "take_profit": tp,
                        "risk": risk,
                        "target_rr": target_rr
                    })

        return setups

    # =========================================================================
    # DETECTOR 2: ORDER BLOCK (OB) RETEST
    # =========================================================================
    def _find_order_block_setups(self, candles: List[Dict[str, Any]], direction: str, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        setups = []
        target_rr = cfg.get("target_rr", 2.0)
        raw_sl = cfg.get("sl_points")
        custom_sl = raw_sl if (raw_sl and 1.0 <= raw_sl <= 40.0) else None
        raw_tp = cfg.get("tp_points")
        custom_tp = raw_tp if (raw_tp and 1.0 <= raw_tp <= 120.0) else None

        for i in range(1, len(candles) - 2):
            c_prev = candles[i-1]
            c_curr = candles[i]
            c_next = candles[i+1]

            # Bullish OB: Bearish candle (c_prev) followed by strong bullish impulse
            if direction in ["BULLISH", "BOTH"]:
                is_bearish_bar = float(c_prev["close"]) < float(c_prev["open"])
                impulse_up = float(c_next["close"]) > float(c_prev["high"]) and (float(c_next["close"]) - float(c_next["open"]) > 2.0)
                if is_bearish_bar and impulse_up:
                    ob_high = float(c_prev["high"])
                    ob_low = float(c_prev["low"])
                    entry = round(ob_high, 2)
                    sl = round(ob_low - 1.2, 2) if not custom_sl else round(entry - custom_sl, 2)
                    sl = max(1.0, sl)
                    risk = max(round(entry - sl, 2), 1.5)
                    tp = round(entry + (risk * target_rr), 2) if not custom_tp else round(entry + custom_tp, 2)
                    setups.append({
                        "name": "Bullish Order Block Retest",
                        "direction": "BULLISH",
                        "formation_bar": i + 1,
                        "entry_style": "LIMIT",
                        "entry_price": entry,
                        "stop_loss": sl,
                        "take_profit": tp,
                        "risk": risk,
                        "target_rr": target_rr
                    })

            # Bearish OB: Bullish candle followed by strong bearish impulse
            if direction in ["BEARISH", "BOTH"]:
                is_bullish_bar = float(c_prev["close"]) > float(c_prev["open"])
                impulse_down = float(c_next["close"]) < float(c_prev["low"]) and (float(c_next["open"]) - float(c_next["close"]) > 2.0)
                if is_bullish_bar and impulse_down:
                    ob_high = float(c_prev["high"])
                    ob_low = float(c_prev["low"])
                    entry = round(ob_low, 2)
                    sl = round(ob_high + 1.2, 2) if not custom_sl else round(entry + custom_sl, 2)
                    sl = max(1.0, sl)
                    risk = max(round(sl - entry, 2), 1.5)
                    tp = round(entry - (risk * target_rr), 2) if not custom_tp else round(entry - custom_tp, 2)
                    tp = max(1.0, tp)
                    setups.append({
                        "name": "Bearish Order Block Retest",
                        "direction": "BEARISH",
                        "formation_bar": i + 1,
                        "entry_style": "LIMIT",
                        "entry_price": entry,
                        "stop_loss": sl,
                        "take_profit": tp,
                        "risk": risk,
                        "target_rr": target_rr
                    })

        return setups

    # =========================================================================
    # DETECTOR 3: TURTLE SOUP (SWEEP & RECLAIM)
    # =========================================================================
    def _find_turtle_soup_setups(self, candles: List[Dict[str, Any]], direction: str, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        setups = []
        target_rr = cfg.get("target_rr", 2.0)
        lookback = 12

        for i in range(lookback, len(candles) - 1):
            prior_lows = [float(c["low"]) for c in candles[i-lookback:i]]
            prior_highs = [float(c["high"]) for c in candles[i-lookback:i]]
            min_low = min(prior_lows)
            max_high = max(prior_highs)

            c = candles[i]
            low = float(c["low"])
            high = float(c["high"])
            close = float(c["close"])

            # Bullish Turtle Soup: Low sweeps below min_low, but closes back above min_low
            if direction in ["BULLISH", "BOTH"] and low < min_low and close > min_low:
                entry = round(close, 2)
                sl = max(1.0, round(low - 1.2, 2))
                risk = max(round(entry - sl, 2), 1.5)
                tp = round(entry + (risk * target_rr), 2)
                setups.append({
                    "name": "Bullish Turtle Soup Sweep & Reclaim",
                    "direction": "BULLISH",
                    "formation_bar": i,
                    "entry_style": "MARKET",
                    "entry_price": entry,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "risk": risk,
                    "target_rr": target_rr
                })

            # Bearish Turtle Soup: High sweeps above max_high, but closes back below max_high
            if direction in ["BEARISH", "BOTH"] and high > max_high and close < max_high:
                entry = round(close, 2)
                sl = max(1.0, round(high + 1.2, 2))
                risk = max(round(sl - entry, 2), 1.5)
                tp = max(1.0, round(entry - (risk * target_rr), 2))
                setups.append({
                    "name": "Bearish Turtle Soup Sweep & Reclaim",
                    "direction": "BEARISH",
                    "formation_bar": i,
                    "entry_style": "MARKET",
                    "entry_price": entry,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "risk": risk,
                    "target_rr": target_rr
                })

        return setups

    # =========================================================================
    # DETECTOR 4: BREAKOUT & MOMENTUM EXPANSION
    # =========================================================================
    def _find_breakout_setups(self, candles: List[Dict[str, Any]], direction: str, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        setups = []
        target_rr = cfg.get("target_rr", 2.0)
        lookback = 15

        for i in range(lookback, len(candles) - 1):
            prior_highs = [float(c["high"]) for c in candles[i-lookback:i]]
            prior_lows = [float(c["low"]) for c in candles[i-lookback:i]]
            swing_high = max(prior_highs)
            swing_low = min(prior_lows)

            c = candles[i]
            close = float(c["close"])

            # Bullish BOS Breakout: Close > Swing High
            if direction in ["BULLISH", "BOTH"] and close > swing_high:
                entry = round(close, 2)
                sl = max(1.0, round(float(c["low"]) - 1.2, 2))
                risk = max(round(entry - sl, 2), 2.0)
                tp = round(entry + (risk * target_rr), 2)
                setups.append({
                    "name": "Bullish Range Breakout Expansion",
                    "direction": "BULLISH",
                    "formation_bar": i,
                    "entry_style": "MARKET",
                    "entry_price": entry,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "risk": risk,
                    "target_rr": target_rr
                })

            # Bearish BOS Breakout: Close < Swing Low
            if direction in ["BEARISH", "BOTH"] and close < swing_low:
                entry = round(close, 2)
                sl = max(1.0, round(float(c["high"]) + 1.2, 2))
                risk = max(round(sl - entry, 2), 2.0)
                tp = max(1.0, round(entry - (risk * target_rr), 2))
                setups.append({
                    "name": "Bearish Range Breakout Expansion",
                    "direction": "BEARISH",
                    "formation_bar": i,
                    "entry_style": "MARKET",
                    "entry_price": entry,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "risk": risk,
                    "target_rr": target_rr
                })

        return setups

    # =========================================================================
    # DETECTOR 5: TREND EMA PULLBACK
    # =========================================================================
    def _find_ema_pullback_setups(self, candles: List[Dict[str, Any]], direction: str, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        setups = []
        target_rr = cfg.get("target_rr", 2.0)
        closes = [float(c["close"]) for c in candles]
        
        # Calculate EMA20
        ema20 = []
        k = 2.0 / (20 + 1)
        prev = closes[0]
        for c in closes:
            val = (c * k) + (prev * (1 - k))
            ema20.append(val)
            prev = val

        for i in range(20, len(candles) - 1):
            c = candles[i]
            low = float(c["low"])
            high = float(c["high"])
            close = float(c["close"])
            open_p = float(c["open"])
            ema_val = ema20[i]

            # Bullish trend pullback: price touches EMA20 and closes bullish
            if direction in ["BULLISH", "BOTH"] and low <= ema_val <= high and close > open_p:
                entry = round(close, 2)
                sl = max(1.0, round(low - 1.2, 2))
                risk = max(round(entry - sl, 2), 1.5)
                tp = round(entry + (risk * target_rr), 2)
                setups.append({
                    "name": "Bullish EMA20 Trend Pullback",
                    "direction": "BULLISH",
                    "formation_bar": i,
                    "entry_style": "MARKET",
                    "entry_price": entry,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "risk": risk,
                    "target_rr": target_rr
                })

            # Bearish trend pullback: price touches EMA20 and closes bearish
            if direction in ["BEARISH", "BOTH"] and low <= ema_val <= high and close < open_p:
                entry = round(close, 2)
                sl = max(1.0, round(high + 1.2, 2))
                risk = max(round(sl - entry, 2), 1.5)
                tp = max(1.0, round(entry - (risk * target_rr), 2))
                setups.append({
                    "name": "Bearish EMA20 Trend Pullback",
                    "direction": "BEARISH",
                    "formation_bar": i,
                    "entry_style": "MARKET",
                    "entry_price": entry,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "risk": risk,
                    "target_rr": target_rr
                })

        return setups

    # =========================================================================
    # DETECTOR 6: BREAKER BLOCK (S/R FLIP)
    # =========================================================================
    def _find_breaker_block_setups(self, candles: List[Dict[str, Any]], direction: str, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        setups = []
        target_rr = cfg.get("target_rr", 2.0)
        raw_sl = cfg.get("sl_points")
        custom_sl = raw_sl if (raw_sl and 1.0 <= raw_sl <= 40.0) else None
        raw_tp = cfg.get("tp_points")
        custom_tp = raw_tp if (raw_tp and 1.0 <= raw_tp <= 120.0) else None
        lookback = 10

        for i in range(lookback, len(candles) - 1):
            prior_highs = [float(c["high"]) for c in candles[i-lookback:i]]
            prior_lows = [float(c["low"]) for c in candles[i-lookback:i]]
            swing_high = max(prior_highs)
            swing_low = min(prior_lows)

            c = candles[i]
            high = float(c["high"])
            low = float(c["low"])
            close = float(c["close"])
            open_p = float(c["open"])

            # Bullish Breaker: prior swing high breached upward by displacement candle
            if direction in ["BULLISH", "BOTH"] and close > swing_high and (close - open_p > 1.5):
                entry = round(swing_high, 2)
                sl = round(low - 1.2, 2) if not custom_sl else round(entry - custom_sl, 2)
                sl = max(1.0, sl)
                risk = max(round(entry - sl, 2), 1.5)
                tp = round(entry + (risk * target_rr), 2) if not custom_tp else round(entry + custom_tp, 2)
                setups.append({
                    "name": "Bullish Breaker Block Retest",
                    "direction": "BULLISH",
                    "formation_bar": i,
                    "entry_style": "LIMIT",
                    "entry_price": entry,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "risk": risk,
                    "target_rr": target_rr
                })

            # Bearish Breaker: prior swing low breached downward by displacement candle
            if direction in ["BEARISH", "BOTH"] and close < swing_low and (open_p - close > 1.5):
                entry = round(swing_low, 2)
                sl = round(high + 1.2, 2) if not custom_sl else round(entry + custom_sl, 2)
                sl = max(1.0, sl)
                risk = max(round(sl - entry, 2), 1.5)
                tp = round(entry - (risk * target_rr), 2) if not custom_tp else round(entry - custom_tp, 2)
                tp = max(1.0, tp)
                setups.append({
                    "name": "Bearish Breaker Block Retest",
                    "direction": "BEARISH",
                    "formation_bar": i,
                    "entry_style": "LIMIT",
                    "entry_price": entry,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "risk": risk,
                    "target_rr": target_rr
                })

        return setups

    # =========================================================================
    # DETECTOR 7: REJECTION WICK / INSTITUTIONAL PINBAR
    # =========================================================================
    def _find_rejection_wick_setups(self, candles: List[Dict[str, Any]], direction: str, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
        setups = []
        target_rr = cfg.get("target_rr", 2.0)
        raw_sl = cfg.get("sl_points")
        custom_sl = raw_sl if (raw_sl and 1.0 <= raw_sl <= 40.0) else None
        raw_tp = cfg.get("tp_points")
        custom_tp = raw_tp if (raw_tp and 1.0 <= raw_tp <= 120.0) else None

        for i in range(1, len(candles) - 1):
            c = candles[i]
            high = float(c["high"])
            low = float(c["low"])
            close = float(c["close"])
            open_p = float(c["open"])
            candle_range = high - low

            if candle_range < 1.2:
                continue

            lower_wick = min(open_p, close) - low
            upper_wick = high - max(open_p, close)

            # Bullish Pin / Rejection Wick: lower wick >= 50% of candle range
            if direction in ["BULLISH", "BOTH"] and (lower_wick / candle_range >= 0.50) and (upper_wick / candle_range <= 0.35):
                entry = round(close, 2)
                sl = round(low - 1.0, 2) if not custom_sl else round(entry - custom_sl, 2)
                sl = max(1.0, sl)
                risk = max(round(entry - sl, 2), 1.5)
                tp = round(entry + (risk * target_rr), 2) if not custom_tp else round(entry + custom_tp, 2)
                setups.append({
                    "name": "Bullish Rejection Wick Pinbar",
                    "direction": "BULLISH",
                    "formation_bar": i,
                    "entry_style": "MARKET",
                    "entry_price": entry,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "risk": risk,
                    "target_rr": target_rr
                })

            # Bearish Pin / Rejection Wick: upper wick >= 50% of candle range
            if direction in ["BEARISH", "BOTH"] and (upper_wick / candle_range >= 0.50) and (lower_wick / candle_range <= 0.35):
                entry = round(close, 2)
                sl = round(high + 1.0, 2) if not custom_sl else round(entry + custom_sl, 2)
                sl = max(1.0, sl)
                risk = max(round(sl - entry, 2), 1.5)
                tp = round(entry - (risk * target_rr), 2) if not custom_tp else round(entry - custom_tp, 2)
                tp = max(1.0, tp)
                setups.append({
                    "name": "Bearish Rejection Wick Pinbar",
                    "direction": "BEARISH",
                    "formation_bar": i,
                    "entry_style": "MARKET",
                    "entry_price": entry,
                    "stop_loss": sl,
                    "take_profit": tp,
                    "risk": risk,
                    "target_rr": target_rr
                })

        return setups
