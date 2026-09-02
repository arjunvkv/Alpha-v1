# -*- coding: utf-8 -*-
# nng/safety_guards.py - Institutional Risk & Execution Safety Guards
#
# Covers all real-world operational and quantitative blind spots:
#   1. Spread Blowout Guard (Midnight Rollover & Liquidity Voids)
#   2. Weekend / Friday Close Rollover Risk Guard
#   3. Duplicate Pending Order & Over-Exposure Guard
#   4. FTMO Rule & Maximum Drawdown Guard ($100k Account Specs)
#   5. Broker Minimum StopLevel / FreezeLevel Rejection Guard

import datetime
from typing import Dict, Any, Optional, Tuple, List

# FTMO $100K Account Risk Parameters
FTMO_MAX_DAILY_LOSS = 4500.0  # $5,000 official limit, $4,500 safe cushion
FTMO_MAX_TOTAL_LOSS = 9000.0  # $10,000 official limit, $9,000 safe cushion
MAX_ALLOWED_SPREAD_PTS = 8.0  # Normal Gold spread is 2.5 - 4.5 pts. >8.0 = blowout
MAX_ACTIVE_ORDERS_PER_SYMBOL = 2


def check_spread_guard(live_spread_pts: float, max_allowed: float = MAX_ALLOWED_SPREAD_PTS) -> Dict[str, Any]:
    """
    Blocks execution if the current broker spread is blown out.
    Protects against execution during liquidity voids or broker quotes freeze.
    """
    is_safe = live_spread_pts <= max_allowed
    return {
        "guard_passed": is_safe,
        "spread_pts": round(live_spread_pts, 1),
        "max_allowed": max_allowed,
        "reason": "NORMAL_SPREAD" if is_safe else f"SPREAD_BLOWOUT: {live_spread_pts} pts > {max_allowed} max"
    }


def check_rollover_window(utc_now: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """
    Checks if current time is within broker midnight swap rollover (23:55 - 00:10 UTC).
    Liquidity providers pull bid/ask quotes during this 15-minute window every day.
    """
    if utc_now is None:
        utc_now = datetime.datetime.now(datetime.timezone.utc)

    h = utc_now.hour
    m = utc_now.minute

    in_rollover = (h == 23 and m >= 55) or (h == 0 and m <= 10)
    return {
        "guard_passed": not in_rollover,
        "in_rollover_window": in_rollover,
        "utc_time": utc_now.strftime("%H:%M UTC"),
        "reason": "OK" if not in_rollover else "DAILY_ROLLOVER_WINDOW: Liquidity providers offline (23:55-00:10 UTC)"
    }


def check_weekend_close_guard(utc_now: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """
    Checks if it is Friday after 21:00 UTC.
    Holding open positions into the weekend carries gap risk past stop-loss orders.
    """
    if utc_now is None:
        utc_now = datetime.datetime.now(datetime.timezone.utc)

    # 4 = Friday
    is_friday_close = (utc_now.weekday() == 4 and utc_now.hour >= 21) or (utc_now.weekday() == 5)
    return {
        "guard_passed": not is_friday_close,
        "is_weekend_close": is_friday_close,
        "reason": "OK" if not is_friday_close else "FRIDAY_WEEKEND_CLOSE_GUARD: Holding over weekend prohibited"
    }


def check_duplicate_orders(symbol: str, planned_order_type: str, planned_entry: float, tolerance_pts: float = 2.0) -> Dict[str, Any]:
    """
    Checks MT5 terminal for existing open positions or pending orders.
    Prevents stacking identical orders at the exact same price level.
    """
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return {"guard_passed": True, "reason": "MT5_OFFLINE_BYPASS"}

        # 1. Check open positions
        positions = mt5.positions_get(symbol=symbol)
        pos_count = len(positions) if positions else 0

        # 2. Check pending orders
        orders = mt5.orders_get(symbol=symbol)
        order_count = len(orders) if orders else 0

        # Check if identical pending order already rests at planned entry
        duplicate_found = False
        if orders:
            for o in orders:
                if abs(o.price_open - planned_entry) <= tolerance_pts:
                    duplicate_found = True
                    break

        too_many_orders = (pos_count + order_count) >= MAX_ACTIVE_ORDERS_PER_SYMBOL
        is_safe = (not duplicate_found) and (not too_many_orders)

        reason = "OK"
        if duplicate_found:
            reason = f"DUPLICATE_ORDER_EXISTS: Order already rests near {planned_entry}"
        elif too_many_orders:
            reason = f"MAX_EXPOSURE_REACHED: {pos_count} positions + {order_count} pending orders active"

        return {
            "guard_passed": is_safe,
            "duplicate_found": duplicate_found,
            "active_positions": pos_count,
            "pending_orders": order_count,
            "reason": reason
        }
    except Exception as e:
        return {"guard_passed": True, "reason": f"CHECK_ERROR: {e}"}


def check_ftmo_risk_guard() -> Dict[str, Any]:
    """
    Validates current account equity and daily P&L against FTMO $100K thresholds.
    """
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return {"guard_passed": True, "reason": "MT5_OFFLINE_BYPASS"}

        acc = mt5.account_info()
        if acc is None:
            return {"guard_passed": True, "reason": "ACCOUNT_INFO_UNAVAILABLE"}

        balance = acc.balance
        equity = acc.equity
        floating_pnl = equity - balance

        # Today's closed P&L
        now = datetime.datetime.now(datetime.timezone.utc)
        today_start = datetime.datetime(now.year, now.month, now.day, tzinfo=datetime.timezone.utc)
        history_deals = mt5.history_deals_get(today_start, now)
        today_closed_pnl = 0.0
        if history_deals:
            today_closed_pnl = sum(d.profit for d in history_deals if d.entry in (1, 3))  # out or in/out

        total_daily_pnl = today_closed_pnl + floating_pnl
        daily_loss = -total_daily_pnl if total_daily_pnl < 0 else 0.0
        total_drawdown = balance - equity if equity < balance else 0.0

        daily_breached = daily_loss >= FTMO_MAX_DAILY_LOSS
        total_breached = total_drawdown >= FTMO_MAX_TOTAL_LOSS

        is_safe = (not daily_breached) and (not total_breached)

        reason = "OK"
        if daily_breached:
            reason = f"FTMO_DAILY_LOSS_GUARD: Today's loss ${daily_loss:.2f} >= ${FTMO_MAX_DAILY_LOSS:.2f} limit"
        elif total_breached:
            reason = f"FTMO_MAX_DRAWDOWN_GUARD: Total drawdown ${total_drawdown:.2f} >= ${FTMO_MAX_TOTAL_LOSS:.2f} limit"

        return {
            "guard_passed": is_safe,
            "balance": balance,
            "equity": equity,
            "today_daily_pnl": round(total_daily_pnl, 2),
            "current_drawdown": round(total_drawdown, 2),
            "reason": reason
        }
    except Exception as e:
        return {"guard_passed": True, "reason": f"CHECK_ERROR: {e}"}


def check_broker_stoplevel_distance(symbol: str, order_type: str, entry_price: float, live_bid: float, live_ask: float) -> Dict[str, Any]:
    """
    Ensures limit order entry is far enough from current Bid/Ask to avoid broker RETCODE 10016 rejection.
    """
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return {"guard_passed": True, "reason": "MT5_OFFLINE_BYPASS"}

        sym_info = mt5.symbol_info(symbol)
        if sym_info is None:
            return {"guard_passed": True, "reason": "SYMBOL_INFO_UNAVAILABLE"}

        stop_level_pts = sym_info.trade_stops_level * sym_info.point
        freeze_level_pts = sym_info.trade_freeze_level * sym_info.point
        min_distance = max(stop_level_pts, freeze_level_pts, 0.5)

        ot = order_type.upper()
        if "BUY_LIMIT" in ot:
            dist = live_ask - entry_price
            valid = dist >= min_distance
        elif "SELL_LIMIT" in ot:
            dist = entry_price - live_bid
            valid = dist >= min_distance
        elif "BUY_STOP" in ot:
            dist = entry_price - live_ask
            valid = dist >= min_distance
        elif "SELL_STOP" in ot:
            dist = live_bid - entry_price
            valid = dist >= min_distance
        else:
            valid = True
            dist = 999.0

        return {
            "guard_passed": valid,
            "distance_pts": round(dist, 2),
            "min_required_pts": round(min_distance, 2),
            "reason": "OK" if valid else f"BROKER_STOPLEVEL_VIOLATION: Entry {entry_price} too close to market ({dist:.2f} < {min_distance:.2f} pts)"
        }
    except Exception as e:
        return {"guard_passed": True, "reason": f"CHECK_ERROR: {e}"}


def run_full_safety_audit(symbol: str, order_type: Optional[str], entry_price: Optional[float], live_spread_pts: float, live_bid: float, live_ask: float) -> Dict[str, Any]:
    """
    Runs the complete institutional safety audit across all 5 operational blind spots.
    Returns:
      - all_guards_passed: bool
      - blocked_by: list of triggered guards
      - audit_report: full details
    """
    spread_res = check_spread_guard(live_spread_pts)
    rollover_res = check_rollover_window()
    weekend_res = check_weekend_close_guard()
    ftmo_res = check_ftmo_risk_guard()

    dup_res = {"guard_passed": True, "reason": "NO_ORDER_SPECIFIED"}
    stoplevel_res = {"guard_passed": True, "reason": "NO_ORDER_SPECIFIED"}

    if order_type and entry_price and entry_price > 0:
        dup_res = check_duplicate_orders(symbol, order_type, entry_price)
        stoplevel_res = check_broker_stoplevel_distance(symbol, order_type, entry_price, live_bid, live_ask)

    guards = [
        ("SPREAD_GUARD", spread_res),
        ("ROLLOVER_GUARD", rollover_res),
        ("WEEKEND_GUARD", weekend_res),
        ("FTMO_RISK_GUARD", ftmo_res),
        ("DUPLICATE_ORDER_GUARD", dup_res),
        ("BROKER_STOPLEVEL_GUARD", stoplevel_res),
    ]

    blocked = [name for name, res in guards if not res.get("guard_passed", True)]
    reasons = [res.get("reason") for name, res in guards if not res.get("guard_passed", True)]

    return {
        "all_guards_passed": len(blocked) == 0,
        "blocked_by": blocked,
        "block_reasons": reasons,
        "details": {
            "spread": spread_res,
            "rollover": rollover_res,
            "weekend": weekend_res,
            "ftmo": ftmo_res,
            "duplicate": dup_res,
            "stoplevel": stoplevel_res,
        }
    }
