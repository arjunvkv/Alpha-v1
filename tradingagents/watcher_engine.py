"""
Universal Real-Time Watcher Engine for Alpha Trading Desk.

Evaluates high-frequency market telemetry, MT5 order state transitions,
position metrics, and news catalysts against active objective watches.
Designed for 500ms execution cycles without blocking or heavy computation.
"""

import re
import json
import time
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
    VELOCITY_DECAY = "VELOCITY_DECAY"
    SPREAD_SPIKE = "SPREAD_SPIKE"
    CVD_ABOVE = "CVD_ABOVE"
    CVD_BELOW = "CVD_BELOW"
    CVD_FLIP_BULLISH = "CVD_FLIP_BULLISH"
    CVD_FLIP_BEARISH = "CVD_FLIP_BEARISH"
    NEWS_KEYWORD = "NEWS_KEYWORD"
    CUSTOM = "CUSTOM"


def parse_watch_condition(
    condition_str: str,
    target_price: Optional[float] = None,
    direction: str = "",
    condition_type: str = "",
    target_ticket: Optional[int] = None,
    explicit_keywords: Optional[Any] = None
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
        elif any(k in text_lower for k in ["cvd flip bull", "cvd bullish flip", "delta flip bull"]):
            cond_type = WatchConditionType.CVD_FLIP_BULLISH
        elif any(k in text_lower for k in ["cvd flip bear", "cvd bearish flip", "delta flip bear"]):
            cond_type = WatchConditionType.CVD_FLIP_BEARISH
        elif any(k in text_lower for k in ["cvd above", "cvd >", "delta above"]):
            cond_type = WatchConditionType.CVD_ABOVE
        elif any(k in text_lower for k in ["cvd below", "cvd <", "delta below"]):
            cond_type = WatchConditionType.CVD_BELOW
        elif any(k in text_lower for k in ["velocity decay", "vel decay", "tape stall", "exhaustion", "tape quiet", "low velocity"]):
            cond_type = WatchConditionType.VELOCITY_DECAY
        elif any(k in text_lower for k in ["velocity", "ticks/min", "tpm", "kinetic"]):
            cond_type = WatchConditionType.VELOCITY_SPIKE
        elif any(k in text_lower for k in ["spread", "spread blowout"]):
            cond_type = WatchConditionType.SPREAD_SPIKE
        elif any(k in text_lower for k in ["pnl", "profit", "gain", "drawdown", "loss"]):
            if "drawdown" in text_lower or "loss" in text_lower:
                cond_type = WatchConditionType.POSITION_DRAWDOWN
            else:
                cond_type = WatchConditionType.POSITION_PNL
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
        WatchConditionType.VELOCITY_SPIKE, WatchConditionType.VELOCITY_DECAY,
        WatchConditionType.SPREAD_SPIKE, WatchConditionType.CVD_ABOVE,
        WatchConditionType.CVD_BELOW, WatchConditionType.CVD_FLIP_BULLISH,
        WatchConditionType.CVD_FLIP_BEARISH
    ):
        scrubbed = re.sub(r'#?[0-9]{7,12}', '', text)
        matches = re.findall(r'(?:above|below|at|target|breaks|break|price|level|fvg)?\s*([1-9][0-9]{2,4}(?:\.[0-9]+)?)', scrubbed, re.IGNORECASE)
        if not matches:
            matches = re.findall(r' ([1-9][0-9]{3}(?:\.[0-9]+)?) ', scrubbed)
        if matches:
            try:
                val = float(matches[0])
                if 100.0 <= val <= 20000.0:
                    extracted_target_price = val
            except Exception:
                pass

    # 4. Extract velocity thresholds
    max_velocity = None
    if cond_type == WatchConditionType.VELOCITY_DECAY:
        decay_match = re.search(r'(?:velocity|vel|tpm|decay)\s*(?:<|<=|below)?\s*([0-9]{1,4})', text, re.IGNORECASE)
        if decay_match:
            try:
                max_velocity = float(decay_match.group(1))
            except Exception:
                pass
        if max_velocity is None:
            max_velocity = 30.0
    elif cond_type == WatchConditionType.VELOCITY_SPIKE or "velocity" in text.lower():
        vel_match = re.search(r'(?:velocity|tpm|rate)\s*(?:>|>=|above)?\s*([0-9]{2,4})', text, re.IGNORECASE)
        if vel_match:
            try:
                min_velocity = float(vel_match.group(1))
            except Exception:
                pass
        if min_velocity is None and cond_type == WatchConditionType.VELOCITY_SPIKE:
            min_velocity = 100.0

    # 4b. Extract CVD thresholds
    target_cvd = None
    min_cvd = None
    max_cvd = None
    cvd_match = re.search(r'(?:cvd|delta)\s*(?:>|>=|<|<=|above|below|at)?\s*([+-]?[0-9]{1,6})', text, re.IGNORECASE)
    if cvd_match:
        try:
            target_cvd = float(cvd_match.group(1))
        except Exception:
            pass
    if cond_type == WatchConditionType.CVD_ABOVE:
        min_cvd = target_cvd if target_cvd is not None else 100.0
    elif cond_type == WatchConditionType.CVD_BELOW:
        max_cvd = target_cvd if target_cvd is not None else -100.0

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

    # 6. Extract news keywords if explicit keywords provided
    if explicit_keywords:
        if isinstance(explicit_keywords, str):
            tokens = re.split(r'\s+(?:OR|or|AND|and)\s+|[,;]\s*', explicit_keywords)
            keywords = [t.strip().lower() for t in tokens if t.strip()]
        elif isinstance(explicit_keywords, (list, tuple, set)):
            keywords = [str(k).strip().lower() for k in explicit_keywords if str(k).strip()]

    return {
        "condition_type": cond_type,
        "target_price": extracted_target_price,
        "target_ticket": extracted_ticket,
        "tolerance": tolerance,
        "min_velocity": min_velocity,
        "max_velocity": max_velocity,
        "min_cvd": min_cvd,
        "max_cvd": max_cvd,
        "target_cvd": target_cvd,
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
        self.watch_cooldowns: Dict[str, float] = {}
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
                f"=== CHAMPION BROKER SUPREMACY & HOLD MANDATE ===\n"
                f"1. VERIFY BROKER SL & TP: Order is filled with a hard 6.0–10.0 pt structural SL and Mode A TP (4.0–8.0 pts) or Extended Mode B TP (12.0–20.0 pts).\n"
                f"2. NO PANIC SCRATCHES & NO PREMATURE BE: Normal entry shelf retests routinely wick ±0.5 to 1.5 pts past entry. Let the trade breathe behind the structural stop.\n"
                f"3. 3-Burst & 5-Min Breathe cadence is now engaged. LET THE BROKER MANAGE SL AND TP!"
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
        if status in ("TRIGGERED", "CANCELLED", "COMPLETED"):
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

        title_str = watch.get("title") or cond_raw or f"{watch.get('symbol', 'XAUUSD')} Technical Trigger"
        matched_criteria = []
        total_criteria = 0
        all_passed = True
        primary_val = curr_price

        # 1. Price Criterion (if target_price or price condition specified)
        has_price_target = (target_price is not None)
        if has_price_target or cond_type in (
            WatchConditionType.PRICE_ABOVE, WatchConditionType.PRICE_CROSS_ABOVE,
            WatchConditionType.PRICE_BELOW, WatchConditionType.PRICE_CROSS_BELOW,
            WatchConditionType.PRICE_TOUCH
        ):
            if target_price is not None:
                total_criteria += 1
                price_matched = False
                price_detail = ""
                tol = float(params.get("tolerance", 0.50))

                if cond_type in (WatchConditionType.PRICE_CROSS_ABOVE, "CROSS_ABOVE"):
                    if (last_price < target_price and curr_price >= target_price) or (curr_price >= target_price and abs(curr_price - target_price) <= max(2.0, tol)):
                        price_matched = True
                        price_detail = f"Price crossed above {target_price:.2f} (live {curr_price:.2f})"
                elif cond_type in (WatchConditionType.PRICE_ABOVE, "ABOVE"):
                    if curr_price >= target_price:
                        price_matched = True
                        price_detail = f"Price at/above {target_price:.2f} (live {curr_price:.2f})"
                elif cond_type in (WatchConditionType.PRICE_CROSS_BELOW, "CROSS_BELOW"):
                    if (last_price > target_price and curr_price <= target_price) or (curr_price <= target_price and abs(curr_price - target_price) <= max(2.0, tol)):
                        price_matched = True
                        price_detail = f"Price crossed below {target_price:.2f} (live {curr_price:.2f})"
                elif cond_type in (WatchConditionType.PRICE_BELOW, "BELOW"):
                    if curr_price <= target_price:
                        price_matched = True
                        price_detail = f"Price at/below {target_price:.2f} (live {curr_price:.2f})"
                else:  # PRICE_TOUCH or default
                    dist = abs(curr_price - target_price)
                    if dist <= tol or (last_price < target_price <= curr_price) or (last_price > target_price >= curr_price):
                        price_matched = True
                        price_detail = f"Price touched {target_price:.2f} (delta {dist:.2f} pts, live {curr_price:.2f})"

                if price_matched:
                    matched_criteria.append(f"Price: {price_detail}")
                    primary_val = curr_price
                else:
                    all_passed = False

        # 2. Velocity Minimum Criterion (Surge / Momentum)
        min_vel = params.get("min_velocity")
        if min_vel is None and cond_type == WatchConditionType.VELOCITY_SPIKE:
            min_vel = 100.0
        if min_vel is not None:
            total_criteria += 1
            curr_vel = float((tape_metrics or {}).get("velocity", 0.0))
            if curr_vel >= float(min_vel):
                matched_criteria.append(f"Velocity Surge: {curr_vel:.1f} t/m >= {float(min_vel):.1f} t/m")
                if not has_price_target:
                    primary_val = curr_vel
            else:
                all_passed = False

        # 3. Velocity Maximum Criterion (Decay / Exhaustion Floor)
        max_vel = params.get("max_velocity")
        if max_vel is None and cond_type == WatchConditionType.VELOCITY_DECAY:
            max_vel = 30.0
        if max_vel is not None:
            total_criteria += 1
            curr_vel = float((tape_metrics or {}).get("velocity", 0.0))
            if 0.0 < curr_vel <= float(max_vel):
                matched_criteria.append(f"Velocity Decay: {curr_vel:.1f} t/m <= {float(max_vel):.1f} t/m (exhaustion floor)")
                if not has_price_target:
                    primary_val = curr_vel
            else:
                all_passed = False

        # 4. CVD Minimum Criterion (Buyer Accumulation Dominance)
        min_cvd = params.get("min_cvd")
        if min_cvd is None and cond_type == WatchConditionType.CVD_ABOVE:
            min_cvd = params.get("target_cvd") or 100.0
        if min_cvd is not None:
            total_criteria += 1
            curr_cvd = float((tape_metrics or {}).get("cvd_10b", 0.0))
            if curr_cvd >= float(min_cvd):
                matched_criteria.append(f"CVD Net Flow: {int(curr_cvd):+d} >= {int(float(min_cvd)):+d} (buyer dominance)")
                if not has_price_target and min_vel is None:
                    primary_val = curr_cvd
            else:
                all_passed = False

        # 5. CVD Maximum Criterion (Seller Liquidation Dominance)
        max_cvd = params.get("max_cvd")
        if max_cvd is None and cond_type == WatchConditionType.CVD_BELOW:
            max_cvd = params.get("target_cvd") or -100.0
        if max_cvd is not None:
            total_criteria += 1
            curr_cvd = float((tape_metrics or {}).get("cvd_10b", 0.0))
            if curr_cvd <= float(max_cvd):
                matched_criteria.append(f"CVD Net Flow: {int(curr_cvd):+d} <= {int(float(max_cvd)):+d} (seller dominance)")
                if not has_price_target and min_vel is None:
                    primary_val = curr_cvd
            else:
                all_passed = False

        # 6. CVD Directional Flip Criterion (Persistent Active Flow, Dynamic Flip, or Micro-Delta Absorption)
        cvd_flip = str(params.get("cvd_flip") or ("BULLISH" if cond_type == WatchConditionType.CVD_FLIP_BULLISH else ("BEARISH" if cond_type == WatchConditionType.CVD_FLIP_BEARISH else ""))).upper()
        if cvd_flip:
            total_criteria += 1
            curr_cvd = float((tape_metrics or {}).get("cvd_10b", 0.0))
            last_cvd = float(self.last_ticks.get(watch.get("symbol", "XAUUSD"), {}).get("last_cvd", 0.0))
            micro_4m = float((tape_metrics or {}).get("micro_delta_4m", 0.0))
            m1_delta = float((tape_metrics or {}).get("current_m1_delta", 0.0))
            
            if cvd_flip == "BULLISH":
                if curr_cvd > 0:
                    matched_criteria.append(f"CVD Flow: Bullish (+{int(curr_cvd):+d} active delta)")
                elif last_cvd <= 0 and curr_cvd > 0:
                    matched_criteria.append(f"CVD Flip: Bullish (+{int(curr_cvd):+d} from prior {int(last_cvd):+d})")
                elif micro_4m > 0 or m1_delta > 0:
                    matched_criteria.append(f"Micro-Delta Flow: Bullish (M1: {m1_delta:+d} / 4M: {micro_4m:+d})")
                else:
                    all_passed = False
            elif cvd_flip == "BEARISH":
                if curr_cvd < 0:
                    matched_criteria.append(f"CVD Flow: Bearish ({int(curr_cvd):+d} active delta)")
                elif last_cvd >= 0 and curr_cvd < 0:
                    matched_criteria.append(f"CVD Flip: Bearish ({int(curr_cvd):+d} from prior {int(last_cvd):+d})")
                elif micro_4m < 0 or m1_delta < 0:
                    matched_criteria.append(f"Micro-Delta Flow: Bearish (M1: {m1_delta:+d} / 4M: {micro_4m:+d})")
                else:
                    all_passed = False

        # 7. Spread Spike Criterion
        if cond_type == WatchConditionType.SPREAD_SPIKE:
            total_criteria += 1
            curr_spr = float((tape_metrics or {}).get("spread", 0.0))
            max_spr = float(params.get("max_spread") or 60.0)
            if curr_spr >= max_spr:
                matched_criteria.append(f"Spread Blowout: {curr_spr:.1f} pts >= {max_spr:.1f} pts")
                primary_val = curr_spr
            else:
                all_passed = False

        # 8. Position PnL / Drawdown Criterion
        if cond_type in (WatchConditionType.POSITION_PNL, WatchConditionType.POSITION_DRAWDOWN) or params.get("target_pnl") is not None:
            total_criteria += 1
            target_pnl = float(params.get("target_pnl") or (200.0 if cond_type == WatchConditionType.POSITION_PNL else -38.0))
            pos_matched = False
            for p in (positions or []):
                p_ticket = getattr(p, "ticket", None) or (p.get("ticket") if isinstance(p, dict) else None)
                if target_ticket is None or (p_ticket and int(p_ticket) == int(target_ticket)):
                    p_profit = float(getattr(p, "profit", 0.0) or (p.get("profit", 0.0) if isinstance(p, dict) else 0.0))
                    if cond_type == WatchConditionType.POSITION_PNL and p_profit >= target_pnl:
                        pos_matched = True
                        matched_criteria.append(f"Position #{p_ticket} PnL: +${p_profit:.2f} >= +${target_pnl:.2f}")
                        primary_val = p_profit
                        break
                    elif cond_type == WatchConditionType.POSITION_DRAWDOWN and p_profit <= target_pnl:
                        pos_matched = True
                        matched_criteria.append(f"Position #{p_ticket} Drawdown: -${abs(p_profit):.2f} (guard -${abs(target_pnl):.2f})")
                        primary_val = p_profit
                        break
            if not pos_matched:
                all_passed = False

        # If no criteria defined or any condition failed, do not trigger
        if total_criteria == 0 or not all_passed or len(matched_criteria) < total_criteria:
            return None

        tape = tape_metrics or {}
        sym = watch.get("symbol", "XAUUSD")
        tape_summary = (
            f"• Live Tape: Bid {bid:.2f} | Ask {ask:.2f} | Spread {tape.get('spread', round((ask-bid)*10, 1))} pts | "
            f"Velocity {tape.get('velocity', 0)} t/m | CVD {int(tape.get('cvd_10b', 0)):+d}"
        )

        criteria_lines = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(matched_criteria))
        trigger_summary = f"{len(matched_criteria)}/{total_criteria} criteria met: " + "; ".join(matched_criteria)

        prompt = (
            f"⚡ ALPHA EVIDENCE WAKE — WATCH_TRIGGER\n"
            f"WATCH ALERT: {w_id} TRIGGERED!\n"
            f"• Reason Title: {title_str}\n"
            f"• Condition: {cond_raw or cond_type}\n"
            f"• Confluence Match ({len(matched_criteria)}/{total_criteria} criteria satisfied):\n"
            f"{criteria_lines}\n"
            f"• Instruction: {watch.get('instruction', 'Evaluate immediate current-state validation')}\n"
            f"• Rationale: {watch.get('reason', 'N/A')}\n"
            f"{tape_summary}\n\n"
            f"=== 5-POD ADVERSARIAL EXECUTION AUDIT ===\n"
            f"1. STEP 0 (MANDATORY): Call `alpha_get_market_regime_context(symbol='{sym}')` for live broker quote, spread, CVD flow, and economic calendar.\n"
            f"2. EVALUATE VIA 5-POD PROTOCOL: If confirmed by live tape and macro wires, execute direct market or breakout stop directly on MT5 book; if invalidated, stand flat.\n"
            f"3. NO PASSIVE WATCH SENSOR LOOPS: Pre-stage orders directly on MT5 book."
        )

        return {
            "watch": watch,
            "watch_id": w_id,
            "title": title_str,
            "trigger_type": cond_type,
            "trigger_reason": trigger_summary,
            "trigger_value": primary_val,
            "price": curr_price,
            "prompt": prompt
        }