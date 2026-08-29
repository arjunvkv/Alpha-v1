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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure project root paths are in sys.path
PROJECT_ROOT = Path(r"C:\Trading\Alpha")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
TRADING_DIR = Path(r"C:\Trading")
if str(TRADING_DIR) not in sys.path:
    sys.path.insert(0, str(TRADING_DIR))

# Constants
OPENCODE_SESSION_ID = "ses_fb9642e7affeHSS0rTuObAN8Go"
OPENCODE_SESSION_TITLE = "Alpha v4"
FTMO_PATH = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
STORY_LOG_PATH = PROJECT_ROOT / "logs" / "live_story.log"
STATE_FILE_PATH = PROJECT_ROOT / "data" / "live" / "discovery_state.json"
INSTRUMENTS = ["XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD", "XCUUSD", "USOIL.cash"]

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
#   XPDUSD: 40-120 normal -> ceiling 200 (widest normal)
#   XCUUSD: 15-40 normal  -> ceiling 80
#   USOIL:  25-60 normal  -> ceiling 100 (BUFFERED - NOT blocked by global gate)
SPREAD_NORMAL_THRESHOLDS = {
    "XAUUSD": 45,
    "XAGUSD": 70,
    "XPTUSD": 150,
    "XPDUSD": 200,
    "XCUUSD": 80,
    "USOIL.cash": 100,
}
# Elevated is 2x the instrument normal ceiling (beyond that = HIGH_SPIKE).
SPREAD_ELEVATED_FACTOR = 2.0


def spread_classification(symbol: str, spread_pts: float) -> str:
    """Classify a spread as NORMAL / ELEVATED / HIGH_SPIKE using the per-symbol
    buffered ceiling. Falls back to the legacy 45-80 global scale for unknown symbols."""
    floor = SPREAD_NORMAL_THRESHOLDS.get(symbol, 45)
    elevated = floor * SPREAD_ELEVATED_FACTOR
    if spread_pts <= floor:
        return "NORMAL"
    elif spread_pts <= elevated:
        return "ELEVATED"
    else:
        return "HIGH_SPIKE"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
LOG = logging.getLogger("alpha.trading_desk")

# ----------------------------------------------------------------------
# 1. Story Logger & Resilient OpenCode HTTP Session Streamer Module
# ----------------------------------------------------------------------
def post_to_opencode_session(speaker: str, message: str):
    """ALWAYS log communication intent first to live_story.log and stdout log, then attempt background HTTP POST to dynamic active OpenCode session Alpha v3."""
    log_story(speaker, message)
    LOG.info(f"\n=== [COMMUNICATION LOG STREAM] ===\nSpeaker: {speaker}\nTarget Session: {OPENCODE_SESSION_ID} ({OPENCODE_SESSION_TITLE})\nPayload Message:\n{message[:200]}...\n===================================\n")

    def _send():
        try:
            import socket
            import urllib.request

            # Always target the confirmed active Alpha v3 session — hardcoded for reliability
            target_sid = OPENCODE_SESSION_ID

            payload = json.dumps({
                "parts": [{"type": "text", "text": f"[{speaker}] {message}"}]
            }).encode("utf-8")

            path = f"/session/{target_sid}/message"
            http_req = (
                f"POST {path} HTTP/1.1\r\n"
                f"Host: localhost:4096\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(payload)}\r\n"
                f"Connection: close\r\n"
                f"\r\n"
            ).encode("utf-8") + payload

            # Fire-and-forget: connect, send, read first response line, disconnect
            try:
                sock = socket.create_connection(("localhost", 4096), timeout=5)
                sock.sendall(http_req)
                sock.settimeout(2)
                try:
                    first_line = sock.recv(64).decode("utf-8", errors="ignore")
                    LOG.info(f"Fired prompt to {OPENCODE_SESSION_TITLE} session {target_sid}: {first_line.strip()}")
                except Exception:
                    LOG.info(f"Fired prompt to {OPENCODE_SESSION_TITLE} session {target_sid} (no response read)")
                sock.close()
            except Exception as err:
                LOG.error(f"Socket fire-and-forget to {target_sid} failed: {err}")

        except Exception as err:
            LOG.error(f"Post payload creation failed: {err}")

    import threading
    threading.Thread(target=_send, daemon=True).start()

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

def is_opencode_idle(session_id: str = OPENCODE_SESSION_ID) -> bool:
    """Check if OpenCode Alpha v3 session is ready to receive alerts. Always defaults to True to guarantee reliable 3-min and startup dispatch."""
    try:
        import urllib.request
        url = f"http://localhost:4096/session/{session_id}/message"
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
        self.session_id = OPENCODE_SESSION_ID
        self.session_title = OPENCODE_SESSION_TITLE

    def evaluate_discovery_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        symbol = event.get("symbol", "XAUUSD")
        score = float(event.get("conviction_score") or event.get("score") or 0.0)
        bull_points = event.get("bull_points", [])
        bear_points = event.get("bear_points", [])
        summary = (
            f"Discovery evidence update for {symbol}: consensus/conviction score {score}/10. "
            f"Supporting evidence: {bull_points or 'none supplied'}. "
            f"Contradictory evidence: {bear_points or 'none supplied'}. "
            f"This is study evidence only; no score threshold approves, vetoes, or executes a trade."
        )
        log_opencode_said(summary)
        return {
            "decision": "AGENT_REVIEW_REQUIRED",
            "symbol": symbol,
            "conviction_score": score,
            "supporting_evidence": bull_points,
            "contradictory_evidence": bear_points,
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
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.pid == current_pid:
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

        self.desk = TradingAgentsDesk()
        self.mcp_server = AlphaMCPServer()
        self.latch = StatefulDiscoveryLatch()
        self.cio_evaluator = OpenCodeCIOEvaluator()  # evidence streamer only; never executes
        self.instruments = INSTRUMENTS
        self.is_running = False
        self.cycle_count = 0
        self.last_dispatch_time = 0.0
        self.last_reversal_dispatch_time = 0.0

    async def run_cycle(self):
        LOG.info(f"--- Starting Scan Cycle across {len(self.instruments)} instruments ---")
        log_local_llm_monitoring(f"Scanning market data across {len(self.instruments)} instruments (Granger 7-Layers + Global Eyes RSS feeds active)...")

        scores = []
        top_symbol = "XAUUSD"
        top_score = 0.0
        headline = ""

        from mcp_server.alpha_mcp_server import mcp_alpha_get_symbol_conviction
        for symbol in self.instruments:
            try:
                conv_json = mcp_alpha_get_symbol_conviction(symbol)
                conv_data = json.loads(conv_json)
                score = conv_data.get("conviction_score", 5.0)
                summary = conv_data.get("summary", f"{symbol} Conviction: {score}/10")
            except Exception:
                score = 5.0
                summary = f"{symbol} Conviction: 5.0/10"

            scores.append(score)

            if score > top_score:
                top_score = score
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

                # Live MT5 Spread Metrics (Information for OpenCode decision)
                spread_pts = 0
                spread_val = 0.0
                status_str = "N/A"
                if mt5_online:
                    sym_info = mt5.symbol_info(symbol)
                    if sym_info:
                        spread_pts = sym_info.spread
                        spread_val = round((sym_info.ask - sym_info.bid), 3)
                        status_str = spread_classification(symbol, spread_pts)

                spread_dict = {"pts": spread_pts, "val": spread_val, "status": status_str}
                spread_info = f"Spread: {spread_pts} pts (${spread_val}) [{status_str}]"

                from tradingagents.liquidity_radar import LiquidityRadarEngine
                from tradingagents.fair_value_gap import FairValueGapEngine
                
                liq_radar = LiquidityRadarEngine()
                fvg_engine = FairValueGapEngine()
                
                liq_data = liq_radar.get_symbol_liquidity(symbol)
                fvg_line = fvg_engine.get_fvg_summary_line(symbol)
                fvg_data = fvg_engine.get_symbol_fvg_matrix(symbol)

                # Dynamic Risk-to-Reward Ratio (RRR) for 5m-4h holds ($15 Sweet Spot Target)
                rrr_str = "1:3.0 (Risk $5 to Make $15 Sweet Spot)"

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
                    "fvg": fvg_data
                })

                # Collect instrument findings with Intraday Institutional Data, Liquidity Sweeps, 4-TF, FVG & RRR
                inst_summary = (
                    f"• {symbol}: {spread_info} | Velocity: {velocity.get('ticks_per_min')} t/m [{velocity.get('status')}] "
                    f"| ADR20: ${adr_info.get('today_range')}/${adr_info.get('adr_20')} ({adr_info.get('pct_used')}% used) "
                    f"| 4TF Alignment: {mtf.get('formatted_4tf', 'N/A')} [RSI H4:{mtf.get('h4_rsi')} H1:{mtf.get('h1_rsi')} M15:{mtf.get('m15_rsi')} M5:{mtf.get('m5_rsi')}] "
                    f"| {fvg_line} | Liquidity Sweep: {liq_data.get('sweep_status')} [{liq_data.get('trap_warning')}] "
                    f"| Pivots: PP {order_blocks.get('pivot_point', 'N/A')} | Demand: {order_blocks.get('demand_zone', 'N/A')} | Supply: {order_blocks.get('supply_zone', 'N/A')} "
                    f"| RRR: {rrr_str} | Bull/Bear: {debate.get('consensus_score', 5.0)}/10 | Agent Risk Vol (LLM est): {risk.get('max_volume_lots', 0.10)} lots"
                )
                instrument_matrix.append(inst_summary)

                # Log Local LLM Agents' natural thinking dialogue into live_story.log & stdout for primary metals/oil
                if symbol in ("XAUUSD", "XAGUSD"):
                    log_story("Local LLM Technical Analyst", f"[{symbol}] {tech_report.get('thesis', '')} | {fvg_line} | {spread_info} | {velocity.get('ticks_per_min')} t/m")
                    log_story("Local LLM COT/Fund Analyst", f"[{symbol}] {fund_report.get('thesis', '')}")
                    log_story("Local LLM Macro/News Analyst", f"[{symbol}] {macro_report.get('thesis', '')} | News Shield: {news_shield.get('status_text', 'CLEAR')}")
                    log_story("Local LLM Bull/Bear Debater", f"[{symbol}] Consensus: {debate.get('consensus_score', 5.0)}/10 | Conviction: {debate.get('conviction', 'LOW')} | Institutional Risk: {'WARNING' if debate.get('institutional_risk_warning') else 'CLEAR'}")
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
        dossier_res = dossier_logger.write_dossier(
            cycle_count=self.cycle_count,
            instruments_data=instruments_data,
            open_positions=detailed_positions,
            reversal_alerts=reversal_alerts,
            session_info=session_info,
            gsr_data=gsr_data,
            account_health=account_health,
            currency_strength=currency_strength,
            real_yields=real_yields
        )

        read_logger.log_dossier_read("Consolidated Desk Daemon", "MANDATORY_DOSSIER_UPDATE", f"Wrote persistent dossier file:///C:/Trading/Alpha/logs/full_desk_dossier.md for cycle #{self.cycle_count}")

        log_story("Desk Lead Agent", f"Consensus Audit: 6 Instruments Scanned ({', '.join(self.instruments)}). Persistent Dossier & Read Audit Logged. Posture DEEP DOSSIER STREAM.")

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
        review_state = unified_learning_memory.get_review_status()
        learning_status = review_state.get("learning", {})
        live_status = review_state.get("live", {})
        review_lines = ["=== EVIDENCE REVIEW STATUS ==="]
        for source in ("Live Market State", "Active Positions", "Technical / Multi-Timeframe Detail", "Intermarket Context", "Macro / Calendar / World Events"):
            rec = live_status.get(source, {})
            status = rec.get("status", "READ_REQUIRED")
            interval = rec.get("review_interval_seconds")
            review_lines.append(f"  • {source}: {status}" + (f" (review interval: {interval}s)" if interval else ""))
        review_lines.append("")
        review_lines.append("=== MANDATORY LEARNING — EVERY STUDY CYCLE / NO EXPIRY ===")
        for source in ("Unified Learning Memory", "Pattern Book", "Historical Research", "Strategy Evidence Archive"):
            review_lines.append(f"  • {source}: {learning_status.get(source, {}).get('status', 'READ_REQUIRED')}")
        review_block = "\n".join(review_lines)

        mcp_tools_block = """=== AVAILABLE ALPHA MCP TOOLS — USE WHEN RELEVANT ===
  • mcp_alpha_learning_review — check/start study cycle; mark evidence read after actual review.
  • mcp_alpha_register_watch — register an Agent-requested market watch.
  • mcp_alpha_execute_trade — execute an Agent decision; this tool does not decide.
  • mcp_alpha_update_position — update an existing position when the Agent decides.
  • mcp_alpha_get_account_status — retrieve current account state.
  • mcp_alpha_get_symbol_conviction — retrieve stored symbol conviction context.
  • mcp_alpha_query_analyst_desk — query available analyst/desk evidence.
  • mcp_alpha_get_live_world_events — retrieve current world-event evidence.
  • mcp_alpha_record_pattern_observation — record meaningful pattern/learning observations.
  • mcp_alpha_record_pattern_outcome — record pattern outcome evidence.
  • mcp_alpha_get_book_page — retrieve a specific Pattern Book page.
  • mcp_alpha_search_book — search the Pattern Book for relevant evidence.
  • mcp_alpha_get_book_index — inspect Pattern Book structure/index.
  • mcp_alpha_get_full_book — retrieve the full Pattern Book when necessary.

MANDATORY: Know the available MCP capabilities and use the relevant tool when needed.
Do not call tools mechanically. Study, interpret and decide first; MCP tools retrieve,
record, track or execute the Agent's own decisions and do not have independent
decision authority.
"""

        file_ref_header = (
            f"=== ALPHA AGENT STUDY UPDATE ===\n"
            f"  • CURRENT TIME: {ist_ts}\n"
            f"  • UTC: {gen_ts}\n"
            f"  • STUDY CYCLE: {self.cycle_count}\n\n"
            f"=== AVAILABLE EVIDENCE / SYSTEM DIRECTIVES ===\n"
            f"  • MASTER MANDATES MANUAL: file:///C:/Trading/Alpha/OPENCODE_MANDATES.md\n"
            f"  • Strategy Evidence Archive: file:///C:/Trading/Alpha/MICRO_PROFIT_SCALPING_STRATEGY.md\n"
            f"  • Unified Learning Memory: file:///C:/Trading/Alpha/logs/unified_learning_memory.json\n"
            f"  • Pattern Book: file:///C:/Trading/Alpha/logs/pattern_book/\n"
            f"  • Historical Research / Full Desk Evidence ({dossier_line_count} lines): file:///C:/Trading/Alpha/logs/full_desk_dossier.md#{fnd_rng}\n"
            f"  • Institutional Deep Book: file:///C:/Trading/Alpha/logs/institutional_deep_book.md#L1-L100\n"
            f"  • CIO Needs & Gaps Tracker: file:///C:/Trading/Alpha/logs/needs.md\n"
            f"  • Mandatory Read Audit Trail: file:///C:/Trading/Alpha/logs/dossier_read_audit.log\n\n"
            f"{review_block}\n\n"
            f"  • Use mcp_alpha_learning_review to check/start the study cycle and mark sources read after actual review.\n\n"
            f"{mcp_tools_block}\n"
            f"=== MANDATORY AGENT CYCLE ===\n"
            f"  1. Read required live and due evidence.\n"
            f"  2. Consult all four mandatory learning sources.\n"
            f"  3. Study current conditions against accumulated evidence.\n"
            f"  4. Learn continuously even when no trade is active.\n"
            f"  5. Learn from mistakes: incorrect interpretations, failed hypotheses, missed evidence, missed opportunities and repeated reasoning errors.\n"
            f"  6. Identify what was wrong, why, and correct the understanding when evidence supports it.\n"
            f"  7. Record meaningful observations, corrections, contradictions and learning; do not create duplicate narrative merely because another cycle occurred.\n"
            f"  8. Mark evidence READ only after actual review.\n"
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

        # ADAPTIVE DISPATCH CADENCE (1-Min Active Trade Reviews | 2-Min Idle Scans)
        now_ts = time.time()
        is_startup = (self.cycle_count == 1)
        elapsed_since_dispatch = now_ts - self.last_dispatch_time
        required_interval = 60.0 if open_tickets else 120.0

        ready_for_dispatch = False
        if is_startup:
            ready_for_dispatch = True
        elif elapsed_since_dispatch >= required_interval:
            ready_for_dispatch = True

        if ready_for_dispatch:
            self.last_dispatch_time = now_ts
            is_10min_reminder = (now_ts % 600 < 30)

            if open_tickets:
                cycle_label = "Initial Review" if is_startup else ("10-Min Directive" if is_10min_reminder else "1-Min Active Trade Review")
                pos_details_formatted = "\n  • ".join(detailed_positions)

                reversal_section = ""
                if reversal_alerts:
                    alerts_text = "\n  ⚠️ ".join([alert[1] for alert in reversal_alerts])
                    reversal_section = f"\n⚠️ HIGH-PRIORITY DRAWDOWN & REVERSAL ALERTS:\n  ⚠️ {alerts_text}\n"

                scheduled_prompt = (
                    f"OPENCODE CIO EXECUTIVE POSITION REVIEW ({cycle_label}):\n"
                    f"{file_ref_header}"
                    f"{world_header}{top_pick_line}\n\n"
                    f"ACTIVE FTMO MT5 TRADES ({len(open_tickets)}):\n  • {pos_details_formatted}\n"
                    f"{reversal_section}\n"
                    f"{full_4tf_reveal_block}"
                    f"=== MULTI-INSTRUMENT 7-AGENT RAW FINDINGS MATRIX ===\n"
                    f"{matrix_formatted}\n"
                    f"===========================================================\n"
                    f"MANDATORY EXECUTIVE ACTION: Review findings above. Tail file:///C:/Trading/Alpha/logs/full_desk_dossier.md#{fnd_rng} for reasoning. Review relevant Pattern Book / Unified Learning evidence as mandatory study context; historical learning has no independent decision authority. "
                    f"MANDATE: The daemon is strictly a READ-ONLY scanner & dossier streamer. ONLY THE OPENCODE BRAIN (OPENCODE CIO) HAS THE AUTHORITY TO EXECUTE LIVE TRADES."
                )
                log_opencode_said(scheduled_prompt)

            else:
                idle_prompt = (
                    f"OPENCODE CIO EXECUTIVE MULTI-INSTRUMENT DOSSIER ({'Initial Review' if is_startup else ('10-Min Directive' if is_10min_reminder else '2-Min Scheduled Cycle')}):\n"
                    f"{file_ref_header}"
                    f"{world_header}{top_pick_line}\n\n"
                    f"{full_4tf_reveal_block}"
                    f"=== MULTI-INSTRUMENT 7-AGENT RAW FINDINGS MATRIX ===\n"
                    f"{matrix_formatted}\n"
                    f"===========================================================\n"
                    f"MANDATORY EXECUTIVE ACTION: Analyze 6-instrument findings matrix above. Tail file:///C:/Trading/Alpha/logs/full_desk_dossier.md#{fnd_rng} for reasoning. Review relevant Pattern Book / Unified Learning evidence as mandatory study context; historical learning has no independent decision authority. "
                    f"MANDATE: The daemon is strictly a READ-ONLY scanner & dossier streamer. ONLY THE OPENCODE BRAIN (OPENCODE CIO) HAS THE AUTHORITY TO EXECUTE LIVE TRADES."
                )
                log_opencode_said(idle_prompt)

        return has_active_trades

    async def start_loop(self):
        self.is_running = True
        LOG.info("Consolidated Trading Daemon started with Adaptive Briefing Cadence (1-min active trades, 2-min idle).")
        # Immediately fire startup ping to Alpha v3 so user knows daemon is alive
        post_to_opencode_session(
            "OpenCode (CIO)",
            f"=== ALPHA TRADING DESK DAEMON ONLINE ===\n"
            f"Session: {OPENCODE_SESSION_TITLE} ({OPENCODE_SESSION_ID})\n"
            f"Current UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"Daemon: ONLINE | Tick ingestion: 2s | Briefing cadence: 1-Min active trade / 2-Min idle\n\n"
            f"=== AGENT AUTHORITY ===\n"
            f"YOU are the sole interpreter of evidence and the sole trading decision-maker.\n"
            f"Daemons, local agents, adapters and MCP tools provide, retrieve, record or execute your explicit decisions; they do not independently decide, gate or suppress trading decisions.\n\n"
            f"=== STARTUP ORIENTATION ===\n"
            f"The first full Initial Review is being collected now and will arrive shortly.\n"
            f"On that review: read all mandatory learning sources, review required live evidence, study current conditions against accumulated evidence, learn continuously (including from mistakes), and record meaningful observations or corrections without duplicate narrative.\n"
            f"Detailed persistent files are the source evidence; the inline briefing is a current-cycle guide, not a replacement.\n"
            f"Use relevant Alpha MCP capabilities when needed, mark evidence READ only after actual review, and keep interpretation and decisions AGENT-ONLY."
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
        # Default: Run Daemon
        log_story("System Launcher", f"=== CONSOLIDATED TRADING DESK STARTED UNDER OPENCODE SESSION '{OPENCODE_SESSION_TITLE}' ({OPENCODE_SESSION_ID}) ===")
        daemon = ConsolidatedTradingDaemon()
        asyncio.run(daemon.start_loop())
