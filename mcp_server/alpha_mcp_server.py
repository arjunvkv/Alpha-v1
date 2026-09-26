"""
======================================================================
           ALPHA V1 - OFFICIAL FASTMCP SERVER (alpha-daemon-mcp)
======================================================================
Exposes direct autonomous MCP tools to OpenCode.
Learning review state is kept in the existing unified learning surface.
======================================================================
"""

import sys
import os
import json
import re
import logging
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, List

TRADING_ROOT = Path(__file__).resolve().parent.parent.parent
if str(TRADING_ROOT) not in sys.path:
    sys.path.insert(0, str(TRADING_ROOT))
ALPHA_ROOT = Path(__file__).resolve().parent.parent
if str(ALPHA_ROOT) not in sys.path:
    sys.path.insert(0, str(ALPHA_ROOT))

from mcp.server.fastmcp import FastMCP
from logs.story_logger import log_opencode_said, log_local_llm_replied, log_story
from tradingagents.read_logger import DossierReadLogger
from tradingagents.evidence_state import EvidenceStateStore
read_logger = DossierReadLogger()
evidence_state = EvidenceStateStore()
from tradingagents.world_events import LiveWorldEventsEngine
from sensors.evidence_sources import FREDAdapter, GDELTAdapter, RSSRegistry, CommonCrawlAdapter, capability_snapshot
world_events_engine = LiveWorldEventsEngine()

from config import (
    get_opencode_session,
    get_opencode_session_id,
    get_opencode_session_title
)

from tradingagents.agent_graph import (
    TechnicalAnalyst,
    FundamentalAnalyst,
    MacroNewsAnalyst,
    SentimentAnalyst,
    TradingAgentsDesk
)
from tradingagents.institutional_analytics import InstitutionalAnalyticsEngine
from tradingagents.multitimeframe import MultiTimeframeAnalyst

import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor

MCP_EXECUTOR = ThreadPoolExecutor(max_workers=32, thread_name_prefix="alpha-mcp-worker")

async def run_in_thread(func, *args, **kwargs):
    """Executes any blocking function in a dedicated background worker thread to prevent blocking FastMCP event loop."""
    loop = asyncio.get_running_loop()
    if kwargs:
        p_func = functools.partial(func, *args, **kwargs)
        return await loop.run_in_executor(MCP_EXECUTOR, p_func)
    return await loop.run_in_executor(MCP_EXECUTOR, func, *args)

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
LOG = logging.getLogger("alpha.mcp.server")
FTMO_PATH = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
mcp = FastMCP("alpha")

# Pre-instantiated singletons for sub-10ms response times
_tech_analyst = TechnicalAnalyst()
_fund_analyst = FundamentalAnalyst()
_macro_analyst = MacroNewsAnalyst()
_sent_analyst = SentimentAnalyst()
_inst_engine = InstitutionalAnalyticsEngine()
_mtf_analyst = MultiTimeframeAnalyst()
_desk = TradingAgentsDesk()
_active_watches: Dict[str, Dict[str, Any]] = {}
_fred_adapter = FREDAdapter()
_gdelt_adapter = GDELTAdapter()
_rss_registry = RSSRegistry()
_common_crawl_adapter = CommonCrawlAdapter()

class AlphaMCPServer:
    def __init__(self):
        self.session_id = get_opencode_session_id()
        self.session_title = get_opencode_session_title()
        self.active_watches: List[Dict[str, Any]] = []
        self.unsolicited_insights: List[Dict[str, Any]] = []
        _init_mt5()

def _init_mt5():
    try:
        import MetaTrader5 as mt5
        if mt5.terminal_info() is not None and getattr(mt5.terminal_info(), "connected", False):
            return True
        from tradingagents.mt5_connector import ensure_mt5_connected
        return ensure_mt5_connected(timeout=5000)
    except Exception as err:
        LOG.error(f"MT5 init error: {err}")
        return False

def _normalize_symbol(symbol: str) -> str:
    """Normalizes symbol names across broker casing conventions (e.g. USOIL.cash vs USOIL.CASH)."""
    s = str(symbol or "XAUUSD").strip()
    if s.upper() in ("USOIL", "USOIL.CASH"):
        return "USOIL.cash"
    return s.upper()

# Quarantined: passive software watches deprecated in favor of direct MT5 orders
def mcp_alpha_register_watch(
    symbol: str = "XAUUSD",
    title: str = "",
    condition: str = "",
    instruction: str = "",
    target_price: float = None,
    reason: str = "",
    direction: str = "",
    watch_id: str = "",
    condition_type: str = "",
    target_ticket: int = None,
    tolerance: float = 0.50,
    min_velocity: float = None,
    max_velocity: float = None,
    min_cvd: float = None,
    max_cvd: float = None,
    target_cvd: float = None,
    cvd_flip: str = "",
    target_pnl: float = None,
    max_spread: float = None,
    is_recurring: bool = False,
    keywords: Any = None
) -> str:
    """Create or update a universal persistent watch (single technical or multi-criteria composite).
    
    Supports:
        - Reason Title: Specify a clear title (e.g. title="Demand Zone Reclaim & CVD Surge") so OpenCode knows why it triggered.
        - Single Technical Watch: only velocity (min_velocity or max_velocity), only CVD (min_cvd, max_cvd, or cvd_flip), only spread, only price, or only position PnL.
        - Multiple Matching (Composite Confluence): attach min_velocity, min_cvd/max_cvd, cvd_flip to ANY price watch. All populated criteria must match simultaneously (strict AND confluence).
        - Lifecycle: Auto-clears immediately upon trigger.
    """
    from tradingagents.watcher_engine import parse_watch_condition, WatchConditionType
    sym = _normalize_symbol(symbol)

    parsed = parse_watch_condition(
        condition_str=condition,
        target_price=target_price,
        direction=direction,
        condition_type=condition_type,
        target_ticket=target_ticket,
        explicit_keywords=keywords
    )
    final_cond_type = condition_type.upper() if condition_type else parsed["condition_type"]
    if final_cond_type == "NEWS_KEYWORD":
        return json.dumps({
            "status": "REJECTED_BY_STANDING_ORDERS",
            "error": "NEWS_KEYWORD watches are deprecated. Per Standing Orders Section 7: OpenCode owns 100% of news & macro synthesis via Proxima sweeps. The 500ms daemon watcher is strictly reserved for pure structural execution. Please translate your catalyst into a deterministic structural trigger: PRICE_CROSS_ABOVE, PRICE_CROSS_BELOW, PRICE_TOUCH, or ORDER_FILL."
        }, indent=2)

    final_price = float(target_price) if target_price is not None else parsed["target_price"]
    final_ticket = int(target_ticket) if target_ticket is not None else parsed["target_ticket"]
    final_dir = (direction or parsed["direction"]).upper()

    params = {
        "tolerance": float(tolerance) if tolerance is not None else parsed["tolerance"],
        "min_velocity": float(min_velocity) if min_velocity is not None else parsed["min_velocity"],
        "max_velocity": float(max_velocity) if max_velocity is not None else parsed["max_velocity"],
        "min_cvd": float(min_cvd) if min_cvd is not None else parsed["min_cvd"],
        "max_cvd": float(max_cvd) if max_cvd is not None else parsed["max_cvd"],
        "target_cvd": float(target_cvd) if target_cvd is not None else parsed["target_cvd"],
        "cvd_flip": str(cvd_flip).upper() if cvd_flip else "",
        "target_pnl": float(target_pnl) if target_pnl is not None else None,
        "max_spread": float(max_spread) if max_spread is not None else parsed["max_spread"],
        "target_ticket": final_ticket,
        "keywords": parsed["keywords"],
        "is_recurring": False  # Enforced: All watches auto-clear immediately upon trigger
    }

    final_title = title or reason or condition or instruction or f"Watching {sym} [{final_cond_type}]"
    desc = condition or instruction or reason or f"Watching {sym} [{final_cond_type}] @ {final_price}"
    watch = evidence_state.upsert_watch({
        "id": watch_id or None,
        "symbol": sym,
        "title": final_title,
        "condition": desc,
        "condition_type": final_cond_type,
        "instruction": instruction,
        "target_price": final_price,
        "target_ticket": final_ticket,
        "direction": final_dir,
        "reason": reason,
        "params": params,
        "status": "ACTIVE"
    })
    _active_watches[watch["id"]] = watch
    return json.dumps({"status": "REGISTERED", "watch": watch}, indent=2)

def mcp_alpha_get_active_watches(symbol: str = None, include_closed: bool = False) -> str:
    """Fetch persistent active watches. Returns clean, compact watch definitions with zero redundant fields to prevent context bloat."""
    raw_watches = evidence_state.get_watches(_normalize_symbol(symbol) if symbol else None, include_closed)
    clean_watches = []
    for w in raw_watches:
        if not isinstance(w, dict):
            continue
        clean_w = {
            "id": w.get("id"),
            "status": w.get("status"),
            "symbol": w.get("symbol"),
            "title": w.get("title") or w.get("reason", "Watch Alert"),
            "target_price": w.get("target_price"),
            "condition_type": w.get("condition_type"),
            "reason": w.get("reason") or w.get("condition", "")
        }
        # Include specific trigger gates if configured
        params = w.get("params", {})
        if isinstance(params, dict) and params:
            gates = {}
            for k in ("min_velocity", "max_velocity", "min_cvd", "max_cvd", "cvd_flip", "max_spread", "target_pnl"):
                if params.get(k) is not None:
                    gates[k] = params[k]
            if gates:
                clean_w["gates"] = gates
        clean_watches.append(clean_w)
    return json.dumps(clean_watches, indent=2)

def mcp_alpha_update_watch(watch_id: str, status: str = "", condition: str = "", instruction: str = "", target_price: float = None, reason: str = "") -> str:
    changes={"status": status or None, "condition": condition or None, "instruction": instruction or None,
             "target_price": target_price, "reason": reason or None}
    watch=evidence_state.update_watch(watch_id, **changes)
    if not watch: return json.dumps({"status":"NOT_FOUND","watch_id":watch_id})
    _active_watches[watch_id]=watch
    return json.dumps({"status":"UPDATED","watch":watch}, indent=2)

def mcp_alpha_cancel_watch(watch_id: str) -> str:
    """Cancel / remove an active persistent watch by ID."""
    w = evidence_state.cancel_watch(watch_id)
    if not w:
        return json.dumps({"status": "NOT_FOUND", "watch_id": watch_id}, indent=2)
    _active_watches[watch_id] = w
    return json.dumps({"status": "CANCELLED", "watch": w}, indent=2)

def mcp_alpha_clear_completed_watches(symbol: str = None) -> str:
    """Clear all triggered and cancelled watches from disk memory."""
    sym = _normalize_symbol(symbol) if symbol else None
    cleared = evidence_state.clear_completed_watches(sym)
    return json.dumps({"status": "SUCCESS", "cleared_count": cleared, "symbol": sym or "ALL"}, indent=2)

def mcp_alpha_mark_watches_observed(watch_ids: List[str]) -> str:
    """Mark one or many watches observed in one MCP call."""
    changed=evidence_state.mark_watches_observed(watch_ids)
    return json.dumps({"status":"UPDATED","count":len(changed),"watches":changed}, indent=2)

def mcp_alpha_mark_evidence_read(evidence_ids: List[str]) -> str:
    """Mark one or many persistent news/evidence records read in one MCP call."""
    changed=evidence_state.mark_read(evidence_ids)
    return json.dumps({"status":"UPDATED","count":len(changed),"items":changed}, indent=2)

def mcp_alpha_get_market_time_context(target_time: str = "", target_timezone: str = "America/New_York") -> str:
    """General market time and session helper."""
    try:
        from tradingagents.time_helper import get_market_time_context
        ctx = get_market_time_context(target_time=target_time, target_timezone=target_timezone)
        return json.dumps(ctx, indent=2)
    except Exception as err:
        return json.dumps({"status": "ERROR", "error": str(err)})

# ======================================================================
# MARKET AREA SEPARATION & VETO GATES (HISTORICAL 68-TRADE DATABASE FILTER)
# ======================================================================

def _validate_market_area_gates(sym: str, side: str, entry_price: float, tag: str) -> tuple[bool, str]:
    """Autonomous CIO execution gate: Unrestricted execution authorized.
    Never auto-blocks or vetoes OpenCode execution.
    """
    return True, ""

# ======================================================================
# 1. DIRECT MARKET EXECUTION (VOLUME & STRUCTURAL SL/TP DIRECTLY SET)
# ======================================================================

def mcp_alpha_execute_market_order(
    symbol: str = "XAUUSD",
    side: str = "BUY",
    volume: float = 1.0,
    sl_price: float = 0.0,
    tp_price: float = 0.0,
    sl: float = 0.0,
    tp: float = 0.0,
    comment: str = "OpenCode Market Order"
) -> str:
    """Execute direct market order on FTMO MT5 with custom volume, stop loss, and take profit.
    
    Args:
        symbol: Instrument symbol (default: 'XAUUSD')
        side: 'BUY' or 'SELL'
        volume: Trade lot size (default: 1.0)
        sl_price: Specific stop loss price level (alias: sl)
        tp_price: Specific take profit price level (alias: tp)
        sl: Stop loss price level (alias for sl_price)
        tp: Take profit price level (alias for tp_price)
        comment: Order comment tag
    """
    final_sl = float(sl_price) if sl_price and float(sl_price) > 0 else (float(sl) if sl and float(sl) > 0 else 0.0)
    final_tp = float(tp_price) if tp_price and float(tp_price) > 0 else (float(tp) if tp and float(tp) > 0 else 0.0)
    
    vol = float(volume) if volume and float(volume) > 0 else 0.50
    sym_norm = _normalize_symbol(symbol)
    _init_mt5()
    
    read_logger.log_dossier_read("OpenCode CIO (MCP Market Order)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Market Order: {side.upper()} {vol} lots on {symbol} (SL: {final_sl}, TP: {final_tp})")
    
    # Weekend Guardrail
    try:
        from tradingagents.world_market import IntradayInstitutionalEngine
        session_info = IntradayInstitutionalEngine().get_session_status()
        is_weekend = (not session_info.get("market_open", True)) or session_info.get("market_status") == "WEEKEND_MARKET_CLOSED" or session_info.get("session") == "WEEKEND_MARKET_CLOSED"
        if is_weekend:
            return json.dumps({
                "status": "EXECUTION_BLOCKED_WEEKEND_MARKET_CLOSED",
                "error": "Interbank & FTMO broker markets are CLOSED for the weekend. Execution is prohibited until Sunday 21:00 UTC."
            }, indent=2)
    except Exception as e:
        LOG.warning(f"Weekend guardrail check error: {e}")

    _init_mt5()
    try:
        import MetaTrader5 as mt5
        sym = _normalize_symbol(symbol)
        s_side = side.lower().strip()
        
        # Ensure symbol is selected in Market Watch
        mt5.symbol_select(sym, True)
        
        sym_info = mt5.symbol_info(sym)
        if not sym_info:
            return json.dumps({"status": "FAILED", "error": f"Symbol {sym} not found in MT5 terminal"}, indent=2)
            
        tick_info = mt5.symbol_info_tick(sym)
        if not tick_info:
            return json.dumps({"status": "FAILED", "error": f"No live tick info for {sym}"}, indent=2)
            
        price = tick_info.ask if s_side == "buy" else tick_info.bid
        order_type = mt5.ORDER_TYPE_BUY if s_side == "buy" else mt5.ORDER_TYPE_SELL
        
        # Normalize volume to broker step and bounds
        step = sym_info.volume_step if sym_info.volume_step > 0 else 0.01
        vol = round(round(vol / step) * step, 2)
        vol = max(sym_info.volume_min, min(sym_info.volume_max, vol))
        
        # Determine valid filling mode from broker capability (FTMO accepts IOC or FOK)
        filling_mode = mt5.ORDER_FILLING_IOC
        if sym_info.filling_mode & 1:  # FOK mask or IOC
            filling_mode = mt5.ORDER_FILLING_IOC
        elif sym_info.filling_mode & 2:
            filling_mode = mt5.ORDER_FILLING_FOK
            
        clean_comment = re.sub(r'[^A-Za-z0-9_\- ]', '', str(comment or "Alpha"))[:25]
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": sym,
            "volume": vol,
            "type": order_type,
            "price": price,
            "sl": float(final_sl),
            "tp": float(final_tp),
            "deviation": 50,
            "magic": 234000,
            "comment": clean_comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode
        }
        
        res = mt5.order_send(req)
        # If filling mode rejected (10030), retry with alternate filling mode
        if not res or res.retcode == 10030:
            req["type_filling"] = mt5.ORDER_FILLING_FOK if filling_mode != mt5.ORDER_FILLING_FOK else mt5.ORDER_FILLING_IOC
            res = mt5.order_send(req)
            
        # If still failed due to comment / argument error (-2), retry with minimal comment
        if not res:
            last_err = mt5.last_error()
            if last_err and last_err[0] == -2:
                req["comment"] = "Alpha"
                res = mt5.order_send(req)
            
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            log_local_llm_replied(f"Market Order executed on MT5! {s_side.upper()} {vol} lots on {sym} @ {price} | SL: {final_sl} | TP: {final_tp} (Ticket #{res.order}).")
            return json.dumps({
                "status": "EXECUTED",
                "symbol": sym,
                "side": s_side.upper(),
                "volume": vol,
                "price": price,
                "sl": final_sl,
                "tp": final_tp,
                "ticket": res.order,
                "retcode": res.retcode,
                "message": f"Market order filled! Active ticket #{res.order} is live on MT5."
            }, indent=2)
            
        # Detailed diagnostics
        if res:
            err_comment = f"MT5 Retcode {res.retcode}: {res.comment}"
        else:
            last_err = mt5.last_error()
            err_comment = f"MT5 order_send returned None (Last Error: {last_err})"
            
        return json.dumps({
            "status": "FAILED",
            "symbol": sym,
            "error": err_comment,
            "retcode": getattr(res, 'retcode', None),
            "last_error": mt5.last_error() if not res else None
        }, indent=2)
    except Exception as err:
        return json.dumps({"status": "FAILED", "error": str(err)}, indent=2)

@mcp.tool()
def execute_market_order(symbol: str = "XAUUSD", side: str = "BUY", volume: float = 1.0, sl_price: float = 0.0, tp_price: float = 0.0, sl: float = 0.0, tp: float = 0.0, comment: str = "OpenCode Market Order") -> str:
    """Execute direct market order on FTMO MT5 with custom volume, SL, and TP."""
    return mcp_alpha_execute_market_order(symbol, side, volume, sl_price, tp_price, sl, tp, comment)


# ======================================================================
# 2. PLANNED PENDING ORDER (VOLUME & STRUCTURAL SL/TP DIRECTLY SET)
# ======================================================================

def mcp_alpha_place_pending_order(
    symbol: str = "XAUUSD",
    order_type: str = "SELL_LIMIT",
    price: float = 0.0,
    volume: float = 1.0,
    sl_price: float = 0.0,
    tp_price: float = 0.0,
    sl: float = 0.0,
    tp: float = 0.0,
    tag: str = ""
) -> str:
    """Place planned pending limit or stop order on MT5 at key structural points with custom volume, SL, and TP.
    
    Supports:
      • Limits: SELL_LIMIT (Supply Ceiling / FVG CE), BUY_LIMIT (Demand Floor / Support)
      • Stops: BUY_STOP (breakout continuation), SELL_STOP (breakdown continuation)
    
    Args:
        symbol: Instrument symbol (default: 'XAUUSD')
        order_type: 'SELL_LIMIT', 'BUY_LIMIT', 'BUY_STOP', 'SELL_STOP'
        price: Planned entry price level
        volume: Order lot size (default: 1.0)
        sl_price: Specific stop loss price level (alias: sl)
        tp_price: Specific take profit price level (alias: tp)
        sl: Stop loss price level (alias for sl_price)
        tp: Take profit price level (alias for tp_price)
        tag: Custom tag / structural description (e.g. 'Supply_Ceiling_4318')
    """
    final_sl = float(sl_price) if sl_price and float(sl_price) > 0 else (float(sl) if sl and float(sl) > 0 else 0.0)
    final_tp = float(tp_price) if tp_price and float(tp_price) > 0 else (float(tp) if tp and float(tp) > 0 else 0.0)
    
    vol = float(volume) if volume and float(volume) > 0 else 0.50
    
    _init_mt5()
    read_logger.log_dossier_read("OpenCode CIO (MCP Pending Order)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Pending Order requested: {order_type.upper()} {vol} lots on {symbol} @ {price} (SL: {final_sl}, TP: {final_tp}, Tag: {tag})")
    
    try:
        import MetaTrader5 as mt5, re
        sym = _normalize_symbol(symbol)
        mt5.symbol_select(sym, True)
        sym_info = mt5.symbol_info(sym)
        if not sym_info:
            return json.dumps({"status": "FAILED", "error": f"Symbol {sym} not found in MT5"}, indent=2)
            
        ot_clean = order_type.upper().strip()
        type_map = {
            "BUY_LIMIT": mt5.ORDER_TYPE_BUY_LIMIT,
            "SELL_LIMIT": mt5.ORDER_TYPE_SELL_LIMIT,
            "BUY_STOP": mt5.ORDER_TYPE_BUY_STOP,
            "SELL_STOP": mt5.ORDER_TYPE_SELL_STOP
        }
        
        if ot_clean not in type_map:
            return json.dumps({
                "status": "INVALID_ORDER_TYPE",
                "error": f"Invalid order_type '{order_type}'. Supported: {list(type_map.keys())}"
            }, indent=2)
            
        target_price = float(price)
        if target_price <= 0:
            return json.dumps({
                "status": "INVALID_PRICE",
                "error": "Price must be a positive number greater than 0."
            }, indent=2)

        # Pre-validate price distance against live market quotes to prevent MT5 Retcode 10015
        tick_info = mt5.symbol_info_tick(sym)
        if tick_info:
            curr_bid = getattr(tick_info, "bid", 0.0)
            curr_ask = getattr(tick_info, "ask", 0.0)
            point = getattr(sym_info, "point", 0.01) or 0.01
            stops_level_pts = (getattr(sym_info, "trade_stops_level", 0) or 0) * point
            min_dist = max(stops_level_pts, point * 5)

            if ot_clean == "BUY_STOP" and target_price < (curr_ask + min_dist):
                return json.dumps({
                    "status": "INVALID_PRICE_DISTANCE",
                    "error": f"BUY_STOP price ({target_price}) must be strictly ABOVE current ask ({curr_ask:.2f}) by at least stops_level ({min_dist:.2f} pts). Target price must be >= {curr_ask + min_dist:.2f}"
                }, indent=2)
            elif ot_clean == "SELL_STOP" and target_price > (curr_bid - min_dist):
                return json.dumps({
                    "status": "INVALID_PRICE_DISTANCE",
                    "error": f"SELL_STOP price ({target_price}) must be strictly BELOW current bid ({curr_bid:.2f}) by at least stops_level ({min_dist:.2f} pts). Target price must be <= {curr_bid - min_dist:.2f}"
                }, indent=2)
            elif ot_clean == "BUY_LIMIT" and target_price > (curr_ask - min_dist):
                return json.dumps({
                    "status": "INVALID_PRICE_DISTANCE",
                    "error": f"BUY_LIMIT price ({target_price}) must be strictly BELOW current ask ({curr_ask:.2f}) by at least stops_level ({min_dist:.2f} pts). Target price must be <= {curr_ask - min_dist:.2f}"
                }, indent=2)
            elif ot_clean == "SELL_LIMIT" and target_price < (curr_bid + min_dist):
                return json.dumps({
                    "status": "INVALID_PRICE_DISTANCE",
                    "error": f"SELL_LIMIT price ({target_price}) must be strictly ABOVE current bid ({curr_bid:.2f}) by at least stops_level ({min_dist:.2f} pts). Target price must be >= {curr_bid + min_dist:.2f}"
                }, indent=2)
            
        step = sym_info.volume_step if sym_info.volume_step > 0 else 0.01
        vol = round(round(vol / step) * step, 2)
        vol = max(sym_info.volume_min, min(sym_info.volume_max, vol))
        clean_tag = re.sub(r'[^A-Za-z0-9_]', '_', str(tag or 'PlannedOrder'))[:20]
        
        req = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": sym,
            "volume": vol,
            "type": type_map[ot_clean],
            "price": target_price,
            "sl": float(final_sl),
            "tp": float(final_tp),
            "deviation": 50,
            "magic": 234000,
            "comment": clean_tag,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN
        }
        
        res = mt5.order_send(req)
        # Robust filling mode retries
        if not res or res.retcode == 10030:
            for f_mode in [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, 0]:
                req["type_filling"] = f_mode
                res = mt5.order_send(req)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    break
                    
        # If still failed due to comment / argument error (-2), retry with minimal comment
        if not res:
            last_err = mt5.last_error()
            if last_err and last_err[0] == -2:
                req["comment"] = "Alpha"
                res = mt5.order_send(req)
                    
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            log_local_llm_replied(f"Pending order placed on MT5! {ot_clean} {vol} lots on {sym} @ {target_price} | SL: {final_sl} | TP: {final_tp} (Order #{res.order}).")
            return json.dumps({
                "status": "PLACED",
                "order_ticket": res.order,
                "symbol": sym,
                "order_type": ot_clean,
                "price": target_price,
                "volume": vol,
                "sl": final_sl,
                "tp": final_tp,
                "tag": clean_tag,
                "retcode": res.retcode,
                "message": f"Pending order staged on MT5! Order ticket #{res.order} active."
            }, indent=2)
            
        err_msg = f"MT5 Retcode {res.retcode}: {res.comment}" if res else f"MT5 error: {mt5.last_error()}"
        return json.dumps({
            "status": "FAILED",
            "symbol": sym,
            "order_type": ot_clean,
            "price": target_price,
            "error": err_msg,
            "retcode": getattr(res, 'retcode', None),
            "last_error": mt5.last_error() if not res else None
        }, indent=2)
    except Exception as err:
        return json.dumps({"status": "FAILED", "error": str(err)}, indent=2)

@mcp.tool()
def place_pending_order(symbol: str = "XAUUSD", order_type: str = "SELL_LIMIT", price: float = 0.0, volume: float = 1.0, sl_price: float = 0.0, tp_price: float = 0.0, sl: float = 0.0, tp: float = 0.0, tag: str = "") -> str:
    """Place planned pending limit or stop order on MT5 at key structural points with custom volume, SL, and TP."""
    return mcp_alpha_place_pending_order(symbol, order_type, price, volume, sl_price, tp_price, sl, tp, tag)

# ======================================================================
# 4. ORDER & POSITION MANAGEMENT
# ======================================================================

def mcp_alpha_cancel_pending_order(order_ticket: int = 0, symbol: str = "ALL") -> str:
    """Cancel / remove active pending orders on MT5 (pass specific ticket or 0 for all)."""
    _init_mt5()
    try:
        import MetaTrader5 as mt5
        cancelled = []
        if order_ticket > 0:
            req = {"action": mt5.TRADE_ACTION_REMOVE, "order": int(order_ticket)}
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                return json.dumps({"status": "CANCELLED", "order_ticket": order_ticket}, indent=2)
            return json.dumps({"status": "FAILED", "order_ticket": order_ticket, "error": res.comment if res else "Unknown error"}, indent=2)
        else:
            orders = mt5.orders_get() or []
            sym_clean = symbol.upper().strip() if symbol else "ALL"
            for o in orders:
                if sym_clean != "ALL" and o.symbol.upper() != sym_clean:
                    continue
                req = {"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket}
                res = mt5.order_send(req)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    cancelled.append(o.ticket)
            return json.dumps({"status": "ALL_CANCELLED", "cancelled_tickets": cancelled, "count": len(cancelled)}, indent=2)
    except Exception as err:
        return json.dumps({"status": "FAILED", "error": str(err)}, indent=2)

@mcp.tool()
def cancel_pending_order(order_ticket: int = 0, symbol: str = "ALL") -> str:
    """Cancel / remove active pending orders on MT5."""
    return mcp_alpha_cancel_pending_order(order_ticket, symbol)

def mcp_alpha_modify_pending_order(order_ticket: int, price: float = 0.0, sl: float = 0.0, tp: float = 0.0) -> str:
    """Modify price, Stop Loss (sl), or Take Profit (tp) of an existing pending order on MT5."""
    _init_mt5()
    try:
        import MetaTrader5 as mt5
        orders = mt5.orders_get(ticket=int(order_ticket))
        if not orders:
            return json.dumps({"status": "FAILED", "error": f"Pending order #{order_ticket} not found"}, indent=2)
        o = orders[0]
        final_price = float(price) if price and float(price) > 0 else o.price_open
        final_sl = float(sl) if sl and float(sl) > 0 else o.sl
        final_tp = float(tp) if tp and float(tp) > 0 else o.tp



        req = {
            "action": mt5.TRADE_ACTION_MODIFY,
            "order": int(order_ticket),
            "price": final_price,
            "sl": final_sl,
            "tp": final_tp,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }
        res = mt5.order_send(req)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            return json.dumps({
                "status": "MODIFIED",
                "order_ticket": order_ticket,
                "price": final_price,
                "sl": final_sl,
                "tp": final_tp,
                "retcode": res.retcode,
                "message": f"Order #{order_ticket} successfully modified: price={final_price}, sl={final_sl}, tp={final_tp}"
            }, indent=2)
        return json.dumps({"status": "FAILED", "order_ticket": order_ticket, "error": res.comment if res else "Unknown error"}, indent=2)
    except Exception as err:
        return json.dumps({"status": "FAILED", "error": str(err)}, indent=2)

@mcp.tool()
def modify_pending_order(order_ticket: int, price: float = 0.0, sl: float = 0.0, tp: float = 0.0) -> str:
    """Modify price, Stop Loss (sl), or Take Profit (tp) of an existing pending order on MT5."""
    return mcp_alpha_modify_pending_order(order_ticket, price, sl, tp)

def mcp_alpha_get_pending_orders(symbol: str = "ALL") -> str:
    """Fetch all active pending orders on MT5."""
    _init_mt5()
    try:
        import MetaTrader5 as mt5
        orders = mt5.orders_get()
        orders_data = []
        sym_clean = symbol.upper().strip() if symbol else "ALL"
        
        type_names = {
            mt5.ORDER_TYPE_BUY_LIMIT: "BUY_LIMIT",
            mt5.ORDER_TYPE_SELL_LIMIT: "SELL_LIMIT",
            mt5.ORDER_TYPE_BUY_STOP: "BUY_STOP",
            mt5.ORDER_TYPE_SELL_STOP: "SELL_STOP"
        }
        
        for o in orders or []:
            if sym_clean != "ALL" and o.symbol.upper() != sym_clean:
                continue
            orders_data.append({
                "ticket": o.ticket,
                "symbol": o.symbol,
                "type": type_names.get(o.type, f"TYPE_{o.type}"),
                "volume": o.volume_current,
                "price_open": o.price_open,
                "sl": o.sl,
                "tp": o.tp,
                "comment": o.comment,
                "magic": o.magic
            })
        return json.dumps({
            "status": "SUCCESS",
            "total_pending_orders": len(orders_data),
            "pending_orders": orders_data
        }, indent=2)
    except Exception as err:
        return json.dumps({"status": "FAILED", "error": str(err)}, indent=2)

@mcp.tool()
def get_pending_orders(symbol: str = "ALL") -> str:
    """Fetch all active pending orders on MT5."""
    return mcp_alpha_get_pending_orders(symbol)

_pending_delayed_tickets = set()

def mcp_alpha_update_position(ticket: int, action: str, params_json: str = "{}") -> str:
    """Update active MT5 trade tickets (BREAK_EVEN, TRAIL_SL, FULL_EXIT)."""
    _init_mt5()
    try:
        import MetaTrader5 as mt5
        import threading
        import time
        pos = mt5.positions_get(ticket=ticket)
        if not pos:
            all_p = mt5.positions_get()
            pos = [p for p in all_p or [] if p.ticket == int(ticket)] or None
        if not pos:
            return json.dumps({"status": "FAILED", "error": f"Ticket #{ticket} not found on MT5"})
            
        p = pos[0]
        act = action.upper()
        symbol = p.symbol
        params = json.loads(params_json) if isinstance(params_json, str) and params_json.strip().startswith("{") else {}

        # Fresh tick quotes & accurate duration in broker server time (FundedNext standard)
        tick_info = mt5.symbol_info_tick(symbol)
        curr_price = (tick_info.bid if p.type == 0 else tick_info.ask) if tick_info else 0.0

        tick_t_msc = getattr(tick_info, "time_msc", 0)
        pos_t_msc = getattr(p, "time_msc", 0)
        if tick_t_msc > 0 and pos_t_msc > 0:
            pos_duration = max(0.0, float(tick_t_msc - pos_t_msc) / 1000.0)
        else:
            pos_duration = max(0.0, float(getattr(tick_info, "time", 0) - getattr(p, "time", 0)))
        
        if act in ("BREAK_EVEN", "BREAKEVEN", "BE"):
            # Universal Pullback Check:
            # If price has pulled back to or below entry, cleanly cut at market without erroring!
            is_pulled_back = (curr_price <= p.price_open) if p.type == 0 else (curr_price >= p.price_open)
            if is_pulled_back:
                for fill_mode in [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, 0, mt5.ORDER_FILLING_RETURN]:
                    close_req = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "position": p.ticket,
                        "symbol": symbol,
                        "volume": p.volume,
                        "type": mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY,
                        "price": curr_price,
                        "deviation": 50,
                        "magic": p.magic,
                        "comment": "BE Pullback Cut",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": fill_mode
                    }
                    res = mt5.order_send(close_req)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        return json.dumps({
                            "status": "CUT_AT_MARKET",
                            "ticket": ticket,
                            "action": "BREAK_EVEN_PULLBACK_CUT",
                            "close_price": curr_price,
                            "profit": p.profit,
                            "message": f"Position #{ticket} pulled back to {curr_price:.2f} (Entry {p.price_open:.2f}). Cleanly cut at current market price instead of erroring."
                        })
                return json.dumps({"status": "FAILED", "ticket": ticket, "error": f"Failed to execute pullback cut: {res.comment if res else 'Unknown MT5 error'}"})

            # FundedNext 30s rule: If duration < 32s, delay moving SL into profit
            if pos_duration < 32.0:
                remaining_sec = round(32.0 - pos_duration, 1)

                def _delayed_be(pos_t, sym, vol, p_type, mag, req_sl, delay_s):
                    time.sleep(delay_s)
                    try:
                        _init_mt5()
                        cur_p = mt5.positions_get(ticket=pos_t)
                        if not cur_p:
                            return
                        tk = mt5.symbol_info_tick(sym)
                        cp = (tk.bid if p_type == 0 else tk.ask) if tk else 0.0
                        is_pb = (cp <= req_sl) if p_type == 0 else (cp >= req_sl)
                        if is_pb:
                            for fm in [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, 0, mt5.ORDER_FILLING_RETURN]:
                                c_req = {
                                    "action": mt5.TRADE_ACTION_DEAL,
                                    "position": pos_t,
                                    "symbol": sym,
                                    "volume": vol,
                                    "type": mt5.ORDER_TYPE_SELL if p_type == 0 else mt5.ORDER_TYPE_BUY,
                                    "price": cp,
                                    "deviation": 50,
                                    "magic": mag,
                                    "comment": "BE Pullback Cut",
                                    "type_time": mt5.ORDER_TIME_GTC,
                                    "type_filling": fm
                                }
                                rc = mt5.order_send(c_req)
                                if rc and rc.retcode == mt5.TRADE_RETCODE_DONE:
                                    LOG.info(f"🛡️ [FUNDEDNEXT 30S COMPLIANCE] Position #{pos_t} pulled back; cleanly cut at market at {cp:.2f}.")
                                    break
                        else:
                            sl_req = {"action": mt5.TRADE_ACTION_SLTP, "position": pos_t, "symbol": sym, "sl": req_sl, "tp": cur_p[0].tp}
                            mt5.order_send(sl_req)
                    except Exception as _err:
                        LOG.error(f"Delayed BE execution error: {_err}")

                threading.Thread(
                    target=_delayed_be,
                    args=(p.ticket, symbol, p.volume, p.type, p.magic, p.price_open, remaining_sec),
                    daemon=True
                ).start()

                return json.dumps({
                    "status": "ACCEPTED_DELAYED_BREAK_EVEN",
                    "ticket": ticket,
                    "remaining_seconds": remaining_sec,
                    "message": f"Break-even request ACCEPTED. Stop loss will be moved to break-even (or position cut at market if pulled back) in {remaining_sec} seconds to comply with FundedNext 30-second Quick Strike rule."
                })

            new_sl = p.price_open
            if abs(new_sl - p.sl) < 0.001:
                return json.dumps({"status": "NO_CHANGE", "ticket": ticket, "sl": p.sl, "reason": "SL is already at Break-Even"})
            req = {"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "symbol": symbol, "sl": new_sl, "tp": p.tp}
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                return json.dumps({"status": "UPDATED", "ticket": ticket, "action": "BREAK_EVEN", "sl": new_sl, "retcode": res.retcode})
            return json.dumps({"status": "FAILED", "ticket": ticket, "error": res.comment if res else "Unknown MT5 error"})

        if act in ("FULL_EXIT", "EXIT", "CLOSE"):
            adverse_pts = (p.price_open - curr_price) if p.type == 0 else (curr_price - p.price_open)
            is_underwater = adverse_pts > 0.05
            is_force = bool(params.get("force") or params.get("override") or params.get("manual"))

            # --- FUNDEDNEXT 30-SECOND QUICK STRIKE COMPLIANCE ---
            # If trade is in profit and duration is under 32 seconds:
            # User mandate: Accept request, tell session when it will close, and close automatically when time is over.
            if not is_underwater and pos_duration < 32.0 and not is_force:
                remaining_sec = round(32.0 - pos_duration, 1)

                if p.ticket in _pending_delayed_tickets:
                    return json.dumps({
                        "status": "ALREADY_SCHEDULED",
                        "ticket": ticket,
                        "remaining_seconds": remaining_sec,
                        "message": f"Exit already scheduled for position #{ticket}. Will execute in {remaining_sec}s."
                    })

                _pending_delayed_tickets.add(p.ticket)

                def _delayed_fn_close(pos_t, sym, vol, p_type, mag, delay_s):
                    time.sleep(delay_s)
                    try:
                        _init_mt5()
                        tk = mt5.symbol_info_tick(sym)
                        cp = (tk.bid if p_type == 0 else tk.ask) if tk else 0.0
                        for fm in [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, 0, mt5.ORDER_FILLING_RETURN]:
                            req_c = {
                                "action": mt5.TRADE_ACTION_DEAL,
                                "position": pos_t,
                                "symbol": sym,
                                "volume": vol,
                                "type": mt5.ORDER_TYPE_SELL if p_type == 0 else mt5.ORDER_TYPE_BUY,
                                "price": cp,
                                "deviation": 50,
                                "magic": mag,
                                "comment": "FN 30s Delayed Close",
                                "type_time": mt5.ORDER_TIME_GTC,
                                "type_filling": fm
                            }
                            rc = mt5.order_send(req_c)
                            if rc and rc.retcode == mt5.TRADE_RETCODE_DONE:
                                LOG.info(f"🛡️ [FUNDEDNEXT 30S COMPLIANCE] Position #{pos_t} closed at market after {delay_s}s delay at price {cp:.2f}.")
                                break
                    except Exception as _err:
                        LOG.error(f"Delayed close execution failed: {_err}")
                    finally:
                        _pending_delayed_tickets.discard(pos_t)

                threading.Thread(
                    target=_delayed_fn_close,
                    args=(p.ticket, symbol, p.volume, p.type, p.magic, remaining_sec),
                    daemon=True
                ).start()

                return json.dumps({
                    "status": "ACCEPTED_DELAYED_CLOSE",
                    "ticket": ticket,
                    "remaining_seconds": remaining_sec,
                    "message": f"Exit order ACCEPTED. Position #{ticket} will be automatically closed at market in {remaining_sec} seconds (at 32.0s hold) to comply with FundedNext 30-second Quick Strike rule (<30% profit from trades under 30s)."
                })

            # --- CONST_NO_PREMATURE_CUT SERVER-SIDE HARD ENFORCEMENT ---
            if is_underwater and p.sl > 0 and not is_force:
                # Check Authorized Emergency Exit Gate 1 (Tier-1 news < 30m)
                is_tier1_blackout = False
                try:
                    from tradingagents.economic_calendar import EconomicCalendarEngine
                    summary = EconomicCalendarEngine().get_news_countdown_summary()
                    st = str(summary.get("shield_status", "")).upper()
                    if "BLACKOUT" in st or "LOCKOUT" in st:
                        is_tier1_blackout = True
                except Exception:
                    pass
                if params.get("emergency_gate") == "TIER1_BLACKOUT" or params.get("reason") == "TIER1_BLACKOUT":
                    is_tier1_blackout = True

                # Check Authorized Emergency Exit Gate 2 (M15 candle closed beyond structural SL)
                m15_closed_beyond_sl = False
                if p.sl > 0:
                    try:
                        m15_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 1, 1)
                        if m15_rates is not None and len(m15_rates) > 0:
                            last_m15_close = float(m15_rates[0]['close'])
                            if p.type == 0 and last_m15_close <= p.sl:
                                m15_closed_beyond_sl = True
                            elif p.type == 1 and last_m15_close >= p.sl:
                                m15_closed_beyond_sl = True
                    except Exception:
                        pass

                if not is_tier1_blackout and not m15_closed_beyond_sl:
                    sl_dist = abs(p.price_open - p.sl) if p.sl > 0 else 8.0
                    return json.dumps({
                        "status": "VETOED",
                        "ticket": ticket,
                        "error": (
                            f"CONST_NO_PREMATURE_CUT VETO: Position #{ticket} is underwater by {adverse_pts:.2f} pts (Price {curr_price:.2f} vs Entry {p.price_open:.2f}). "
                            f"Discretionary manual cuts before structural invalidation are strictly prohibited. "
                            f"The broker bracket (SL {p.sl:.2f}, {sl_dist:.1f} pts) governs trade breathing. "
                            f"Manual exit is permitted ONLY on a confirmed M15 candle close beyond SL or Tier-1 macro blackout (<30m to CPI/FOMC/NFP). "
                            f"Pass params_json='{{\"force\": true}}' if emergency operator override is required."
                        )
                    })

            for fill_mode in [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, 0, mt5.ORDER_FILLING_RETURN]:
                close_req = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "position": p.ticket,
                    "symbol": symbol,
                    "volume": p.volume,
                    "type": mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY,
                    "price": curr_price,
                    "deviation": 50,
                    "magic": p.magic,
                    "comment": "OpenCode CIO Exit",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": fill_mode
                }
                res = mt5.order_send(close_req)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    return json.dumps({"status": "CLOSED", "ticket": ticket, "close_price": curr_price, "profit": p.profit})
            return json.dumps({"status": "FAILED", "ticket": ticket, "error": res.comment if res else "Unknown MT5 error"})
            
        if act in ("TRAIL_SL", "SL_UPDATE", "MODIFY", "TRAIL"):
            new_sl = float(params.get("sl") or params.get("new_sl") or p.sl)
            new_tp = float(params.get("tp") or params.get("new_tp") or p.tp)

            # Determine if this is a protective trailing stop (locking profit or tightening risk)
            is_protective_trail = False
            if p.type == 0:  # BUY
                if new_sl > p.sl or new_sl >= p.price_open:
                    is_protective_trail = True
            else:  # SELL
                if (new_sl < p.sl and p.sl > 0) or (p.sl == 0 and new_sl <= p.price_open) or (new_sl <= p.price_open):
                    is_protective_trail = True

            # Universal Pullback check:
            is_pulled_back = False
            if curr_price > 0 and new_sl > 0 and is_protective_trail:
                if p.type == 0 and curr_price <= new_sl:
                    is_pulled_back = True
                elif p.type == 1 and curr_price >= new_sl:
                    is_pulled_back = True

            if is_pulled_back:
                for fill_mode in [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, 0, mt5.ORDER_FILLING_RETURN]:
                    close_req = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "position": p.ticket,
                        "symbol": symbol,
                        "volume": p.volume,
                        "type": mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY,
                        "price": curr_price,
                        "deviation": 50,
                        "magic": p.magic,
                        "comment": "Trail Pullback Cut",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": fill_mode
                    }
                    res = mt5.order_send(close_req)
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        return json.dumps({
                            "status": "CUT_AT_MARKET",
                            "ticket": ticket,
                            "action": "TRAIL_PULLBACK_CUT",
                            "close_price": curr_price,
                            "profit": p.profit,
                            "message": f"Position #{ticket} pulled back to {curr_price:.2f} (Target protective SL was {new_sl:.2f}). Instead of erroring on trailing stop, position was cleanly cut at current market price."
                        })
                return json.dumps({"status": "FAILED", "ticket": ticket, "error": f"Failed to execute trail pullback cut: {res.comment if res else 'Unknown MT5 error'}"})

            # FundedNext 30s rule: if trailing into profit and duration < 32s, delay setting SL
            is_in_profit_sl = (new_sl > p.price_open) if p.type == 0 else (new_sl < p.price_open)
            if is_in_profit_sl and pos_duration < 32.0:
                remaining_sec = round(32.0 - pos_duration, 1)

                def _delayed_trail(pos_t, sym, vol, p_type, mag, sl_val, tp_val, delay_s):
                    time.sleep(delay_s)
                    try:
                        _init_mt5()
                        cur_p = mt5.positions_get(ticket=pos_t)
                        if not cur_p:
                            return
                        tk = mt5.symbol_info_tick(sym)
                        cp = (tk.bid if p_type == 0 else tk.ask) if tk else 0.0
                        is_pb = (cp <= sl_val) if p_type == 0 else (cp >= sl_val)
                        if is_pb:
                            for fm in [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, 0, mt5.ORDER_FILLING_RETURN]:
                                c_req = {
                                    "action": mt5.TRADE_ACTION_DEAL,
                                    "position": pos_t,
                                    "symbol": sym,
                                    "volume": vol,
                                    "type": mt5.ORDER_TYPE_SELL if p_type == 0 else mt5.ORDER_TYPE_BUY,
                                    "price": cp,
                                    "deviation": 50,
                                    "magic": mag,
                                    "comment": "Trail Pullback Cut",
                                    "type_time": mt5.ORDER_TIME_GTC,
                                    "type_filling": fm
                                }
                                rc = mt5.order_send(c_req)
                                if rc and rc.retcode == mt5.TRADE_RETCODE_DONE:
                                    LOG.info(f"🛡️ [TRAIL PULLBACK CUT] Position #{pos_t} cut at market at {cp:.2f}")
                                    break
                        else:
                            sl_req = {"action": mt5.TRADE_ACTION_SLTP, "position": pos_t, "symbol": sym, "sl": sl_val, "tp": tp_val}
                            mt5.order_send(sl_req)
                    except Exception as _e:
                        LOG.error(f"Delayed trail error: {_e}")

                threading.Thread(
                    target=_delayed_trail,
                    args=(p.ticket, symbol, p.volume, p.type, p.magic, new_sl, new_tp, remaining_sec),
                    daemon=True
                ).start()

                return json.dumps({
                    "status": "ACCEPTED_DELAYED_TRAIL_SL",
                    "ticket": ticket,
                    "remaining_seconds": remaining_sec,
                    "target_sl": new_sl,
                    "message": f"Trail SL request ACCEPTED. Stop loss will be updated to {new_sl:.2f} (or position cut at market if pulled back) in {remaining_sec} seconds to comply with FundedNext 30-second Quick Strike rule."
                })

            req = {"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "symbol": symbol, "sl": new_sl, "tp": new_tp}
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                return json.dumps({"status": "UPDATED", "ticket": ticket, "sl": new_sl, "tp": new_tp})
            return json.dumps({"status": "FAILED", "ticket": ticket, "error": res.comment if res else "Unknown MT5 error"})
            
        return json.dumps({"status": "UNKNOWN_ACTION", "action": action})
    except Exception as err:
        return json.dumps({"status": "FAILED", "error": str(err)})

@mcp.tool()
def update_position(ticket: int, action: str, params_json: str = "{}") -> str:
    """Update active MT5 trade tickets (BREAK_EVEN, TRAIL_SL, FULL_EXIT)."""
    return mcp_alpha_update_position(ticket, action, params_json)

def mcp_alpha_get_account_status() -> str:
    """OpenCode fetches live FTMO MT5 account status and active positions."""
    _init_mt5()
    try:
        import MetaTrader5 as mt5
        acc = mt5.account_info(); pos = mt5.positions_get(); positions_data = []
        for p in pos or []:
            positions_data.append({"ticket": p.ticket, "symbol": p.symbol, "type": "BUY" if p.type == 0 else "SELL", "volume": p.volume, "price_open": p.price_open, "price_current": p.price_current, "sl": p.sl, "tp": p.tp, "profit": p.profit})
        return json.dumps({"login": getattr(acc, "login", 0), "balance": getattr(acc, "balance", 0.0), "equity": getattr(acc, "equity", 0.0), "margin_free": getattr(acc, "margin_free", 0.0), "positions_count": len(positions_data), "positions": positions_data})
    except Exception as err: return json.dumps({"error": str(err)})

def _sync_query_analyst_desk(query: str = "Full 7-layer technical, fundamental COT, and macro market analysis", symbol: str = "XAUUSD") -> str:
    """OpenCode CIO queries the 7-Layer Local LLM Analyst Desk; outputs are multi-source evidence, not decisions."""
    _init_mt5()
    try:
        import MetaTrader5 as mt5
        from datetime import datetime, timezone
        sym = _normalize_symbol(symbol)
        sym_info = mt5.symbol_info(sym) or mt5.symbol_info(sym.upper())
        tick = mt5.symbol_info_tick(sym) or mt5.symbol_info_tick(sym.upper()) or mt5.symbol_info_tick(sym.lower())
        
        live_bid = float(getattr(tick, "bid", 0.0))
        live_ask = float(getattr(tick, "ask", 0.0))
        tick_time_raw = getattr(tick, "time", 0)
        
        # Real MT5 tick recency & provenance check (no deceptive frozen labels)
        now_utc = datetime.now(timezone.utc)
        tick_time_dt = datetime.fromtimestamp(tick_time_raw, tz=timezone.utc) if tick_time_raw else None
        # Broker clock offset adjustment (FTMO is UTC+2 or UTC+3)
        raw_diff = abs(now_utc.timestamp() - tick_time_raw) if tick_time_raw else 999999.0
        # If difference is ~10800s (UTC+3) or ~7200s (UTC+2), account for timezone
        for offset_hrs in (0, 1, 2, 3, -1, -2, -3, 4, 5):
            adjusted_diff = abs((now_utc.timestamp() + (offset_hrs * 3600)) - tick_time_raw)
            if adjusted_diff < raw_diff:
                raw_diff = adjusted_diff
        tick_age_seconds = round(raw_diff, 1)
        is_live_tick = bool(tick and tick_time_raw > 0 and tick_age_seconds < 180.0)
        
        from tradingagents.world_market import IntradayInstitutionalEngine
        session_info = IntradayInstitutionalEngine().get_session_status()
        is_weekend = (not session_info.get("market_open", True)) and (not is_live_tick)
        
        data_asof_tag = tick_time_dt.strftime("%Y-%m-%d %H:%M:%S BrokerTime") if tick_time_dt else "MT5 Connected"
        status_tag = "LIVE_MARKET" if is_live_tick else ("MARKET_WEEKEND_CLOSED" if is_weekend else "MARKET_QUIET_SESSION")
        
        point_size = float(getattr(sym_info, "point", 0.01)) if sym_info else 0.01
        spread_pts = round((live_ask - live_bid) / point_size) if live_ask > 0 and live_bid > 0 else 0
        spread_usd = round(live_ask - live_bid, 3)

        # Multi-Timeframe true EMAs and RSI
        mtf_res = _mtf_analyst.analyze_mtf(sym)
        rsi_val = mtf_res.get("m15_rsi", 50.0)
        
        # COT Fundamental Data (honest provenance, no hallucinated 100% certainty)
        cot_full = _inst_engine.get_futuresbench_cot_data()
        raw_cot = cot_full.get("markets", {}).get(sym, {})
        cot_pct_52w = raw_cot.get("cot_index_52w") if raw_cot.get("cot_index_52w") is not None else raw_cot.get("cot_index_26w", 50.0)
        cot_pct_26w = raw_cot.get("cot_index_26w", cot_pct_52w)
        net_noncomm = raw_cot.get("net_noncommercial", 0)
        net_comm = raw_cot.get("net_commercial", raw_cot.get("commercial_net", -net_noncomm))
        is_cot_live = bool(cot_full.get("is_live", False))
        
        cot_data = {
            "managed_money_percentile_52w": cot_pct_52w,
            "managed_money_percentile_26w": cot_pct_26w,
            "net_noncommercial": net_noncomm,
            "net_commercial": net_comm,
            "bias": raw_cot.get("bias", "NEUTRAL"),
            "weekly_change": raw_cot.get("change", 0),
            "report_date": raw_cot.get("report_date", cot_full.get("report_date", "2026-09-15")),
            "is_live_api": is_cot_live,
            "data_provenance": "FUTURESBENCH_LIVE_API" if is_cot_live else "CFTC_HISTORICAL_CACHE"
        }

        # Technical structure and analysts
        tech_res = _tech_analyst.analyze(sym, {
            "h4_bias": mtf_res.get("h4_trend"),
            "h1_bias": mtf_res.get("h1_trend"),
            "m15_bias": mtf_res.get("m15_trend"),
            "m5_bias": mtf_res.get("m5_trend"),
            "alignment": mtf_res.get("alignment"),
            "indicators": {
                "rsi_14": rsi_val,
                "m15_ema20": mtf_res.get("m15_ema20"),
                "m15_ema50": mtf_res.get("m15_ema50")
            }
        })
        fund_res = _fund_analyst.analyze(sym, cot_data)

        # Macro rates and yield context
        macro_feed = _inst_engine.get_macro_and_gamma_feeds()
        dxy_val = float(macro_feed.get("dxy", 100.5)) if isinstance(macro_feed.get("dxy"), (int, float)) else float(macro_feed.get("dxy", {}).get("val", 100.5))
        us10y_val = float(macro_feed.get("us_10y", 4.90)) if isinstance(macro_feed.get("us_10y"), (int, float)) else 4.90
        vix_val = float(macro_feed.get("vix", 15.5)) if isinstance(macro_feed.get("vix"), (int, float)) else 15.5
        
        from tradingagents.agent_graph import MacroNewsAnalyst
        macro = MacroNewsAnalyst()
        macro_res = macro.analyze({"dxy": dxy_val, "us10y": us10y_val, "vix": vix_val}, [])
        sent_res = _sent_analyst.analyze({"vader_compound": 0.0}, [])

        # Run full Bull vs Bear Debate
        debate_res = _desk.debater.debate(sym, tech_res, fund_res, macro_res, sent_res)

        # Microstructure, FVG overlays, and Order Blocks
        from tradingagents.fair_value_gap import FairValueGapEngine
        from tradingagents.cvd_engine import CumulativeVolumeDeltaEngine
        from tradingagents.multitimeframe import OrderBlockEngine
        fvg_mat = FairValueGapEngine().get_symbol_fvg_matrix(sym)
        cvd_data = CumulativeVolumeDeltaEngine().get_symbol_cvd(sym)
        ob_data = OrderBlockEngine().calculate_levels(sym)

        nearest_fvg = fvg_mat.get("nearest_unmitigated_fvg") or fvg_mat.get("m5_fvg") or {}
        fvg_top = float(nearest_fvg.get("top", 0.0))
        fvg_bottom = float(nearest_fvg.get("bottom", 0.0))
        fvg_ce = float(nearest_fvg.get("consequent_encroachment", 0.0))
        fvg_fill = float(nearest_fvg.get("fill_pct", 0.0))
        fvg_type = str(nearest_fvg.get("type", "FVG"))
        dist_to_ce = round(abs(live_ask - fvg_ce), 2) if fvg_ce > 0 else 0.0
        
        fvg_str = f"{fvg_type} [{fvg_top:.2f}-{fvg_bottom:.2f}, 50% CE: {fvg_ce:.2f}, {fvg_fill:.1f}% filled, {dist_to_ce} pts from live ask]"

        # Build Intelligent Synthesis aligned strictly with Champion Execution Blueprint
        q_upper = query.upper()
        if "CONVICTION" in q_upper or "AUDIT" in q_upper:
            tactical_verdict = (
                f"Conviction Audit: 4TF is {mtf_res.get('formatted_4tf')}. "
                f"Regime Divergence: {'YES - Caution' if debate_res.get('is_regime_conflict') else 'NO - Aligned'}. "
                f"Tick Velocity: {cvd_data.get('tick_velocity_tpm', 0.0):.1f} t/m, Spread: {spread_pts} pts (${spread_usd}). "
                f"Order Architecture: High-growth 0.50-1.00L sizing (1.00L on conviction >= 8.0/10), structural SL 6.0-12.0 pts behind HTF shelf + 1.5x ATR14 buffer. Mandatory positive R:R >= 1.5:1 to 2.5:1+ targeting opposing structural liquidity (12.0-25.0 pts). Inverted negative R:R (<1.5:1) strictly vetoed."
            )
        elif "SWEEP" in q_upper or "TRAP" in q_upper or "LOW" in q_upper or "HIGH" in q_upper:
            tactical_verdict = (
                f"Liquidity Sweep & Trap Audit: Nearest structure at {live_ask:.2f}. "
                f"Precedent requires M5 delta absorption and candle close back beyond {fvg_str} before validating a reversal. "
                f"Do not front-run untested extreme wicks without confirmed delta turn."
            )
        elif "BUY" in q_upper or "LONG" in q_upper:
            tactical_verdict = (
                f"Long Thesis Evaluation: Confluence at {fvg_str}. "
                f"Optimal long entry requires resting limit at structural discount CE ({fvg_ce:.2f}) or momentum BUY_STOP on confirmed expansion. "
                f"SL floor >= 6.0-12.0 pts anchored below demand shelf ({ob_data.get('demand_zone', 'N/A')}) + 1.5x ATR14 buffer. Target opposing structural magnet with positive R:R >= 1.5:1 to 2.5:1+ (+12.0 to +25.0 pts). Sizing 0.50-1.00L."
            )
        elif "SELL" in q_upper or "SHORT" in q_upper:
            tactical_verdict = (
                f"Short Thesis Evaluation: Confluence against {ob_data.get('supply_zone', 'N/A')}. "
                f"Optimal short entry requires resting limit at structural premium CE ({fvg_ce:.2f}) or momentum SELL_STOP below immediate consolidation shelf. "
                f"SL floor >= 6.0-12.0 pts anchored above supply shelf + 1.5x ATR14 buffer. Target opposing structural magnet with positive R:R >= 1.5:1 to 2.5:1+ (+12.0 to +25.0 pts). Sizing 0.50-1.00L."
            )
        else:
            tactical_verdict = (
                f"Multi-Agent Consensus: 4TF is {mtf_res.get('formatted_4tf')}, COT bias is {cot_data.get('bias', 'NEUTRAL')}. "
                f"Key structure: {fvg_str}. Velocity: {cvd_data.get('tick_velocity_tpm', 0.0):.1f} t/m. "
                f"Execution Blueprint: 0.50-1.00L sizing, structural SL >= 6.0-12.0 pts (+ 1.5x ATR14), asymmetric TP with R:R >= 1.5:1 to 2.5:1+ (+12.0 to +25.0 pts). Mechanical bracket discipline; progressive structural trailing (BE -> +1R -> +2R) with 3-5 pt buffer once > +1R."
            )

        return json.dumps({
            "status": status_tag,
            "query": query,
            "symbol": sym,
            "is_frozen": is_weekend,
            "data_asof": data_asof_tag,
            "tick_age_seconds": round(tick_age_seconds, 1),
            "unmasked_prices": {
                "bid": live_bid,
                "ask": live_ask,
                "spread_pts": spread_pts,
                "spread_usd": spread_usd
            },
            "4tf_alignment": mtf_res.get("formatted_4tf"),
            "4tf_numeric_metrics": {
                "h4": {"trend": mtf_res.get("h4_trend"), "close": mtf_res.get("h4_close"), "ema20": mtf_res.get("h4_ema20"), "ema50": mtf_res.get("h4_ema50"), "rsi": mtf_res.get("h4_rsi")},
                "h1": {"trend": mtf_res.get("h1_trend"), "close": mtf_res.get("h1_close"), "ema20": mtf_res.get("h1_ema20"), "ema50": mtf_res.get("h1_ema50"), "rsi": mtf_res.get("h1_rsi")},
                "m15": {"trend": mtf_res.get("m15_trend"), "close": mtf_res.get("m15_close"), "ema20": mtf_res.get("m15_ema20"), "ema50": mtf_res.get("m15_ema50"), "rsi": mtf_res.get("m15_rsi")},
                "m5": {"trend": mtf_res.get("m5_trend"), "close": mtf_res.get("m5_close"), "ema20": mtf_res.get("m5_ema20"), "ema50": mtf_res.get("m5_ema50"), "rsi": mtf_res.get("m5_rsi")}
            },
            "structural_consensus": {
                "is_regime_conflict": debate_res.get("is_regime_conflict", False),
                "structural_risk_warning": debate_res.get("structural_risk_warning", False)
            },
            "debate_breakdown": {
                "bull_arguments": debate_res.get("bull_points", []),
                "bear_arguments": debate_res.get("bear_points", [])
            },
            "microstructure_overlay": {
                "live_spread_pts": spread_pts,
                "tick_velocity_tpm": cvd_data.get("tick_velocity_tpm", 0.0),
                "nearest_fvg": fvg_str,
                "fvg_exact_coordinates": {
                    "top": fvg_top,
                    "bottom": fvg_bottom,
                    "consequent_encroachment": fvg_ce,
                    "fill_pct": fvg_fill,
                    "distance_to_ce_pts": dist_to_ce
                },
                "demand_zone": ob_data.get("demand_zone"),
                "supply_zone": ob_data.get("supply_zone")
            },
            "multisource_intelligence": {
                "technical_analyst": tech_res,
                "fundamental_cot_analyst": cot_data,
                "macro_news_analyst": macro_res
            },
            "tactical_analyst_synthesis": tactical_verdict
        }, indent=2)
    except Exception as err:
        return json.dumps({"status": "ERROR", "query": query, "error": str(err)})

async def mcp_alpha_query_analyst_desk(query: str = "Full 7-layer technical, fundamental COT, and macro market analysis", symbol: str = "XAUUSD") -> str:
    """OpenCode CIO queries the 7-Layer Local LLM Analyst Desk in a non-blocking background thread."""
    return await run_in_thread(_sync_query_analyst_desk, query=query, symbol=symbol)

@mcp.tool()
async def query_analyst_desk(query: str = "Full 7-layer technical, fundamental COT, and macro market analysis", symbol: str = "XAUUSD") -> str:
    """7-Layer Local LLM Analyst Desk alias."""
    return await run_in_thread(_sync_query_analyst_desk, query=query, symbol=symbol)
def mcp_alpha_get_trade_forensics(ticket: int = 0) -> str:
    """Query granular post-trade forensics and entry market context for closed MT5 deals."""
    try:
        from tradingagents.trade_forensics import TradeForensicsEngine
        read_logger.log_dossier_read("OpenCode CIO (MCP Trade Forensics)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Queried trade forensics for ticket #{ticket}")
        forensics = TradeForensicsEngine()
        return json.dumps(forensics.get_trade_forensics(ticket), indent=2)
    except Exception as err:
        return json.dumps({"status": "ERROR", "ticket": ticket, "error": str(err)}, indent=2)

@mcp.tool()
def get_trade_forensics(ticket: int = 0) -> str:
    """Query granular post-trade forensics and entry market context for closed MT5 deals (short alias)."""
    return mcp_alpha_get_trade_forensics(ticket=ticket)

import threading
_backtest_cache = {}
_backtest_lock = threading.Lock()

def _sync_backtest_thesis(query: str, symbol: str = "XAUUSD", timeframe: str = "M5", bars: int = 0, offset: int = 0) -> str:
    from backtesting.pipeline import PureLLMBacktestPipeline
    sym = _normalize_symbol(symbol)
    cache_key = f"{sym}_{timeframe}_{bars}_{offset}_{query}"
    with _backtest_lock:
        if cache_key in _backtest_cache:
            return _backtest_cache[cache_key]

    read_logger.log_dossier_read("OpenCode CIO (MCP Backtest Thesis)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Requested natural backtest: '{query}' on {sym} ({timeframe}, {bars} bars)")
    pipeline = PureLLMBacktestPipeline()
    res = json.dumps(pipeline.run_backtest(query=query, symbol=sym, timeframe=timeframe, bars=bars, offset=offset), indent=2)
    
    with _backtest_lock:
        _backtest_cache[cache_key] = res
    return res

async def mcp_alpha_backtest_thesis(
    query: str,
    symbol: str = "XAUUSD",
    timeframe: str = "M5",
    bars: int = 0,
    offset: int = 0
) -> str:
    """Ultra-fast multi-threaded natural backtester powered by Proxima + MT5 Data Harness + Local LLM.
    
    Executes in a dedicated background worker thread to support simultaneous concurrent backtest executions without blocking.
    """
    return await run_in_thread(_sync_backtest_thesis, query=query, symbol=symbol, timeframe=timeframe, bars=bars, offset=offset)

@mcp.tool()
async def backtest_thesis(
    query: str,
    symbol: str = "XAUUSD",
    timeframe: str = "M5",
    bars: int = 0,
    offset: int = 0
) -> str:
    """STRICTLY POD 5 PRE-FLIGHT ONLY: Call only when actively staging an order in Pod 5 to verify historical sample win rate and R:R over recent bars. Prohibited on routine scans."""
    return await run_in_thread(_sync_backtest_thesis, query=query, symbol=symbol, timeframe=timeframe, bars=bars, offset=offset)


def mcp_alpha_get_fred_observations(series_id: str, limit: int = 100, vintage_date: str = "") -> str:
    """Retrieve factual FRED/ALFRED observations; unavailable credentials never produce fallback values."""
    return json.dumps(_fred_adapter.observations(series_id, limit, vintage_date or None), indent=2)

@mcp.tool()
def get_fred_observations(series_id: str, limit: int = 100, vintage_date: str = "") -> str:
    """Retrieve factual vintage-aware Federal Reserve economic observations (e.g. series 'DGS10', 'T10YIE', 'DFII10') for macroeconomic interest rate analysis."""
    return mcp_alpha_get_fred_observations(series_id, limit, vintage_date)

def mcp_alpha_get_live_world_events(category: str = "ALL", limit: int = 15, force_refresh: bool = False) -> str:
    """Retrieve verified, real-time live financial news headlines, Treasury wires, central bank releases, and geopolitical events.
    
    Aggregated live across 10 institutional wire feeds (US Treasury & Buyback Wires, Federal Reserve Press Releases, Yahoo Commodities & Metals, FXStreet Live Wire, CNBC World, CNBC Economy, CNBC Energy & Commodities, MarketWatch).
    
    Args:
        category: Filter by category ('ALL', 'MACRO', 'MICRO', 'GEOPOLITICAL', 'CENTRAL_BANKS_FED', 'COMMODITIES_ENERGY').
        limit: Number of headlines to return (default: 15, max: 30).
        force_refresh: Set True to force immediate network refresh instead of cache.
    """
    read_logger.log_dossier_read("OpenCode CIO (MCP World Events)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Queried live world events (cat: {category}, limit: {limit})")
    try:
        evs = world_events_engine.fetch_live_events(force_refresh=force_refresh)
        cat_filter = str(category or "ALL").upper().strip()
        filtered = []
        for ev in evs:
            ev_cat = str(ev.get("category", "")).upper()
            if cat_filter != "ALL" and cat_filter not in ev_cat:
                continue
            filtered.append({
                "title": ev.get("title"),
                "category": ev.get("category"),
                "source": ev.get("source"),
                "pub_date": ev.get("pub_date"),
                "summary": (ev.get("summary") or ev.get("description") or "")[:200]
            })
            if len(filtered) >= int(limit):
                break
        return json.dumps({
            "status": "SUCCESS",
            "count": len(filtered),
            "category_filter": cat_filter,
            "events": filtered
        }, indent=2)
    except Exception as err:
        return json.dumps({"status": "ERROR", "error": str(err)}, indent=2)

@mcp.tool()
def get_live_world_events(category: str = "ALL", limit: int = 15, force_refresh: bool = False) -> str:
    """Retrieve verified, real-time live financial news headlines, Treasury wires, central bank releases, and geopolitical events."""
    return mcp_alpha_get_live_world_events(category=category, limit=limit, force_refresh=force_refresh)

# Quarantined: passive software watches deprecated in favor of direct MT5 orders
def register_watch(
    symbol: str = "XAUUSD",
    title: str = "",
    condition: str = "",
    instruction: str = "",
    target_price: float = None,
    reason: str = "",
    direction: str = "",
    watch_id: str = "",
    condition_type: str = "",
    target_ticket: int = None,
    tolerance: float = 0.50,
    min_velocity: float = None,
    max_velocity: float = None,
    min_cvd: float = None,
    max_cvd: float = None,
    target_cvd: float = None,
    cvd_flip: str = "",
    target_pnl: float = None,
    max_spread: float = None,
    is_recurring: bool = False,
    keywords: Any = None
) -> str:
    """Create or update an objective persistent watch with a descriptive Reason Title.
    
    Supports:
    - Single Technical Watch: only velocity (min_velocity or max_velocity), only CVD (min_cvd, max_cvd, cvd_flip), only spread, only price, or only position PnL.
    - Multiple Matching at Once (Composite Confluence): combine price + velocity + CVD (e.g. target_price=4345.0, min_velocity=100.0, min_cvd=50.0). All specified criteria must match simultaneously (AND confluence).
    - Descriptive Reason Title: OpenCode must supply title='...' so the alert explains exactly why it woke.
    - Auto-Clearing: Watch automatically clears immediately upon trigger.
    """
    return mcp_alpha_register_watch(
        symbol=symbol,
        title=title,
        condition=condition,
        instruction=instruction,
        target_price=target_price,
        reason=reason,
        direction=direction,
        watch_id=watch_id,
        condition_type=condition_type,
        target_ticket=target_ticket,
        tolerance=tolerance,
        min_velocity=min_velocity,
        max_velocity=max_velocity,
        min_cvd=min_cvd,
        max_cvd=max_cvd,
        target_cvd=target_cvd,
        cvd_flip=cvd_flip,
        target_pnl=target_pnl,
        max_spread=max_spread,
        is_recurring=is_recurring,
        keywords=keywords
    )

def get_active_watches(symbol: str = None, include_closed: bool = False) -> str:
    """Fetch persistent watches tracked by the trading desk. Defaults to ACTIVE watches only (include_closed=False) to prevent context bloat."""
    return mcp_alpha_get_active_watches(symbol, include_closed)

def update_watch(watch_id: str, status: str = "", condition: str = "", instruction: str = "", target_price: float = None, reason: str = "") -> str:
    """Update status (ACTIVE/TRIGGERED/CANCELLED), target_price, condition, or notes on an existing watch."""
    return mcp_alpha_update_watch(watch_id, status, condition, instruction, target_price, reason)

def cancel_watch(watch_id: str) -> str:
    """Cancel / remove an active persistent watch by ID."""
    return mcp_alpha_cancel_watch(watch_id)

def clear_completed_watches(symbol: str = None) -> str:
    """Clear all triggered and cancelled watches from disk memory."""
    return mcp_alpha_clear_completed_watches(symbol)

_global_arbiter = None

@mcp.tool()
def get_market_regime_context(symbol: str = "XAUUSD", force_refresh: bool = False) -> str:
    """Retrieve pure real-time physical market telemetry and raw kinetic metrics (live broker quotes, spread, tape velocity, CVD ratios, 4m/M1 footprints, Level 2 order book depth, real yields, and calendar countdown) without artificial labels or calculated fluff. Set force_refresh=True to bypass cached macro yields and pull live endpoints."""
    global _global_arbiter
    from tradingagents.catalyst_arbiter import CatalystArbiterEngine
    if _global_arbiter is None:
        _global_arbiter = CatalystArbiterEngine()
    sym = _normalize_symbol(symbol)
    read_logger.log_dossier_read("OpenCode CIO (MCP Telemetry Context)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Requested raw physical market telemetry for {sym}")
    raw_res = _global_arbiter.get_market_regime(sym, force_refresh=force_refresh)
    # Token optimization: Remove prompt duplicate badge, redundant 1m series, and verbose OHLC dump (already summarized in roadways)
    if isinstance(raw_res, dict):
        raw_res.pop("compact_prompt_badge", None)
        if "raw_metrics" in raw_res and isinstance(raw_res["raw_metrics"], dict):
            raw_res["raw_metrics"].pop("raw_footprints_30_m1", None)
            raw_res["raw_metrics"].pop("raw_ohlc_60b", None)
    return json.dumps(raw_res, separators=(',', ':'))

def mcp_alpha_get_deep_orderflow_telemetry(symbol: str = "XAUUSD") -> str:
    """Retrieve ultra-compact, non-label, pure numerical institutional order flow coordinates without context bloat:
    1. Institutional VWAP & ±1σ, ±2σ deviation bands with live distance in points
    2. Level 2 DOM depth ladder (top 3 bids/asks with lot sizes) & DOM imbalance
    3. Asian session extreme (high, low, width) & live sweep status
    4. Retail stop pools (nearest Buy-Stop Liquidity & Sell-Stop Liquidity distance)
    5. Active unmitigated FVG 50% Consequent Encroachment (CE) coordinates
    6. Volatility physics (ATR14 M5, ADR20 % used)
    """
    _init_mt5()
    sym = _normalize_symbol(symbol)
    try:
        from tradingagents.market_depth_engine import MarketDepthEngine
        from tradingagents.fair_value_gap import FairValueGapEngine

        def _f(v, digits=2):
            return round(float(v), digits) if v is not None else None

        # 1. Institutional VWAP
        vwap_data = _inst_engine.get_institutional_vwap(sym)
        vwap_block = {
            "vwap": _f(vwap_data.get("vwap")),
            "upper_1s": _f(vwap_data.get("upper_band_1")),
            "upper_2s": _f(vwap_data.get("upper_band_2")),
            "lower_1s": _f(vwap_data.get("lower_band_1")),
            "lower_2s": _f(vwap_data.get("lower_band_2")),
            "dist_pts": _f(vwap_data.get("distance_usd"))
        }

        # 2. Level 2 DOM Depth Ladder
        depth_eng = MarketDepthEngine()
        dom = depth_eng.get_broker_dom(sym)
        bids = [[_f(b["price"]), _f(b["lots"], 1)] for b in dom.get("bids", [])[:3]]
        asks = [[_f(a["price"]), _f(a["lots"], 1)] for a in dom.get("asks", [])[:3]]
        top_bid_w = dom.get("top_bid_wall")
        top_ask_w = dom.get("top_ask_wall")
        dom_block = {
            "bids_top3": bids,
            "asks_top3": asks,
            "dom_imbalance": _f(dom.get("dom_imbalance", 0.0), 3),
            "top_bid_wall": [_f(top_bid_w["price"]), _f(top_bid_w["lots"], 1)] if top_bid_w else None,
            "top_ask_wall": [_f(top_ask_w["price"]), _f(top_ask_w["lots"], 1)] if top_ask_w else None
        }

        # 3. Asian Session Extreme & Sweep
        asian = _inst_engine.get_asian_range_metrics(sym)
        asian_high = asian.get("asian_high")
        asian_low = asian.get("asian_low")
        curr_p = asian.get("current_price", 0)
        asian_block = {
            "high": _f(asian_high),
            "low": _f(asian_low),
            "width_pts": _f(asian.get("range_pts")),
            "swept_high": bool(curr_p > asian_high) if asian_high else False,
            "swept_low": bool(curr_p < asian_low) if asian_low else False
        }

        # 4. Retail Liquidity Targets (BSL/SSL)
        stops = _inst_engine.get_retail_stop_clusters(sym)
        retail_block = {
            "buy_stop_pool": [_f(stops.get("buy_stop_pool")), _f(stops.get("dist_to_buy_stops"))],
            "sell_stop_pool": [_f(stops.get("sell_stop_pool")), _f(stops.get("dist_to_sell_stops"))]
        }

        # 5. Active Unmitigated FVGs with 50% Consequent Encroachment (CE)
        fvg_eng = FairValueGapEngine()
        fvg_mat = fvg_eng.get_symbol_fvg_matrix(sym)
        near_fvg = fvg_mat.get("nearest_unmitigated_fvg")
        fvg_block = {
            "tf": near_fvg.get("timeframe"),
            "type": near_fvg.get("type"),
            "range": [_f(near_fvg.get("bottom")), _f(near_fvg.get("top"))],
            "ce_50pct": _f(near_fvg.get("consequent_encroachment")),
            "fill_pct": _f(near_fvg.get("fill_pct"), 1)
        } if near_fvg else None

        # 6. Volatility Physics
        vol = _inst_engine.get_volatility_regime(sym)
        vol_block = {
            "m15_atr": _f(vol.get("m15_atr")),
            "vol_ratio": _f(vol.get("vol_ratio"))
        }

        payload = {
            "symbol": sym,
            "vwap_bands": vwap_block,
            "level2_dom": dom_block,
            "asian_session": asian_block,
            "retail_liquidity": retail_block,
            "nearest_unmitigated_fvg": fvg_block,
            "volatility_physics": vol_block
        }
        return json.dumps(payload, separators=(',', ':'))
    except Exception as err:
        return json.dumps({"status": "ERROR", "symbol": sym, "error": str(err)})

@mcp.tool()
def get_deep_orderflow_telemetry(symbol: str = "XAUUSD") -> str:
    """Retrieve ultra-compact, non-label, pure numerical institutional order flow coordinates: VWAP ±1s/2s bands, Level 2 DOM depth ladder (top 3 bids/asks), Asian session extreme & sweep state, retail stop pools (BSL/SSL), and nearest unmitigated FVG 50% CE."""
    return mcp_alpha_get_deep_orderflow_telemetry(symbol)

@mcp.tool()
def get_account_status() -> str:
    """Check live FTMO MT5 equity, balance, free margin, margin utilization % and active ticket states."""
    return mcp_alpha_get_account_status()

# Deprecated meta-tool: direct tool calls enforced
def list_desk_tools() -> str:
    """Live dynamic discovery of ALL available FastMCP tools and their capabilities in the desk daemon."""
    tools_list = [
        {"name":"get_account_status","description":"Live account, margin and active position facts."},
        {"name":"get_mt5_deals_history","description":"Factual closed-deal history from MT5."},
        {"name":"get_full_institutional_profile","description":"Calculated market structure and cross-market evidence."},
        {"name":"get_live_microstructure","description":"Current measured spread, tick velocity, order-book and CVD evidence."},
        {"name":"get_measured_cvd","description":"Measured tick CVD and delta evidence."},
        {"name":"get_crowd_liquidity_vector","description":"Evidence telemetry revealing crowd entrapment, stop density, and absorption dynamics."},
        {"name":"get_fvg_matrix","description":"Multi-timeframe FVG geometry."},
        {"name":"get_fred_observations","description":"Vintage-aware FRED/ALFRED macro observations."},
        {"name":"backtest_thesis","description":"Historical empirical replay evidence; never an automatic signal."},
        {"name":"record_decision_snapshot","description":"Persist factual pre-decision context."},
        {"name":"execute_trade","description":"Execute only with explicit validated volume, SL and TP."},
        {"name":"place_pending_order","description":"Place only an explicitly specified pending order."},
        {"name":"cancel_pending_order","description":"Cancel a pending order."},
        {"name":"get_pending_orders","description":"Fetch current pending orders."},
        {"name":"update_position","description":"Manage an explicitly identified position."},
        {"name":"mark_evidence_read","description":"Batch-mark evidence read."},
        {"name":"get_market_regime_context","description":"Retrieve pure real-time physical market telemetry, tape kinetics, and macro yields."},
        {"name":"get_deep_orderflow_telemetry","description":"Retrieve ultra-compact, non-label, pure numerical institutional order flow coordinates: VWAP ±1s/2s bands, Level 2 DOM depth ladder (top 3 bids/asks), Asian session extreme & sweep state, retail stop pools (BSL/SSL), and nearest unmitigated FVG 50% CE."},
        {"name":"record_pattern_observation","description":"Record pattern evidence directly into Graphiti Temporal Memory on every observation cycle."},
        {"name":"record_trade_observation","description":"Commit verified trade outcomes and autopsy lessons into Graphiti Temporal Memory."},
        {"name":"get_trade_forensics","description":"Query granular post-trade forensics and entry market context for closed MT5 deals."},
        {"name":"execute_market_order","description":"Execute direct market order on FTMO MT5 with custom volume, SL, and TP."},
        {"name":"get_symbol_conviction","description":"Query live 4TF institutional alignment, exact EMA20/50 & RSI values, FVG geometry, and COT percentiles."},
        {"name":"get_market_time_context","description":"Retrieve synchronized market clocks across UTC, New York (EDT/EST), London (BST/GMT), Tokyo (JST), Sydney (AEST), live trading sessions, or calculate exact countdowns to any target time."},
        {"name":"get_live_world_events","description":"Retrieve verified, real-time live financial news headlines, Treasury wires, central bank releases, and geopolitical events."},
        {"name":"query_analyst_desk","description":"The 7-Layer Local Multi-Agent Analyst Desk synthesis: true 4TF EMAs/RSI, COT positioning, FVG CE geometry, and automated Bull vs Bear debate."}
    ]
    return json.dumps({"status": "SUCCESS", "tools_count": len(tools_list), "tools": tools_list}, indent=2)


@mcp.tool()
def get_topological_liquidity_map(symbol: str = "XAUUSD") -> str:
    """
    Topological Market Graph & Liquidity Cascade Radar (Graphify GPS).
    Extracts the localized 1-hop spatial ego-graph around current price:
    - Nearest Ceiling & Floor coordinates with distance in points.
    - Downward and Upward Liquidity Cascade Chains (trapped retail stops).
    - Macro Runway R:R ratio to primary target.
    - Uncompleted Sweep Trap Hazard warning (<3.0 pts clearance).
    Zero Level 2 DOM noise. Pure structural auction geometry.
    """
    try:
        from tradingagents.topological_graph_engine import get_topological_engine
        eng = get_topological_engine()
        return eng.format_ego_graph_card(symbol=symbol)
    except Exception as e:
        LOG.error(f"Error in get_topological_liquidity_map: {e}")
        return f"Topological map error: {e}"


def alpha_get_topological_liquidity_map(symbol: str = "XAUUSD") -> str:
    """Internal alias for get_topological_liquidity_map."""
    return get_topological_liquidity_map(symbol=symbol)


# Quarantined / Deprecated: direct native tool calls enforced per Standing Orders
def call_desk_tool(tool_name: str, arguments_json: str = "{}") -> str:
    """Universal Dynamic Tool Dispatcher. Executes any desk tool by name dynamically with auto-reload pickup."""
    name = tool_name.strip()
    if name.startswith("mcp_alpha_"):
        name = name.replace("mcp_alpha_", "")
    
    try:
        args = json.loads(arguments_json) if isinstance(arguments_json, str) and arguments_json.strip() else {}
    except Exception as e:
        args = {}

    fn_map = {
        "get_account_status": mcp_alpha_get_account_status,
        "get_fred_observations": lambda: get_fred_observations(**args),
        "get_live_world_events": lambda: get_live_world_events(args.get("category","ALL"),args.get("limit",15),args.get("force_refresh",False)),
        "alpha_get_live_world_events": lambda: get_live_world_events(args.get("category","ALL"),args.get("limit",15),args.get("force_refresh",False)),
        "backtest_thesis": lambda: _sync_backtest_thesis(args.get("query",""),args.get("symbol","XAUUSD"),args.get("timeframe","M5"),args.get("bars",60),args.get("offset",0)),
        "alpha_backtest_thesis": lambda: _sync_backtest_thesis(args.get("query",""),args.get("symbol","XAUUSD"),args.get("timeframe","M5"),args.get("bars",60),args.get("offset",0)),
        "place_pending_order": lambda: mcp_alpha_place_pending_order(args.get("symbol",""),args.get("order_type",""),args.get("price",0.0),args.get("volume",0.0),args.get("sl",0.0),args.get("tp",0.0),args.get("comment","OpenCode Planned Order"),args.get("tag","")),
        "cancel_pending_order": lambda: mcp_alpha_cancel_pending_order(args.get("order_ticket",args.get("ticket",0))),
        "modify_pending_order": lambda: mcp_alpha_modify_pending_order(args.get("order_ticket",args.get("ticket",0)),args.get("price",0.0),args.get("sl",0.0),args.get("tp",0.0)),
        "get_pending_orders": lambda: mcp_alpha_get_pending_orders(args.get("symbol","ALL")),
        "update_position": lambda: mcp_alpha_update_position(args.get("ticket",0),args.get("action",""),args.get("params_json","")),
        "get_market_regime_context": lambda: get_market_regime_context(args.get("symbol","XAUUSD"), args.get("force_refresh", False)),
        "get_trade_forensics": lambda: mcp_alpha_get_trade_forensics(args.get("ticket", 0)),
        "execute_market_order": lambda: mcp_alpha_execute_market_order(args.get("symbol","XAUUSD"),args.get("side","BUY"),args.get("volume",1.0),args.get("sl_price",0.0),args.get("tp_price",0.0),args.get("sl",0.0),args.get("tp",0.0),args.get("comment","OpenCode Market Order")),
        "get_deep_orderflow_telemetry": lambda: mcp_alpha_get_deep_orderflow_telemetry(args.get("symbol","XAUUSD")),
        "alpha_get_deep_orderflow_telemetry": lambda: mcp_alpha_get_deep_orderflow_telemetry(args.get("symbol","XAUUSD")),
        "get_topological_liquidity_map": lambda: get_topological_liquidity_map(args.get("symbol","XAUUSD")),
        "alpha_get_topological_liquidity_map": lambda: get_topological_liquidity_map(args.get("symbol","XAUUSD")),
        "query_analyst_desk": lambda: _sync_query_analyst_desk(args.get("query","Full 7-layer technical, fundamental COT, and macro market analysis"), args.get("symbol","XAUUSD"))
    }

    if name in fn_map:

        try:
            return fn_map[name]()
        except Exception as e:
            return json.dumps({"status": "ERROR", "tool": name, "error": str(e)}, indent=2)
    
    return json.dumps({"status": "UNKNOWN_TOOL", "requested_tool": name, "available_tools": list(fn_map.keys())}, indent=2)


if __name__ == "__main__":
    _init_mt5()
    mcp.run()
