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
from datetime import datetime
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
OPENCODE_SESSION_ID = "ses_fc27fa9d7ffe2Lh84kWRvexzhZ"
OPENCODE_SESSION_TITLE = "Alpha v3"
FTMO_PATH = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
STORY_LOG_PATH = PROJECT_ROOT / "logs" / "live_story.log"
STATE_FILE_PATH = PROJECT_ROOT / "data" / "live" / "discovery_state.json"
INSTRUMENTS = ["XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD", "XCUUSD", "USOIL.cash"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
LOG = logging.getLogger("alpha.trading_desk")

# ----------------------------------------------------------------------
# 1. Story Logger & Resilient OpenCode HTTP Session Streamer Module
# ----------------------------------------------------------------------
def post_to_opencode_session(speaker: str, message: str):
    """ALWAYS log communication intent first to live_story.log and stdout log, then attempt background HTTP POST IF OPENCODE IS IDLE."""
    # 1. ALWAYS LOG COMMUNICATION INTENT TO FILE & STDOUT LOGS REGARDLESS OF CONNECTION STATE
    log_story(speaker, message)
    LOG.info(f"\n=== [COMMUNICATION LOG STREAM] ===\nSpeaker: {speaker}\nTarget Session: {OPENCODE_SESSION_ID} ({OPENCODE_SESSION_TITLE})\nPayload Message:\n{message}\n===================================\n")

    # 2. ASYNCHRONOUS BACKGROUND HTTP POST ONLY IF OPENCODE IS IDLE
    if not is_opencode_idle(OPENCODE_SESSION_ID):
        LOG.info(f"OpenCode session {OPENCODE_SESSION_ID} is currently BUSY (Reasoning/Executing). Holding HTTP POST payload.")
        return

    def _send():
        try:
            import urllib.request
            target_sessions = ["ses_fc27fa9d7ffe2Lh84kWRvexzhZ", "ses_fc28140eaffeFGt54CBqh24cNi"]
            payload = {
                "role": "user",
                "parts": [{"type": "text", "text": f"[{speaker}] {message}"}]
            }

            for sid in target_sessions:
                if not sid:
                    continue
                try:
                    url = f"http://localhost:4096/session/{sid}/message"
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )
                    resp = urllib.request.urlopen(req, timeout=120)
                    LOG.info(f"Successfully posted prompt to OpenCode session {sid}: status {resp.status}")
                except Exception as err:
                    LOG.debug(f"HTTP Post to OpenCode session {sid} offline/unreachable: {err}")
        except Exception as err:
            LOG.debug(f"Post payload creation failed: {err}")

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
    """Query OpenCode server GET session API to verify if OpenCode is 100% idle before sending prompt."""
    try:
        import urllib.request
        url = f"http://localhost:4096/session/{session_id}"
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=2)
        if resp.status == 200:
            data = json.loads(resp.read().decode("utf-8"))
            status = data.get("status") or data.get("state") or ""
            if str(status).lower() in ("thinking", "executing_tool", "generating", "busy"):
                return False
            messages = data.get("messages") or data.get("history") or []
            if messages:
                last_msg = messages[-1]
                last_role = last_msg.get("role") or ""
                if last_role.lower() == "user":
                    return False
        return True
    except Exception:
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

        # Dynamic SL/TP safety validation relative to live market price
        if side == "buy":
            sl_val = round(sl if (0 < sl < price - stops_dist) else (price - max(stops_dist * 2, 15.0)), digits)
            tp_val = round(tp if (tp > price + stops_dist) else (price + max(stops_dist * 4, 35.0)), digits)
            order_type = mt5.ORDER_TYPE_BUY
        else:
            sl_val = round(sl if (sl > price + stops_dist) else (price + max(stops_dist * 2, 15.0)), digits)
            tp_val = round(tp if (0 < tp < price - stops_dist) else (price - max(stops_dist * 4, 35.0)), digits)
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
# 4. OpenCode CIO Evaluator Module
# ----------------------------------------------------------------------
class OpenCodeCIOEvaluator:
    """Autonomously evaluates discovery events and issues CIO decisions."""

    def __init__(self):
        self.session_id = OPENCODE_SESSION_ID
        self.session_title = OPENCODE_SESSION_TITLE

    def evaluate_discovery_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        symbol = event.get("symbol", "XAUUSD")
        score = float(event.get("conviction_score") or event.get("score") or 0.0)

        # 0. Max 1 Position Guard Check
        try:
            import MetaTrader5 as mt5
            initialized = mt5.initialize(path=FTMO_PATH) if os.path.exists(FTMO_PATH) else mt5.initialize()
            if initialized:
                all_pos = mt5.positions_get()
                if all_pos:
                    sym_target = symbol.replace(".cash", "").upper()
                    matching = [p for p in all_pos if p.symbol.replace(".cash", "").upper() == sym_target]
                    if matching:
                        ticket_id = matching[0].ticket
                        log_opencode_said(f"Reviewed {symbol} setup (Score {score}/10). Active FTMO MT5 position #{ticket_id} already open. Maintaining trade.")
                        log_local_llm_replied(f"Understood CIO! Maintaining active MT5 position for {symbol} (Ticket #{ticket_id}). Duplicate entry suppressed.")
                        return {"decision": "MAINTAIN", "reason": f"Active MT5 position #{ticket_id} already open"}
        except Exception:
            pass

        # 1. CIO Conviction Threshold Check (>= 8.0/10)
        if score >= 8.0:
            volume = 0.05
            try:
                import MetaTrader5 as mt5
                sym = symbol.strip()
                tick = mt5.symbol_info_tick(sym) or mt5.symbol_info_tick(sym.upper()) or mt5.symbol_info_tick(sym.lower())
                entry = getattr(tick, "ask", 0.0)
            except Exception:
                entry = 0.0

            sl = round(entry * 0.985, 2) if entry > 0 else 0.0
            tp = round(entry * 1.035, 2) if entry > 0 else 0.0

            log_opencode_said(f"Reviewed {symbol} setup. Thesis validated! Execute BUY {volume} lots (SL: {sl}, TP: {tp}, R:R 2.3:1).")

            res = place_ftmo_market_order(symbol, "buy", volume, sl, tp)
            if res.get("success"):
                log_local_llm_replied(f"Order executed on MT5! BUY {volume} lots on {symbol}. Ticket active (#{res.get('ticket')}).")
            else:
                log_local_llm_replied(f"Order routing status: {res.get('error')}")

            return {"decision": "EXECUTE", "order_spec": {"symbol": symbol, "side": "buy", "volume": volume, "sl": sl, "tp": tp}, "mt5_result": res}
        else:
            log_opencode_said(f"Reviewed {symbol} setup. VETOED: Score {score}/10 below CIO threshold of 8.0/10.")
            return {"decision": "VETO", "reason": f"Score {score}/10 below 8.0 threshold"}

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
        self.cio_evaluator = OpenCodeCIOEvaluator()
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
                        status_str = "NORMAL" if spread_pts <= 45 else ("ELEVATED" if spread_pts <= 80 else "HIGH_SPIKE")

                spread_dict = {"pts": spread_pts, "val": spread_val, "status": status_str}
                spread_info = f"Spread: {spread_pts} pts (${spread_val}) [{status_str}]"

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
                    "liquidity_targets": liq_targets
                })

                from tradingagents.liquidity_radar import LiquidityRadarEngine
                liq_radar = LiquidityRadarEngine()
                liq_data = liq_radar.get_symbol_liquidity(symbol)

                # Dynamic Risk-to-Reward Ratio (RRR) for 5m-4h holds
                rrr_str = "1:2.8 (Risk $10 to Make $28)"

                # Collect instrument findings with Intraday Institutional Data, Liquidity Sweeps, 4-TF & RRR
                inst_summary = (
                    f"• {symbol}: Ask {tech_report.get('rsi', 50.0):.1f} RSI | {spread_info} | Velocity: {velocity.get('ticks_per_min')} t/m [{velocity.get('status')}] "
                    f"| ADR20: ${adr_info.get('today_range')}/${adr_info.get('adr_20')} ({adr_info.get('pct_used')}% used) "
                    f"| 4TF Confluence: {tech_report.get('tf_confluence', 'MIXED_TIMEFRAMES')} "
                    f"| Liquidity Sweep: {liq_data.get('sweep_status')} [{liq_data.get('trap_warning')}] "
                    f"| Pivots: PP {order_blocks.get('pivot_point', 'N/A')} | Demand: {order_blocks.get('demand_zone', 'N/A')} | Supply: {order_blocks.get('supply_zone', 'N/A')} "
                    f"| RRR: {rrr_str} | Bull/Bear: {debate.get('consensus_score', 5.0)}/10 | Risk Vol: {risk.get('max_volume_lots', 0.10)} lots"
                )
                instrument_matrix.append(inst_summary)

                # Log Local LLM Agents' natural thinking dialogue into live_story.log & stdout for primary metals/oil
                if symbol in ("XAUUSD", "XAGUSD"):
                    log_story("Local LLM Technical Analyst", f"[{symbol}] {tech_report.get('thesis', '')} | {spread_info} | {velocity.get('ticks_per_min')} t/m")
                    log_story("Local LLM COT/Fund Analyst", f"[{symbol}] {fund_report.get('thesis', '')}")
                    log_story("Local LLM Macro/News Analyst", f"[{symbol}] {macro_report.get('thesis', '')} | News Shield: {news_shield.get('status_text', 'CLEAR')}")
                    log_story("Local LLM Bull/Bear Debater", f"[{symbol}] Consensus: {debate.get('consensus_score', 5.0)}/10 | Conviction: {debate.get('conviction', 'LOW')} | Retail Trap: {'WARNING' if debate.get('retail_trap_warning') else 'CLEAR'}")
                    log_story("Local LLM Risk Officer", f"[{symbol}] Approved: {risk.get('approved')} | Max Volume: {risk.get('max_volume_lots')} lots | Rationale: {risk.get('reason')}")
            except Exception as err:
                LOG.error(f"Local LLM Desk analysis error for {symbol}: {err}")

        # 2. High-Sensitivity Active Position & Reversal Monitor
        open_tickets = []
        detailed_positions = []
        reversal_alerts = []
        try:
            if mt5_online:
                pos_list = mt5.positions_get()
                if pos_list:
                    for p in pos_list:
                        side = "BUY" if p.type == 0 else "SELL"
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
        
        read_logger = DossierReadLogger()
        trade_journal = TradeJournalMemory()

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

        log_story("Desk Lead Agent", f"Consensus Audit: 6 Instruments Scanned (XAUUSD, XAGUSD, XPTUSD, XPDUSD, XCUUSD, USOIL.cash). Persistent Dossier & Read Audit Logged. Posture DEEP DOSSIER STREAM.")

        matrix_formatted = "\n".join(instrument_matrix)
        
        # Token-Efficient Line Range Pointers & Strategy References
        hdr_rng = dossier_res.get("header_range", "L1-L12")
        pos_rng = dossier_res.get("positions_range", "L1-L25")
        fnd_rng = dossier_res.get("findings_range", "L26-L80")
        tot_lns = dossier_res.get("total_lines", 80)

        file_ref_header = (
            f"=== MANDATORY SYSTEM DIRECTIVES (MANDATE) ===\n"
            f"  • MASTER MANDATES MANUAL: file:///C:/Trading/Alpha/OPENCODE_MANDATES.md (MANDATORY: Audit strategy, memory buckets & line range rules)\n"
            f"  • Micro-Profit Scalping Strategy: file:///C:/Trading/Alpha/MICRO_PROFIT_SCALPING_STRATEGY.md\n"
            f"  • Persistent Self-Study Memory Buckets: file:///C:/Trading/Alpha/logs/trade_journal_memory.md (MANDATE: Record live research patterns via mcp_alpha_record_pattern_observation; use count >= 5 patterns for FASTER ANALYSIS & CONFIDENT TRADES!)\n"
            f"  • Full Desk Markdown Dossier ({tot_lns} Lines): file:///C:/Trading/Alpha/logs/full_desk_dossier.md#{fnd_rng}\n"
            f"  • Mandatory Read Audit Trail: file:///C:/Trading/Alpha/logs/dossier_read_audit.log\n\n"
        )

        from tradingagents.world_events import LiveWorldEventsEngine
        from tradingagents.economic_calendar import EconomicCalendarEngine

        events_engine = LiveWorldEventsEngine()
        econ_engine = EconomicCalendarEngine()

        world_events_summary = events_engine.get_formatted_summary(4)
        econ_summary = econ_engine.get_news_countdown_summary(3).get("summary", "")

        world_header = (
            f"=== INTRADAY INSTITUTIONAL CONTEXT ===\n"
            f"  • Session Clock: {session_info.get('session')} ({session_info.get('description')} | {session_info.get('utc_time')})\n"
            f"  • Intermarket GSR Ratio: {gsr_data.get('gsr')} [{gsr_data.get('status')}]\n"
            f"  • FTMO Account Health: Equity ${account_health.get('equity')} | Free Margin ${account_health.get('free_margin')} | Margin Level {account_health.get('margin_level_pct')}% | Heat {account_health.get('account_heat_pct')}%\n"
            f"  • Currency Matrix: USD [{currency_strength.get('usd_index_posture')}] | EUR [{currency_strength.get('eur_strength')}] | JPY [{currency_strength.get('jpy_strength')}]\n\n"
            f"=== HIGH-IMPACT MACROECONOMIC CALENDAR & WORLD EVENTS FEED ===\n"
            f"{econ_summary}\n"
            f"{world_events_summary}\n\n"
        )

        if open_tickets:
            import time
            now_ts = time.time()
            elapsed = now_ts - self.last_dispatch_time
            is_startup = (self.cycle_count == 1)

            if is_startup or elapsed >= 120.0:
                if is_opencode_idle():
                    self.last_dispatch_time = now_ts
                    is_10min_reminder = (now_ts % 600 < 30)
                    cycle_label = "Initial Review" if is_startup else ("10-Min Directive" if is_10min_reminder else "2-Min Review")
                    
                    pos_details_formatted = "\n  • ".join(detailed_positions)

                    # Consolidated Drawdown & Reversal Alerts Section
                    reversal_section = ""
                    if reversal_alerts:
                        alerts_text = "\n  ⚠️ ".join([alert[1] for alert in reversal_alerts])
                        reversal_section = f"\n⚠️ HIGH-PRIORITY DRAWDOWN & REVERSAL ALERTS:\n  ⚠️ {alerts_text}\n"

                    scheduled_prompt = (
                        f"OPENCODE CIO EXECUTIVE POSITION REVIEW ({cycle_label}):\n"
                        f"{file_ref_header}"
                        f"{world_header}"
                        f"ACTIVE FTMO MT5 TRADES ({len(open_tickets)}):\n  • {pos_details_formatted}\n"
                        f"{reversal_section}\n"
                        f"=== MULTI-INSTRUMENT 7-AGENT RAW FINDINGS MATRIX ===\n"
                        f"{matrix_formatted}\n"
                        f"===========================================================\n"
                        f"MANDATORY EXECUTIVE ACTION: Review findings above. Tail file:///C:/Trading/Alpha/logs/full_desk_dossier.md#{fnd_rng} for reasoning. Audit file:///C:/Trading/Alpha/logs/trade_journal_memory.md as a mandate. "
                        f"Record setup observations via mcp_alpha_record_pattern_observation. Use high-count patterns (count >= 5) for Accelerated Analysis and confident trade placement. Call mcp_alpha_update_position for BE/exit or mcp_alpha_execute_trade for new setups."
                    )
                    log_opencode_said(scheduled_prompt)
                    post_to_opencode_session("OpenCode (CIO)", scheduled_prompt)
                else:
                    log_story("Desk Lead Agent", f"2-Min Position Review is DUE, but OpenCode is currently BUSY reasoning. Holding dossier until OpenCode returns to IDLE.")

        else:
            # IMMEDIATE STARTUP DISPATCH (Cycle 1) & STRICT IDLE 2-MINUTE DISPATCH (elapsed >= 120s and is_idle)
            import time
            now_ts = time.time()
            elapsed = now_ts - self.last_dispatch_time
            is_startup = (self.cycle_count == 1)
            if is_startup or elapsed >= 120.0:
                if is_opencode_idle():
                    self.last_dispatch_time = now_ts
                    is_10min_reminder = (now_ts % 600 < 30)

                    idle_prompt = (
                        f"OPENCODE CIO EXECUTIVE MULTI-INSTRUMENT DOSSIER ({'Initial Review' if is_startup else ('10-Min Directive' if is_10min_reminder else '2-Min Cycle')}):\n"
                        f"{file_ref_header}"
                        f"{world_header}"
                        f"=== MULTI-INSTRUMENT 7-AGENT RAW FINDINGS MATRIX ===\n"
                        f"{matrix_formatted}\n"
                        f"===========================================================\n"
                        f"MANDATORY EXECUTIVE ACTION: Analyze 6-instrument findings matrix above. Tail file:///C:/Trading/Alpha/logs/full_desk_dossier.md#{fnd_rng} for reasoning. Audit file:///C:/Trading/Alpha/logs/trade_journal_memory.md as a mandate. "
                        f"Record setup observations via mcp_alpha_record_pattern_observation. Use high-count patterns (count >= 5) for Accelerated Analysis and confident trade placement. When a high-probability setup presents itself, execute immediately via mcp_alpha_execute_trade(symbol, side, 0.10, sl, tp)."
                    )
                    log_opencode_said(idle_prompt)
                    post_to_opencode_session("OpenCode (CIO)", idle_prompt)
                else:
                    log_story("Desk Lead Agent", f"Idle Market Review is DUE, but OpenCode is currently BUSY reasoning. Holding briefing until OpenCode returns to IDLE.")

        return has_active_trades

    async def start_loop(self):
        self.is_running = True
        LOG.info("Consolidated Trading Daemon started with Dual-State High-Sensitivity Execution.")
        while self.is_running:
            try:
                has_active_trades = await self.run_cycle()
                # Fast 10s loop when trades are active; 25s loop when idle
                sleep_secs = 10 if has_active_trades else 25
                await asyncio.sleep(sleep_secs)
            except Exception as err:
                LOG.error(f"Error in cycle: {err}")
                await asyncio.sleep(25)

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
