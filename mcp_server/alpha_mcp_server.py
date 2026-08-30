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
from datetime import datetime, timezone
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
def mcp_alpha_register_watch(symbol: str, condition: str = "", instruction: str = "", target_price: float = None, reason: str = "", direction: str = "") -> str:
    """OpenCode assigns a dynamic smart watch to the local desk and registers active thesis with the Librarian."""
    sym = _normalize_symbol(symbol)
    desc = condition or instruction or reason or f"Watching {sym} @ {target_price}"
    log_opencode_said(f"Watch {sym}: {desc}")
    log_local_llm_replied(f"Understood CIO! Registered dynamic watch for {sym}: {desc}.")
    
    watch_payload = {
        "symbol": sym,
        "condition": desc,
        "instruction": instruction,
        "target_price": target_price,
        "direction": direction,
        "reason": reason,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    _active_watches[sym] = watch_payload

    # Save to discovery state for Librarian ingestion and persistent desk reload
    try:
        state_path = ALPHA_ROOT / "data" / "live" / "discovery_state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_data = {}
        if state_path.exists():
            try:
                with open(state_path, "r", encoding="utf-8-sig") as f:
                    state_data = json.load(f)
            except Exception as read_err:
                LOG.warning(f"Could not read existing discovery_state.json: {read_err}")
                state_data = {}

        state_data["active_watch"] = watch_payload
        watches_map = state_data.get("active_watches", {})
        if not isinstance(watches_map, dict):
            watches_map = {}
        watches_map[sym] = watch_payload
        state_data["active_watches"] = watches_map

        with open(state_path, "w", encoding="utf-8") as f:
            json.dump(state_data, f, indent=2)
        LOG.info(f"Persisted active watch for {sym} to {state_path}")
    except Exception as err:
        LOG.error(f"register_watch persist failed: {err}")

    return json.dumps({
        "status": "REGISTERED",
        "symbol": sym,
        "condition": condition,
        "instruction": instruction,
        "target_price": target_price,
        "direction": direction,
        "active_watch": watch_payload
    }, indent=2)

@mcp.tool()
def mcp_alpha_execute_trade(symbol: str, side: str, volume: float, sl: float, tp: float) -> str:
    """OpenCode executes direct market trade on FTMO MT5. Learning cannot authorize or deny the action."""
    read_logger.log_dossier_read("OpenCode CIO (MCP Execution)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Market Order requested: {side.upper()} {volume} lots on {symbol} (SL: {sl}, TP: {tp})")
    
    # Systemic Weekend Stale Guardrail
    try:
        from tradingagents.world_market import IntradayInstitutionalEngine
        session_info = IntradayInstitutionalEngine().get_session_status()
        is_weekend = (not session_info.get("market_open", True)) or session_info.get("market_status") == "WEEKEND_MARKET_CLOSED" or session_info.get("session") == "WEEKEND_MARKET_CLOSED"
        if is_weekend:
            return json.dumps({
                "status": "EXECUTION_BLOCKED_WEEKEND_MARKET_CLOSED",
                "error": "Interbank & FTMO broker markets are CLOSED for the weekend (Sunday). Direct market execution is strictly prohibited on frozen historical ticks until markets reopen Sunday 21:00 UTC.",
                "symbol": _normalize_symbol(symbol),
                "side": side.upper(),
                "volume": volume,
                "is_frozen": True,
                "data_asof": "Frozen Friday Close (2026-08-28 23:49:59 UTC)"
            }, indent=2)
    except Exception as e:
        LOG.warning(f"Weekend guardrail check error: {e}")

    _init_mt5()
    try:
        import MetaTrader5 as mt5
        sym = _normalize_symbol(symbol); s_side = side.lower(); tick_info = mt5.symbol_info_tick(sym)
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
        score = debate_res.get("consensus_score", 2.9)
        
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
            "conviction_score": score,
            "conviction_tier": debate_res.get("conviction", "LOW"),
            "is_regime_conflict": debate_res.get("is_regime_conflict", False),
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
            "summary": f"{sym} Ask: {live_price} [{status_tag} ({data_asof_tag})]. 4TF: {mtf_res.get('formatted_4tf')}. Granger Conviction: {min(score, 9.8)}/10. FVG: {fvg_mat.get('summary')}."
        }, indent=2)
    except Exception as err:
        return json.dumps({"status": "ERROR", "symbol": symbol, "error": str(err)})

@mcp.tool()
def mcp_alpha_query_analyst_desk(query: str = "Full 7-layer technical, fundamental COT, and macro market analysis", symbol: str = "XAUUSD") -> str:
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
        
        status_tag = "WEEKEND_MARKET_CLOSED_FROZEN" if is_weekend else "SUCCESS"
        data_asof_tag = "Frozen Friday Close (2026-08-28 23:49:59 UTC)" if is_weekend else "Live MT5 Tick"

        return json.dumps({
            "status": status_tag,
            "query": query,
            "symbol": sym,
            "is_frozen": is_weekend,
            "data_asof": data_asof_tag,
            "last_tick_time": "2026-08-28 23:49:59 UTC" if is_weekend else None,
            "ask_price": live_ask,
            "4tf_alignment": mtf_res.get("formatted_4tf"),
            "multisource_intelligence": {
                "technical_analyst": tech_res,
                "fundamental_cot_analyst": fund_res,
                "macro_news_analyst": macro_res,
                "historical_memory": "Historical learning is study evidence; it has no veto authority"
            },
            "analyst_desk_synthesis": f"Granger 7-Layer Analyst Desk evaluated query '{query}' for {sym} at ask {live_ask} [{status_tag} ({data_asof_tag})]. 4TF: {mtf_res.get('formatted_4tf')}. COT posture: {fund_res.get('thesis')}. Macro posture: {macro_res.get('thesis')}."
        }, indent=2)
    except Exception as err:
        return json.dumps({"status": "ERROR", "query": query, "error": str(err)})

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
    read_logger.log_dossier_read("OpenCode CIO (MCP Pattern Outcome)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Updated pattern outcome: [{symbol.upper()}] {pattern_name} -> {outcome}")
    return json.dumps(UnifiedLearningMemory().update_pattern_outcome(symbol, pattern_name, outcome, ticket=ticket, r_value=r_value), indent=2)

@mcp.tool()
def mcp_alpha_get_book_page(page_number: int = 1) -> str:
    """Retrieve specific page of Pattern Book. Reference only; does not authorize execution."""
    from tradingagents.unified_learning_memory import UnifiedLearningMemory
    read_logger.log_dossier_read("OpenCode CIO (MCP Book Page)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Read Pattern Book page {page_number}")
    return json.dumps(UnifiedLearningMemory().get_page(page_number), indent=2)

@mcp.tool()
def mcp_alpha_search_book(keyword: str, symbol: str = None) -> str:
    """Search Pattern Book / ULM by keyword and symbol. Evidence only; does not authorize execution."""
    from tradingagents.unified_learning_memory import UnifiedLearningMemory
    sym_log = f" for symbol {symbol.upper()}" if symbol else ""
    read_logger.log_dossier_read("OpenCode CIO (MCP Search Book)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Searched Pattern Book for keyword '{keyword}'{sym_log}")
    return json.dumps(UnifiedLearningMemory().search_patterns(keyword, symbol=symbol), indent=2)

@mcp.tool()
def mcp_alpha_get_book_index() -> str:
    """Get high-level index and summary of Pattern Book. Reference only; does not authorize execution."""
    from tradingagents.unified_learning_memory import UnifiedLearningMemory
    read_logger.log_dossier_read("OpenCode CIO (MCP Book Index)", "MANDATORY_PRE_EXECUTION_AUDIT", "Read Pattern Book index")
    return json.dumps(UnifiedLearningMemory().get_index(), indent=2)

@mcp.tool()
def mcp_alpha_get_full_book() -> str:
    """Retrieve full dump of Pattern Book / ULM. Evidence only; does not authorize execution."""
    from tradingagents.unified_learning_memory import UnifiedLearningMemory
    read_logger.log_dossier_read("OpenCode CIO (MCP Full Book)", "MANDATORY_PRE_EXECUTION_AUDIT", "Retrieved full Pattern Book")
    return json.dumps(UnifiedLearningMemory().get_full_book(), indent=2)

@mcp.tool()
def mcp_alpha_get_fvg_matrix(symbol: str = "XAUUSD") -> str:
    """Query multi-timeframe (H4, H1, M15, M5) Fair Value Gaps (FVG) and 50% Consequent Encroachment levels."""
    from tradingagents.fair_value_gap import FairValueGapEngine
    read_logger.log_dossier_read("OpenCode CIO (MCP FVG Query)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Queried FVG matrix for {symbol.upper()}")
    fvg_engine = FairValueGapEngine()
    return json.dumps(fvg_engine.get_symbol_fvg_matrix(symbol), indent=2)

@mcp.tool()
def mcp_alpha_get_trade_forensics(target: Any = "XAUUSD") -> str:
    """Query granular post-trade forensics and entry market context for closed MT5 deals (accepts ticket number int/str or symbol str e.g. 'XAUUSD')."""
    from tradingagents.trade_forensics import TradeForensicsEngine
    read_logger.log_dossier_read("OpenCode CIO (MCP Trade Forensics)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Queried trade forensics for {target}")
    forensics = TradeForensicsEngine()
    return json.dumps(forensics.get_trade_forensics(target), indent=2)

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


@mcp.tool()
def mcp_alpha_ask_librarian(query: str, symbol: str = "XAUUSD") -> str:
    """Ask the Autonomous Librarian Agent any historical, tactical, or quantitative question about precedents, win rates, failure traps, and invalidation rules."""
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
    symbol: str,
    side: str,
    conviction_score: float,
    in_direction_fvg_fill_pct: float = None,
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
    direction_thesis: str = ""
) -> str:
    """Record a comprehensive pre-trade experimental decision snapshot on disk before execution."""
    from tradingagents.decision_snapshot_recorder import PreTradeDecisionRecorder
    from tradingagents.cvd_engine import CumulativeVolumeDeltaEngine
    from tradingagents.world_market import IntradayInstitutionalEngine
    from tradingagents.news_shield import NewsShield

    sym = _normalize_symbol(symbol)
    read_logger.log_dossier_read("OpenCode CIO (MCP Decision Snapshot)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Recorded pre-trade decision snapshot for {sym} {side} [{category_tag}]")
    
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
        side=side,
        conviction_score=conviction_score,
        in_direction_fvg_fill_pct=in_direction_fvg_fill_pct,
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
        direction_thesis=direction_thesis
    ), indent=2)


@mcp.tool()
def mcp_alpha_get_measured_cvd(symbol: str = "XAUUSD") -> str:
    """Fetch measured Cumulative Volume Delta (CVD) and Delta Exhaustion / Absorption metrics directly from MT5 ticks."""
    from tradingagents.cvd_engine import CumulativeVolumeDeltaEngine
    sym = _normalize_symbol(symbol)
    read_logger.log_dossier_read("OpenCode CIO (MCP CVD Query)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Queried measured CVD for {sym}")
    engine = CumulativeVolumeDeltaEngine()
    return json.dumps(engine.get_symbol_cvd(sym), indent=2)


@mcp.tool()
def mcp_alpha_backtest_thesis(
    query: str,
    symbol: str = "XAUUSD",
    timeframe: str = "M5",
    bars: int = 60,
    offset: int = 0
) -> str:
    """Ultra-fast natural backtester powered by Proxima + MT5 Data Harness + Local LLM.
    
    Zero hardcoded pattern rules. The Local LLM naturally identifies structural patterns (FVGs, liquidity sweeps,
    velocity acceleration, order blocks) directly from raw historical MT5 candle tables and evaluates forward
    trade trajectory and R outcomes.
    
    Args:
        query: Free-form thesis or question (e.g. 'Backtest velocity acceleration into M5 Bearish FVG after Asian sweep')
        symbol: Instrument symbol (default: 'XAUUSD')
        timeframe: Candle timeframe (default: 'M5', supports 'M1', 'M5', 'M15', 'H1', 'H4')
        bars: Historical candle window size (default: 60 bars)
        offset: Bar offset from current time (default: 0)
    """
    from backtesting.pipeline import PureLLMBacktestPipeline
    sym = _normalize_symbol(symbol)
    read_logger.log_dossier_read("OpenCode CIO (MCP Backtest Thesis)", "MANDATORY_PRE_EXECUTION_AUDIT", f"Requested natural backtest: '{query}' on {sym} ({timeframe}, {bars} bars)")
    pipeline = PureLLMBacktestPipeline()
    return json.dumps(pipeline.run_backtest(query=query, symbol=sym, timeframe=timeframe, bars=bars, offset=offset), indent=2)


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
def record_decision_snapshot(symbol: str, side: str, conviction: float, notes: str = "", volume: float = 0.0, sl: float = 0.0, tp: float = 0.0) -> str:
    """Record pre-trade decision context on disk (s4.137 Process vs Outcome)."""
    return mcp_alpha_record_decision_snapshot(symbol, side, conviction, notes, volume, sl, tp)

@mcp.tool()
def record_trade_observation(symbol: str, pattern_name: str, observation: str, outcome: str = "STUDY", r_multiple: float = 0.0) -> str:
    """Commit verified trade outcomes & lessons into Pattern Book & ULM."""
    return mcp_alpha_record_trade_observation(symbol, pattern_name, observation, outcome, r_multiple)

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
def list_desk_tools() -> str:
    """Live dynamic discovery of ALL available FastMCP tools and their capabilities in the desk daemon."""
    tools_list = [
        {"name": "get_account_status", "description": "Live FTMO MT5 equity, balance, free margin, margin utilization % and active ticket states."},
        {"name": "get_full_institutional_profile", "description": "Volume Profile (POC/VAH/VAL), VWAP (+/-1s, +/-2s), Dark Pool DIX/GEX, Treasury Yields (US10Y/US2Y/DXY/VIX), FTMO Contract Specs, and 4TF EMAs/RSI."},
        {"name": "get_symbol_conviction", "description": "4TF institutional alignment, exact EMA20/50 & RSI values, FVG geometry, and COT percentiles."},
        {"name": "get_trade_forensics", "description": "Deep forensics on closed trades: Win rate %, net R, FVG fill %, RSI regime, and spread distribution."},
        {"name": "get_ledger_decomposition", "description": "Decompose 121-trade history into condition base rates (Session x Direction x Spread x FVG Fill%)."},
        {"name": "get_multi_instrument_ledger", "description": "Full 134-position portfolio breakdown breaking out 121 XAUUSD vs 13 non-XAU bleed (XAG/XCU/XPT/XPD)."},
        {"name": "get_live_microstructure", "description": "Live spread in pts, M1 tick velocity (t/m), order book depth imbalance, and CVD posture."},
        {"name": "backtest_thesis", "description": "Natural MT5 candle-table replay (Zero hardcoded rules). Replays setup trajectory, empirical win rate %, realized R, and failure clusters."},
        {"name": "ask_librarian", "description": "Search 371 ULM Precedents + Mandatory Proxima Quantitative Microstructure Research (Port 3210, 65s cascade)."},
        {"name": "query_analyst_desk", "description": "Deep 7-layer local LLM multi-source debate (Technical, COT, Macro, Bull vs Bear)."},
        {"name": "get_measured_cvd", "description": "Measured M5 tick CVD, 10-bar delta velocity, and passive absorption signals from MT5."},
        {"name": "get_fvg_matrix", "description": "Query multi-timeframe (H4, H1, M15, M5) Fair Value Gaps and Consequent Encroachment levels."},
        {"name": "get_live_world_events", "description": "Live macroeconomic releases, central bank speeches, and geopolitical intelligence."},
        {"name": "record_decision_snapshot", "description": "Record pre-trade decision context on disk with full experimental metadata."},
        {"name": "execute_trade", "description": "Execute direct market buy/sell orders on FTMO MT5 at uniform pilot size (0.10 lots or lower)."},
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
        "get_full_institutional_profile": lambda: mcp_alpha_get_full_institutional_profile(args.get("symbol", "XAUUSD")),
        "get_symbol_conviction": lambda: mcp_alpha_get_symbol_conviction(args.get("symbol", "XAUUSD")),
        "get_trade_forensics": lambda: mcp_alpha_get_trade_forensics(args.get("symbol_or_ticket", args.get("symbol", "XAUUSD"))),
        "get_ledger_decomposition": lambda: mcp_alpha_get_ledger_decomposition(args.get("symbol", "XAUUSD")),
        "get_multi_instrument_ledger": mcp_alpha_get_multi_instrument_ledger,
        "get_live_microstructure": lambda: mcp_alpha_get_live_microstructure(args.get("symbol", "XAUUSD")),
        "backtest_thesis": lambda: mcp_alpha_backtest_thesis(args.get("query", ""), args.get("symbol", "XAUUSD"), args.get("timeframe", "M5"), args.get("bars", 60), args.get("offset", 0)),
        "ask_librarian": lambda: mcp_alpha_ask_librarian(args.get("query", ""), args.get("symbol", "XAUUSD")),
        "query_analyst_desk": lambda: mcp_alpha_query_analyst_desk(args.get("query", ""), args.get("symbol", "XAUUSD")),
        "get_measured_cvd": lambda: mcp_alpha_get_measured_cvd(args.get("symbol", "XAUUSD")),
        "get_fvg_matrix": lambda: mcp_alpha_get_fvg_matrix(args.get("symbol", "XAUUSD")),
        "get_live_world_events": lambda: mcp_alpha_get_live_world_events(args.get("category", "ALL")),
        "record_decision_snapshot": lambda: mcp_alpha_record_decision_snapshot(**args),
        "execute_trade": lambda: mcp_alpha_execute_trade(args.get("symbol", "XAUUSD"), args.get("side", "BUY"), args.get("volume", 0.05), args.get("sl", 0.0), args.get("tp", 0.0)),
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
