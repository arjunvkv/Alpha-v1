"""
Universal Real-Time Watcher Engine for Alpha Trading Desk.

Evaluates high-frequency market telemetry, MT5 order state transitions,
position metrics, and news catalysts against active objective watches.
Designed for 500ms execution cycles without blocking or heavy computation.
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple

LOG = logging.getLogger("alpha.watcher_engine")


class WatchConditionType:
    PRICE_ABOVE = "PRICE_ABOVE"
    PRICE_BELOW = "PRICE_BELOW"
    PRICE_TOUCH = "PRICE_TOUCH"
    PRICE_CROSS_ABOVE = "PRICE_CROSS_ABOVE"
    PRICE_CROSS_BELOW = "PRICE_CROSS_BELOW"
    ORDER_FILL = "ORDER_FILL"
    ORDER_CANCEL = "ORDER_CANCEL"
    POSITION_PNL = "POSITION_PNL"
    POSITION_DRAWDOWN = "POSITION_DRAWDOWN"
    VELOCITY_SPIKE = "VELOCITY_SPIKE"
    SPREAD_SPIKE = "SPREAD_SPIKE"
    NEWS_KEYWORD = "NEWS_KEYWORD"
    CUSTOM = "CUSTOM"


def parse_watch_condition(
    condition_str: str,
    target_price: Optional[float] = None,
    direction: str = "",
    condition_type: str = "",
    target_ticket: Optional[int] = None
) -> Dict[str, Any]:
    """
    Intelligently parses user / LLM natural language or structured condition
    into standardized criteria with safe extraction.
    """
    text = (condition_str or "").strip()
    dir_clean = (direction or "").upper().strip()
    cond_type = (condition_type or "").upper().strip()
    extracted_target_price = float(target_price) if target_price is not None else None
    extracted_ticket = int(target_ticket) if target_ticket is not None else None
    tolerance = 0.50
    min_velocity = None
    max_spread = None
    keywords = []

    # 1. Identify Target Ticket if not passed
    if extracted_ticket is None:
        ticket_match = re.search(r'(?:ticket|order|#)\s*([0-9]{7,10})', text, re.IGNORECASE)
        if ticket_match:
            try:
                extracted_ticket = int(ticket_match.group(1))
            except Exception:
                pass

    # 2. Identify Condition Type if not explicitly provided
    if not cond_type:
        text_lower = text.lower()
        if any(k in text_lower for k in ["fill", "filled", "executed", "order trigger", "probe fill"]):
            cond_type = WatchConditionType.ORDER_FILL
        elif any(k in text_lower for k in ["velocity", "ticks/min", "tpm", "kinetic"]):
            cond_type = WatchConditionType.VELOCITY_SPIKE
        elif any(k in text_lower for k in ["spread", "spread blowout"]):
            cond_type = WatchConditionType.SPREAD_SPIKE
        elif any(k in text_lower for k in ["pnl", "profit", "gain", "drawdown", "loss"]):
            if "drawdown" in text_lower or "loss" in text_lower:
                cond_type = WatchConditionType.POSITION_DRAWDOWN
            else:
                cond_type = WatchConditionType.POSITION_PNL
        elif any(k in text_lower for k in ["news", "headline", "geopolitical", "shock", "war", "hormuz", "cpi", "fed"]):
            cond_type = WatchConditionType.NEWS_KEYWORD
        elif any(k in text_lower for k in ["cross above", "crosses above", "breaks above", "breakout above"]):
            cond_type = WatchConditionType.PRICE_CROSS_ABOVE
        elif any(k in text_lower for k in ["cross below", "crosses below", "breaks below", "breakdown below"]):
            cond_type = WatchConditionType.PRICE_CROSS_BELOW
        elif any(k in text_lower for k in ["above", ">", "greater", "higher"]):
            cond_type = WatchConditionType.PRICE_ABOVE
        elif any(k in text_lower for k in ["below", "<", "less", "lower"]):
            cond_type = WatchConditionType.PRICE_BELOW
        elif any(k in text_lower for k in ["touch", "reach", "level", "near", "at"]):
            cond_type = WatchConditionType.PRICE_TOUCH
        elif "BUY" in dir_clean or "LONG" in dir_clean:
            cond_type = WatchConditionType.PRICE_ABOVE
        elif "SELL" in dir_clean or "SHORT" in dir_clean:
            cond_type = WatchConditionType.PRICE_BELOW
        else:
            cond_type = WatchConditionType.PRICE_TOUCH

    # 3. Extract Target Price safely (DO NOT match 8+ digit tickets as prices!)
    if extracted_target_price is None and cond_type not in (
        WatchConditionType.ORDER_FILL, WatchConditionType.NEWS_KEYWORD,
        WatchConditionType.VELOCITY_SPIKE, WatchConditionType.SPREAD_SPIKE
    ):
        scrubbed = re.sub(r'#?[0-9]{7,12}', '', text)
        matches = re.findall(r'(?:above|below|at|target|breaks|break|price|level|fvg)?\s*([1-9][0-9]{2,4}(?:\.[0-9]+)?)', scrubbed, re.IGNORECASE)
        if not matches:
            matches = re.findall(r'([1-9][0-9]{3}(?:\.[0-9]+)?)', scrubbed)
        if matches:
            try:
                val = float(matches[0])
                if 100.0 <= val <= 20000.0:
                    extracted_target_price = val
            except Exception:
                pass

    # 4. Extract velocity threshold if velocity spike
    if cond_type == WatchConditionType.VELOCITY_SPIKE or "velocity" in text.lower():
        vel_match = re.search(r'(?:velocity|tpm|rate)\s*(?:>|>=|above)?\s*([0-9]{2,4})', text, re.IGNORECASE)
        if vel_match:
            try:
                min_velocity = float(vel_match.group(1))
            except Exception:
                pass
        if min_velocity is None:
            min_velocity = 100.0

    # 5. Extract spread threshold if spread spike
    if cond_type == WatchConditionType.SPREAD_SPIKE or "spread" in text.lower():
        spread_match = re.search(r'spread\s*(?:>|>=|above)?\s*([0-9]{2,4})', text, re.IGNORECASE)
        if spread_match:
            try:
                max_spread = float(spread_match.group(1))
            except Exception:
                pass
        if max_spread is None:
            max_spread = 60.0

    # 6. Extract news keywords if news condition
    if cond_type == WatchConditionType.NEWS_KEYWORD:
        quotes = re.findall(r'["\']([^"\']+)["\']', text)
        if quotes:
            keywords = quotes
        else:
            candidates = ["hormuz", "iran", "israel", "strike", "war", "cpi", "fed", "rate cut", "hike", "saudi", "opec"]
            keywords = [c for c in candidates if c in text.lower()]
            if not keywords:
                keywords = [text.strip()]

    return {
        "condition_type": cond_type,
        "target_price": extracted_target_price,
        "target_ticket": extracted_ticket,
        "tolerance": tolerance,
        "min_velocity": min_velocity,
        "max_spread": max_spread,
        "keywords": keywords,
        "direction": dir_clean
    }


class UniversalWatcherEngine:
    """
    Sub-second evaluator for persistent watches, MT5 order state transitions,
    and tape dynamics.
    """

    def __init__(self):
        self.last_ticks: Dict[str, Dict[str, float]] = {}
        self.known_positions: Dict[int, Dict[str, Any]] = {}
        self.known_pending_orders: Dict[int, Dict[str, Any]] = {}
        self.initialized: bool = False

    def sync_initial_state(self, positions: List[Any], pending_orders: List[Any]):
        """Warm up known positions and orders so startup does not trigger false fills."""
        if positions:
            for p in positions:
                t = getattr(p, "ticket", None) or (p.get("ticket") if isinstance(p, dict) else None)
                if t:
                    self.known_positions[int(t)] = {
                        "symbol": getattr(p, "symbol", "") or (p.get("symbol") if isinstance(p, dict) else ""),
                        "type": getattr(p, "type", 0) or (p.get("type") if isinstance(p, dict) else 0),
                        "volume": getattr(p, "volume", 0.0) or (p.get("volume") if isinstance(p, dict) else 0.0),
                        "price_open": getattr(p, "price_open", 0.0) or (p.get("price_open") if isinstance(p, dict) else 0.0),
                    }
        if pending_orders:
            for o in pending_orders:
                t = getattr(o, "ticket", None) or (o.get("ticket") if isinstance(o, dict) else None)
                if t:
                    self.known_pending_orders[int(t)] = {
                        "symbol": getattr(o, "symbol", "") or (o.get("symbol") if isinstance(o, dict) else ""),
                        "type": getattr(o, "type", 0) or (o.get("type") if isinstance(o, dict) else 0),
                        "price_open": getattr(o, "price_open", 0.0) or (o.get("price_open") if isinstance(o, dict) else 0.0),
                    }
        self.initialized = True

    def check_pending_order_fills(
        self,
        current_positions: List[Any],
        current_pending_orders: List[Any],
        active_watches: List[Dict[str, Any]],
        live_tape: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Detects pending orders that have just executed into live positions.
        Returns triggered alerts with fill details and rich tape context.
        """
        triggered = []
        curr_pos_map = {}
        for p in current_positions or []:
            t = getattr(p, "ticket", None) or (p.get("ticket") if isinstance(p, dict) else None)
            if t:
                curr_pos_map[int(t)] = p

        curr_pending_map = {}
        for o in current_pending_orders or []:
            t = getattr(o, "ticket", None) or (o.get("ticket") if isinstance(o, dict) else None)
            if t:
                curr_pending_map[int(t)] = o

        if not self.initialized:
            self.sync_initial_state(current_positions, current_pending_orders)
            return []

        # Find newly created position tickets
        new_tickets = set(curr_pos_map.keys()) - set(self.known_positions.keys())
        for ticket in new_tickets:
            p = curr_pos_map[ticket]
            sym = (getattr(p, "symbol", "") or (p.get("symbol") if isinstance(p, dict) else "")).upper()
            p_type = getattr(p, "type", 0) or (p.get("type") if isinstance(p, dict) else 0)
            vol = getattr(p, "volume", 0.0) or (p.get("volume") if isinstance(p, dict) else 0.0)
            p_open = getattr(p, "price_open", 0.0) or (p.get("price_open") if isinstance(p, dict) else 0.0)
            sl = getattr(p, "sl", 0.0) or (p.get("sl") if isinstance(p, dict) else 0.0)
            tp = getattr(p, "tp", 0.0) or (p.get("tp") if isinstance(p, dict) else 0.0)
            comment = getattr(p, "comment", "") or (p.get("comment") if isinstance(p, dict) else "")
            side_str = "BUY" if p_type == 0 else "SELL"
            is_probe = vol <= 0.05
            category = "0.01 PROBE FILL" if is_probe else f"{vol:.2f} LOT POSITION FILL"

            matching_watch = None
            for w in active_watches:
                w_ticket = w.get("target_ticket") or (w.get("params") or {}).get("target_ticket")
                w_type = (w.get("condition_type") or "").upper()
                if (w_ticket and int(w_ticket) == ticket) or w_type == WatchConditionType.ORDER_FILL:
                    if not w.get("symbol") or str(w.get("symbol")).upper() == str(sym).upper():
                        matching_watch = w
                        break

            tape_str = ""
            if live_tape:
                tape_str = (
                    f"Tape Kinetics: Velocity {live_tape.get('velocity', 'N/A')} t/m | "
                    f"Spread {live_tape.get('spread', 'N/A')} pts | "
                    f"Micro-CVD {live_tape.get('cvd_10b', 'N/A')}"
                )

            prompt = (
                f"🚨 [SPLIT-SECOND {category} ALERT] 🚨\n"
                f"• Symbol: {sym} | Ticket: #{ticket} | Side: {side_str} | Volume: {vol:.2f} lots\n"
                f"• Fill Price: {p_open:.2f} | Live SL: {sl:.2f} | Live TP: {tp:.2f}\n"
                f"• Comment: {comment or 'Pending Trigger Executed'}\n"
                f"• {tape_str}\n\n"
                f"=== IMMEDIATE ACTION ARMED ===\n"
                f"1. Pull `get_live_microstructure(symbol='{sym}')` to inspect immediate order flow absorption.\n"
                f"2. If reaction confirms thesis (+1.0 to +1.5 pts in profit), prepare scale tranche or set safety stop.\n"
                f"3. If adverse aggressive absorption detected, evaluate immediate early scratch."
            )

            triggered.append({
                "watch": matching_watch,
                "trigger_type": WatchConditionType.ORDER_FILL,
                "ticket": ticket,
                "symbol": sym,
                "price": p_open,
                "volume": vol,
                "side": side_str,
                "prompt": prompt,
                "note": f"Order #{ticket} filled at {p_open:.2f}"
            })

        self.known_positions = {
            t: {
                "symbol": getattr(p, "symbol", "") or (p.get("symbol") if isinstance(p, dict) else ""),
                "type": getattr(p, "type", 0) or (p.get("type") if isinstance(p, dict) else 0),
                "volume": getattr(p, "volume", 0.0) or (p.get("volume") if isinstance(p, dict) else 0.0),
                "price_open": getattr(p, "price_open", 0.0) or (p.get("price_open") if isinstance(p, dict) else 0.0),
            }
            for t, p in curr_pos_map.items()
        }
        self.known_pending_orders = {
            t: {
                "symbol": getattr(o, "symbol", "") or (o.get("symbol") if isinstance(o, dict) else ""),
                "type": getattr(o, "type", 0) or (o.get("type") if isinstance(o, dict) else 0),
                "price_open": getattr(o, "price_open", 0.0) or (o.get("price_open") if isinstance(o, dict) else 0.0),
            }
            for t, o in curr_pending_map.items()
        }

        return triggered

    def evaluate_watch(
        self,
        watch: Dict[str, Any],
        live_tick: Dict[str, float],
        last_tick: Optional[Dict[str, float]] = None,
        tape_metrics: Optional[Dict[str, Any]] = None,
        positions: Optional[List[Any]] = None,
        recent_headlines: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates a single active watch against live conditions.
        Returns trigger dict if fired, None otherwise.
        """
        w_id = watch.get("id") or watch.get("watch_id")
        status = (watch.get("status") or "ACTIVE").upper()
        is_recurring = bool((watch.get("params") or {}).get("is_recurring", False))
        if status in ("TRIGGERED", "CANCELLED", "COMPLETED") and not is_recurring:
            return None

        cond_raw = watch.get("condition", "")
        cond_type = (watch.get("condition_type") or "").upper()
        target_price = watch.get("target_price")
        target_ticket = watch.get("target_ticket")
        direction = str(watch.get("direction", "")).upper()
        params = watch.get("params") or {}

        if not cond_type or cond_type == "PRICE_LEVEL" or target_price is None:
            parsed = parse_watch_condition(
                condition_str=cond_raw,
                target_price=target_price,
                direction=direction,
                condition_type="" if cond_type == "PRICE_LEVEL" else cond_type,
                target_ticket=target_ticket
            )
            cond_type = parsed["condition_type"] if (not cond_type or cond_type == "PRICE_LEVEL") else cond_type
            target_price = target_price if target_price is not None else parsed["target_price"]
            target_ticket = target_ticket if target_ticket is not None else parsed["target_ticket"]
            direction = direction or parsed["direction"]

        bid = float(live_tick.get("bid", 0.0))
        ask = float(live_tick.get("ask", 0.0))
        mid = (bid + ask) / 2.0 if (bid > 0 and ask > 0) else float(live_tick.get("price", 0.0))

        # Traded/execution price context:
        # If buying, relevant price is Ask; if selling, relevant price is Bid.
        # For general directional/level threshold crossing, Bid or Mid accurately reflects price arrival.
        if cond_type in (WatchConditionType.PRICE_BELOW, WatchConditionType.PRICE_CROSS_BELOW):
            curr_price = bid if bid > 0 else mid
        elif cond_type in (WatchConditionType.PRICE_ABOVE, WatchConditionType.PRICE_CROSS_ABOVE):
            curr_price = ask if ("BUY" in direction or "LONG" in direction) else (bid if bid > 0 else mid)
        else:
            curr_price = mid if mid > 0 else bid

        last_bid = float((last_tick or {}).get("bid", bid))
        last_ask = float((last_tick or {}).get("ask", ask))
        last_mid = (last_bid + last_ask) / 2.0 if (last_bid > 0 and last_ask > 0) else float((last_tick or {}).get("price", curr_price))
        if cond_type in (WatchConditionType.PRICE_BELOW, WatchConditionType.PRICE_CROSS_BELOW):
            last_price = last_bid if last_bid > 0 else last_mid
        elif cond_type in (WatchConditionType.PRICE_ABOVE, WatchConditionType.PRICE_CROSS_ABOVE):
            last_price = last_ask if ("BUY" in direction or "LONG" in direction) else (last_bid if last_bid > 0 else last_mid)
        else:
            last_price = last_mid if last_mid > 0 else last_bid

        triggered = False
        trigger_reason = ""
        trigger_val = None

        if cond_type in (WatchConditionType.PRICE_ABOVE, WatchConditionType.PRICE_CROSS_ABOVE):
            if target_price is not None:
                if cond_type == WatchConditionType.PRICE_CROSS_ABOVE:
                    if last_price < target_price and curr_price >= target_price:
                        triggered = True
                        trigger_reason = f"Price crossed above {target_price:.2f} (now {curr_price:.2f})"
                        trigger_val = curr_price
                else:
                    if curr_price >= target_price:
                        triggered = True
                        trigger_reason = f"Price at/above {target_price:.2f} (live {curr_price:.2f})"
                        trigger_val = curr_price

        elif cond_type in (WatchConditionType.PRICE_BELOW, WatchConditionType.PRICE_CROSS_BELOW):
            if target_price is not None:
                if cond_type == WatchConditionType.PRICE_CROSS_BELOW:
                    if last_price > target_price and curr_price <= target_price:
                        triggered = True
                        trigger_reason = f"Price crossed below {target_price:.2f} (now {curr_price:.2f})"
                        trigger_val = curr_price
                else:
                    if curr_price <= target_price:
                        triggered = True
                        trigger_reason = f"Price at/below {target_price:.2f} (live {curr_price:.2f})"
                        trigger_val = curr_price

        elif cond_type == WatchConditionType.PRICE_TOUCH:
            if target_price is not None:
                tol = float(params.get("tolerance", 0.50))
                dist = abs(curr_price - target_price)
                if dist <= tol or (last_price < target_price <= curr_price) or (last_price > target_price >= curr_price):
                    triggered = True
                    trigger_reason = f"Price touched {target_price:.2f} (delta {dist:.2f} pts, live {curr_price:.2f})"
                    trigger_val = curr_price

        elif cond_type == WatchConditionType.VELOCITY_SPIKE:
            min_vel = float(params.get("min_velocity") or 100.0)
            curr_vel = float((tape_metrics or {}).get("velocity", 0.0))
            if curr_vel >= min_vel:
                triggered = True
                trigger_reason = f"Tick velocity spiked to {curr_vel:.1f} t/m (threshold {min_vel:.1f})"
                trigger_val = curr_vel

        elif cond_type == WatchConditionType.SPREAD_SPIKE:
            max_spr = float(params.get("max_spread") or 60.0)
            curr_spr = float((tape_metrics or {}).get("spread", 0.0))
            if curr_spr >= max_spr:
                triggered = True
                trigger_reason = f"Spread widened to {curr_spr:.1f} pts (threshold {max_spr:.1f})"
                trigger_val = curr_spr

        elif cond_type in (WatchConditionType.POSITION_PNL, WatchConditionType.POSITION_DRAWDOWN):
            target_pnl = float(params.get("target_pnl") or (200.0 if cond_type == WatchConditionType.POSITION_PNL else -38.0))
            for p in (positions or []):
                p_ticket = getattr(p, "ticket", None) or (p.get("ticket") if isinstance(p, dict) else None)
                if target_ticket is None or (p_ticket and int(p_ticket) == int(target_ticket)):
                    p_profit = float(getattr(p, "profit", 0.0) or (p.get("profit", 0.0) if isinstance(p, dict) else 0.0))
                    if cond_type == WatchConditionType.POSITION_PNL and p_profit >= target_pnl:
                        triggered = True
                        trigger_reason = f"Position #{p_ticket} PnL reached +${p_profit:.2f} (target +${target_pnl:.2f})"
                        trigger_val = p_profit
                        break
                    elif cond_type == WatchConditionType.POSITION_DRAWDOWN and p_profit <= target_pnl:
                        triggered = True
                        trigger_reason = f"Drawdown alert on position #{p_ticket}: PnL -${abs(p_profit):.2f} (guard -${abs(target_pnl):.2f})"
                        trigger_val = p_profit
                        break

        elif cond_type == WatchConditionType.NEWS_KEYWORD:
            kw_list = params.get("keywords") or [cond_raw]
            for h in (recent_headlines or []):
                h_lower = h.lower()
                for kw in kw_list:
                    if kw.lower() in h_lower:
                        triggered = True
                        trigger_reason = f"News headline matched keyword '{kw}': {h[:90]}..."
                        trigger_val = h
                        break
                if triggered:
                    break

        if not triggered:
            return None

        tape = tape_metrics or {}
        sym = watch.get("symbol", "XAUUSD")
        tape_summary = (
            f"• Live Tape: Bid {bid:.2f} | Ask {ask:.2f} | Spread {tape.get('spread', round((ask-bid)*10, 1))} pts | "
            f"Velocity {tape.get('velocity', 0)} t/m | CVD {tape.get('cvd_10b', 0):+d}"
        )

        prompt = (
            f"⚡ ALPHA EVIDENCE WAKE — WATCH_TRIGGER\n"
            f"WATCH ALERT: {w_id} TRIGGERED!\n"
            f"• Condition: {cond_raw or cond_type}\n"
            f"• Trigger Event: {trigger_reason}\n"
            f"• Instruction: {watch.get('instruction', 'Evaluate immediate current-state validation')}\n"
            f"• Rationale: {watch.get('reason', 'N/A')}\n"
            f"{tape_summary}\n\n"
            f"=== EXECUTION AUDIT ===\n"
            f"1. STEP 0 (MANDATORY): Call `get_market_regime_context(symbol='{sym}')` for live broker quote, spread, CVD flow, and economic calendar.\n"
            f"2. RE-VERIFY THESIS: Audit current price against order book depth (DOM walls), FVGs, volume POC, and footprints.\n"
            f"3. DECIDE: If confirmed by live tape, execute or stage order; if invalidated, cancel or update watch."
        )

        return {
            "watch": watch,
            "watch_id": w_id,
            "trigger_type": cond_type,
            "trigger_reason": trigger_reason,
            "trigger_value": trigger_val,
            "price": curr_price,
            "prompt": prompt
        }