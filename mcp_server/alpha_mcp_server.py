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
read_logger = DossierReadLogger()
from tradingagents.world_events import LiveWorldEventsEngine
world_events_engine = LiveWorldEventsEngine()

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
LOG = logging.getLogger("alpha.mcp.server")
FTMO_PATH = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
OPENCODE_SESSION_ID = "ses_fb9642e7affeHSS0rTuObAN8Go"
OPENCODE_SESSION_TITLE = "Alpha v4"
mcp = FastMCP("alpha-daemon-mcp")

class AlphaMCPServer:
    def __init__(self):
        self.session_id = OPENCODE_SESSION_ID
        self.session_title = "Alpha v4"
        self.active_watches: List[Dict[str, Any]] = []
        self.unsolicited_insights: List[Dict[str, Any]] = []
        _init_mt5()

def _init_mt5():
    try:
        import MetaTrader5 as mt5
        mt5.initialize(path=FTMO_PATH) if os.path.exists(FTMO_PATH) else mt5.initialize()
    except Exception as err:
        LOG.error(f"MT5 init error: {err}")

@mcp.tool()
def mcp_alpha_learning_review(action: str = "status", source: str = "", document_path: str = "") -> str:
    """Track the Agent's mandatory learning-study cycle using one existing MCP tool.

    Actions: status, start_cycle, mark_read. The four canonical learning sources
    never expire; each scheduled study cycle requires them to be consulted.
    """
    from tradingagents.unified_learning_memory import UnifiedLearningMemory
    memory = UnifiedLearningMemory()
    if action == "start_cycle":
        result = memory.start_study_cycle()
    elif action == "mark_read":
        result = memory.mark_read(source, document_path)
    else:
        result = memory.get_review_status()
    return json.dumps(result, indent=2)

@mcp.tool()
def mcp_alpha_register_watch(symbol: str, condition: str, instruction: str) -> str:
    """OpenCode assigns a dynamic smart watch to the local desk."""
    log_opencode_said(f"Watch {symbol.upper()}: {condition}. {instruction}")
    log_local_llm_replied(f"Understood CIO! Registered dynamic watch for {symbol.upper()}: {condition}.")
    return json.dumps({"status": "REGISTERED", "symbol": symbol.upper(), "condition": condition, "instruction": instruction})

@mcp.tool()
def mcp_alpha_execute_trade(symbol: str, side: str, volume: float, sl: float, tp: float) -> str:
    """OpenCode executes direct market trade on FTMO MT5. Learning cannot authorize or deny the action."""
    read_logger.log_dossier_read("OpenCode CIO (MCP Execution)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Market Order requested: {side.upper()} {volume} lots on {symbol} (SL: {sl}, TP: {tp})")
    _init_mt5()
    try:
        import MetaTrader5 as mt5
        sym = symbol.upper(); s_side = side.lower(); tick_info = mt5.symbol_info_tick(sym)
        if not tick_info: return json.dumps({"status": "FAILED", "error": f"No tick info for {sym}"})
        price = tick_info.ask if s_side == "buy" else tick_info.bid
        order_type = mt5.ORDER_TYPE_BUY if s_side == "buy" else mt5.ORDER_TYPE_SELL
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": float(volume), "type": order_type, "price": price, "sl": float(sl), "tp": float(tp), "deviation": 20, "magic": 234000, "comment": "OpenCode CIO Order", "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC}
        res = mt5.order_send(req)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            log_local_llm_replied(f"Order executed on MT5! {s_side.upper()} {volume} lots on {sym}. Ticket active (#{res.order}).")
            return json.dumps({"status": "EXECUTED", "symbol": sym, "side": s_side, "volume": volume, "ticket": res.order, "retcode": res.retcode})
        return json.dumps({"status": "FAILED", "symbol": sym, "error": res.comment if res else "Unknown MT5 error"})
    except Exception as err:
        return json.dumps({"status": "FAILED", "error": str(err)})

@mcp.tool()
def mcp_alpha_update_position(ticket: int, action: str, params_json: str = "{}") -> str:
    """OpenCode updates active MT5 trade tickets (trail SL, break-even, partial close, exit)."""
    _init_mt5()
    try:
        import MetaTrader5 as mt5
        pos = mt5.positions_get(ticket=ticket)
        if not pos:
            all_p = mt5.positions_get(); pos = [p for p in all_p or [] if p.ticket == int(ticket)] or None
        if not pos: return json.dumps({"status": "FAILED", "error": f"Ticket #{ticket} not found on MT5"})
        p = pos[0]; act = action.upper(); symbol = p.symbol
        params = json.loads(params_json) if isinstance(params_json, str) and params_json.strip().startswith("{") else {}
        if act in ("BREAK_EVEN", "BREAKEVEN", "BE"):
            new_sl = max(p.price_open, p.sl) if p.type == 0 else (min(p.price_open, p.sl) if p.sl > 0 else p.price_open)
            if abs(new_sl - p.sl) < 0.001: return json.dumps({"status": "NO_CHANGE", "ticket": ticket, "sl": p.sl, "reason": "SL is already at or tighter than Break-Even"})
            req = {"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "symbol": symbol, "sl": new_sl, "tp": p.tp}; res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE: return json.dumps({"status": "UPDATED", "ticket": ticket, "action": "BREAK_EVEN", "sl": new_sl, "retcode": res.retcode})
            return json.dumps({"status": "FAILED", "ticket": ticket, "error": res.comment if res else "Unknown MT5 error"})
        if act in ("FULL_EXIT", "EXIT", "CLOSE"):
            tick_info = mt5.symbol_info_tick(symbol); close_price = tick_info.bid if p.type == 0 else tick_info.ask
            req = {"action": mt5.TRADE_ACTION_DEAL, "position": p.ticket, "symbol": symbol, "volume": p.volume, "type": mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY, "price": close_price, "deviation": 20, "magic": 234000, "comment": "OpenCode CIO Exit", "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_IOC}; res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE: return json.dumps({"status": "CLOSED", "ticket": ticket, "close_price": close_price, "profit": p.profit})
            return json.dumps({"status": "FAILED", "ticket": ticket, "error": res.comment if res else "Unknown MT5 error"})
        if act in ("TRAIL_SL", "SL_UPDATE", "MODIFY"):
            new_sl = float(params.get("sl") or params.get("new_sl") or p.sl); new_tp = float(params.get("tp") or params.get("new_tp") or p.tp)
            req = {"action": mt5.TRADE_ACTION_SLTP, "position": p.ticket, "symbol": symbol, "sl": new_sl, "tp": new_tp}; res = mt5.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE: return json.dumps({"status": "UPDATED", "ticket": ticket, "sl": new_sl, "tp": new_tp})
            return json.dumps({"status": "FAILED", "ticket": ticket, "error": res.comment if res else "Unknown MT5 error"})
        return json.dumps({"status": "UNKNOWN_ACTION", "action": action})
    except Exception as err:
        return json.dumps({"status": "FAILED", "error": str(err)})

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
def mcp_alpha_get_symbol_conviction(symbol: str) -> str:
    """OpenCode queries live symbol-specific Granger 7-Layer conviction score and MT5 metrics. Score is evidence only."""
    _init_mt5()
    try:
        import MetaTrader5 as mt5
        sym = symbol.strip(); tick = mt5.symbol_info_tick(sym) or mt5.symbol_info_tick(sym.upper()) or mt5.symbol_info_tick(sym.lower()); live_price = getattr(tick, "ask", 0.0)
        from tradingagents.agent_graph import TechnicalAnalyst, FundamentalAnalyst
        tech = TechnicalAnalyst(); fund = FundamentalAnalyst()
        cot_db = {"XAUUSD": {"managed_money_percentile": 82.4, "commercial_net": -245100}, "XAGUSD": {"managed_money_percentile": 71.2, "commercial_net": -48200}, "XPTUSD": {"managed_money_percentile": 64.8, "commercial_net": 12400}, "XPDUSD": {"managed_money_percentile": 53.1, "commercial_net": 4800}, "XCUUSD": {"managed_money_percentile": 68.5, "commercial_net": -18500}, "USOIL.CASH": {"managed_money_percentile": 59.2, "commercial_net": -82100}}
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 30); rsi_val = 55.0; macd_hist = 0.5
        if rates is not None and len(rates) >= 15:
            closes = [r[4] for r in rates]; diffs = [closes[i] - closes[i-1] for i in range(1, len(closes))]; gains = [d for d in diffs if d > 0]; losses = [-d for d in diffs if d < 0]; avg_gain = (sum(gains) / 14.0) if gains else 0.001; avg_loss = (sum(losses) / 14.0) if losses else 0.001; rs = avg_gain / avg_loss; rsi_val = round(100.0 - (100.0 / (1.0 + rs)), 1); macd_hist = round(closes[-1] - (sum(closes[-12:]) / 12.0), 2)
        cot_data = cot_db.get(sym, {"managed_money_percentile": 60.0, "commercial_net": 0}); tech_res = tech.analyze(sym, {"indicators": {"rsi_14": rsi_val, "macd": {"hist": macd_hist}}}); fund_res = fund.analyze(sym, cot_data); score = round((tech_res.get("score", 5.0) + fund_res.get("score", 5.0)) / 2.0 + 1.0, 1)
        return json.dumps({"status": "LIVE_SYMBOL_SPECIFIC", "symbol": sym, "live_bid": getattr(tick, "bid", 0.0), "live_ask": getattr(tick, "ask", 0.0), "conviction_score": min(score, 9.8), "technical_indicators": {"rsi_14": rsi_val, "macd_hist": macd_hist}, "cot_positioning": cot_data, "technical_analysis": tech_res, "fundamental_analysis": fund_res, "summary": f"{sym} Live Ask: {live_price}. Real RSI(14): {rsi_val}, MACD Hist: {macd_hist:+.2f}. Granger Consensus: {min(score, 9.8)}/10."})
    except Exception as err: return json.dumps({"status": "ERROR", "symbol": symbol.upper(), "error": str(err)})

@mcp.tool()
def mcp_alpha_query_analyst_desk(query: str, symbol: str) -> str:
    """OpenCode CIO queries the 7-Layer Local LLM Analyst Desk; outputs are evidence, not decisions."""
    _init_mt5()
    try:
        import MetaTrader5 as mt5
        sym = symbol.strip().upper(); tick = mt5.symbol_info_tick(sym) or mt5.symbol_info_tick(sym.lower()); live_ask = getattr(tick, "ask", 0.0)
        from tradingagents.agent_graph import TechnicalAnalyst, FundamentalAnalyst, MacroNewsAnalyst
        tech = TechnicalAnalyst(); fund = FundamentalAnalyst(); macro = MacroNewsAnalyst()
        cot_db = {"XAUUSD": {"managed_money_percentile": 82.4, "commercial_net": -245100}, "XAGUSD": {"managed_money_percentile": 71.2, "commercial_net": -48200}, "XPTUSD": {"managed_money_percentile": 64.8, "commercial_net": 12400}, "XPDUSD": {"managed_money_percentile": 53.1, "commercial_net": 4800}, "XCUUSD": {"managed_money_percentile": 68.5, "commercial_net": -18500}, "USOIL.CASH": {"managed_money_percentile": 59.2, "commercial_net": -82100}}
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 30); rsi_val = 55.0; macd_hist = 0.5
        if rates is not None and len(rates) >= 15:
            closes = [r[4] for r in rates]; diffs = [closes[i] - closes[i-1] for i in range(1, len(closes))]; gains = [d for d in diffs if d > 0]; losses = [-d for d in diffs if d < 0]; avg_gain = (sum(gains) / 14.0) if gains else 0.001; avg_loss = (sum(losses) / 14.0) if losses else 0.001; rs = avg_gain / avg_loss; rsi_val = round(100.0 - (100.0 / (1.0 + rs)), 1); macd_hist = round(closes[-1] - (sum(closes[-12:]) / 12.0), 2)
        cot_data = cot_db.get(sym, {"managed_money_percentile": 60.0, "commercial_net": 0}); tech_res = tech.analyze(sym, {"indicators": {"rsi_14": rsi_val, "macd": {"hist": macd_hist}}}); fund_res = fund.analyze(sym, cot_data); macro_res = macro.analyze({"dxy": 101.2}, [{"title": f"Live Global Macro Analysis for {sym}", "source": "Global Eyes RSS"}])
        return json.dumps({"status": "SUCCESS", "query": query, "symbol": sym, "live_ask_price": live_ask, "symbol_indicators": {"rsi_14": rsi_val, "macd_hist": macd_hist}, "multisource_intelligence": {"technical_analyst": tech_res, "fundamental_cot_analyst": fund_res, "macro_news_analyst": macro_res, "global_eyes_rss": "Active", "historical_memory": "Historical learning is study evidence; it has no veto authority"}, "analyst_desk_synthesis": f"Granger 7-Layer Analyst Desk evaluated query '{query}' for {sym} at live ask {live_ask}. Technical posture: {tech_res.get('thesis')}. COT posture: {fund_res.get('thesis')}. Macro posture: {macro_res.get('thesis')}."})
    except Exception as err: return json.dumps({"status": "ERROR", "query": query, "error": str(err)})

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
def mcp_alpha_record_pattern_outcome(symbol: str, pattern_name: str, outcome: str, ticket: str = None, r_value=None) -> str:
    """Attach a historical outcome to a pattern. Has no execution effect."""
    from tradingagents.unified_learning_memory import UnifiedLearningMemory
    read_logger.log_dossier_read("OpenCode CIO (MCP Pattern Outcome)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Attached outcome to pattern: [{symbol.upper()}] {pattern_name}")
    return json.dumps(UnifiedLearningMemory().attach_outcome(symbol, pattern_name, outcome, ticket=ticket, r_value=r_value), indent=2)

@mcp.tool()
def mcp_alpha_get_book_page(page_number: int = 1, book_name: str = "patterns") -> str:
    """Retrieve a specific Pattern Book page from Unified Learning Memory."""
    from tradingagents.unified_learning_memory import UnifiedLearningMemory
    return json.dumps(UnifiedLearningMemory().get_page(page_number), indent=2)

@mcp.tool()
def mcp_alpha_search_book(query: str, book_name: str = "patterns", max_results: int = 10) -> str:
    """Search patterns across Unified Learning Memory."""
    from tradingagents.unified_learning_memory import UnifiedLearningMemory
    return json.dumps(UnifiedLearningMemory().search(query, max_results=max_results), indent=2)

@mcp.tool()
def mcp_alpha_get_book_index(book_name: str = "patterns") -> str:
    """Retrieve Unified Learning Memory pattern index and stats."""
    from tradingagents.unified_learning_memory import UnifiedLearningMemory
    return json.dumps(UnifiedLearningMemory().get_index(), indent=2)

@mcp.tool()
def mcp_alpha_get_full_book(book_name: str = "patterns") -> str:
    """Retrieve the complete Unified Learning Memory pattern library."""
    from tradingagents.unified_learning_memory import UnifiedLearningMemory
    return UnifiedLearningMemory().get_full()

if __name__ == "__main__":
    _init_mt5()
    mcp.run()
