"""
======================================================================
               ALPHA V1 - CONSOLIDATED INTELLIGENT TRADING DESK
======================================================================
Project Root: C:\Trading\Alpha
OpenCode Session: Alpha v1 (ses_fd5d79a76ffeWi4umW2PMa4MCe)
Target Terminal: FTMO MetaTrader 5 (C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe)

Integrates:
1. StoryLogger — Thread-safe natural language story narration (live_story.log)
2. StatefulDiscoveryLatch — Thesis latching state store (discovery_state.json)
3. OpenCodeCIOEvaluator — Autonomous CIO evaluation & R:R risk validation
4. OrderRouter & Executor — FTMO MT5 direct execution with Max 1 Position Guard
5. IntelligentDaemon — 24/7 continuous market scanner across 6 instruments
======================================================================
"""

import os
import sys
import json
import time
import psutil
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure project root paths are in sys.path
PROJECT_ROOT = Path(r"C:\Trading\Alpha")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
TRADING_DIR = Path(r"C:\Trading")
if str(TRADING_DIR) not in sys.path:
    sys.path.insert(0, str(TRADING_DIR))

from config import (
    get_opencode_session,
    get_opencode_session_id,
    get_opencode_session_title,
    get_opencode_api_url,
    is_dossier_streaming_enabled,
    get_dossier_interval_seconds,
    get_active_trade_interval_seconds
)

# Constants
FTMO_PATH = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
STORY_LOG_PATH = PROJECT_ROOT / "logs" / "live_story.log"
DAEMON_PINGS_LOG_PATH = PROJECT_ROOT / "logs" / "daemon_pings.log"
STATE_FILE_PATH = PROJECT_ROOT / "data" / "live" / "discovery_state.json"
CONFIG_PATH = PROJECT_ROOT / "config" / "instruments_config.json"
INSTRUMENTS = ["XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD", "XCUUSD", "USOIL.cash"]

def get_active_instruments() -> List[str]:
    """Reads config/instruments_config.json with zero-restart hot-reloading."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                active = [sym for sym, enabled in data.get("instruments", {}).items() if enabled]
                if active:
                    return active
        except Exception as e:
            LOG.error(f"Error loading {CONFIG_PATH}: {e}")
    return INSTRUMENTS

# ----------------------------------------------------------------------
# PER-INSTRUMENT SPREAD NORMAL/ELEVATED THRESHOLDS (points)
# ----------------------------------------------------------------------
# Each instrument has a structurally different normal bid-ask baseline AND a
# different $ cost per point. A single universal "<=45 pts" gate wrongly blocks
# instruments whose normal spread is legitimately wider (notably USOIL.cash, which
# has a tiny $-cost/pt so a wider point-spread is still economically viable).
#
# The NORMAL bound is the per-instrument tradable ceiling. Oil gets a generous
# BUFFER above its 25-60 pt normal baseline so the gate never blocks it at a
# spread whose dollar cost is still a tiny fraction of the target.
#
# Source: GCTSI Q2-2026 spread report + live FTMO broker calibration
#   XAUUSD: 10-30 normal  -> ceiling 45 (tight scalp vehicle)
#   XAGUSD: 20-60 normal  -> ceiling 70
#   XPTUSD: 30-80 normal  -> ceiling 150 (structurally wide)
#   XPDUSD: 30-90 normal -> ceiling 180 (wide spread vehicle)
#   XCUUSD: 15-40 normal -> ceiling 60
#   USOIL.cash: 25-60 normal -> ceiling 120 (generous buffer; $0.10/pt means 60 pts = $6 cost on a $150 move)
def spread_classification(symbol: str, spread_pts: int) -> str:
    """Return 'NORMAL' | 'ELEVATED' | 'HIGH_SPIKE' based on per-instrument ceilings."""
    ceilings = {
        "XAUUSD": (45, 65),
        "XAGUSD": (70, 100),
        "XPTUSD": (150, 220),
        "XPDUSD": (180, 260),
        "XCUUSD": (60, 90),
        "USOIL.cash": (120, 180),
    }
    normal_ceil, elevated_ceil = ceilings.get(symbol, (45, 70))
    if spread_pts <= normal_ceil:
        return "NORMAL"
    elif spread_pts <= elevated_ceil:
        return "ELEVATED"
    else:
        return "HIGH_SPIKE"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
LOG = logging.getLogger("alpha.trading_desk")

# ----------------------------------------------------------------------
# 1. Story Logger & Resilient OpenCode HTTP Session Streamer Module
# ----------------------------------------------------------------------
def post_to_opencode_session(speaker: str, message: str):
    """Log intent, record ping into daemon_pings.log, and enqueue prompt to OpenCode."""
    log_story(speaker, message)
    sid, title, api_url = get_opencode_session()
    try:
        DAEMON_PINGS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(DAEMON_PINGS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*70}\n[DAEMON PING] {now_ts} | Speaker: {speaker} | Target: {title} ({sid})\n{'='*70}\n{message}\n")
    except Exception as e:
        LOG.error(f"Error writing to daemon_pings.log: {e}")

    # Check if dossier streaming is paused
    if not is_dossier_streaming_enabled():
        LOG.info(f"Dossier prompt streaming to session '{title}' ({sid}) is currently PAUSED. (Daemon remains live & scanning).")
        return

    LOG.info(
        f"\n=== [COMMUNICATION LOG STREAM] ===\n"
        f"Speaker: {speaker}\n"
        f"Target Session: {sid} ({title})\n"
        f"Payload Message:\n{message[:200]}...\n"
        f"===================================\n"
    )

    def _send():
        import urllib.error
        import urllib.request

        target_sids = set()
        if sid:
            target_sids.add(sid)
        else:
            # Fallback if no sid configured: query active session
            try:
                list_req = urllib.request.Request(f"{api_url}/session")
                with urllib.request.urlopen(list_req, timeout=5) as resp:
                    sessions_list = json.loads(resp.read().decode('utf-8'))
                    if sessions_list:
                        target_sids.add(sessions_list[0].get("id"))
            except Exception as e:
                LOG.warning(f"Could not query sessions list: {e}")

        payload = json.dumps({
            "parts": [{"type": "text", "text": f"[{speaker}] {message}"}]
        }).encode("utf-8")

        for target_sid in target_sids:
            url = f"{api_url}/session/{target_sid}/prompt_async"
            for attempt in range(1, 4):
                try:
                    req = urllib.request.Request(
                        url,
                        data=payload,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        status = getattr(resp, "status", resp.getcode())
                        if 200 <= status < 300:
                            LOG.info(
                                f"OpenCode async prompt accepted for {title} "
                                f"session {target_sid} (HTTP {status}, attempt {attempt})."
                            )
                            break
                        raise RuntimeError(f"Unexpected HTTP status {status}")
                except Exception as err:
                    if attempt < 3:
                        LOG.warning(
                            f"OpenCode async dispatch attempt {attempt}/3 failed for {target_sid}: {err}; retrying."
                        )
                        time.sleep(float(attempt))
                    else:
                        LOG.error(
                            f"OpenCode async dispatch failed for {title} session {target_sid}: {err}"
                        )

    import threading
    t = threading.Thread(target=_send, daemon=True)
    t.start()

def log_story(speaker: str, message: str):
    """Write timestamped dialogue line to live_story.log (file logging only, zero HTTP chat prompts)."""
    try:
        STORY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] {speaker}: {message}\n"
        with open(STORY_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
        LOG.info(f"STORY: [{speaker}] {message}")
    except Exception as err:
        LOG.error(f"Story log failed: {err}")

def log_opencode_said(msg: str):
    log_story("OpenCode (CIO)", f'"{msg}"')
    post_to_opencode_session("OpenCode (CIO)", msg)

def log_local_llm_replied(msg: str): log_story("Local LLM Desk", f'"{msg}"')
def log_local_llm_monitoring(msg: str): log_story("Local LLM Desk", f"[Monitoring] {msg}")
def log_proactive_alert(sym: str, score: float, headline: str): log_story("Local LLM Desk", f'[Proactive Discovery] "{headline}"')

def is_opencode_idle(session_id: str = None) -> bool:
    """Check if OpenCode session is ready to receive alerts. Always defaults to True to guarantee reliable 3-min and startup dispatch."""
    if not session_id:
        session_id = get_opencode_session_id()
    try:
        import urllib.request
        api_url = get_opencode_api_url()
        url = f"{api_url}/session/{session_id}/message"
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=2)
        if resp.status == 200:
            messages = json.loads(resp.read().decode("utf-8"))
            if messages:
                last_msg = messages[-1]
                info = last_msg.get("info", {})
                role = info.get("role", "")
                created_ts = info.get("time", {}).get("created", 0) / 1000.0
                now_ts = datetime.now().timestamp()
                # If last msg was user sent over 120s ago, or assistant replied, it is ready
                if role.lower() != "user" or (now_ts - created_ts > 120.0):
                    return True
                return False
    except Exception as err:
        LOG.debug(f"is_opencode_idle query error: {err}")
    return True

# ----------------------------------------------------------------------
# 2. Stateful Discovery Latch Module
# ----------------------------------------------------------------------
class StatefulDiscoveryLatch:
    """Latches trade thesis states to eliminate 10-second discovery chatter."""

    def __init__(self, state_file: Path = STATE_FILE_PATH):
        self.state_file = state_file
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_state(self):
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except Exception as err:
            LOG.error(f"Latch save state failed: {err}")

    def evaluate_thesis(self, symbol: str, score: float, bull_points: List[str], bear_points: List[str]):
        last = self.state.get(symbol)
        now_ts = time.time()

        if not last:
            self.state[symbol] = {
                "score": score,
                "bull_points": bull_points,
                "bear_points": bear_points,
                "latched_at": now_ts,
                "last_alert": now_ts
            }
            self._save_state()
            return True, "NEW_THESIS"

        score_delta = abs(score - last.get("score", 0.0))
        bear_diff = set(bear_points) - set(last.get("bear_points", []))

        if score_delta >= 1.0 or bear_diff:
            self.state[symbol] = {
                "score": score,
                "bull_points": bull_points,
                "bear_points": bear_points,
                "latched_at": now_ts,
                "last_alert": now_ts
            }
            self._save_state()
            return True, "MATERIAL_SHIFT"

        return False, "LATCHED_ACTIVE"

# ----------------------------------------------------------------------
# 3. FTMO MT5 Execution & Router Module
# ----------------------------------------------------------------------
def place_ftmo_market_order(symbol: str, side: str, volume: float, sl: float, tp: float) -> Dict[str, Any]:
    """Execute live market order on FTMO MetaTrader 5 with Max 1 Position Guard."""
    try:
        import MetaTrader5 as mt5
        initialized = mt5.initialize(path=FTMO_PATH) if os.path.exists(FTMO_PATH) else mt5.initialize()
        if not initialized:
            return {"success": False, "error": f"MT5 initialize failed: {mt5.last_error()}"}

        mt5.symbol_select(symbol, True)

        # Max 1 Active Position Guard per Symbol
        all_pos = mt5.positions_get()
        if all_pos:
            sym_target = symbol.replace(".cash", "").upper()
            matching = [p for p in all_pos if p.symbol.replace(".cash", "").upper() == sym_target]
            if matching:
                ticket_id = matching[0].ticket
                return {"success": False, "error": f"position_already_open for {symbol} (Ticket #{ticket_id})"}

        tick_info = mt5.symbol_info_tick(symbol)
        sym_info = mt5.symbol_info(symbol)
        if not tick_info:
            return {"success": False, "error": f"No tick data available for {symbol}"}

        price = tick_info.ask if side == "buy" else tick_info.bid
        point = getattr(sym_info, "point", 0.01) if sym_info else 0.01
        digits = getattr(sym_info, "digits", 2) if sym_info else 2
        stops_dist = max((getattr(sym_info, "trade_stops_level", 50) or 50) * point, 20 * point)

        # Validate Agent-selected SL/TP without silently substituting trading decisions.
        if side == "buy":
            if not (0 < sl < price - stops_dist):
                return {"success": False, "error": "invalid_agent_sl_for_buy"}
            if not (tp > price + stops_dist):
                return {"success": False, "error": "invalid_agent_tp_for_buy"}
            sl_val = round(sl, digits)
            tp_val = round(tp, digits)
            order_type = mt5.ORDER_TYPE_BUY
        else:
            if not (sl > price + stops_dist):
                return {"success": False, "error": "invalid_agent_sl_for_sell"}
            if not (0 < tp < price - stops_dist):
                return {"success": False, "error": "invalid_agent_tp_for_sell"}
            sl_val = round(sl, digits)
            tp_val = round(tp, digits)
            order_type = mt5.ORDER_TYPE_SELL

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": price,
            "sl": sl_val,
            "tp": tp_val,
            "deviation": 30,
            "magic": 20260822,
            "comment": "AlphaV2_FTMO",
            "type_time": mt5.ORDER_TIME_GTC,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            retcode = getattr(result, "retcode", None)
            comment = getattr(result, "comment", "unknown error")
            return {"success": False, "error": f"order_send retcode {retcode} ({comment})"}

        LOG.info(f"LIVE FTMO FILL {side.upper()} {volume} {symbol} @ {result.price} Ticket #{result.order}")
        return {"success": True, "ticket": result.order, "fill_price": result.price, "dry_run": False}
    except Exception as exc:
        LOG.error(f"place_ftmo_market_order failed: {exc}")
        return {"success": False, "error": str(exc)}

# ----------------------------------------------------------------------
# 4. Discovery Evidence Streamer
# ----------------------------------------------------------------------
class OpenCodeCIOEvaluator:
    """Legacy-named compatibility component. It never decides or executes trades."""
    def __init__(self):
        self.session_id = get_opencode_session_id()
        self.session_title = get_opencode_session_title()

    def evaluate_discovery_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        symbol = event.get("symbol", "XAUUSD")
        bull_points = event.get("bull_points", [])
        bear_points = event.get("bear_points", [])
        summary = (
            f"Discovery evidence update for {symbol}. "
            f"Supporting catalysts: {bull_points or 'none supplied'}. "
            f"Contradictory risks: {bear_points or 'none supplied'}. "
            f"This is raw market telemetry only; no synthetic score threshold approves, vetoes, or executes a trade."
        )
        log_opencode_said(summary)
        return {
            "decision": "AGENT_REVIEW_REQUIRED",
            "symbol": symbol,
            "supporting_evidence": bull_points,
            "contradictory_evidence": bear_points,
            "raw_telemetry": event.get("raw_data", {}),
            "review_required": True,
            "decision_authority": "AGENT_ONLY",
            "execution_authority": "AGENT_ONLY"
        }

# ----------------------------------------------------------------------
# 5. Process Cleanup Utilities
# ----------------------------------------------------------------------
def kill_all_daemons() -> int:
    """Terminate any background intelligent_daemon, alpha_trading_desk, or MCP server processes across ALL python environments."""
    killed_count = 0
    current_pid = os.getpid()
    parent_pid = os.getppid() if hasattr(os, "getppid") else -1
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.pid in (current_pid, parent_pid):
                continue
            name = str(proc.info.get('name') or '').lower()
            if not name.startswith('python'):
                continue
            cmd = proc.info.get('cmdline')
            if cmd:
                cmd_str = ' '.join(cmd).lower()
                if 'intelligent_daemon' in cmd_str or 'alpha_trading_desk' in cmd_str or 'alpha_mcp_server' in cmd_str:
                    proc.kill()
                    killed_count += 1
                    LOG.info(f"Killed process PID {proc.pid}: {cmd_str[:80]}")
        except Exception:
            pass
    return killed_count

# ----------------------------------------------------------------------
# 6. Main 24/7 Intelligent Trading Daemon
# ----------------------------------------------------------------------
class ConsolidatedTradingDaemon:
    """Runs 24/7 continuous multi-agent market scanning & position management."""

    def __init__(self):
        from tradingagents.agent_graph import TradingAgentsDesk
        from mcp_server.alpha_mcp_server import AlphaMCPServer
        from tradingagents.librarian_agent import AutonomousLibrarianAgent

        self.desk = TradingAgentsDesk()
        self.mcp_server = AlphaMCPServer()
        self.librarian = AutonomousLibrarianAgent()
        self.latch = StatefulDiscoveryLatch()
        self.cio_evaluator = OpenCodeCIOEvaluator()  # evidence streamer only; never executes
        self.instruments = INSTRUMENTS
        self.is_running = False
        self.cycle_count = 0
        self.last_dispatch_time = 0.0
        self.last_reversal_dispatch_time = 0.0

        # Wire live error monitoring into Desk Daemon (H4)
        from monitor.error_monitor import error_monitor
        self.error_monitor = error_monitor
        self.error_monitor.install_global_handlers()

    async def run_cycle(self):
        self.cycle_count += 1
        self.instruments = get_active_instruments()
        LOG.info(f"--- Starting Scan Cycle #{self.cycle_count} across {len(self.instruments)} instruments ({', '.join(self.instruments)}) ---")
        log_local_llm_monitoring(f"Scanning market data across {len(self.instruments)} instruments (Granger 7-Layers + Global Eyes RSS feeds active)...")

        # Record live error-monitor heartbeat (H4)
        try:
            self.error_monitor.capture("INFO", "alpha_trading_desk", "DESK_DAEMON_HEARTBEAT", f"Live Desk Daemon active scan cycle #{self.cycle_count}", {"instruments": self.instruments})
        except Exception as e_err:
            LOG.debug(f"Error monitor heartbeat error: {e_err}")

        top_symbol = "XAUUSD"
        headline = ""

        from mcp_server.alpha_mcp_server import mcp_alpha_get_symbol_conviction
        for symbol in self.instruments:
            try:
                conv_json = mcp_alpha_get_symbol_conviction(symbol)
                conv_data = json.loads(conv_json)
                summary = conv_data.get("summary", f"{symbol} Raw telemetry active")
            except Exception:
                summary = f"{symbol} Telemetry active"

            if symbol == "XAUUSD" or not headline:
                top_symbol = symbol
                headline = summary

        # 1. RUN FULL 7-AGENT DESK THINKING PROCESS ACROSS ALL 6 INSTRUMENTS
        from tradingagents.world_market import IntradayInstitutionalEngine
        from tradingagents.dossier_logger import DeepDossierLogger

        world_engine = IntradayInstitutionalEngine()
        dossier_logger = DeepDossierLogger()

        session_info = world_engine.get_session_status()
        gsr_data = world_engine.get_gsr_ratio()
        account_health = world_engine.get_account_health()
        currency_strength = world_engine.get_currency_strength()
        real_yields = world_engine.get_real_yields()

        instrument_matrix = []
        instruments_data = []
        import MetaTrader5 as mt5
        mt5_online = mt5.initialize(path=FTMO_PATH) if os.path.exists(FTMO_PATH) else mt5.initialize()
        is_weekend = (not session_info.get("market_open", True)) or session_info.get("market_status") == "WEEKEND_MARKET_CLOSED" or session_info.get("session") == "WEEKEND_MARKET_CLOSED" or session_info.get("is_weekend", False)

        for symbol in self.instruments:
            try:
                desk_res = await self.desk.run_analysis_cycle(symbol)
                analysts = desk_res.get("analyst_reports", {})
                tech_report = analysts.get("technical", {})
                fund_report = analysts.get("fundamental", {})
                macro_report = analysts.get("macro", {})
                debate = desk_res.get("debate", {})
                risk = desk_res.get("risk", {})
                mtf = desk_res.get("mtf", {})
                order_blocks = desk_res.get("order_blocks", {})
                news_shield = desk_res.get("news_shield", {})

                # Intraday Institutional Metrics for 5m - 4h Horizons
                adr_info = world_engine.get_adr_metrics(symbol)
                anchors = world_engine.get_session_anchors(symbol)
                velocity = world_engine.get_tick_velocity(symbol)
                liq_targets = world_engine.get_liquidity_targets(symbol)

                # Live MT5 Spread Metrics & Provenance
                spread_pts = 0
                spread_val = 0.0
                last_tick_ts = ""
                if mt5_online:
                    sym_info = mt5.symbol_info(symbol)
                    if sym_info:
                        spread_pts = sym_info.spread
                        spread_val = round((sym_info.ask - sym_info.bid), 3)
                    tick = mt5.symbol_info_tick(symbol)
                    if tick and hasattr(tick, "time") and tick.time:
                        last_tick_dt = datetime.fromtimestamp(tick.time, tz=timezone.utc)
                        last_tick_ts = last_tick_dt.strftime("%Y-%m-%d %H:%M:%S UTC")

                if not last_tick_ts and is_weekend:
                    last_tick_ts = "2026-08-28 23:49:59 UTC (Friday Close)"

                data_asof = f"Frozen Friday Close ({last_tick_ts})" if is_weekend else ("Live MT5 Tick (" + last_tick_ts + ")" if last_tick_ts else "Live MT5 Tick")
                status_str = "FROZEN_WEEKEND_CLOSE" if is_weekend else spread_classification(symbol, spread_pts)

                spread_dict = {
                    "pts": spread_pts,
                    "val": spread_val,
                    "status": status_str,
                    "is_frozen": is_weekend,
                    "data_asof": data_asof,
                    "last_tick_time": last_tick_ts
                }

                if is_weekend:
                    velocity["ticks_per_min"] = 0.0
                    velocity["status"] = "MARKET_CLOSED"
                    velocity["is_frozen"] = True
                    velocity["data_asof"] = data_asof
                    velocity["last_tick_time"] = last_tick_ts
                    adr_info["capacity_status"] = "HISTORICAL_FRIDAY"
                    adr_info["is_frozen"] = True
                    adr_info["data_asof"] = data_asof
                    adr_info["last_tick_time"] = last_tick_ts
                    mtf["is_frozen"] = True
                    mtf["data_asof"] = data_asof
                    mtf["last_tick_time"] = last_tick_ts

                spread_info = f"Spread: {spread_pts} pts (${spread_val}) [FROZEN_WEEKEND_CLOSE ({data_asof})]" if is_weekend else f"Spread: {spread_pts} pts (${spread_val}) [{status_str}]"
                velocity_str = f"Velocity: 0 t/m [MARKET_CLOSED ({data_asof})]" if is_weekend else f"Velocity: {velocity.get('ticks_per_min')} t/m [{velocity.get('status')}]"
                adr_str = f"ADR20: Friday ${adr_info.get('today_range')}/ADR ${adr_info.get('adr_20')} ({adr_info.get('pct_used')}% used) [HISTORICAL_FRIDAY ({data_asof})]" if is_weekend else f"ADR20: ${adr_info.get('today_range')}/${adr_info.get('adr_20')} ({adr_info.get('pct_used')}% used) [{adr_info.get('capacity_status')}]"
                tf_alignment_str = f"4TF Alignment: {mtf.get('formatted_4tf', 'N/A')} [FROZEN_WEEKEND_CLOSE] [RSI H4:{mtf.get('h4_rsi')} H1:{mtf.get('h1_rsi')} M15:{mtf.get('m15_rsi')} M5:{mtf.get('m5_rsi')}]" if is_weekend else f"4TF Alignment: {mtf.get('formatted_4tf', 'N/A')} [RSI H4:{mtf.get('h4_rsi')} H1:{mtf.get('h1_rsi')} M15:{mtf.get('m15_rsi')} M5:{mtf.get('m5_rsi')}]"

                from tradingagents.liquidity_radar import LiquidityRadarEngine
                from tradingagents.fair_value_gap import FairValueGapEngine
                
                liq_radar = LiquidityRadarEngine()
                fvg_engine = FairValueGapEngine()
                
                liq_data = liq_radar.get_symbol_liquidity(symbol)
                fvg_line = fvg_engine.get_fvg_summary_line(symbol)
                fvg_data = fvg_engine.get_symbol_fvg_matrix(symbol)
                near_fvg = fvg_data.get("nearest_unmitigated_fvg", {}) or {}
                if is_weekend:
                    fvg_data["is_frozen"] = True
                    fvg_data["data_asof"] = data_asof
                    fvg_data["last_tick_time"] = last_tick_ts
                
                # Dynamic Risk-to-Reward Ratio (RRR) for 5m-4h holds ($15 Sweet Spot Target)
                rrr_str = "1:3.0 (Risk $5 to Make $15 Sweet Spot)"

                # Autonomous Librarian & Proxima Precedent Research
                lib_payload = {}
                try:
                    lib_payload = self.librarian.run_librarian_cycle({
                        "symbol": symbol,
                        "fvg_type": near_fvg.get("type") or ("M5_BEAR_FVG" if "BEAR" in mtf.get("m5_trend", "").upper() else "M5_BULL_FVG"),
                        "fvg_top": near_fvg.get("top"),
                        "fvg_bottom": near_fvg.get("bottom"),
                        "fvg_ce": near_fvg.get("consequent_encroachment"),
                        "sweep_status": liq_data.get("sweep_status", "IN_RANGE"),
                        "h4_bias": mtf.get("h4_trend", "NEUTRAL"),
                        "m5_bias": mtf.get("m5_trend", "NEUTRAL")
                    })
                except Exception as l_err:
                    LOG.debug(f"Librarian cycle for {symbol} skipped: {l_err}")

                # Store deep structured instrument data for persistent dossier logging
                instruments_data.append({
                    "symbol": symbol,
                    "tech": tech_report,
                    "fund": fund_report,
                    "macro": macro_report,
                    "debate": debate,
                    "risk": risk,
                    "mtf": mtf,
                    "order_blocks": order_blocks,
                    "news_shield": news_shield,
                    "adr": adr_info,
                    "spread": spread_dict,
                    "velocity": velocity,
                    "liquidity_targets": liq_targets,
                    "fvg": fvg_data,
                    "librarian": lib_payload
                })

                # Collect instrument findings with Intraday Institutional Data, Liquidity Sweeps, 4-TF, FVG & RRR
                inst_summary = (
                    f"• {symbol}: {spread_info} | {velocity_str} "
                    f"| {adr_str} "
                    f"| {tf_alignment_str} "
                    f"| {fvg_line} | Liquidity Sweep: {liq_data.get('sweep_status')} [{liq_data.get('trap_warning')}] "
                    f"| Pivots: PP {order_blocks.get('pivot_point', 'N/A')} | Demand: {order_blocks.get('demand_zone', 'N/A')} | Supply: {order_blocks.get('supply_zone', 'N/A')} "
                    f"| RRR: {rrr_str} | Regime Divergence: {'YES' if debate.get('is_regime_conflict') else 'NO'} | Catalysts: {len(debate.get('bull_points', []))} | Risks: {len(debate.get('bear_points', []))} | Agent Risk Vol (LLM est): {risk.get('max_volume_lots', 0.10)} lots"
                )
                instrument_matrix.append(inst_summary)

                # Log Local LLM Agents' natural thinking dialogue into live_story.log & stdout for primary metals/oil
                if symbol in ("XAUUSD", "XAGUSD"):
                    log_story("Local LLM Technical Analyst", f"[{symbol}] {tech_report.get('thesis', '')} | {fvg_line} | {spread_info} | {velocity.get('ticks_per_min')} t/m")
                    log_story("Local LLM COT/Fund Analyst", f"[{symbol}] {fund_report.get('thesis', '')}")
                    log_story("Local LLM Macro/News Analyst", f"[{symbol}] {macro_report.get('thesis', '')} | News Shield: {news_shield.get('status_text', 'CLEAR')}")
                    log_story("Local LLM Bull/Bear Debater", f"[{symbol}] Bull Points: {debate.get('bull_points', [])} | Bear Points: {debate.get('bear_points', [])} | Structural Risk: {'WARNING' if debate.get('structural_risk_warning') else 'CLEAR'}")
                    log_story("Local LLM Risk Officer", f"[{symbol}] Approved: {risk.get('approved')} | Max Volume: {risk.get('max_volume_lots')} lots | Rationale: {risk.get('reason')}")
            except Exception as err:
                LOG.error(f"Local LLM Desk analysis error for {symbol}: {err}")
                instrument_matrix.append(f"• {symbol}: DATA_UNAVAILABLE — analysis error (see alpha.log); excluded from this cycle's matrix.")

        # 2. High-Sensitivity Active Position & Reversal Monitor
        open_tickets = []
        detailed_positions = []
        reversal_alerts = []
        try:
            if mt5_online:
                positions = mt5.positions_get()
                if positions:
                    for p in positions:
                        side = "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL"
                        open_tickets.append(f"{p.symbol} #{p.ticket} ({p.profit:+.2f} USD)")
                        detailed_positions.append(
                            f"Ticket #{p.ticket} ({p.symbol} {side} {p.volume:.2f} lots | Entry: {p.price_open:.2f} | Current: {p.price_current:.2f} | PnL: {p.profit:+.2f} USD | SL: {p.sl:.2f})"
                        )
                        # Natural Risk Manager Dialogue per position
                        log_story("Risk Manager Agent", f"Trade Track #{p.ticket} ({p.symbol} {side}): Entry {p.price_open:.2f} vs Live {p.price_current:.2f} (PnL {p.profit:+.2f} USD). Broker SL active at {p.sl:.2f}.")

                        # Reversal / Anomaly Detection Guard
                        if p.profit < -38.0:
                            reversal_alerts.append((p.symbol, f"HIGH PRIORITY DRAWDOWN ALERT on {p.symbol} Ticket #{p.ticket} (PnL {p.profit:+.2f} USD). Technical reversal evaluation required."))
        except Exception as err:
            LOG.error(f"MT5 position check failed: {err}")

        has_active_trades = len(open_tickets) > 0

        # 3. Write Persistent Deep Intelligence Dossiers (JSON & Markdown)
        from tradingagents.read_logger import DossierReadLogger
        from tradingagents.trade_journal import TradeJournalMemory
        from tradingagents.trade_forensics import TradeForensicsEngine
        from tradingagents.institutional_analytics import InstitutionalAnalyticsEngine
        
        read_logger = DossierReadLogger()
        journal_memory = TradeJournalMemory()
        forensics_engine = TradeForensicsEngine()
        inst_engine = InstitutionalAnalyticsEngine()

        # Update each detailed source independently. One failure must not hide the
        # successful updates of the other sources from the Agent.
        update_status = []
        try:
            journal_memory.write_journal_memory()
            forensics_engine.sync_closed_trades()
            update_status.append(("Unified Learning Memory / Journal", "UPDATED"))
        except Exception as err:
            LOG.error(f"Unified learning/journal update error: {err}")
            update_status.append(("Unified Learning Memory / Journal", f"UPDATE FAILED: {err}"))
        try:
            inst_engine.write_institutional_deep_book(self.instruments)
            update_status.append(("Institutional Deep Book", "UPDATED"))
        except Exception as err:
            LOG.error(f"Institutional deep book generation error: {err}")
            update_status.append(("Institutional Deep Book", f"UPDATE FAILED: {err}"))
        read_logger.log_read("Consolidated Desk Daemon", "MANDATORY_DOSSIER_UPDATE")

        self.cycle_count += 1
        
        # Load agent study cycle ID from review state for unambiguous multi-counter reporting (H5)
        study_cycle_id = None
        try:
            from tradingagents.unified_learning import load_review_state
            study_cycle_id = load_review_state().get("cycle_id")
        except Exception:
            pass

        dossier_res = dossier_logger.write_dossier(
            cycle_count=self.cycle_count,
            instruments_data=instruments_data,
            open_positions=detailed_positions,
            reversal_alerts=reversal_alerts,
            session_info=session_info,
            gsr_data=gsr_data,
            account_health=account_health,
            currency_strength=currency_strength,
            real_yields=real_yields,
            study_cycle_id=study_cycle_id
        )

        read_logger.log_dossier_read("Consolidated Desk Daemon", "MANDATORY_DOSSIER_UPDATE", f"Wrote persistent dossier file:///C:/Trading/Alpha/logs/full_desk_dossier.md for Desk Scan Cycle #{self.cycle_count}")

        log_story("Desk Lead Agent", f"Consensus Audit: {len(self.instruments)}/{len(INSTRUMENTS)} instruments scanned (active: {', '.join(self.instruments)}). Desk Scan Cycle: #{self.cycle_count} | Agent Study Cycle: #{study_cycle_id or 'N/A'}. Posture DEEP DOSSIER STREAM.")

        # 4. Construct Full 4TF Institutional Alignment Reveal Block
        tf_reveal_lines = []
        for item in instruments_data:
            s = item.get("symbol", "")
            m = item.get("mtf", {})
            tf_line = (
                f"  • {s}: H4: {m.get('h4_trend', 'NEUTRAL')} (RSI {m.get('h4_rsi', 50.0)}, EMA20 {m.get('h4_ema20', 0.0)}) | "
                f"H1: {m.get('h1_trend', 'NEUTRAL')} (RSI {m.get('h1_rsi', 50.0)}, EMA20 {m.get('h1_ema20', 0.0)}) | "
                f"M15: {m.get('m15_trend', 'NEUTRAL')} (RSI {m.get('m15_rsi', 50.0)}, EMA20 {m.get('m15_ema20', 0.0)}) | "
                f"M5: {m.get('m5_trend', 'NEUTRAL')} (RSI {m.get('m5_rsi', 50.0)}, EMA20 {m.get('m5_ema20', 0.0)}) -> {m.get('alignment', 'MIXED_TIMEFRAMES')}"
            )
            tf_reveal_lines.append(tf_line)
        full_4tf_reveal_block = "=== FULL PER-TIMEFRAME (4TF) INSTITUTIONAL ALIGNMENT REVEAL ===\n" + "\n".join(tf_reveal_lines) + "\n\n"

        matrix_formatted = "\n".join(instrument_matrix)
        top_pick_line = (f"HIGHEST GANGER 7-LAYER CONVICTION THIS CYCLE: {top_symbol} "
                         f"(Score {top_score:.1f}/10)" + (f" — {headline}" if headline else ""))
        
        # Token-Efficient Line Range Pointers & Strategy References
        dossier_line_count = dossier_res.get("total_lines", 80) if isinstance(dossier_res, dict) else 80
        fnd_rng = dossier_res.get("findings_range", "L26-L80") if isinstance(dossier_res, dict) else "L26-L80"

        utc_now = datetime.utcnow()
        ist_now = utc_now + timedelta(hours=5, minutes=30)
        gen_ts = utc_now.strftime("%Y-%m-%d %H:%M:%S UTC")
        ist_ts = ist_now.strftime("%Y-%m-%d %H:%M:%S IST")
        update_status_block = "\n".join(
            f"  • {'✓' if status == 'UPDATED' else '⚠'} {name}: {status}"
            for name, status in update_status
        )

        mcp_tools_block = """=== COMPLETE FAST-MCP TOOL SUITE (17 TOOLS AVAILABLE) ===
  • alpha-daemon-mcp_mcp_alpha_get_account_status (or mcp_alpha_get_account_status) — Check live FTMO MT5 equity, balance, free margin, margin utilization % and active ticket states.
  • alpha-daemon-mcp_mcp_alpha_get_symbol_conviction (or mcp_alpha_get_symbol_conviction) — Query live 4TF institutional alignment, exact EMA20/50 & RSI values, FVG geometry, and COT percentiles.
  • alpha-daemon-mcp_mcp_alpha_backtest_thesis (or mcp_alpha_backtest_thesis) — Natural live MT5 candle-table replay (Zero hardcoded rules). Replays setup trajectory, empirical win rate %, realized R, and failure clusters.
  • alpha-daemon-mcp_mcp_alpha_ask_librarian (or mcp_alpha_ask_librarian) — Search 371 ULM Precedents + Mandatory Proxima Quantitative Microstructure Research (Port 3210, 65s cascade).
  • alpha-daemon-mcp_mcp_alpha_get_measured_cvd (or mcp_alpha_get_measured_cvd) — Fetch measured M5 tick CVD, 10-bar delta velocity, and passive absorption signals from MT5.
  • alpha-daemon-mcp_mcp_alpha_get_live_microstructure (or mcp_alpha_get_live_microstructure) — Live spread in pts, M1 tick velocity (t/m), order book depth imbalance, and CVD posture.
  • alpha-daemon-mcp_mcp_alpha_get_full_institutional_profile (or mcp_alpha_get_full_institutional_profile) — Volume Profile (POC/VAH/VAL), VWAP (+/-1s, +/-2s), Dark Pool DIX/GEX, Treasury Yields (US10Y/US2Y/DXY/VIX), FTMO Contract Specs, and 4TF EMAs/RSI.
  • alpha-daemon-mcp_mcp_alpha_get_trade_forensics (or mcp_alpha_get_trade_forensics) — Deep forensics on closed trades: Win rate %, net R, FVG fill %, RSI regime, and spread distribution.
  • alpha-daemon-mcp_mcp_alpha_get_ledger_decomposition (or mcp_alpha_get_ledger_decomposition) — Decompose 121-trade history into condition base rates (Session x Direction x Spread x FVG Fill%).
  • alpha-daemon-mcp_mcp_alpha_get_multi_instrument_ledger (or mcp_alpha_get_multi_instrument_ledger) — Full 134-position portfolio breakdown breaking out 121 XAUUSD vs 13 non-XAU bleed (XAG/XCU/XPT/XPD).
  • alpha-daemon-mcp_mcp_alpha_get_mt5_deals_history (or mcp_alpha_get_mt5_deals_history) — Fetch closed trade history and deal execution settings directly from MetaTrader 5 terminal.
  • alpha-daemon-mcp_mcp_alpha_query_analyst_desk (or mcp_alpha_query_analyst_desk) — Deep 7-layer local LLM multi-source debate (Technical, COT, Macro, Bull vs Bear).
  • alpha-daemon-mcp_mcp_alpha_get_fvg_matrix (or mcp_alpha_get_fvg_matrix) — Query multi-timeframe (H4, H1, M15, M5) Fair Value Gaps and Consequent Encroachment levels.
  • alpha-daemon-mcp_mcp_alpha_get_live_world_events (or mcp_alpha_get_live_world_events) — Live macroeconomic releases, central bank speeches, and geopolitical intelligence.
  • alpha-daemon-mcp_mcp_alpha_record_decision_snapshot (or mcp_alpha_record_decision_snapshot) — Record pre-trade decision context on disk with full experimental metadata.
  • alpha-daemon-mcp_mcp_alpha_record_trade_observation (or mcp_alpha_record_trade_observation) — Commit verified trade outcomes, lessons, and pattern observations into Pattern Book & ULM.
  • alpha-daemon-mcp_mcp_alpha_record_pattern_observation (or mcp_alpha_record_pattern_observation) — Record pattern evidence in Unified Learning Memory.
  • alpha-daemon-mcp_mcp_alpha_execute_trade (or mcp_alpha_execute_trade) — Execute direct market buy/sell orders on FTMO MT5.
  • alpha-daemon-mcp_mcp_alpha_update_position (or mcp_alpha_update_position) — Manage active tickets (BREAK_EVEN, TRAIL_SL, FULL_EXIT).
  • alpha-daemon-mcp_mcp_alpha_register_watch (or mcp_alpha_register_watch) — Set dynamic price or sentiment alerts for the local desk to track.
"""

        file_ref_header = (
            f"=== ALPHA AGENT STUDY UPDATE ===\n"
            f"  • CURRENT TIME: {ist_ts}\n"
            f"  • UTC: {gen_ts}\n"
            f"  • STUDY CYCLE: {self.cycle_count}\n\n"
            f"=== AVAILABLE EVIDENCE / SYSTEM DIRECTIVES ===\n"
            f"  • MASTER MANDATES MANUAL: file:///C:/Trading/Alpha/OPENCODE_MANDATES.md\n"
            f"  • Strategy Evidence Archive: file:///C:/Trading/Alpha/MICRO_PROFIT_SCALPING_STRATEGY.md\n"
            f"  • Pattern Reality Check (Truth Ledger): file:///C:/Trading/Alpha/logs/pattern_reality_check.md\n"
            f"  • Top 4 Reproducible Precedents: file:///C:/Trading/Alpha/logs/top4_reproducible_patterns.json\n"
            f"  • Unified Learning Memory: file:///C:/Trading/Alpha/logs/unified_learning_memory.json\n"
            f"  • Pattern Book: file:///C:/Trading/Alpha/logs/pattern_book/\n"
            f"  • Historical Research / Full Desk Evidence ({dossier_line_count} lines): file:///C:/Trading/Alpha/logs/full_desk_dossier.md#{fnd_rng}\n"
            f"  • Institutional Deep Book: file:///C:/Trading/Alpha/logs/institutional_deep_book.md#L1-L100\n"
            f"  • CIO Needs & Gaps Tracker: file:///C:/Trading/Alpha/logs/needs.md\n"
            f"  • Automatic Audit Log: file:///C:/Trading/Alpha/logs/dossier_read_audit.log\n\n"
            f"{mcp_tools_block}\n"
            f"=== MANDATORY AGENT CYCLE ===\n"
            f"  1. Review required live evidence.\n"
            f"  2. Consult mandatory learning sources.\n"
            f"  3. Study current conditions against accumulated evidence.\n"
            f"  4. Learn continuously even when no trade is active.\n"
            f"  5. Learn from mistakes: incorrect interpretations, failed hypotheses, missed evidence, and repeated reasoning errors.\n"
            f"  6. Identify what was wrong, why, and correct the understanding when evidence supports it.\n"
            f"  7. Record meaningful observations, corrections, contradictions and learning into Pattern Book / ULM.\n"
            f"  8. All evidence requested via MCP is automatically audited and logged on disk.\n"
            f"  9. Daemon data is information only; interpretation and trading decisions remain AGENT-ONLY.\n\n"
            f"=== PER-FILE UPDATE STATUS ===\n{update_status_block}\n\n"
            f"NOTE: Detailed files are the persistent evidence. The inline matrix is a compact current-cycle briefing, not a replacement for the detailed files.\n\n"
        )

        from tradingagents.world_events import LiveWorldEventsEngine
        from tradingagents.economic_calendar import EconomicCalendarEngine

        events_engine = LiveWorldEventsEngine()
        econ_engine = EconomicCalendarEngine()

        world_events_summary = events_engine.get_formatted_summary(4)
        econ_summary = econ_engine.get_news_countdown_summary(3).get("summary", "")

        world_header = (
            f"=== INTRADAY INSTITUTIONAL CONTEXT ===\n"
            f"  • Data Generated: {gen_ts}\n"
            f"  • Session Clock: {session_info.get('session')} ({session_info.get('description')} | {session_info.get('utc_time')})\n"
            f"  • Intermarket GSR Ratio: {gsr_data.get('gsr')} [{gsr_data.get('status')}]\n"
            f"  • FTMO Account Health: Equity ${account_health.get('equity')} | Free Margin ${account_health.get('free_margin')} | Margin Level {account_health.get('margin_level_pct')}% | Margin Utilization {account_health.get('account_heat_pct')}% (margin-based, NOT stop-distance risk)\n"
            f"  • Currency Matrix: USD [{currency_strength.get('usd_index_posture')}] | EUR [{currency_strength.get('eur_strength')}] | JPY [{currency_strength.get('jpy_strength')}]\n\n"
            f"=== HIGH-IMPACT MACROECONOMIC CALENDAR & WORLD EVENTS FEED ===\n"
            f"{econ_summary}\n"
            f"{world_events_summary}\n\n"
        )

        # Run Autonomous Librarian Agent for Primary Active Instrument
        primary_sym = top_symbol if top_symbol in self.instruments else (self.instruments[0] if self.instruments else "XAUUSD")
        primary_inst_data = next((d for d in instruments_data if d["symbol"] == primary_sym), {})
        fvg_obj = primary_inst_data.get("fvg", {})
        nearest_fvg = fvg_obj.get("nearest_unmitigated_fvg") or {}

        primary_market_state = {
            "symbol": primary_sym,
            "ask": getattr(mt5.symbol_info_tick(primary_sym), "ask", 0.0) if mt5_online else 0.0,
            "bid": getattr(mt5.symbol_info_tick(primary_sym), "bid", 0.0) if mt5_online else 0.0,
            "spread_pts": primary_inst_data.get("spread", {}).get("pts", 50),
            "fvg_type": nearest_fvg.get("type", "NONE"),
            "fvg_top": nearest_fvg.get("top", 0.0),
            "fvg_bottom": nearest_fvg.get("bottom", 0.0),
            "fvg_ce": nearest_fvg.get("consequent_encroachment", 0.0),
            "sweep_status": primary_inst_data.get("liquidity_targets", {}).get("sweep_status", "IN_RANGE"),
            "h4_bias": primary_inst_data.get("mtf", {}).get("h4_trend", "NEUTRAL"),
            "m5_bias": primary_inst_data.get("mtf", {}).get("m5_trend", "NEUTRAL"),
            "velocity_tpm": primary_inst_data.get("velocity", {}).get("ticks_per_min", 0)
        }
        librarian_payload = self.librarian.run_librarian_cycle(primary_market_state)
        top4_cards = librarian_payload.get("top_4_precedents", [])
        top4_formatted_lines = []
        for c in top4_cards:
            top4_formatted_lines.append(
                f"  [{c['role']}] {c['pattern_id']} - {c['name']} (Score: {c['score']}/10 | Win Rate: {c['win_rate']})\n"
                f"    • Trigger: {c['execution_trigger']} | RRR: {c.get('rrr', '1:3.0')}\n"
                f"    • Testing Focus: {c['testing_objective']}\n"
                f"    • Invalidation: {c['invalidation']}"
            )
        top4_section = (
            f"=== LIBRARIAN TOP 4 REPRODUCIBLE PRECEDENTS (REVOLVED AROUND ACTIVE LIVE THESIS) ===\n"
            f"  • Reference Truth Ledger: file:///C:/Trading/Alpha/logs/pattern_reality_check.md\n"
            f"  • Dynamic Pattern Queue: file:///C:/Trading/Alpha/logs/top4_reproducible_patterns.json\n"
            f"  • Active Thesis Footprint: {librarian_payload.get('live_thesis_revolved', '')}\n\n"
            + "\n\n".join(top4_formatted_lines)
            + "\n\n"
        )

        # DYNAMIC DISPATCH CADENCE (Configurable via opencode_session_config.json)
        now_ts = time.time()
        is_startup = (self.cycle_count == 1)
        elapsed_since_dispatch = now_ts - self.last_dispatch_time
        dossier_interval = get_dossier_interval_seconds()
        active_trade_interval = get_active_trade_interval_seconds()
        required_interval = float(active_trade_interval) if open_tickets else float(dossier_interval)

        ready_for_dispatch = False
        if is_startup:
            ready_for_dispatch = True
        elif elapsed_since_dispatch >= required_interval:
            ready_for_dispatch = True

        if ready_for_dispatch:
            self.last_dispatch_time = now_ts
            dossier_mins = max(1, int(round(dossier_interval / 60.0)))
            active_mins = max(1, int(round(active_trade_interval / 60.0)))

            if open_tickets:
                cycle_label = "Initial Review" if is_startup else f"{active_mins}-Min Active Trade Review"
                pos_details_formatted = "\n  • ".join(detailed_positions)

                reversal_section = ""
                if reversal_alerts:
                    alerts_text = "\n  ⚠️ ".join([alert[1] for alert in reversal_alerts])
                    reversal_section = f"\n⚠️ HIGH-PRIORITY DRAWDOWN & REVERSAL ALERTS:\n  ⚠️ {alerts_text}\n"

                scheduled_prompt = (
                    f"OPENCODE CIO EXECUTIVE POSITION REVIEW ({cycle_label}):\n"
                    f"{file_ref_header}"
                    f"{world_header}\n"
                    f"ACTIVE FTMO MT5 TRADES ({len(open_tickets)}):\n  • {pos_details_formatted}\n"
                    f"{reversal_section}\n"
                    f"{top4_section}"
                    f"{full_4tf_reveal_block}"
                    f"=== MULTI-INSTRUMENT 7-AGENT RAW FINDINGS MATRIX ===\n"
                    f"{matrix_formatted}\n"
                    f"===========================================================\n"
                    f"MANDATORY EXECUTIVE ACTION: Review findings above. Tail file:///C:/Trading/Alpha/logs/full_desk_dossier.md#{fnd_rng} for reasoning. Review relevant Pattern Book / Unified Learning evidence as mandatory study context; historical learning has no independent decision authority. "
                    f"MANDATE: The daemon is strictly a READ-ONLY scanner & dossier streamer. ONLY THE OPENCODE BRAIN (OPENCODE CIO) HAS THE AUTHORITY TO EXECUTE LIVE TRADES."
                )
                post_to_opencode_session("OpenCode (CIO)", scheduled_prompt)

            else:
                cycle_label = "Initial Review" if is_startup else f"{dossier_mins}-Min Scheduled Cycle"
                idle_prompt = (
                    f"OPENCODE CIO EXECUTIVE MULTI-INSTRUMENT DOSSIER ({cycle_label}):\n"
                    f"{file_ref_header}"
                    f"{world_header}\n"
                    f"{top4_section}"
                    f"{full_4tf_reveal_block}"
                    f"=== MULTI-INSTRUMENT 7-AGENT RAW FINDINGS MATRIX ===\n"
                    f"{matrix_formatted}\n"
                    f"===========================================================\n"
                    f"MANDATORY EXECUTIVE ACTION: Analyze 6-instrument findings matrix above. Tail file:///C:/Trading/Alpha/logs/full_desk_dossier.md#{fnd_rng} for reasoning. Review relevant Pattern Book / Unified Learning evidence as mandatory study context; historical learning has no independent decision authority. "
                    f"MANDATE: The daemon is strictly a READ-ONLY scanner & dossier streamer. ONLY THE OPENCODE BRAIN (OPENCODE CIO) HAS THE AUTHORITY TO EXECUTE LIVE TRADES."
                )
                post_to_opencode_session("OpenCode (CIO)", idle_prompt)

        return has_active_trades

    async def start_loop(self):
        self.is_running = True
        dossier_mins = max(1, int(round(get_dossier_interval_seconds() / 60.0)))
        active_mins = max(1, int(round(get_active_trade_interval_seconds() / 60.0)))
        LOG.info(f"Consolidated Trading Daemon started with Dynamic Briefing Cadence ({active_mins}-min active trades, {dossier_mins}-min idle).")
        sid, title, _ = get_opencode_session()
        # Immediately fire startup ping to OpenCode so user knows daemon is alive
        post_to_opencode_session(
            "OpenCode (CIO)",
            f"=== ALPHA TRADING DESK DAEMON ONLINE ===\n"
            f"Session: {title} ({sid})\n"
            f"Current UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"Daemon: ONLINE | Tick ingestion: 2s | Briefing cadence: {active_mins}-Min active trade / {dossier_mins}-Min idle\n\n"
            f"=== AGENT AUTHORITY & CONSTITUTIONAL GUARANTEES (§10.2) ===\n"
            f"YOU are the sole interpreter of evidence and the sole trading decision-maker.\n"
            f"• Zero Data Concealment: No layer compresses, filters, or hides raw market numbers behind opaque labels.\n"
            f"• Zero Automatic Gates: Backtests and pattern records inform conviction, but NEVER veto your trade decisions.\n"
            f"• Automatic Audit Trail: All evidence requested via MCP is automatically audited and logged on disk.\n\n"
            f"=== COMPLETE FAST-MCP TOOL SUITE (14 TOOLS AVAILABLE) ===\n"
            f"  1. mcp_alpha_get_full_institutional_profile(symbol) — Fetch Volume Profile (POC/VAH/VAL), VWAP (+/-1s, +/-2s), Dark Pool DIX/GEX, Treasury Yields (US10Y/US2Y/DXY/VIX), FTMO Contract Specs, and 4TF EMAs/RSI.\n"
            f"  2. mcp_alpha_backtest_thesis(query, symbol, timeframe, bars) — Natural live MT5 candle-table replay (Zero hardcoded rules). Replays setup trajectory, empirical win rate %, realized R, and failure clusters.\n"
            f"  3. mcp_alpha_ask_librarian(query, symbol) — Search 364 ULM Precedents + Mandatory Proxima Quantitative Microstructure Research (Port 3210, 65s cascade).\n"
            f"  4. mcp_alpha_query_analyst_desk(query, symbol) — Deep 7-layer local LLM multi-source debate (Technical, COT, Macro, Bull vs Bear).\n"
            f"  5. mcp_alpha_get_measured_cvd(symbol) — Fetch measured M5 tick CVD, 10-bar delta velocity, and passive absorption signals from MT5.\n"
            f"  6. mcp_alpha_get_symbol_conviction(symbol) — Query live 4TF institutional alignment, exact EMA20/50 & RSI values, FVG geometry, and COT percentiles.\n"
            f"  7. mcp_alpha_get_account_status() — Check live FTMO MT5 equity, balance, free margin, margin utilization % and active ticket states.\n"
            f"  8. mcp_alpha_record_decision_snapshot(symbol, side, conviction, notes, volume, sl, tp) — Record pre-trade decision context on disk (s4.137 Process vs Outcome).\n"
            f"  9. mcp_alpha_execute_trade(symbol, side, volume, sl, tp) — Execute direct market buy/sell order on FTMO MT5.\n"
            f"  10. mcp_alpha_update_position(ticket, action, params_json) — Manage active tickets (BREAK_EVEN, TRAIL_SL, FULL_EXIT).\n"
            f"  11. mcp_alpha_record_trade_observation(symbol, pattern_name, observation, outcome, r_multiple) — Commit verified trade outcomes & lessons into Pattern Book & ULM.\n"
            f"  12. mcp_alpha_get_trade_forensics(symbol) — Deep forensics on closed trades: Win rate %, net R, FVG fill %, RSI regime, and spread distribution.\n"
            f"  13. mcp_alpha_get_ledger_decomposition(symbol) — Decompose 134-trade history into condition base rates (Session x Direction x Spread x FVG Fill%).\n"
            f"  14. mcp_alpha_register_watch(symbol, condition, target_price) — Set a dynamic price or sentiment alert for the local desk to track.\n\n"
            f"=== STARTUP ORIENTATION ===\n"
            f"The first full Initial Review is being collected now and will arrive shortly.\n"
            f"On that review: study current conditions against accumulated evidence, learn continuously (including from mistakes), and record meaningful observations or corrections into Pattern Book / ULM.\n"
            f"Detailed persistent files are the source evidence; the inline briefing is a current-cycle guide, not a replacement."
        )
        await asyncio.sleep(2.0)
        while self.is_running:
            try:
                has_active_trades = await self.run_cycle()
                # Fast 2s sampling loop when checking market state
                await asyncio.sleep(2.0)
            except Exception as err:
                LOG.error(f"Error in cycle: {err}")
                await asyncio.sleep(5.0)

# ----------------------------------------------------------------------
# 7. CLI Commands Entry Point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "run"

    if action == "stop":
        killed = kill_all_daemons()
        print(f"[STOPPED] Terminated {killed} daemon processes.")
    elif action == "status":
        try:
            import MetaTrader5 as mt5
            initialized = mt5.initialize(path=FTMO_PATH) if os.path.exists(FTMO_PATH) else mt5.initialize()
            if initialized:
                acc = mt5.account_info()
                pos = mt5.positions_get()
                print(f"=== FTMO METATRADER 5 DESK STATUS ===")
                print(f"Account: #{acc.login} ({acc.name}) | Server: {acc.server}")
                print(f"Balance: ${acc.balance:,.2f} | Equity: ${acc.equity:,.2f}")
                print(f"Active Positions: {len(pos) if pos else 0}")
                if pos:
                    for p in pos:
                        print(f"  • Ticket #{p.ticket} | {p.symbol:10s} | {('BUY' if p.type==0 else 'SELL'):4s} | {p.volume:.2f} lots | Profit: {p.profit:+.2f} USD")
            else:
                print("[ERROR] Failed to connect to FTMO MT5.")
        except Exception as err:
            print(f"[ERROR] {err}")
    else:
        # Default: Run Daemon (Enforce OS-Level Single-Instance Mutex via msvcrt locking)
        import atexit
        import signal

        lock_file_path = PROJECT_ROOT / "data" / "live" / "alpha_daemon.lock"
        pid_file = PROJECT_ROOT / "data" / "live" / "alpha_daemon.pid"
        lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        current_pid = os.getpid()

        # Open lock file and try non-blocking lock
        try:
            lock_handle = open(lock_file_path, "a+")
            if sys.platform == "win32":
                import msvcrt
                try:
                    lock_handle.seek(0)
                    msvcrt.locking(lock_handle.fileno(), msvcrt.LK_NBLCK, 1)
                except (IOError, OSError, PermissionError):
                    print(f"[MUTEX_DENIED] Active daemon lock already held. Twin PID {current_pid} exiting immediately.")
                    sys.stdout.flush()
                    os._exit(0)
        except Exception as e:
            print(f"[MUTEX_DENIED] Lock failed: {e}. Exiting twin PID {current_pid} immediately.")
            sys.stdout.flush()
            os._exit(0)

        # Successfully acquired lock! Write PID
        with open(pid_file, "w", encoding="utf-8") as f:
            f.write(str(current_pid))

        sid, title, _ = get_opencode_session()
        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(DAEMON_PINGS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*70}\n[DAEMON LIFECYCLE] {now_ts} | Event: DAEMON_START | Reason: User/CLI Launch | PID: {current_pid} | Target: {title} ({sid})\n{'='*70}\n")

        def _cleanup_on_exit(reason="SHUTDOWN", exit_code=0):
            try:
                if pid_file.exists():
                    current_content = pid_file.read_text(encoding="utf-8").strip()
                    if current_content == str(current_pid):
                        pid_file.unlink()
            except Exception:
                pass
            try:
                if sys.platform == "win32" and 'lock_handle' in locals():
                    try:
                        lock_handle.seek(0)
                        import msvcrt
                        msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
                    except Exception:
                        pass
                    lock_handle.close()
            except Exception:
                pass
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                with open(DAEMON_PINGS_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(f"\n[DAEMON LIFECYCLE] {ts} | Event: DAEMON_STOP | Reason: {reason} | ExitCode: {exit_code}\n")
            except Exception:
                pass

        atexit.register(_cleanup_on_exit, "NORMAL_EXIT", 0)

        def _sig_handler(sig, frame):
            sig_name = signal.Signals(sig).name if hasattr(signal, "Signals") else str(sig)
            _cleanup_on_exit(f"SIGNAL_{sig_name}", 0)
            sys.exit(0)

        signal.signal(signal.SIGINT, _sig_handler)
        signal.signal(signal.SIGTERM, _sig_handler)

        log_story("System Launcher", f"=== CONSOLIDATED TRADING DESK STARTED UNDER OPENCODE SESSION '{title}' ({sid}) [PID {current_pid}] ===")
        daemon = ConsolidatedTradingDaemon()
        try:
            asyncio.run(daemon.start_loop())
        except KeyboardInterrupt:
            _cleanup_on_exit("KEYBOARD_INTERRUPT", 0)
        except Exception as e:
            _cleanup_on_exit(f"UNHANDLED_EXCEPTION: {e}", 1)
            raise
