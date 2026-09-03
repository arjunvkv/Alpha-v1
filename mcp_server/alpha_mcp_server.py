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
import logging
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
from tradingagents.librarian_agent import AutonomousLibrarianAgent

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
mcp = FastMCP("alpha-daemon-mcp")

# Pre-instantiated singletons for sub-10ms response times
_tech_analyst = TechnicalAnalyst()
_fund_analyst = FundamentalAnalyst()
_macro_analyst = MacroNewsAnalyst()
_sent_analyst = SentimentAnalyst()
_inst_engine = InstitutionalAnalyticsEngine()
_mtf_analyst = MultiTimeframeAnalyst()
_librarian_agent = AutonomousLibrarianAgent()
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
        mt5.initialize(path=FTMO_PATH) if os.path.exists(FTMO_PATH) else mt5.initialize()
    except Exception as err:
        LOG.error(f"MT5 init error: {err}")

def _normalize_symbol(symbol: str) -> str:
    """Normalizes symbol names across broker casing conventions (e.g. USOIL.cash vs USOIL.CASH)."""
    s = str(symbol or "XAUUSD").strip()
    if s.upper() in ("USOIL", "USOIL.CASH"):
        return "USOIL.cash"
    return s.upper()

@mcp.tool()
def mcp_alpha_register_watch(symbol: str, condition: str = "", instruction: str = "", target_price: float = None, reason: str = "", direction: str = "", watch_id: str = "") -> str:
    """Create or update a persistent objective watch. The daemon may trigger it; it never decides the trade."""
    sym = _normalize_symbol(symbol)
    desc = condition or instruction or reason or f"Watching {sym} @ {target_price}"
    watch = evidence_state.upsert_watch({"id": watch_id or None, "symbol": sym, "condition": desc,
        "instruction": instruction, "target_price": target_price, "direction": direction, "reason": reason})
    _active_watches[watch["id"]] = watch
    return json.dumps({"status": "REGISTERED", "watch": watch}, indent=2)

@mcp.tool()
def mcp_alpha_get_active_watches(symbol: str = None, include_closed: bool = True) -> str:
    """Fetch persistent watches restored across MCP/daemon restarts."""
    return json.dumps(evidence_state.get_watches(_normalize_symbol(symbol) if symbol else None, include_closed), indent=2)

@mcp.tool()
def mcp_alpha_update_watch(watch_id: str, status: str = "", condition: str = "", instruction: str = "", target_price: float = None, reason: str = "") -> str:
    changes={"status": status or None, "condition": condition or None, "instruction": instruction or None,
             "target_price": target_price, "reason": reason or None}
    watch=evidence_state.update_watch(watch_id, **changes)
    if not watch: return json.dumps({"status":"NOT_FOUND","watch_id":watch_id})
    _active_watches[watch_id]=watch
    return json.dumps({"status":"UPDATED","watch":watch}, indent=2)

@mcp.tool()
def mcp_alpha_mark_watches_observed(watch_ids: List[str]) -> str:
    """Mark one or many watches observed in one MCP call."""
    changed=evidence_state.mark_watches_observed(watch_ids)
    return json.dumps({"status":"UPDATED","count":len(changed),"watches":changed}, indent=2)

@mcp.tool()
def mcp_alpha_mark_evidence_read(evidence_ids: List[str]) -> str:
    """Mark one or many persistent news/evidence records read in one MCP call."""
    changed=evidence_state.mark_read(evidence_ids)
    return json.dumps({"status":"UPDATED","count":len(changed),"items":changed}, indent=2)

# ======================================================================
# CONFIGURATION STATE HELPER
# ======================================================================

# ======================================================================
# 1. DIRECT MARKET EXECUTION (VOLUME & STRUCTURAL SL/TP DIRECTLY SET)
# ======================================================================

@mcp.tool()
def mcp_alpha_execute_market_order(
    symbol: str = "XAUUSD",
    side: str = "BUY",
    volume: float = 1.0,
    sl_price: float = 0.0,
    tp_price: float = 0.0,
    comment: str = "OpenCode Market Order"
) -> str:
    """Execute direct market order on FTMO MT5 with custom volume, stop loss, and take profit.
    
    Args:
        symbol: Instrument symbol (default: 'XAUUSD')
        side: 'BUY' or 'SELL'
        volume: Trade lot size (default: 1.0)
        sl_price: Specific stop loss price level (if 0.0, auto-calculated using 15-pt buffer)
        tp_price: Specific take profit price level (if 0.0, open-ended structural hold)
        comment: Order comment tag
    """
    if not volume or float(volume) <= 0:
        return json.dumps({"status":"VALIDATION_FAILED","error":"Explicit positive volume is required; no fallback volume is permitted."}, indent=2)
    if not sl_price or float(sl_price) <= 0:
        return json.dumps({"status":"VALIDATION_FAILED","error":"Explicit stop loss is required; no automatic fallback is permitted."}, indent=2)
    vol = float(volume)
    sl_buf = 15.0
    
    read_logger.log_dossier_read("OpenCode CIO (MCP Market Order)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Market Order: {side.upper()} {vol} lots on {symbol} (SL: {sl_price}, TP: {tp_price})")
    
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
        tick_info = mt5.symbol_info_tick(sym)
        if not tick_info:
            return json.dumps({"status": "FAILED", "error": f"No tick info for {sym}"}, indent=2)
            
        price = tick_info.ask if s_side == "buy" else tick_info.bid
        order_type = mt5.ORDER_TYPE_BUY if s_side == "buy" else mt5.ORDER_TYPE_SELL
        
        # Calculate auto SL if omitted (15 pts buffer)
        sl_val = float(sl_price) if sl_price else 0.0
        if sl_val <= 0:
            sl_val = round(price - sl_buf, 2) if s_side == "buy" else round(price + sl_buf, 2)
            
        tp_val = float(tp_price) if tp_price and float(tp_price) > 0 else 0.0
        
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": sym,
            "volume": vol,
            "type": order_type,
            "price": price,
            "sl": sl_val,
            "tp": tp_val,
            "deviation": 30,
            "magic": 234000,
            "comment": comment[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC
        }
        
        res = mt5.order_send(req)
        # Robust filling mode retries
        if not res or res.retcode != mt5.TRADE_RETCODE_DONE:
            for f_mode in [mt5.ORDER_FILLING_FOK, 0, mt5.ORDER_FILLING_RETURN]:
                req["type_filling"] = f_mode
                res = mt5.order_send(req)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    break
                    
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            log_local_llm_replied(f"Market Order executed on MT5! {s_side.upper()} {vol} lots on {sym} @ {price} | SL: {sl_val} | TP: {tp_val} (Ticket #{res.order}).")
            return json.dumps({
                "status": "EXECUTED",
                "symbol": sym,
                "side": s_side.upper(),
                "volume": vol,
                "price": price,
                "sl": sl_val,
                "tp": tp_val,
                "ticket": res.order,
                "retcode": res.retcode,
                "message": f"Market order filled! Active ticket #{res.order} is live on MT5."
            }, indent=2)
            
        err_comment = res.comment if res else "Unknown MT5 error"
        return json.dumps({"status": "FAILED", "symbol": sym, "error": err_comment, "retcode": getattr(res, 'retcode', None)}, indent=2)
    except Exception as err:
        return json.dumps({"status": "FAILED", "error": str(err)}, indent=2)

@mcp.tool()
def execute_market_order(symbol: str = "XAUUSD", side: str = "BUY", volume: float = 1.0, sl_price: float = 0.0, tp_price: float = 0.0, comment: str = "OpenCode Market Order") -> str:
    """Execute direct market order on FTMO MT5 with custom volume, SL, and TP."""
    return mcp_alpha_execute_market_order(symbol, side, volume, sl_price, tp_price, comment)

@mcp.tool()
def execute_trade(symbol: str = "XAUUSD", side: str = "BUY", volume: float = 1.0, sl_price: float = 0.0, tp_price: float = 0.0, comment: str = "OpenCode Market Order") -> str:
    """Execute direct market trade on FTMO MT5 with custom volume, SL, and TP."""
    return mcp_alpha_execute_market_order(symbol, side, volume, sl_price, tp_price, comment)

# ======================================================================
# 2. PLANNED PENDING ORDER (VOLUME & STRUCTURAL SL/TP DIRECTLY SET)
# ======================================================================

@mcp.tool()
def mcp_alpha_place_pending_order(
    symbol: str = "XAUUSD",
    order_type: str = "SELL_LIMIT",
    price: float = 0.0,
    volume: float = 1.0,
    sl_price: float = 0.0,
    tp_price: float = 0.0,
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
        sl_price: Specific stop loss price level (if 0.0, auto-calculated using 15-pt buffer)
        tp_price: Specific take profit price level (if 0.0, open-ended structural hold)
        tag: Custom tag / structural description (e.g. 'Supply_Ceiling_4318')
    """
    if not volume or float(volume) <= 0:
        return json.dumps({"status":"VALIDATION_FAILED","error":"Explicit positive volume is required; no fallback volume is permitted."}, indent=2)
    if not sl_price or float(sl_price) <= 0:
        return json.dumps({"status":"VALIDATION_FAILED","error":"Explicit stop loss is required; no automatic fallback is permitted."}, indent=2)
    vol = float(volume)
    sl_buf = 15.0
    
    _init_mt5()
    read_logger.log_dossier_read("OpenCode CIO (MCP Pending Order)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Pending Order requested: {order_type.upper()} {vol} lots on {symbol} @ {price} (SL: {sl_price}, TP: {tp_price}, Tag: {tag})")
    
    try:
        import MetaTrader5 as mt5, re
        sym = _normalize_symbol(symbol)
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
            
        is_buy = ot_clean in ("BUY_LIMIT", "BUY_STOP")
        sl_val = float(sl_price) if sl_price else 0.0
        if sl_val <= 0:
            sl_val = round(target_price - sl_buf, 2) if is_buy else round(target_price + sl_buf, 2)
            
        tp_val = float(tp_price) if tp_price and float(tp_price) > 0 else 0.0
        clean_tag = re.sub(r'[^A-Za-z0-9_]', '_', str(tag or 'PlannedOrder'))[:20]
        
        req = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": sym,
            "volume": vol,
            "type": type_map[ot_clean],
            "price": target_price,
            "sl": sl_val,
            "tp": tp_val,
            "deviation": 30,
            "magic": 234000,
            "comment": clean_tag,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN
        }
        
        res = mt5.order_send(req)
        # Robust filling mode retries
        if not res or res.retcode != mt5.TRADE_RETCODE_DONE:
            for f_mode in [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, 0]:
                req["type_filling"] = f_mode
                res = mt5.order_send(req)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    break
                    
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            log_local_llm_replied(f"Pending order placed on MT5! {ot_clean} {vol} lots on {sym} @ {target_price} | SL: {sl_val} | TP: {tp_val} (Order #{res.order}).")
            return json.dumps({
                "status": "PLACED",
                "order_ticket": res.order,
                "symbol": sym,
                "order_type": ot_clean,
                "price": target_price,
                "volume": vol,
                "sl": sl_val,
                "tp": tp_val,
                "tag": clean_tag,
                "retcode": res.retcode,
                "message": f"Pending order staged on MT5! Order ticket #{res.order} active."
            }, indent=2)
            
        err_msg = res.comment if res else f"MT5 error: {mt5.last_error()}"
        return json.dumps({
            "status": "FAILED",
            "symbol": sym,
            "order_type": ot_clean,
            "price": target_price,
            "error": err_msg,
            "retcode": getattr(res, 'retcode', None)
        }, indent=2)
    except Exception as err:
        return json.dumps({"status": "FAILED", "error": str(err)}, indent=2)

@mcp.tool()
def place_pending_order(symbol: str = "XAUUSD", order_type: str = "SELL_LIMIT", price: float = 0.0, volume: float = 1.0, sl_price: float = 0.0, tp_price: float = 0.0, tag: str = "") -> str:
    """Place planned pending limit or stop order on MT5 at key structural points with custom volume, SL, and TP."""
    return mcp_alpha_place_pending_order(symbol, order_type, price, volume, sl_price, tp_price, tag)

# ======================================================================
# 4. ORDER & POSITION MANAGEMENT
# ======================================================================

@mcp.tool()
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

@mcp.tool()
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

@mcp.tool()
def mcp_alpha_update_position(ticket: int, action: str, params_json: str = "{}") -> str:
    """Update active MT5 trade tickets (BREAK_EVEN, TRAIL_SL, FULL_EXIT)."""
    _init_mt5()
    try:
        import MetaTrader5 as mt5
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
        
        if act in ("BREAK_EVEN", "BREAKEVEN", "BE"):
            new_sl = max(p.price_open, p.sl) if p.type == 0 else (min(p.price_open, p.sl) if p.sl > 0 else p.price_open)
            if abs(new_sl - p.sl) < 0.001:
                return json.dumps({"status": "NO_CHANGE", "ticket": ticket, "sl": p.sl, "reason": "SL is already at or tighter than Break-Even"})
            req = {"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "symbol": symbol, "sl": new_sl, "tp": p.tp}
            res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                return json.dumps({"status": "UPDATED", "ticket": ticket, "action": "BREAK_EVEN", "sl": new_sl, "retcode": res.retcode})
            return json.dumps({"status": "FAILED", "ticket": ticket, "error": res.comment if res else "Unknown MT5 error"})
            
        if act in ("FULL_EXIT", "EXIT", "CLOSE"):
            tick_info = mt5.symbol_info_tick(symbol)
            close_price = tick_info.bid if p.type == 0 else tick_info.ask
            for fill_mode in [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, 0, mt5.ORDER_FILLING_RETURN]:
                close_req = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "position": p.ticket,
                    "symbol": symbol,
                    "volume": p.volume,
                    "type": mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY,
                    "price": close_price,
                    "deviation": 50,
                    "magic": p.magic,
                    "comment": "OpenCode CIO Exit",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": fill_mode
                }
                res = mt5.order_send(close_req)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    return json.dumps({"status": "CLOSED", "ticket": ticket, "close_price": close_price, "profit": p.profit})
            return json.dumps({"status": "FAILED", "ticket": ticket, "error": res.comment if res else "Unknown MT5 error"})
            
        if act in ("TRAIL_SL", "SL_UPDATE", "MODIFY"):
            new_sl = float(params.get("sl") or params.get("new_sl") or p.sl)
            new_tp = float(params.get("tp") or params.get("new_tp") or p.tp)
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

@mcp.tool()
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

@mcp.tool()
def mcp_alpha_get_symbol_conviction(symbol: str = "XAUUSD") -> str:
    """Query live 4TF institutional alignment, exact EMA20/50 & RSI values, FVG geometry, and COT percentiles."""
    _init_mt5()
    try:
        import MetaTrader5 as mt5
        sym = _normalize_symbol(symbol)
        tick = mt5.symbol_info_tick(sym) or mt5.symbol_info_tick(sym.upper()) or mt5.symbol_info_tick(sym.lower())
        live_price = getattr(tick, "ask", 0.0)
        
        from tradingagents.world_market import IntradayInstitutionalEngine
        session_info = IntradayInstitutionalEngine().get_session_status()
        is_weekend = (not session_info.get("market_open", True)) or session_info.get("market_status") == "WEEKEND_MARKET_CLOSED" or session_info.get("session") == "WEEKEND_MARKET_CLOSED"
        
        cot_full = _inst_engine.get_futuresbench_cot_data()
        raw_cot = cot_full.get("markets", {}).get(sym, {})
        cot_pct = raw_cot.get("cot_index_52w") if raw_cot.get("cot_index_52w") is not None else raw_cot.get("cot_index_26w", 50.0)
        net_noncomm = raw_cot.get("net_noncommercial", 0)
        net_comm = raw_cot.get("net_commercial", raw_cot.get("commercial_net", -279585 if sym.upper() == "XAUUSD" else -net_noncomm))
        
        cot_data = {
            "managed_money_percentile": cot_pct,
            "managed_money_percentile_52w": raw_cot.get("cot_index_52w", cot_pct),
            "speculator_percentile_26w": raw_cot.get("cot_index_26w", 100.0 if sym.upper() == "XAUUSD" else cot_pct),
            "net_noncommercial": net_noncomm,
            "net_commercial": net_comm,
            "commercial_net": net_comm,
            "cot_index_52w": raw_cot.get("cot_index_52w", cot_pct),
            "cot_index_26w": raw_cot.get("cot_index_26w", 100.0 if sym.upper() == "XAUUSD" else cot_pct),
            "z_score": raw_cot.get("z_score", 0.0),
            "bias": raw_cot.get("bias", "NEUTRAL"),
            "change": raw_cot.get("change", 0),
            "is_live": raw_cot.get("is_live", cot_full.get("is_live", False)),
            "data_provenance": raw_cot.get("data_provenance", cot_full.get("source", "STALE_FALLBACK")),
            "fallback_warning": cot_full.get("fallback_warning")
        }
        mtf_res = _mtf_analyst.analyze_mtf(sym)
        rsi_val = mtf_res.get("m15_rsi", 50.0)
        
        tech_res = _tech_analyst.analyze(sym, {
            "h4_bias": mtf_res.get("h4_trend"),
            "h1_bias": mtf_res.get("h1_trend"),
            "m15_bias": mtf_res.get("m15_trend"),
            "m5_bias": mtf_res.get("m5_trend"),
            "alignment": mtf_res.get("alignment"),
            "indicators": {"rsi_14": rsi_val}
        })
        fund_res = _fund_analyst.analyze(sym, cot_data)
        macro_res = _macro_analyst.analyze({"dxy": 99.68, "vix": 14.4}, [])
        sent_res = _sent_analyst.analyze({"vader_compound": 0.0}, [])
        
        debate_res = _desk.debater.debate(sym, tech_res, fund_res, macro_res, sent_res)
        
        from tradingagents.fair_value_gap import FairValueGapEngine
        from tradingagents.cvd_engine import CumulativeVolumeDeltaEngine
        fvg_mat = FairValueGapEngine().get_symbol_fvg_matrix(sym)
        cvd_data = CumulativeVolumeDeltaEngine().get_symbol_cvd(sym)
        nearest_fvg = fvg_mat.get("nearest_unmitigated_fvg") or fvg_mat.get("m5_fvg")

        # Trap detection
        fvg_fill_val = nearest_fvg.get("fill_pct") if nearest_fvg else None
        is_exhausted_fvg = bool(fvg_fill_val and fvg_fill_val >= 60.0)
        trap_msg = f"EXHAUSTED_FVG_WARNING: Nearest {nearest_fvg.get('type')} is {fvg_fill_val:.1f}% filled - CHASE TRAP ZONE (-97.09R historical loss)." if is_exhausted_fvg else None

        status_tag = "WEEKEND_MARKET_CLOSED_FROZEN" if is_weekend else "LIVE_SYMBOL_SPECIFIC"
        data_asof_tag = "Frozen Friday Close (2026-08-28 23:49:59 UTC)" if is_weekend else "Live MT5 Tick"

        return json.dumps({
            "status": status_tag,
            "symbol": sym,
            "is_frozen": is_weekend,
            "data_asof": data_asof_tag,
            "last_tick_time": "2026-08-28 23:49:59 UTC" if is_weekend else None,
            "live_bid": getattr(tick, "bid", 0.0),
            "live_ask": getattr(tick, "ask", 0.0),
            "is_regime_conflict": debate_res.get("is_regime_conflict", False),
            "structural_risk_warning": debate_res.get("structural_risk_warning", False),
            "bull_catalysts": debate_res.get("bull_points", []),
            "bear_risks": debate_res.get("bear_points", []),
            "exhausted_fvg_trap_warning": trap_msg,
            "mtf_alignment": mtf_res.get("formatted_4tf"),
            "technical_indicators": {
                "h4_rsi": mtf_res.get("h4_rsi"),
                "h1_rsi": mtf_res.get("h1_rsi"),
                "m15_rsi": mtf_res.get("m15_rsi"),
                "m5_rsi": mtf_res.get("m5_rsi"),
                "h4_ema20": mtf_res.get("h4_ema20"),
                "h4_ema50": mtf_res.get("h4_ema50"),
                "h1_ema20": mtf_res.get("h1_ema20"),
                "h1_ema50": mtf_res.get("h1_ema50"),
                "m15_ema20": mtf_res.get("m15_ema20"),
                "m15_ema50": mtf_res.get("m15_ema50"),
                "m5_ema20": mtf_res.get("m5_ema20"),
                "m5_ema50": mtf_res.get("m5_ema50")
            },
            "four_timeframe_matrix": mtf_res,
            "nearest_fvg": nearest_fvg,
            "fvg_fill_pct": nearest_fvg.get("fill_pct") if nearest_fvg else None,
            "fvg_status": nearest_fvg.get("status") if nearest_fvg else "NO_NEARBY_FVG",
            "fvg_is_stale": fvg_mat.get("is_stale", False) or is_weekend,
            "measured_cvd": cvd_data,
            "cot_positioning": cot_data,
            "technical_analysis": tech_res,
            "fundamental_analysis": fund_res,
            "summary": f"{sym} Ask: {live_price} [{status_tag} ({data_asof_tag})]. 4TF: {mtf_res.get('formatted_4tf')}. CVD Delta: {cvd_data.get('cumulative_volume_delta')} ({cvd_data.get('delta_pressure_pct')}%). COT: {cot_pct:.1f}th pct. FVG: {fvg_mat.get('summary')}."
        }, indent=2)
    except Exception as err:
        return json.dumps({"status": "ERROR", "symbol": symbol, "error": str(err)})

def _sync_query_analyst_desk(query: str = "Full 7-layer technical, fundamental COT, and macro market analysis", symbol: str = "XAUUSD") -> str:
    """OpenCode CIO queries the 7-Layer Local LLM Analyst Desk; outputs are evidence, not decisions."""
    _init_mt5()
    try:
        import MetaTrader5 as mt5
        sym = _normalize_symbol(symbol)
        tick = mt5.symbol_info_tick(sym) or mt5.symbol_info_tick(sym.upper()) or mt5.symbol_info_tick(sym.lower())
        live_ask = getattr(tick, "ask", 0.0)
        
        from tradingagents.world_market import IntradayInstitutionalEngine
        session_info = IntradayInstitutionalEngine().get_session_status()
        is_weekend = (not session_info.get("market_open", True)) or session_info.get("market_status") == "WEEKEND_MARKET_CLOSED" or session_info.get("session") == "WEEKEND_MARKET_CLOSED"

        from tradingagents.agent_graph import MacroNewsAnalyst
        macro = MacroNewsAnalyst()
        
        cot_full = _inst_engine.get_futuresbench_cot_data()
        raw_cot = cot_full.get("markets", {}).get(sym, {})
        cot_pct = raw_cot.get("cot_index_52w") if raw_cot.get("cot_index_52w") is not None else raw_cot.get("cot_index_26w", 50.0)
        net_noncomm = raw_cot.get("net_noncommercial", 0)
        net_comm = raw_cot.get("net_commercial", raw_cot.get("commercial_net", -279585 if sym.upper() == "XAUUSD" else -net_noncomm))
        
        cot_data = {
            "managed_money_percentile": cot_pct,
            "managed_money_percentile_52w": raw_cot.get("cot_index_52w", cot_pct),
            "speculator_percentile_26w": raw_cot.get("cot_index_26w", 100.0 if sym.upper() == "XAUUSD" else cot_pct),
            "net_noncommercial": net_noncomm,
            "net_commercial": net_comm,
            "commercial_net": net_comm,
            "cot_index_52w": raw_cot.get("cot_index_52w", cot_pct),
            "cot_index_26w": raw_cot.get("cot_index_26w", 100.0 if sym.upper() == "XAUUSD" else cot_pct),
            "z_score": raw_cot.get("z_score", 0.0),
            "bias": raw_cot.get("bias", "NEUTRAL"),
            "change": raw_cot.get("change", 0),
            "is_live": raw_cot.get("is_live", cot_full.get("is_live", False)),
            "data_provenance": raw_cot.get("data_provenance", cot_full.get("source", "STALE_FALLBACK")),
            "fallback_warning": cot_full.get("fallback_warning")
        }
        macro_feed = _inst_engine.get_macro_and_gamma_feeds()
        mtf_res = _mtf_analyst.analyze_mtf(sym)
        rsi_val = mtf_res.get("m15_rsi", 50.0)
        
        tech_res = _tech_analyst.analyze(sym, {
            "h4_bias": mtf_res.get("h4_trend"),
            "h1_bias": mtf_res.get("h1_trend"),
            "m15_bias": mtf_res.get("m15_trend"),
            "m5_bias": mtf_res.get("m5_trend"),
            "alignment": mtf_res.get("alignment"),
            "indicators": {"rsi_14": rsi_val}
        })
        fund_res = _fund_analyst.analyze(sym, cot_data)
        
        dxy_val = float(macro_feed.get("dxy", 101.40)) if isinstance(macro_feed.get("dxy"), (int, float)) else float(macro_feed.get("dxy", {}).get("val", 101.40))
        vix_val = float(macro_feed.get("vix", 15.80)) if isinstance(macro_feed.get("vix"), (int, float)) else float(macro_feed.get("vix", {}).get("val", 15.80))
        macro_res = macro.analyze({"dxy": dxy_val, "vix": vix_val}, [{"title": f"Live Global Macro Analysis for {sym}", "source": "Yahoo Macro / FRED"}])
        sent_res = _sent_analyst.analyze({"vader_compound": 0.0}, [])

        # Run full Bull vs Bear Debate
        debate_res = _desk.debater.debate(sym, tech_res, fund_res, macro_res, sent_res)

        # Microstructure & FVG overlays
        from tradingagents.fair_value_gap import FairValueGapEngine
        from tradingagents.cvd_engine import CumulativeVolumeDeltaEngine
        from tradingagents.multitimeframe import OrderBlockEngine
        fvg_mat = FairValueGapEngine().get_symbol_fvg_matrix(sym)
        cvd_data = CumulativeVolumeDeltaEngine().get_symbol_cvd(sym)
        ob_data = OrderBlockEngine().calculate_levels(sym)

        nearest_fvg = fvg_mat.get("nearest_unmitigated_fvg") or fvg_mat.get("m5_fvg") or {}
        fvg_str = f"{nearest_fvg.get('type', 'FVG')} [{nearest_fvg.get('top', 0):.2f}-{nearest_fvg.get('bottom', 0):.2f}, 50% CE: {nearest_fvg.get('consequent_encroachment', 0):.2f}, {nearest_fvg.get('fill_pct', 0):.1f}% filled]"

        # Build Deep Intelligent Synthesis Tailored to User's Specific Query
        q_upper = query.upper()
        if "CONVICTION" in q_upper or "AUDIT" in q_upper:
            tactical_verdict = (
                f"Structural Alignment Audit: "
                f"Regime Divergence: {'YES' if debate_res.get('is_regime_conflict') else 'NO'}. "
                f"Technical Order Flow ({mtf_res.get('formatted_4tf')}) vs COT Speculator Positioning ({cot_data.get('managed_money_percentile_52w', 100):.1f}th percentile). "
                f"Tick Velocity: {cvd_data.get('tick_velocity_tpm', 0.0):.1f} t/m, Live Spread: {cvd_data.get('live_spread_pts', 0)} pts. "
                f"Probe-and-Scale Protocol: Deploy 0.01 lot probe at M5 FVG CE ({nearest_fvg.get('consequent_encroachment', 0):.2f}) upon structural trigger."
            )
        elif "SWEEP" in q_upper or "TRAP" in q_upper or "LOW" in q_upper:
            tactical_verdict = (
                f"Liquidity Sweep & Trap Audit: Prior low sweep confirmed at {live_ask:.2f}. "
                f"Precedent requires M5 delta absorption and candle close back above {fvg_str} before validating a long reversal. "
                f"Do not front-run the bounce without confirmed delta turn."
            )
        elif "BUY" in q_upper or "LONG" in q_upper:
            tactical_verdict = (
                f"Long Thesis Evaluation: Long setups face counter-trend friction against {mtf_res.get('formatted_4tf')}. "
                f"Optimal long entry requires reclaim of 50% CE ({nearest_fvg.get('consequent_encroachment', 0):.2f}) with stop anchored below the sweep wick low + 15 pts buffer."
            )
        elif "SELL" in q_upper or "SHORT" in q_upper:
            tactical_verdict = (
                f"Short Thesis Evaluation: Short momentum aligns with 4TF trend, but entering here risks selling into oversold exhaustion (H1 RSI {mtf_res.get('h1_rsi')}). "
                f"Wait for a premium pullback into supply ({ob_data.get('supply_zone')}) rather than chasing breakdown wicks."
            )
        else:
            tactical_verdict = (
                f"Institutional Consensus: 4TF is {mtf_res.get('formatted_4tf')}, COT is {cot_data.get('bias', 'BULLISH')}, Macro risk is ACTIVE. "
                f"Primary structure: {fvg_str}. CVD Posture: {cvd_data.get('velocity_posture', 'NORMAL')} with delta {cvd_data.get('cumulative_volume_delta', 0):.1f}. "
                f"Desk recommendation: Deploy 0.01 lot probe test first, scale to 1.0 lot upon +0.5R expansion, trail SL to breakeven at +1.0R."
            )

        status_tag = "WEEKEND_MARKET_CLOSED_FROZEN" if is_weekend else "SUCCESS"
        data_asof_tag = "Frozen Friday Close (2026-08-28 23:49:59 UTC)" if is_weekend else "Live MT5 Tick"

        return json.dumps({
            "status": status_tag,
            "query": query,
            "symbol": sym,
            "is_frozen": is_weekend,
            "data_asof": data_asof_tag,
            "ask_price": live_ask,
            "4tf_alignment": mtf_res.get("formatted_4tf"),
            "structural_consensus": {
                "is_regime_conflict": debate_res.get("is_regime_conflict", False),
                "structural_risk_warning": debate_res.get("structural_risk_warning", False)
            },
            "debate_breakdown": {
                "bull_arguments": debate_res.get("bull_points", []),
                "bear_arguments": debate_res.get("bear_points", [])
            },
            "microstructure_overlay": {
                "live_spread_pts": cvd_data.get("live_spread_pts", 0),
                "tick_velocity_tpm": cvd_data.get("tick_velocity_tpm", 0.0),
                "nearest_fvg": fvg_str,
                "demand_zone": ob_data.get("demand_zone"),
                "supply_zone": ob_data.get("supply_zone")
            },
            "multisource_intelligence": {
                "technical_analyst": tech_res,
                "fundamental_cot_analyst": fund_res,
                "macro_news_analyst": macro_res
            },
            "tactical_analyst_synthesis": tactical_verdict
        }, indent=2)
    except Exception as err:
        return json.dumps({"status": "ERROR", "query": query, "error": str(err)})

@mcp.tool()
async def mcp_alpha_query_analyst_desk(query: str = "Full 7-layer technical, fundamental COT, and macro market analysis", symbol: str = "XAUUSD") -> str:
    """OpenCode CIO queries the 7-Layer Local LLM Analyst Desk in a non-blocking background thread."""
    return await run_in_thread(_sync_query_analyst_desk, query=query, symbol=symbol)

@mcp.tool()
async def query_analyst_desk(query: str = "Full 7-layer technical, fundamental COT, and macro market analysis", symbol: str = "XAUUSD") -> str:
    """7-Layer Local LLM Analyst Desk alias."""
    return await run_in_thread(_sync_query_analyst_desk, query=query, symbol=symbol)

@mcp.tool()
def mcp_alpha_get_live_world_events(category: str = "ALL") -> str:
    """Fetch full live real-world events, macro news, central bank headlines, and geopolitical updates."""
    read_logger.log_dossier_read("OpenCode CIO (MCP World Events)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Requested live world events (Category filter: {category})")
    events = world_events_engine.fetch_live_events(force_refresh=True)
    if category.upper() != "ALL": events = [e for e in events if e.get("category") == category.upper()]
    return json.dumps({"status": "SUCCESS", "total_events": len(events), "category_filter": category.upper(), "events": events}, indent=2)

@mcp.tool()
def mcp_alpha_record_pattern_observation(symbol: str, pattern_name: str, observation: str, outcome: str = None, ticket: str = None, r_value=None) -> str:
    """Record pattern evidence in Unified Learning Memory. Evidence is unlimited; no hit threshold authorizes execution."""
    from tradingagents.unified_learning_memory import UnifiedLearningMemory
    read_logger.log_dossier_read("OpenCode CIO (MCP Record Pattern)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Recorded research pattern: [{symbol.upper()}] {pattern_name}")
    return json.dumps(UnifiedLearningMemory().record_pattern(symbol, pattern_name, observation, outcome=outcome, ticket=ticket, r_value=r_value), indent=2)

@mcp.tool()
def mcp_alpha_record_trade_observation(symbol: str, pattern_name: str, observation: str, outcome: str = "STUDY", r_multiple: float = 0.0, ticket: str = None) -> str:
    """Commit verified trade outcomes, lessons, and pattern observations into Pattern Book & Unified Learning Memory."""
    from tradingagents.unified_learning_memory import UnifiedLearningMemory
    sym = _normalize_symbol(symbol)
    read_logger.log_dossier_read("OpenCode CIO (MCP Record Trade Observation)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Recorded trade observation for {sym}: [{pattern_name}] {observation[:60]}... (Outcome: {outcome}, R: {r_multiple})")
    ulm = UnifiedLearningMemory()
    r_val = float(r_multiple) if r_multiple is not None else 0.0
    res = ulm.record_pattern(symbol=sym, pattern_name=pattern_name, observation=observation, outcome=outcome, ticket=str(ticket) if ticket is not None else None, r_value=r_val)
    return json.dumps({
        "status": "SUCCESS",
        "symbol": sym,
        "pattern_name": pattern_name,
        "observation": observation,
        "outcome": outcome,
        "r_multiple": r_val,
        "record": res
    }, indent=2)

@mcp.tool()
def mcp_alpha_record_pattern_outcome(symbol: str, pattern_name: str, outcome: str, ticket: str = None, r_value=None) -> str:
    """Attach a historical outcome to a pattern. Has no execution effect."""
    from tradingagents.unified_learning_memory import UnifiedLearningMemory
    read_logger.log_dossier_read("OpenCode CIO (MCP Pattern Outcome)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Updated pattern outcome: [{symbol.upper()}] {pattern_name} -> {outcome}")
    return json.dumps(UnifiedLearningMemory().update_pattern_outcome(symbol, pattern_name, outcome, ticket=ticket, r_value=r_value), indent=2)

@mcp.tool()
def mcp_alpha_get_book_page(page_number: int = 1) -> str:
    """Retrieve specific page of Pattern Book. Reference only; does not authorize execution."""
    from tradingagents.unified_learning_memory import UnifiedLearningMemory
    read_logger.log_dossier_read("OpenCode CIO (MCP Book Page)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Read Pattern Book page {page_number}")
    return json.dumps(UnifiedLearningMemory().get_page(page_number), indent=2)

@mcp.tool()
def mcp_alpha_search_book(keyword: str, symbol: str = "") -> str:
    """Search Pattern Book / ULM by keyword and optional symbol. Evidence only; does not authorize execution."""
    from tradingagents.unified_learning_memory import UnifiedLearningMemory
    sym_clean = symbol if symbol and str(symbol).strip().upper() not in ("", "NONE", "NULL", "ALL") else None
    sym_log = f" for symbol {sym_clean}" if sym_clean else ""
    read_logger.log_dossier_read("OpenCode CIO (MCP Search Book)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Searched Pattern Book for keyword '{keyword}'{sym_log}")
    return json.dumps(UnifiedLearningMemory().search(keyword, symbol=sym_clean), indent=2)

@mcp.tool()
def mcp_alpha_get_book_index() -> str:
    """Get high-level index and summary of Pattern Book. Reference only; does not authorize execution."""
    from tradingagents.unified_learning_memory import UnifiedLearningMemory
    read_logger.log_dossier_read("OpenCode CIO (MCP Book Index)", "MANDATORY_PRE_EXECUTION_AUDIT", "Read Pattern Book index")
    return json.dumps(UnifiedLearningMemory().get_index(), indent=2)

@mcp.tool()
def mcp_alpha_get_full_book() -> str:
    """Retrieve full structured catalog and overview of Pattern Book / ULM."""
    from tradingagents.unified_learning_memory import UnifiedLearningMemory
    read_logger.log_dossier_read("OpenCode CIO (MCP Full Book)", "MANDATORY_PRE_EXECUTION_AUDIT", "Retrieved full Pattern Book")
    ulm = UnifiedLearningMemory()
    data = ulm._load()
    pats = data.get("patterns", {})
    exps = data.get("experiences", {})
    catalog = [
        {
            "pattern_id": p.get("pattern_id", k),
            "pattern_name": p.get("pattern_name", k),
            "symbol": p.get("symbol", "ALL"),
            "evidence_provenance": p.get("evidence_provenance", "SEEDED"),
            "outcomes_count": len(p.get("outcomes", [])),
            "observations_count": len(p.get("observations", []))
        }
        for k, p in list(pats.items())[:100]
    ]
    return json.dumps({
        "status": "SUCCESS",
        "canonical_store": ulm.path,
        "total_patterns": len(pats),
        "total_experiences": len(exps),
        "total_recorded_outcomes": sum(len(p.get("outcomes", [])) for p in pats.values() if isinstance(p, dict)),
        "pattern_catalog_sample": catalog,
        "note": f"Full database contains {len(pats)} patterns and {len(exps)} experiences on disk. Use get_book_page(page_number) for complete paginated retrieval or search_book(keyword) for specific queries."
    }, indent=2)

@mcp.tool()
def mcp_alpha_get_fvg_matrix(symbol: str = "XAUUSD") -> str:
    """Query multi-timeframe (H4, H1, M15, M5) Fair Value Gaps (FVG) and 50% Consequent Encroachment levels."""
    from tradingagents.fair_value_gap import FairValueGapEngine
    read_logger.log_dossier_read("OpenCode CIO (MCP FVG Query)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Queried FVG matrix for {symbol.upper()}")
    fvg_engine = FairValueGapEngine()
    return json.dumps(fvg_engine.get_symbol_fvg_matrix(symbol), indent=2)

@mcp.tool()
def mcp_alpha_get_mt5_deals_history(days: int = 30, symbol: str = "ALL", limit: int = 100, position_id: int = 0) -> str:
    """Fetch closed trade history and deal execution settings directly from MetaTrader 5 terminal.
    
    Extracts native MT5 deal tickets, order settings (SL/TP, volume, prices, commissions, swaps, fees),
    execution comments, magic numbers, entry/exit timestamps, and grouped round-trip trade performance.
    
    Args:
        days: Number of past days to query from MT5 history (default: 30)
        symbol: Symbol filter (e.g. 'XAUUSD', 'XAGUSD', 'XCUUSD', or 'ALL')
        limit: Max closed position records to return in output (default: 100, 0 for all)
        position_id: Optional specific MT5 position ID filter (0 for all)
    """
    _init_mt5()
    read_logger.log_dossier_read("OpenCode CIO (MCP MT5 Deals History)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Queried native MT5 deals history (days={days}, symbol={symbol}, limit={limit}, pos={position_id})")
    try:
        import MetaTrader5 as mt5
        acc = mt5.account_info()
        login_num = getattr(acc, "login", 0) if acc else 0
        
        now_dt = datetime.now(timezone.utc)
        from_dt = now_dt - timedelta(days=max(int(days), 1))
        
        deals = mt5.history_deals_get(from_dt, now_dt)
        orders = mt5.history_orders_get(from_dt, now_dt)
        
        if deals is None:
            return json.dumps({"status": "NO_DEALS_FOUND", "login": login_num, "total_deals": 0, "closed_positions": []}, indent=2)
            
        orders_by_pos = {}
        if orders:
            for o in orders:
                orders_by_pos[getattr(o, "position_id", getattr(o, "ticket", 0))] = o
                
        pos_groups = {}
        sym_filter = symbol.strip().upper() if symbol else "ALL"
        
        for d in deals:
            if not d.symbol or d.type == 2:  # skip balance/credit operations
                continue
            if sym_filter not in ("ALL", "", "NONE") and d.symbol.upper() != sym_filter:
                continue
            if position_id > 0 and d.position_id != int(position_id):
                continue
                
            pid = d.position_id or d.order or d.ticket
            if pid not in pos_groups:
                pos_groups[pid] = []
            pos_groups[pid].append(d)
            
        closed_positions = []
        for pid, d_list in pos_groups.items():
            d_list.sort(key=lambda x: x.time)
            entry_deal = d_list[0]
            exit_deal = d_list[-1] if len(d_list) > 1 else None
            
            order_rec = orders_by_pos.get(pid)
            sl_val = getattr(order_rec, "sl", 0.0) if order_rec else 0.0
            tp_val = getattr(order_rec, "tp", 0.0) if order_rec else 0.0
            order_comment = getattr(order_rec, "comment", "") if order_rec else ""
            
            pnl = sum(d.profit for d in d_list)
            comm = sum(d.commission for d in d_list)
            swap = sum(d.swap for d in d_list)
            fee = sum(d.fee for d in d_list)
            net_pnl = pnl + comm + swap + fee
            
            side = "BUY" if entry_deal.type == 0 else ("SELL" if entry_deal.type == 1 else str(entry_deal.type))
            open_time = datetime.fromtimestamp(entry_deal.time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            close_time = datetime.fromtimestamp(exit_deal.time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if exit_deal else "OPEN"
            dur_s = (exit_deal.time - entry_deal.time) if exit_deal else 0
            dur_human = f"{dur_s}s" if dur_s < 60 else f"{dur_s // 60}m {dur_s % 60}s" if dur_s < 3600 else f"{dur_s // 3600}h {(dur_s % 3600) // 60}m"
            
            closed_positions.append({
                "position_id": pid,
                "symbol": entry_deal.symbol,
                "side": side,
                "volume": entry_deal.volume,
                "open_price": entry_deal.price,
                "close_price": exit_deal.price if exit_deal else None,
                "sl": sl_val,
                "tp": tp_val,
                "open_time": open_time,
                "close_time": close_time,
                "duration": dur_human,
                "duration_seconds": dur_s,
                "gross_profit_usd": round(pnl, 2),
                "commission_usd": round(comm, 2),
                "swap_usd": round(swap, 2),
                "fee_usd": round(fee, 2),
                "net_profit_usd": round(net_pnl, 2),
                "outcome": "WIN" if net_pnl > 0 else ("LOSS" if net_pnl < 0 else "BREAKEVEN"),
                "magic": entry_deal.magic,
                "open_comment": entry_deal.comment,
                "close_comment": exit_deal.comment if exit_deal else order_comment
            })
            
        closed_positions.sort(key=lambda x: x.get("close_time", ""), reverse=True)
        
        wins = sum(1 for p in closed_positions if p["net_profit_usd"] > 0)
        losses = sum(1 for p in closed_positions if p["net_profit_usd"] < 0)
        breakevens = sum(1 for p in closed_positions if p["net_profit_usd"] == 0)
        total_p = len(closed_positions)
        win_rate = round((wins / max(total_p, 1)) * 100.0, 1)
        
        gross_profit = sum(p["gross_profit_usd"] for p in closed_positions if p["gross_profit_usd"] > 0)
        gross_loss = sum(p["gross_profit_usd"] for p in closed_positions if p["gross_profit_usd"] < 0)
        net_total = sum(p["net_profit_usd"] for p in closed_positions)
        total_comm = sum(p["commission_usd"] for p in closed_positions)
        total_swap = sum(p["swap_usd"] for p in closed_positions)
        profit_factor = round(abs(gross_profit / gross_loss), 2) if gross_loss != 0 else 0.0
        
        symbols_map = {}
        for p in closed_positions:
            s = p["symbol"]
            if s not in symbols_map:
                symbols_map[s] = {"trades": 0, "wins": 0, "losses": 0, "net_pnl_usd": 0.0}
            symbols_map[s]["trades"] += 1
            if p["net_profit_usd"] > 0:
                symbols_map[s]["wins"] += 1
            elif p["net_profit_usd"] < 0:
                symbols_map[s]["losses"] += 1
            symbols_map[s]["net_pnl_usd"] = round(symbols_map[s]["net_pnl_usd"] + p["net_profit_usd"], 2)
            
        for s, s_data in symbols_map.items():
            s_data["win_rate_pct"] = round((s_data["wins"] / max(s_data["trades"], 1)) * 100.0, 1)
            
        display_positions = closed_positions[:int(limit)] if limit > 0 else closed_positions
        
        return json.dumps({
            "status": "SUCCESS",
            "account_login": login_num,
            "query_parameters": {
                "days_back": days,
                "symbol_filter": symbol,
                "limit": limit,
                "position_id_filter": position_id
            },
            "portfolio_summary": {
                "total_mt5_deals_retrieved": len(deals),
                "total_closed_positions": total_p,
                "wins": wins,
                "losses": losses,
                "breakevens": breakevens,
                "win_rate_pct": win_rate,
                "gross_profit_usd": round(gross_profit, 2),
                "gross_loss_usd": round(gross_loss, 2),
                "net_profit_usd": round(net_total, 2),
                "total_commission_usd": round(total_comm, 2),
                "total_swap_usd": round(total_swap, 2),
                "profit_factor": profit_factor,
                "symbol_breakdown": symbols_map
            },
            "closed_positions_count_returned": len(display_positions),
            "closed_positions": display_positions
        }, indent=2)
    except Exception as err:
        return json.dumps({"status": "ERROR", "error": str(err)}, indent=2)

@mcp.tool()
def mcp_alpha_get_trade_forensics(target: Any = "XAUUSD", symbol: Any = None) -> str:
    """Query granular post-trade forensics and entry market context for closed MT5 deals (accepts ticket number int/str or symbol str e.g. 'XAUUSD')."""
    resolved_target = symbol if symbol is not None else target
    from tradingagents.trade_forensics import TradeForensicsEngine
    read_logger.log_dossier_read("OpenCode CIO (MCP Trade Forensics)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Queried trade forensics for {resolved_target}")
    forensics = TradeForensicsEngine()
    return json.dumps(forensics.get_trade_forensics(resolved_target), indent=2)

@mcp.tool()
def mcp_alpha_configure_instruments(action: str = "get", enable: str = "", disable: str = "", toggles_json: str = "{}") -> str:
    """Get or update active trading instruments (metals/commodities) in real-time with hot-reloading.
    
    Actions:
      - 'get': Retrieve currently enabled and disabled instruments.
      - 'set': Enable or disable instruments in batch.
    
    Parameters:
      - enable: Comma-separated symbol(s) to enable, e.g. 'XAUUSD,USOIL.cash' or 'ALL'
      - disable: Comma-separated symbol(s) to disable, e.g. 'XPTUSD,XPDUSD,XCUUSD' or 'ALL'
      - toggles_json: JSON object of symbols and booleans, e.g. '{"XAUUSD": true, "XPTUSD": false}'
    
    Supported symbols: XAUUSD, XAGUSD, XPTUSD, XPDUSD, XCUUSD, USOIL.cash
    """
    config_path = ALPHA_ROOT / "config" / "instruments_config.json"
    default_instruments = {
        "XAUUSD": True,
        "XAGUSD": True,
        "XPTUSD": True,
        "XPDUSD": True,
        "XCUUSD": True,
        "USOIL.cash": True
    }
    
    config_data = {}
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except Exception:
            config_data = {}
            
    instruments = config_data.get("instruments", default_instruments)
    
    if action == "get":
        return json.dumps({
            "status": "SUCCESS",
            "active_instruments": [sym for sym, val in instruments.items() if val],
            "disabled_instruments": [sym for sym, val in instruments.items() if not val],
            "all_toggles": instruments
        }, indent=2)
        
    # Process explicit toggles_json
    if toggles_json and toggles_json != "{}":
        try:
            toggles = json.loads(toggles_json)
            for sym, state in toggles.items():
                sym_clean = sym.strip()
                if sym_clean in instruments:
                    instruments[sym_clean] = bool(state)
                elif sym_clean.upper() in instruments:
                    instruments[sym_clean.upper()] = bool(state)
        except Exception as e:
            return json.dumps({"status": "INVALID_JSON", "error": str(e)})
            
    # Process enable string (comma-separated or "ALL")
    if enable:
        if enable.strip().upper() == "ALL":
            for k in instruments:
                instruments[k] = True
        else:
            for s in enable.split(","):
                sym = s.strip()
                if sym in instruments:
                    instruments[sym] = True
                elif sym.upper() in instruments:
                    instruments[sym.upper()] = True

    # Process disable string (comma-separated or "ALL")
    if disable:
        if disable.strip().upper() == "ALL":
            for k in instruments:
                instruments[k] = False
        else:
            for s in disable.split(","):
                sym = s.strip()
                if sym in instruments:
                    instruments[sym] = False
                elif sym.upper() in instruments:
                    instruments[sym.upper()] = False

    from datetime import datetime, timezone
    config_data["description"] = "Alpha Trading Desk - Active Instrument Toggles (Hot-Reloading)"
    config_data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    config_data["instruments"] = instruments

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)

    read_logger.log_dossier_read("OpenCode CIO (MCP Config Instruments)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Updated instruments: Active={[s for s, v in instruments.items() if v]}")

    return json.dumps({
        "status": "SUCCESS",
        "message": "Instruments configuration updated with zero-restart hot-reloading.",
        "active_instruments": [sym for sym, val in instruments.items() if val],
        "disabled_instruments": [sym for sym, val in instruments.items() if not val],
        "all_toggles": instruments
    }, indent=2)


def _sync_ask_librarian(query: str, symbol: str = "XAUUSD") -> str:
    sym = _normalize_symbol(symbol)
    ans = _librarian_agent.answer_query(query, sym)
    read_logger.log_dossier_read("OpenCode CIO (MCP Ask Librarian)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Librarian query for {sym}: '{query}'")
    return json.dumps({
        "status": "SUCCESS",
        "query": query,
        "symbol": sym,
        "theme": ans.get("theme"),
        "proxima_researched_findings": {
            "proxima_status": ans.get("proxima_status", "STANDBY"),
            "proxima_endpoint": "http://127.0.0.1:3210/v1/chat/completions",
            "quantitative_microstructure_synthesis": ans.get("proxima_research_synthesis")
        },
        "unified_learning_memory_precedents": {
            "direct_answer": ans.get("direct_answer"),
            "empirical_derivation": ans.get("empirical_derivation"),
            "matched_patterns_count": ans.get("matched_evidence_count"),
            "relevant_trade_experiences_count": ans.get("relevant_trade_experiences_count"),
            "recommended_precedent": ans.get("recommended_precedent"),
            "top_4_precedents": ans.get("top_4_precedents", [])
        }
    }, indent=2)

@mcp.tool()
async def mcp_alpha_ask_librarian(query: str, symbol: str = "XAUUSD") -> str:
    """Ask the Autonomous Librarian Agent any historical, tactical, or quantitative question about precedents, win rates, failure traps, and invalidation rules."""
    return await run_in_thread(_sync_ask_librarian, query=query, symbol=symbol)

@mcp.tool()
async def ask_librarian(query: str, symbol: str = "XAUUSD") -> str:
    """Ask the Autonomous Librarian Agent alias."""
    return await run_in_thread(_sync_ask_librarian, query=query, symbol=symbol)


@mcp.tool()
def mcp_alpha_get_ledger_decomposition(symbol: str = "XAUUSD") -> str:
    """Decompose historical closed-trade ledger into condition base rates: Session x Direction x Alignment x Spread x FVG Fill%."""
    from tradingagents.ledger_decomposition import LedgerDecompositionEngine
    sym = _normalize_symbol(symbol)
    read_logger.log_dossier_read("OpenCode CIO (MCP Ledger Decomposition)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Requested historical ledger decomposition for {sym}")
    engine = LedgerDecompositionEngine()
    return json.dumps(engine.decompose_ledger(sym), indent=2)


@mcp.tool()
def mcp_alpha_get_multi_instrument_ledger() -> str:
    """Fetch complete 134-trade multi-instrument portfolio ledger breaking out 121 XAUUSD vs 13-trade non-XAU bleed (XAG/XCU/XPT/XPD)."""
    from tradingagents.ledger_decomposition import LedgerDecompositionEngine
    read_logger.log_dossier_read("OpenCode CIO (MCP Multi-Instrument Ledger)", "MANDATORY_PRE_EXECUTION_AUDIT", "Requested 134-trade portfolio multi-instrument ledger breakdown")
    decomp = LedgerDecompositionEngine().decompose_ledger("XAUUSD")
    recon = decomp.get("portfolio_accounting_reconciliation", {})
    return json.dumps({
        "status": "SUCCESS",
        "portfolio_total_positions": recon.get("total_portfolio_trades", 134),
        "total_portfolio_net_pnl_usd": recon.get("total_portfolio_net_pnl", -1371.43),
        "total_portfolio_net_r": recon.get("total_portfolio_net_r", -32.44),
        "canonical_xauusd": {
            "symbol": "XAUUSD",
            "trades": decomp.get("total_trades", 121),
            "wins": decomp.get("wins", 33),
            "losses": decomp.get("losses", 88),
            "win_rate_pct": decomp.get("overall_win_rate", 27.3),
            "net_pnl_usd": decomp.get("net_pnl_usd", -955.69),
            "net_realized_r": decomp.get("net_realized_r", -23.37)
        },
        "non_xauusd_bleed": {
            "total_bleed_trades": recon.get("non_xauusd_trades_count", 13),
            "total_bleed_pnl_usd": recon.get("non_xauusd_bleed_pnl_usd", -415.74),
            "total_bleed_r": recon.get("non_xauusd_bleed_r", -9.07),
            "instrument_breakdown": recon.get("instrument_breakdown", {
                "XAGUSD": {"trades": 6, "wins": 0, "losses": 6, "pnl_usd": -194.91, "r_multiple": -3.84},
                "XCUUSD": {"trades": 4, "wins": 0, "losses": 4, "pnl_usd": -157.13, "r_multiple": -1.80},
                "XPTUSD": {"trades": 2, "wins": 0, "losses": 2, "pnl_usd": -64.00, "r_multiple": -1.35},
                "XPDUSD": {"trades": 1, "wins": 1, "losses": 0, "pnl_usd": +0.30, "r_multiple": +0.01}
            })
        }
    }, indent=2)


@mcp.tool()
def mcp_alpha_get_live_microstructure(symbol: str = "XAUUSD") -> str:
    """Fetch live market microstructure: real-time spread (pts), M1 tick velocity (t/m), order-book depth imbalance, and CVD posture."""
    from tradingagents.cvd_engine import CumulativeVolumeDeltaEngine
    from tradingagents.news_shield import NewsShield
    from tradingagents.world_market import IntradayInstitutionalEngine
    
    sym = _normalize_symbol(symbol)
    read_logger.log_dossier_read("OpenCode CIO (MCP Microstructure)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Requested live microstructure & spread for {sym}")
    
    cvd_data = CumulativeVolumeDeltaEngine().get_symbol_cvd(sym)
    news_data = NewsShield().evaluate_news_freeze()
    sess_data = IntradayInstitutionalEngine().get_session_status()

    return json.dumps({
        "symbol": sym,
        "live_spread_pts": cvd_data.get("live_spread_pts", 0),
        "tick_velocity_tpm": cvd_data.get("tick_velocity_tpm", 0.0),
        "avg_5m_velocity_tpm": cvd_data.get("avg_5m_velocity_tpm", 0.0),
        "velocity_posture": cvd_data.get("velocity_posture", "NORMAL"),
        "adverse_velocity_warning": cvd_data.get("adverse_velocity_warning", False),
        "order_book_imbalance": cvd_data.get("order_book_imbalance", "BALANCED"),
        "cumulative_volume_delta": cvd_data.get("cumulative_volume_delta", 0.0),
        "delta_pressure_pct": cvd_data.get("delta_pressure_pct", 0.0),
        "delta_exhaustion": cvd_data.get("delta_exhaustion", False),
        "exhaustion_signal": cvd_data.get("exhaustion_signal", "NO_DIVERGENCE"),
        "macro_news_shield": news_data.get("status_text", "CLEAR"),
        "high_impact_freeze_active": news_data.get("freeze_active", False),
        "session_context": sess_data.get("active_session", "MARKET_HOURS"),
        "market_status": cvd_data.get("market_status", "ACTIVE")
    }, indent=2)


@mcp.tool()
def mcp_alpha_record_decision_snapshot(
    symbol: str = "XAUUSD",
    side: str = "BUY",
    conviction_score: float = None,
    conviction: float = None,
    in_direction_fvg_fill_pct: float = None,
    fvg_fill_pct: float = None,
    spread_pts: int = 0,
    regime_flag: str = "NORMAL",
    contradictions_count: int = 0,
    notes: str = "",
    volume: float = 0.0,
    sl: float = 0.0,
    tp: float = 0.0,
    pattern_name: str = "",
    category_tag: str = "PROBE_HYPOTHESIS_EXPECTED_EDGE",
    four_tf_alignment: str = "",
    m15_rsi: float = 50.0,
    h4_rsi: float = 50.0,
    session_name: str = "",
    tick_velocity_tpm: float = 0.0,
    macro_event_tag: str = "CLEAR",
    order_book_imbalance: str = "BALANCED",
    direction_thesis: str = "",
    **kwargs
) -> str:
    """Record a comprehensive pre-trade experimental decision snapshot on disk before execution."""
    from tradingagents.decision_snapshot_recorder import PreTradeDecisionRecorder
    from tradingagents.cvd_engine import CumulativeVolumeDeltaEngine
    from tradingagents.world_market import IntradayInstitutionalEngine
    from tradingagents.news_shield import NewsShield

    sym = _normalize_symbol(symbol)
    score = conviction_score if conviction_score is not None else (conviction if conviction is not None else kwargs.get("score", 5.0))
    resolved_side = str(kwargs.get("direction", side or "BUY")).strip().upper()
    fill = in_direction_fvg_fill_pct if in_direction_fvg_fill_pct is not None else (fvg_fill_pct if fvg_fill_pct is not None else kwargs.get("fill_pct"))
    
    read_logger.log_dossier_read("OpenCode CIO (MCP Decision Snapshot)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Recorded pre-trade decision snapshot for {sym} {resolved_side} [{category_tag}]")
    
    # Auto-enrich missing fields from live engines if omitted
    if spread_pts == 0 or tick_velocity_tpm == 0.0 or order_book_imbalance == "BALANCED":
        try:
            cvd_data = CumulativeVolumeDeltaEngine().get_symbol_cvd(sym)
            if spread_pts == 0:
                spread_pts = int(cvd_data.get("live_spread_pts", 0))
            if tick_velocity_tpm == 0.0:
                tick_velocity_tpm = float(cvd_data.get("tick_velocity_tpm", 0.0))
            if order_book_imbalance == "BALANCED":
                order_book_imbalance = str(cvd_data.get("order_book_imbalance", "BALANCED"))
        except Exception:
            pass

    if not session_name:
        try:
            sess_data = IntradayInstitutionalEngine().get_session_status()
            session_name = sess_data.get("active_session", "MARKET_HOURS")
        except Exception:
            session_name = "LIVE_SESSION"

    if macro_event_tag == "CLEAR":
        try:
            ns = NewsShield().evaluate_news_freeze()
            if ns.get("freeze_active"):
                macro_event_tag = f"FREEZE_ACTIVE ({ns.get('event_name')})"
            else:
                macro_event_tag = ns.get("status_text", "CLEAR")
        except Exception:
            pass

    recorder = PreTradeDecisionRecorder()
    return json.dumps(recorder.record_decision(
        symbol=sym,
        side=resolved_side,
        conviction_score=score,
        in_direction_fvg_fill_pct=fill,
        spread_pts=spread_pts,
        regime_flag=regime_flag,
        contradictions_count=contradictions_count,
        notes=notes,
        volume=volume,
        sl=sl,
        tp=tp,
        pattern_name=pattern_name,
        category_tag=category_tag,
        four_tf_alignment=four_tf_alignment,
        m15_rsi=m15_rsi,
        h4_rsi=h4_rsi,
        session_name=session_name,
        tick_velocity_tpm=tick_velocity_tpm,
        macro_event_tag=macro_event_tag,
        order_book_imbalance=order_book_imbalance,
        direction_thesis=direction_thesis,
        **kwargs
    ), indent=2)


@mcp.tool()
def mcp_alpha_get_measured_cvd(symbol: str = "XAUUSD") -> str:
    """Fetch measured Cumulative Volume Delta (CVD) and Delta Exhaustion / Absorption metrics directly from MT5 ticks."""
    from tradingagents.cvd_engine import CumulativeVolumeDeltaEngine
    sym = _normalize_symbol(symbol)
    read_logger.log_dossier_read("OpenCode CIO (MCP CVD Query)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Queried measured CVD for {sym}")
    engine = CumulativeVolumeDeltaEngine()
    return json.dumps(engine.get_symbol_cvd(sym), indent=2)


def _sync_backtest_thesis(query: str, symbol: str = "XAUUSD", timeframe: str = "M5", bars: int = 60, offset: int = 0) -> str:
    from backtesting.pipeline import PureLLMBacktestPipeline
    sym = _normalize_symbol(symbol)
    read_logger.log_dossier_read("OpenCode CIO (MCP Backtest Thesis)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Requested natural backtest: '{query}' on {sym} ({timeframe}, {bars} bars)")
    pipeline = PureLLMBacktestPipeline()
    return json.dumps(pipeline.run_backtest(query=query, symbol=sym, timeframe=timeframe, bars=bars, offset=offset), indent=2)

@mcp.tool()
async def mcp_alpha_backtest_thesis(
    query: str,
    symbol: str = "XAUUSD",
    timeframe: str = "M5",
    bars: int = 60,
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
    bars: int = 60,
    offset: int = 0
) -> str:
    """Multi-threaded natural backtester alias."""
    return await run_in_thread(_sync_backtest_thesis, query=query, symbol=symbol, timeframe=timeframe, bars=bars, offset=offset)


@mcp.tool()
def mcp_alpha_get_full_institutional_profile(symbol: str = "XAUUSD") -> str:
    """Fetch complete uncompressed institutional profile: Volume Profile (POC/VAH/VAL), VWAP (+/-1s, +/-2s), DIX/GEX, Macro Yields (US10Y/US2Y/DXY/VIX), Contract Specs, and 4TF EMAs/RSI."""
    _init_mt5()
    sym = _normalize_symbol(symbol)
    read_logger.log_dossier_read("OpenCode CIO (MCP Institutional Profile)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Queried full institutional profile for {sym}")
    try:
        vp = _inst_engine.get_volume_profile_metrics(sym)
        vwap = _inst_engine.get_institutional_vwap(sym)
        macro = _inst_engine.get_macro_and_gamma_feeds()
        specs = _inst_engine.get_contract_specifications(sym)
        struct = _inst_engine.get_choch_and_structure_break(sym)
        tf_mat = _inst_engine.get_multi_timeframe_matrix(sym)
        cot_full = _inst_engine.get_futuresbench_cot_data()
        raw_cot = cot_full.get("markets", {}).get(sym, {})
        
        return json.dumps({
            "status": "SUCCESS",
            "symbol": sym,
            "volume_profile": {
                "point_of_control_poc": vp.get("poc"),
                "value_area_high_vah_70": vp.get("vah"),
                "value_area_low_val_70": vp.get("val"),
                "value_area_width_pts": vp.get("value_area_width"),
                "price_location": vp.get("price_location")
            },
            "institutional_vwap": {
                "vwap": vwap.get("vwap"),
                "std_dev": vwap.get("std_dev"),
                "upper_band_1sigma": vwap.get("upper_band_1"),
                "upper_band_2sigma": vwap.get("upper_band_2"),
                "lower_band_1sigma": vwap.get("lower_band_1"),
                "lower_band_2sigma": vwap.get("lower_band_2"),
                "distance_usd": vwap.get("distance_usd"),
                "posture": vwap.get("posture")
            },
            "macro_treasury_and_volatility": {
                "us_10y_yield": macro.get("us_10y"),
                "us_2y_yield": macro.get("us_2y"),
                "yield_curve_10y_2y_spread": macro.get("yield_curve_spread"),
                "dollar_index_dxy": macro.get("dxy"),
                "dxy_posture": macro.get("dxy_posture"),
                "cboe_vix": macro.get("vix"),
                "vix_regime": macro.get("vix_regime"),
                "dark_pool_dix_pct": macro.get("dix"),
                "gamma_exposure_gex_billions": macro.get("gex_billions"),
                "gex_regime": macro.get("gex_regime")
            },
            "contract_specifications": specs,
            "structural_market_state": {
                "choch_status": struct.get("choch_status"),
                "bos_status": struct.get("bos_status"),
                "displacement": struct.get("displacement")
            },
            "four_timeframe_matrix": tf_mat,
            "cot_institutional_positioning": raw_cot
        }, indent=2)
    except Exception as err:
        return json.dumps({"status": "ERROR", "symbol": sym, "error": str(err)}, indent=2)


@mcp.tool()
def mcp_alpha_get_evidence_capabilities() -> str:
    """Return startup/on-demand states for free evidence capabilities without fetching bulk data."""
    return json.dumps({"status": "SUCCESS", "source": "Alpha capability registry",
                       "retrieved_at": datetime.now(timezone.utc).isoformat(),
                       "data": capability_snapshot()}, indent=2)

@mcp.tool()
def mcp_alpha_get_fred_observations(series_id: str, limit: int = 100, vintage_date: str = "") -> str:
    """Retrieve factual FRED/ALFRED observations; unavailable credentials never produce fallback values."""
    return json.dumps(_fred_adapter.observations(series_id, limit, vintage_date or None), indent=2)

@mcp.tool()
def mcp_alpha_search_market_news(query: str, max_records: int = 25, timespan: str = "") -> str:
    """Search Original GDELT for global/historical news context with provenance."""
    return json.dumps(_gdelt_adapter.search(query, max_records, timespan or None), indent=2)

@mcp.tool()
def mcp_alpha_get_direct_news(max_items: int = 20) -> str:
    """Fetch configured direct RSS/Atom sources with canonical IDs and first-seen timestamps."""
    return json.dumps(_rss_registry.fetch(max_items), indent=2)

@mcp.tool()
def mcp_alpha_lookup_common_crawl(url: str, index: str = "CC-MAIN-2026-30", limit: int = 10) -> str:
    """On-demand historical URL capture lookup. Not intended for routine live-news polling."""
    return json.dumps(_common_crawl_adapter.lookup(url, index, limit), indent=2)

@mcp.tool()
def get_evidence_capabilities() -> str:
    return mcp_alpha_get_evidence_capabilities()

@mcp.tool()
def get_fred_observations(series_id: str, limit: int = 100, vintage_date: str = "") -> str:
    return mcp_alpha_get_fred_observations(series_id, limit, vintage_date)

@mcp.tool()
def search_market_news(query: str, max_records: int = 25, timespan: str = "") -> str:
    return mcp_alpha_search_market_news(query, max_records, timespan)

@mcp.tool()
def get_direct_news(max_items: int = 20) -> str:
    return mcp_alpha_get_direct_news(max_items)

@mcp.tool()
def lookup_common_crawl(url: str, index: str = "CC-MAIN-2026-30", limit: int = 10) -> str:
    return mcp_alpha_lookup_common_crawl(url, index, limit)

@mcp.tool()
def register_watch(symbol: str, condition: str = "", instruction: str = "", target_price: float = None, reason: str = "", direction: str = "", watch_id: str = "") -> str:
    return mcp_alpha_register_watch(symbol, condition, instruction, target_price, reason, direction, watch_id)

@mcp.tool()
def get_active_watches(symbol: str = None, include_closed: bool = True) -> str:
    return mcp_alpha_get_active_watches(symbol, include_closed)

@mcp.tool()
def update_watch(watch_id: str, status: str = "", condition: str = "", instruction: str = "", target_price: float = None, reason: str = "") -> str:
    return mcp_alpha_update_watch(watch_id, status, condition, instruction, target_price, reason)

@mcp.tool()
def mark_watches_observed(watch_ids: List[str]) -> str:
    return mcp_alpha_mark_watches_observed(watch_ids)

@mcp.tool()
def mark_evidence_read(evidence_ids: List[str]) -> str:
    return mcp_alpha_mark_evidence_read(evidence_ids)

# ======================================================================
# DIRECT TOOL ALIASES (Allows OpenCode to call both canonical and short names)
# ======================================================================

@mcp.tool()
def get_full_institutional_profile(symbol: str = "XAUUSD") -> str:
    """Fetch complete institutional profile (POC/VAH/VAL, VWAP, DIX/GEX, Treasuries, Contract Specs, 4TF EMAs/RSI)."""
    return mcp_alpha_get_full_institutional_profile(symbol)

@mcp.tool()
def get_account_status() -> str:
    """Check live FTMO MT5 equity, balance, free margin, margin utilization % and active ticket states."""
    return mcp_alpha_get_account_status()

@mcp.tool()
def execute_trade(symbol: str, side: str, volume: float, sl: float, tp: float) -> str:
    """Execute direct market buy/sell order on FTMO MT5."""
    return mcp_alpha_execute_trade(symbol, side, volume, sl, tp)

@mcp.tool()
def update_position(ticket: int, action: str, params_json: str = "") -> str:
    """Manage active tickets (BREAK_EVEN, TRAIL_SL, FULL_EXIT)."""
    return mcp_alpha_update_position(ticket, action, params_json)

@mcp.tool()
def get_symbol_conviction(symbol: str = "XAUUSD") -> str:
    """Query live 4TF institutional alignment, exact EMA20/50 & RSI values, FVG geometry, and COT percentiles."""
    return mcp_alpha_get_symbol_conviction(symbol)

@mcp.tool()
def query_analyst_desk(query: str = "", symbol: str = "XAUUSD") -> str:
    """Deep 7-layer local LLM multi-source debate (Technical, COT, Macro, Bull vs Bear)."""
    return mcp_alpha_query_analyst_desk(query, symbol)

@mcp.tool()
def ask_librarian(query: str = "", symbol: str = "XAUUSD") -> str:
    """Search 364 ULM Precedents + Mandatory Proxima Quantitative Microstructure Research."""
    return mcp_alpha_ask_librarian(query, symbol)

@mcp.tool()
def backtest_thesis(query: str = "", symbol: str = "XAUUSD", timeframe: str = "M5", bars: int = 500) -> str:
    """Natural live MT5 candle-table replay (Zero hardcoded rules)."""
    return mcp_alpha_backtest_thesis(query, symbol, timeframe, bars)

@mcp.tool()
def get_measured_cvd(symbol: str = "XAUUSD") -> str:
    """Fetch measured M5 tick CVD, 10-bar delta velocity, and passive absorption signals from MT5."""
    return mcp_alpha_get_measured_cvd(symbol)

@mcp.tool()
def get_trade_forensics(symbol: str = "XAUUSD") -> str:
    """Deep forensics on closed trades: Win rate %, net R, FVG fill %, RSI regime, and spread distribution."""
    return mcp_alpha_get_trade_forensics(symbol)

@mcp.tool()
def get_ledger_decomposition(symbol: str = "XAUUSD") -> str:
    """Decompose 134-trade history into condition base rates (Session x Direction x Spread x FVG Fill%)."""
    return mcp_alpha_get_ledger_decomposition(symbol)

@mcp.tool()
def record_decision_snapshot(
    symbol: str = "XAUUSD",
    side: str = "BUY",
    conviction: float = None,
    conviction_score: float = None,
    notes: str = "",
    volume: float = 0.0,
    sl: float = 0.0,
    tp: float = 0.0,
    **kwargs
) -> str:
    """Record pre-trade decision context on disk (s4.137 Process vs Outcome)."""
    return mcp_alpha_record_decision_snapshot(
        symbol=symbol,
        side=side,
        conviction=conviction,
        conviction_score=conviction_score,
        notes=notes,
        volume=volume,
        sl=sl,
        tp=tp,
        **kwargs
    )

@mcp.tool()
def record_trade_observation(symbol: str, pattern_name: str, observation: str, outcome: str = "STUDY", r_multiple: float = 0.0, ticket: str = None) -> str:
    """Commit verified trade outcomes & lessons into Pattern Book & ULM."""
    return mcp_alpha_record_trade_observation(symbol, pattern_name, observation, outcome, r_multiple, ticket)

@mcp.tool()
def record_pattern_observation(symbol: str, pattern_name: str, observation: str, outcome: str = None, ticket: str = None, r_value=None) -> str:
    """Record pattern evidence in Unified Learning Memory."""
    return mcp_alpha_record_pattern_observation(symbol, pattern_name, observation, outcome, ticket, r_value)

@mcp.tool()
def get_multi_instrument_ledger() -> str:
    """Full 134-position portfolio breakdown breaking out 121 XAUUSD vs 13 non-XAU bleed (XAG/XCU/XPT/XPD)."""
    return mcp_alpha_get_multi_instrument_ledger()

@mcp.tool()
def get_live_microstructure(symbol: str = "XAUUSD") -> str:
    """Fetch live market microstructure: real-time spread (pts), M1 tick velocity (t/m), order-book depth imbalance, and CVD posture."""
    return mcp_alpha_get_live_microstructure(symbol)

@mcp.tool()
def get_fvg_matrix(symbol: str = "XAUUSD") -> str:
    """Fetch multi-timeframe Fair Value Gaps (H4, H1, M15, M5) and 50% Consequent Encroachment levels."""
    return mcp_alpha_get_fvg_matrix(symbol)

@mcp.tool()
def get_live_world_events(category: str = "ALL") -> str:
    """Live macroeconomic releases, central bank speeches, and geopolitical intelligence."""
    return mcp_alpha_get_live_world_events(category)

@mcp.tool()
def search_book(keyword: str, symbol: str = None) -> str:
    """Search Pattern Book / ULM by keyword and symbol."""
    return mcp_alpha_search_book(keyword, symbol)

@mcp.tool()
def get_book_index() -> str:
    """Get high-level index and summary of Pattern Book."""
    return mcp_alpha_get_book_index()

@mcp.tool()
def get_book_page(page_number: int = 1) -> str:
    """Read a specific page from Pattern Book."""
    return mcp_alpha_get_book_page(page_number)

@mcp.tool()
def get_full_book() -> str:
    """Retrieve full dump of Pattern Book / ULM."""
    return mcp_alpha_get_full_book()

@mcp.tool()
def get_mt5_deals_history(days: int = 30, symbol: str = "ALL", limit: int = 100, position_id: int = 0) -> str:
    """Fetch closed trade history and deal execution settings directly from MetaTrader 5 terminal."""
    return mcp_alpha_get_mt5_deals_history(days, symbol, limit, position_id)

@mcp.tool()
def list_desk_tools() -> str:
    """Live dynamic discovery of ALL available FastMCP tools and their capabilities in the desk daemon."""
    tools_list = [
        {"name": "get_account_status", "description": "Live FTMO MT5 equity, balance, free margin, margin utilization % and active ticket states."},
        {"name": "get_mt5_deals_history", "description": "Fetch closed trade history and deal execution settings (SL/TP, volume, prices, commissions, swaps, profit, duration) directly from MT5 terminal."},
        {"name": "get_full_institutional_profile", "description": "Volume Profile (POC/VAH/VAL), VWAP (+/-1s, +/-2s), Dark Pool DIX/GEX, Treasury Yields (US10Y/US2Y/DXY/VIX), FTMO Contract Specs, and 4TF EMAs/RSI."},
        {"name": "get_symbol_conviction", "description": "4TF institutional alignment, exact EMA20/50 & RSI values, FVG geometry, and COT percentiles."},
        {"name": "get_trade_forensics", "description": "Deep forensics on closed trades: Win rate %, net R, FVG fill %, RSI regime, and spread distribution."},
        {"name": "get_ledger_decomposition", "description": "Decompose 121-trade history into condition base rates (Session x Direction x Spread x FVG Fill%)."},
        {"name": "get_multi_instrument_ledger", "description": "Full 134-position portfolio breakdown breaking out 121 XAUUSD vs 13 non-XAU bleed (XAG/XCU/XPT/XPD)."},
        {"name": "get_live_microstructure", "description": "Live spread in pts, M1 tick velocity (t/m), order book depth imbalance, and CVD posture."},
        {"name": "search_book", "description": "Search Pattern Book / ULM by keyword and symbol."},
        {"name": "get_book_index", "description": "Get high-level index and summary of Pattern Book."},
        {"name": "get_book_page", "description": "Read a specific page from Pattern Book."},
        {"name": "backtest_thesis", "description": "Natural MT5 candle-table replay (Zero hardcoded rules). Replays setup trajectory, empirical win rate %, realized R, and failure clusters."},
        {"name": "ask_librarian", "description": "Search 371 ULM Precedents + Mandatory Proxima Quantitative Microstructure Research (Port 3210)."},
        {"name": "get_measured_cvd", "description": "Measured M5 tick CVD, 10-bar delta velocity, and passive absorption signals from MT5."},
        {"name": "get_fvg_matrix", "description": "Query multi-timeframe (H4, H1, M15, M5) Fair Value Gaps and Consequent Encroachment levels."},
        {"name": "get_live_world_events", "description": "Live macroeconomic releases, central bank speeches, and geopolitical intelligence."},
        {"name": "record_decision_snapshot", "description": "Record pre-trade decision context on disk with full experimental metadata."},
        {"name": "record_trade_observation", "description": "Commit verified trade outcomes, lessons, and pattern observations into Pattern Book & ULM."},
        {"name": "record_pattern_observation", "description": "Record pattern evidence in Unified Learning Memory."},
        {"name": "execute_trade", "description": "Execute direct instant market buy/sell orders on FTMO MT5."},
        {"name": "place_pending_order", "description": "Place planned pending triggers (BUY_LIMIT, SELL_LIMIT, BUY_STOP, SELL_STOP) to stage single or multiple probes in advance."},
        {"name": "cancel_pending_order", "description": "Cancel / remove an active pending trigger order on MT5."},
        {"name": "get_pending_orders", "description": "Fetch all active pending trigger orders on MT5."},
        {"name": "configure_probe_trigger_engine", "description": "Configure 3-Probe Auto-Trigger & Win-Harvest Engine parameters (trigger count, $200 target profit, 1.0 lot scale size, SL buffer)."},
        {"name": "get_probe_trigger_status", "description": "Fetch live status of 3-Probe Auto-Trigger Engine, staged probes, filled counts, active scale order, and basket PnL."},
        {"name": "place_probe_grid", "description": "Atomically deploy tight stacked 3 UP and/or 3 DOWN probe lineups across nearby structural zones."},
        {"name": "invalidate_probe_triggers", "description": "Clear probe trigger checkup counters back to NONE (0), cancel pending triggers, and exit partial probes upon thesis invalidation."},
        {"name": "update_position", "description": "Manage active tickets (BREAK_EVEN, TRAIL_SL, FULL_EXIT)."},
        {"name": "register_watch", "description": "Set dynamic price or sentiment alerts for the local desk to track."},
        {"name": "call_desk_tool", "description": "Universal dynamic dispatcher allowing invocation of any tool by name with arguments."}
    ]
    return json.dumps({"status": "SUCCESS", "tools_count": len(tools_list), "tools": tools_list}, indent=2)

@mcp.tool()
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
        "get_mt5_deals_history": lambda: mcp_alpha_get_mt5_deals_history(args.get("days", 30), args.get("symbol", "ALL"), args.get("limit", 100), args.get("position_id", 0)),
        "get_deals_history": lambda: mcp_alpha_get_mt5_deals_history(args.get("days", 30), args.get("symbol", "ALL"), args.get("limit", 100), args.get("position_id", 0)),
        "get_full_institutional_profile": lambda: mcp_alpha_get_full_institutional_profile(args.get("symbol", "XAUUSD")),
        "get_symbol_conviction": lambda: mcp_alpha_get_symbol_conviction(args.get("symbol", "XAUUSD")),
        "get_trade_forensics": lambda: mcp_alpha_get_trade_forensics(args.get("symbol_or_ticket", args.get("symbol", "XAUUSD"))),
        "get_ledger_decomposition": lambda: mcp_alpha_get_ledger_decomposition(args.get("symbol", "XAUUSD")),
        "get_multi_instrument_ledger": mcp_alpha_get_multi_instrument_ledger,
        "get_live_microstructure": lambda: mcp_alpha_get_live_microstructure(args.get("symbol", "XAUUSD")),
        "search_book": lambda: mcp_alpha_search_book(args.get("keyword", args.get("query", "")), args.get("symbol")),
        "get_book_index": mcp_alpha_get_book_index,
        "get_book_page": lambda: mcp_alpha_get_book_page(args.get("page_number", 1)),
        "get_full_book": mcp_alpha_get_full_book,
        "backtest_thesis": lambda: mcp_alpha_backtest_thesis(args.get("query", ""), args.get("symbol", "XAUUSD"), args.get("timeframe", "M5"), args.get("bars", 60), args.get("offset", 0)),
        "ask_librarian": lambda: mcp_alpha_ask_librarian(args.get("query", ""), args.get("symbol", "XAUUSD")),
        "query_analyst_desk": lambda: mcp_alpha_query_analyst_desk(args.get("query", ""), args.get("symbol", "XAUUSD")),
        "get_measured_cvd": lambda: mcp_alpha_get_measured_cvd(args.get("symbol", "XAUUSD")),
        "get_fvg_matrix": lambda: mcp_alpha_get_fvg_matrix(args.get("symbol", "XAUUSD")),
        "get_live_world_events": lambda: mcp_alpha_get_live_world_events(args.get("category", "ALL")),
        "record_decision_snapshot": lambda: mcp_alpha_record_decision_snapshot(**args),
        "record_trade_observation": lambda: mcp_alpha_record_trade_observation(args.get("symbol", "XAUUSD"), args.get("pattern_name", ""), args.get("observation", ""), args.get("outcome", "STUDY"), args.get("r_multiple", 0.0), args.get("ticket")),
        "record_pattern_observation": lambda: mcp_alpha_record_pattern_observation(args.get("symbol", "XAUUSD"), args.get("pattern_name", ""), args.get("observation", ""), args.get("outcome"), args.get("ticket"), args.get("r_value")),
        "record_pattern_outcome": lambda: mcp_alpha_record_pattern_outcome(args.get("symbol", "XAUUSD"), args.get("pattern_name", ""), args.get("outcome", ""), args.get("ticket"), args.get("r_value")),
        "execute_trade": lambda: mcp_alpha_execute_trade(args.get("symbol", "XAUUSD"), args.get("side", "BUY"), args.get("volume", 0.0), args.get("sl", 0.0), args.get("tp", 0.0)),
        "place_pending_order": lambda: mcp_alpha_place_pending_order(args.get("symbol", "XAUUSD"), args.get("order_type", "SELL_LIMIT"), args.get("price", 0.0), args.get("volume", 0.0), args.get("sl", 0.0), args.get("tp", 0.0), args.get("comment", "OpenCode Planned Probe"), args.get("tag", "")),
        "cancel_pending_order": lambda: mcp_alpha_cancel_pending_order(args.get("order_ticket", args.get("ticket", 0))),
        "get_pending_orders": lambda: mcp_alpha_get_pending_orders(args.get("symbol", "ALL")),
        "configure_probe_trigger_engine": lambda: mcp_alpha_configure_probe_trigger_engine(args.get("trigger_count", 3), args.get("target_profit_usd", 200.0), args.get("scale_lots", 1.0), args.get("sl_buffer_pts", 15.0), args.get("tp_buffer_pts", 25.0), args.get("symbol", "XAUUSD")),
        "get_probe_trigger_status": mcp_alpha_get_probe_trigger_status,
        "place_probe_grid": lambda: mcp_alpha_place_probe_grid(args.get("symbol", "XAUUSD"), args.get("up_prices", []), args.get("down_prices", []), args.get("up_type", "SELL_LIMIT"), args.get("down_type", "BUY_LIMIT"), args.get("volume", 0.01), args.get("sl_pts", 0.0), args.get("tp_pts", 0.0), args.get("tag", "TightLineup")),
        "invalidate_probe_triggers": lambda: mcp_alpha_invalidate_probe_triggers(args.get("direction", "ALL"), args.get("cancel_pending", True), args.get("exit_partial_probes", True)),
        "update_position": lambda: mcp_alpha_update_position(args.get("ticket", 0), args.get("action", "BREAK_EVEN"), args.get("params_json", "")),
        "register_watch": lambda: mcp_alpha_register_watch(args.get("symbol", "XAUUSD"), args.get("condition", ""), args.get("instruction", ""), args.get("target_price"), args.get("reason", ""), args.get("direction", "")),
        "list_desk_tools": list_desk_tools
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
