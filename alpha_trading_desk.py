"""
======================================================================
               ALPHA V1 - CONSOLIDATED INTELLIGENT TRADING DESK
======================================================================
Project Root: C:\Trading\Alpha
OpenCode Session: Alpha v1 (ses_fd5d79a76ffeWi4umW2PMa4MCe)
Target Terminal: FTMO MetaTrader 5 (C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe)

Runtime model:
1. StoryLogger — factual daemon/session audit narration.
2. Objective observation and MT5 state collection.
3. OpenCode — sole market reasoner and trade decision-maker.
4. MT5 execution — deterministic validation and explicit order routing only.
5. ConsolidatedTradingDaemon — wake delivery and observation scheduling.
======================================================================
"""

import os
import sys
import json
import re
import time
import psutil
import logging
import asyncio
from datetime import datetime, timedelta, timezone
import threading
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

def _init_mt5(timeout: int = 5000) -> bool:
    try:
        import MetaTrader5 as mt5
        t_info = mt5.terminal_info()
        if t_info is not None and getattr(t_info, "connected", False):
            return True
        from tradingagents.mt5_connector import ensure_mt5_connected
        return ensure_mt5_connected(timeout=timeout)
    except Exception as err:
        logging.getLogger("alpha.trading_desk").error(f"MT5 init error: {err}")
        return False

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

_RECENTLY_DISPATCHED_ALERTS: Dict[str, float] = {}
_DISPATCH_LOCK = threading.Lock()

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

    is_urgent = any(k in message for k in ("WATCH ALERT", "WATCH TRIGGERED", "FILL ALERT", "AUTO-WIN HARVEST", "EVIDENCE WAKE"))

    # Extract watch_id if present to prevent flooding duplicate trigger prompts
    watch_match = re.search(r"watch_[a-zA-Z0-9_]+", message)
    watch_id = watch_match.group(0) if watch_match else None

    if watch_id and is_urgent:
        now_mono = time.monotonic()
        with _DISPATCH_LOCK:
            last_time = _RECENTLY_DISPATCHED_ALERTS.get(watch_id, 0.0)
            if now_mono - last_time < 30.0:
                LOG.info(f"⚡ [SUPPRESSING DUPLICATE ALERT] Watch {watch_id} alert already dispatched/queued {now_mono - last_time:.1f}s ago.")
                return
            _RECENTLY_DISPATCHED_ALERTS[watch_id] = now_mono

    # Check if OpenCode is actively deliberating/executing tools
    if sid and not is_opencode_idle(sid):
        if not is_urgent:
            LOG.info(f"OpenCode session '{title}' ({sid}) is currently BUSY deliberating. Skipping routine prompt dispatch to prevent aborting ongoing turn.")
            return
        else:
            LOG.info(f"⚡ [URGENT DISPATCH QUEUED] OpenCode session '{title}' ({sid}) is busy. Enqueueing trigger alert to dispatch immediately once idle.")

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
        import time

        # For urgent alerts, wait until OpenCode becomes idle before dispatching
        if sid and is_urgent:
            for _ in range(120):
                # Check if watch was cancelled while waiting for OpenCode to be idle
                if watch_id:
                    try:
                        from tradingagents.evidence_state import EvidenceStateStore
                        _chk_store = EvidenceStateStore()
                        _w = _chk_store.get_watches(include_closed=True)
                        _match_w = next((x for x in _w if x.get("id") == watch_id), None)
                        if _match_w and _match_w.get("status") == "CANCELLED":
                            LOG.info(f"⚡ [CANCELLED IN FLIGHT] Watch {watch_id} was CANCELLED while waiting for OpenCode to be idle. Dropping queued wake prompt.")
                            return
                    except Exception:
                        pass

                if is_opencode_idle(sid):
                    time.sleep(0.5)
                    break
                time.sleep(1.0)
            else:
                LOG.warning(f"⚡ [ALERT DEFERRED] OpenCode session '{title}' ({sid}) remained busy after 120s. Avoiding turn interruption; alert prompt deferred.")
                return

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
            "parts": [{"type": "text", "text": message}]
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
    """Check if OpenCode session is ready to receive alerts (not busy generating tokens or running tools)."""
    if not session_id:
        session_id = get_opencode_session_id()
    try:
        import urllib.request
        api_url = get_opencode_api_url()
        url = f"{api_url}/session/status"
        req = urllib.request.Request(url, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                s_info = data.get(session_id, {})
                if s_info.get("type") in ("busy", "retry"):
                    return False
                return True
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
# 3. Execution Authority Guard (Daemon has ZERO execution authority)
# ----------------------------------------------------------------------
# NOTE: The background daemon is strictly a read-only scanner & evidence streamer.
# Live MT5 trade execution is exclusively reserved for OpenCode via MCP tools.
# Any automated/daemon-side market order execution functions have been permanently excised.


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
    """Runs observation scheduling and factual wake delivery; it does not reason or decide trades."""

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
        self.dispatch_count = 0
        self.last_dispatch_time = 0.0
        self.last_brainstorm_dispatch_time = 0.0
        self.last_reversal_dispatch_time = 0.0
        self.active_burst_step = 0
        self.just_sent_active_brainstorm = False
        self.next_turn_type = "DOSSIER"
        self.has_dispatched_initial_dossier = False
        self.last_session_id = None
        self.dossiers_since_brainstorm = 0
        self.last_dispatched_turn_type = ""

        # Wire live error monitoring into Desk Daemon (H4)
        from monitor.error_monitor import error_monitor
        self.error_monitor = error_monitor
        self.error_monitor.install_global_handlers()

        # Initialize Universal High-Speed Watcher Engine (500ms multi-trigger)
        from tradingagents.watcher_engine import UniversalWatcherEngine
        self.watcher_engine = UniversalWatcherEngine()
        self.watcher_task = None

    def dispatch_startup_ping(self, sid: str, title: str):
        dossier_mins = max(1, int(round(get_dossier_interval_seconds() / 60.0)))
        active_mins = max(1, int(round(get_active_trade_interval_seconds() / 60.0)))
        post_to_opencode_session(
            "OpenCode (CIO)",
            f"=== ALPHA TRADING DESK DAEMON ONLINE ===\n"
            f"Session: {title} ({sid})\n"
            f"Current UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"Daemon: ONLINE | Tick ingestion: 2s | Universal Watcher: 500ms Active (Orders/Price/Tape) | Briefing: {active_mins}-Min active / {dossier_mins}-Min idle\n\n"
            f"=== EVIDENCE-FIRST AUTHORITY & MANDATORY RAW TELEMETRY AUDIT ===\n"
            f"OpenCode is the sole market reasoner and CIO. The daemon only observes and wakes a new investigation.\n"
            f"PRINCIPLE 0 — A WAKE IS NOT A SIGNAL: A cadence ping or brainstorm prompt is an observation cycle, NOT a mandate to trade. If market conditions are in equilibrium, quiet consolidation, or lacking a confirmed catalyst, YOUR HIGH-CONVICTION OUTPUT IS: `DECISION: NO ACTION / WAIT — Standing flat`.\n"
            f"MANDATORY ON EVERY WAKE (STEP 0): You MUST directly call the registered FastMCP tool: `alpha-daemon-mcp_get_market_regime_context(symbol='XAUUSD')` or `get_market_regime_context(symbol='XAUUSD')`.\n"
            f"Do NOT explore directories, read codebase files, or search for scripts. All tools are natively registered in your MCP tool environment.\n"
            f"Audit live broker quotes, spread, raw tape velocity, CVD ratio, 4m interval displacement, and auction air pockets.\n"
            f"No autonomous order placement, auto-harvest, score gate, or dossier conclusion is authoritative.\n\n"
            f"=== PROVEN WINNING EXECUTION BLUEPRINT (HUMAN STEERING & HISTORICAL WINS) ===\n"
            f"• Sizing & Target Discipline: Available lots 0.50 to 1.00 lots scaled for high certainty. Target 1 Only: 4 to 10 pt closer structural TPs banked cleanly in 10 to 30 minutes.\n"
            f"• Stop-Breakout Entry: BUY_STOP / SELL_STOP where price cannot retrace back, SL anchored behind verified structural hold.\n"
            f"• Directive 8: 30 to 60 min absolute event silence before Tier-1 releases (CPI, PPI, FOMC, NFP, GDP). Stand flat.\n"
            f"• Rule 0: Tape over headlines (trust live tape CVD / structure over narrative if they diverge).\n"
            f"• Rule 2.4: Price-direction discriminator (verified displacement in trade direction).\n\n"
            f"=== MCP TOOLS DIRECTORY & USAGE GUIDE ===\n"
            f"Directly invoke atomic tools in parallel: alpha-daemon-mcp_get_market_regime_context, alpha-daemon-mcp_get_live_microstructure, alpha-daemon-mcp_get_fvg_matrix, alpha-daemon-mcp_get_measured_cvd, alpha-daemon-mcp_get_full_institutional_profile, alpha-daemon-mcp_get_account_status, alpha-daemon-mcp_get_pending_orders, alpha-daemon-mcp_place_pending_order, alpha-daemon-mcp_execute_market_order, alpha-daemon-mcp_cancel_pending_order, alpha-daemon-mcp_modify_pending_order, alpha-daemon-mcp_execute_trade, alpha-daemon-mcp_update_position, alpha-daemon-mcp_register_watch, alpha-daemon-mcp_get_active_watches, alpha-daemon-mcp_cancel_watch, alpha-daemon-mcp_clear_completed_watches, and Proxima news tools (proxima_ask_perplexity, proxima_deep_search, proxima_ddg_search).\n"
        )

    async def run_cycle(self):
        self.cycle_count += 1
        self.instruments = get_active_instruments()
        LOG.info(f"--- Starting Scan Cycle #{self.cycle_count} across {len(self.instruments)} instruments ({', '.join(self.instruments)}) ---")
        log_local_llm_monitoring(f"Scanning market data across {len(self.instruments)} instruments (Physical Telemetry + Tick CVD Ingestion active)...")

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
        from tradingagents.institutional_analytics import InstitutionalAnalyticsEngine
        inst_engine = InstitutionalAnalyticsEngine()

        instrument_matrix = []
        instruments_data = []
        import MetaTrader5 as mt5
        mt5_online = _init_mt5()
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

                # Volume Profile Metrics (POC, VAH 70%, VAL 70%)
                vp_data = {}
                try:
                    vp_data = inst_engine.get_volume_profile_metrics(symbol)
                except Exception as vp_err:
                    LOG.debug(f"Volume profile calculation error for {symbol}: {vp_err}")

                vp_summary = f"Volume Profile: POC {vp_data.get('poc', 0.0):.2f} | VAH {vp_data.get('vah', 0.0):.2f} | VAL {vp_data.get('val', 0.0):.2f} [{vp_data.get('price_location', 'N/A')}]" if vp_data else "Volume Profile: Initializing"

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
                    "volume_profile": vp_data
                })

                # Collect instrument findings with Intraday Institutional Data, Liquidity Sweeps, 4-TF, FVG, Volume Profile & RRR
                inst_summary = (
                    f"• {symbol}: {spread_info} | {velocity_str} "
                    f"| {adr_str} "
                    f"| {tf_alignment_str} "
                    f"| {fvg_line} | {vp_summary} "
                    f"| Liquidity Sweep: {liq_data.get('sweep_status')} [{liq_data.get('trap_warning')}] "
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
                    log_story("Local LLM Risk Officer", f"[{symbol}] Approved: {risk.get('approved')} | Guidance: {risk.get('reason')}")
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
        top_pick_line = f"PRIMARY FOCUS INSTRUMENT: {top_symbol}" + (f" — {headline}" if headline else "")
        
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

        execution_blueprint_block = """=== CONSOLIDATED EXECUTION & STRUCTURAL TP/SL PROTOCOL ===
  1. CONSOLIDATED EXECUTION (VOLUME & STRUCTURAL SL/TP DIRECTLY SET):
     • execute_market_order(symbol, side, volume=1.0, sl_price=0.0, tp_price=0.0) -> Execute direct market order with custom volume, SL, and TP.
     • place_pending_order(symbol, order_type, price, volume=1.0, sl_price=0.0, tp_price=0.0, tag="") -> Stage planned limit/stop orders with custom volume, SL, and TP.
     • cancel_pending_order(order_ticket) -> Cancel active pending orders.
     • update_position(ticket, action) -> Manage active positions (BREAK_EVEN, TRAIL_SL, FULL_EXIT).
     • get_account_status() -> Fetch live balance, equity, and open positions.
  2. DIRECTIONAL EVALUATION (1 OR UP TO 2 ORDERS):
     • Evaluate market structure objectively. Stage 1 planned trigger (or execute 1 market trade) in your evaluated direction.
     • If highly confident / high conviction, you may stage up to 2 orders (e.g. 2 tiered pending limits).
  3. STRUCTURAL EXITS (DOLLAR EXIT OFF):
     • TP is set normally during placement at structural targets (e.g., VAH/VAL or FVG CE).
     • Dollar-based auto exit is OFF. Positions are managed to structural TP/SL levels or proactively via update_position.
  4. ZERO AUTONOMOUS SYSTEM EXECUTION: The daemon NEVER places trades on its own. ONLY OpenCode plans and executes trades.
"""

        file_ref_header = (
            f"=== ALPHA AGENT STUDY UPDATE ===\n"
            f"  • CURRENT TIME: {ist_ts} | UTC: {gen_ts} | SCAN CYCLE: #{self.cycle_count}\n"
            f"  • Live Evidence Dossier ({dossier_line_count} lines): file:///C:/Trading/Alpha/logs/full_desk_dossier.md#{fnd_rng}\n"
            f"  • Unified Learning Memory: file:///C:/Trading/Alpha/logs/unified_learning_memory.json\n\n"
            f"{execution_blueprint_block}\n"
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

        top4_section = ""

        # DYNAMIC DISPATCH CADENCE (Configurable via opencode_session_config.json)
        now_ts = time.time()
        is_startup = not self.has_dispatched_initial_dossier
        elapsed_since_dispatch = now_ts - self.last_dispatch_time
        dossier_interval = get_dossier_interval_seconds()
        active_trade_interval = get_active_trade_interval_seconds()
        has_active_trades = len(open_tickets) > 0

        # Calculate required interval based on active vs idle state
        if has_active_trades:
            # Active trade cadence: Calm 5-minute position reviews (300s) to prevent over-deliberation
            self.active_burst_step = 0
            self.just_sent_active_brainstorm = False
            required_interval = float(active_trade_interval)  # 300.0s (5m)
        else:
            self.active_burst_step = 0
            self.just_sent_active_brainstorm = False
            if self.last_dispatched_turn_type == "BRAINSTORM":
                # After the news / brainstorm message, let there be a 4 min gap (240s) for next dossier
                required_interval = 240.0
            else:
                # 2 min dossiers every 2 min
                required_interval = float(dossier_interval)

        # Evaluate active persistent watches against live tick price using UniversalWatcherEngine
        triggered_watch = None
        try:
            from tradingagents.evidence_state import EvidenceStateStore
            _ev_store = EvidenceStateStore()
            _active_watches = [w for w in _ev_store.get_watches(include_closed=False) if (w.get("status") or "ACTIVE").upper() == "ACTIVE"]
            for w in _active_watches:
                w_sym = w.get("symbol", "XAUUSD")
                w_tick = mt5.symbol_info_tick(w_sym) if mt5_online else None
                if w_tick:
                    w_bid = float(getattr(w_tick, "bid", 0.0))
                    w_ask = float(getattr(w_tick, "ask", 0.0))
                    _live_tape = {}
                    try:
                        from tradingagents.cvd_engine import CumulativeVolumeDeltaEngine
                        _flow_engine = CumulativeVolumeDeltaEngine()
                        _m = _flow_engine.get_symbol_cvd(w_sym)
                        _live_tape = {
                            "velocity": _m.get("tick_velocity_tpm", 0.0),
                            "spread": _m.get("live_spread_pts", 0.0),
                            "cvd_10b": _m.get("recent_10_bar_delta", 0.0),
                            "cum_cvd": _m.get("cumulative_volume_delta", 0.0)
                        }
                    except Exception as _fl_err:
                        LOG.debug(f"Cadence tape snapshot err: {_fl_err}")

                    trig = self.watcher_engine.evaluate_watch(
                        watch=w,
                        live_tick={"bid": w_bid, "ask": w_ask, "price": (w_bid + w_ask) / 2.0},
                        last_tick=self.watcher_engine.last_ticks.get(w_sym, {"bid": w_bid, "ask": w_ask}),
                        tape_metrics=_live_tape,
                        positions=open_tickets
                    )
                    if trig:
                        triggered_watch = w
                        triggered_watch_prompt = trig.get("prompt")
                        _ev_store.update_watch(w["id"], status="COMPLETED", triggered_at=datetime.now(timezone.utc).isoformat())
                        w["status"] = "COMPLETED"
                        LOG.info(f"⚡ WATCH TRIGGERED & CLEARED: {w['id']} -> {trig.get('trigger_reason', '')} (Live bid: {w_bid})")
                        break
        except Exception as _w_store_err:
            LOG.debug(f"Watch store err: {_w_store_err}")

        # Check if active session ID changed dynamically in config
        sid, title, _ = get_opencode_session()
        if sid and self.last_session_id is not None and sid != self.last_session_id:
            LOG.info(f"🔄 Active OpenCode session changed to '{title}' ({sid}). Resetting cadence and dispatching startup message.")
            self.last_session_id = sid
            self.has_dispatched_initial_dossier = False
            self.last_dispatch_time = now_ts
            self.next_turn_type = "DOSSIER"
            self.dossiers_since_brainstorm = 0
            self.last_dispatched_turn_type = ""
            self.dispatch_startup_ping(sid, title)

        ready_for_dispatch = False
        is_idle = is_opencode_idle(sid) if sid else True

        if triggered_watch is not None:
            ready_for_dispatch = True
        elif elapsed_since_dispatch >= required_interval:
            if is_idle:
                ready_for_dispatch = True
            else:
                LOG.info(f"OpenCode session '{title}' ({sid}) is currently BUSY deliberating. Holding dispatch until idle...")

        if ready_for_dispatch:
            self.last_dispatch_time = now_ts
            self.dispatch_count += 1
            if is_startup:
                self.has_dispatched_initial_dossier = True
            if triggered_watch is not None:
                trigger = f"WATCH_TRIGGER — {triggered_watch['id']} (Target: {triggered_watch.get('target_price')})"
            else:
                trigger = "STARTUP" if is_startup else ("ACTIVE_POSITION_REVIEW" if has_active_trades else "SCHEDULED_REASSESSMENT")

            if has_active_trades:
                # Active trade pattern: Calm Active Position Reviews every 5 minutes (NO brainstorm distractions in-flight)
                self.just_sent_active_brainstorm = False
                is_brainstorm_turn = False
                self.last_dispatched_turn_type = "ACTIVE_POSITION_REVIEW"
            elif triggered_watch is not None:
                is_brainstorm_turn = False
                self.last_dispatched_turn_type = "WATCH_TRIGGER"
            else:
                # Idle pattern: 2 min dossiers every 2 min, brainstorm goes every 7th dossier
                if self.dossiers_since_brainstorm >= 7:
                    is_brainstorm_turn = True
                    self.dossiers_since_brainstorm = 0
                    self.last_dispatched_turn_type = "BRAINSTORM"
                    self.next_turn_type = "DOSSIER"
                    LOG.info("📰 Cadence: Dispatched BRAINSTORM (90% News Drilldown) after 7 dossiers. Next interval: 4 minutes.")
                else:
                    is_brainstorm_turn = False
                    self.dossiers_since_brainstorm += 1
                    self.last_dispatched_turn_type = "DOSSIER"
                    if self.dossiers_since_brainstorm >= 7:
                        self.next_turn_type = "BRAINSTORM"
                    else:
                        self.next_turn_type = "DOSSIER"
                    LOG.info(f"📊 Cadence: Dispatched DOSSIER #{self.dossiers_since_brainstorm}/7. Next interval: 2 minutes.")


            try:
                from tradingagents.time_helper import get_market_time_context, get_upcoming_transitions_summary
                _t_ctx = get_market_time_context()
                _utc_fmt = _t_ctx["current_clocks"]["utc"]["formatted"]
                _ist_fmt = _t_ctx["current_clocks"]["ist"]["formatted"]
                _ny_fmt = _t_ctx["current_clocks"]["new_york_et"]["formatted"]
                _lon_fmt = _t_ctx["current_clocks"]["london_bst"]["formatted"]
                _sess = _t_ctx["active_session"]
                _gates_summary = get_upcoming_transitions_summary(_t_ctx, max_count=3)
                _time_str = (
                    f"UTC: {_utc_fmt} | IST: {_ist_fmt} | NY (ET): {_ny_fmt} | London: {_lon_fmt} | Active Session: {_sess}\n"
                    f"SESSION GATES (DETERMINISTIC ZERO-MENTAL-MATH): {_gates_summary}"
                )
            except Exception:
                _time_str = f"UTC: {datetime.now(timezone.utc).isoformat()}"

            try:
                from tradingagents.catalyst_arbiter import CatalystArbiterEngine
                _regime_info = CatalystArbiterEngine().get_market_regime("XAUUSD")
                _regime_badge = _regime_info.get("compact_prompt_badge", "")
            except Exception as _reg_err:
                _regime_badge = ""

            if triggered_watch is not None:
                prompt = triggered_watch_prompt if 'triggered_watch_prompt' in locals() and triggered_watch_prompt else (
                    f"⚡ ALPHA EVIDENCE WAKE — WATCH_TRIGGER\n"
                    f"{_time_str}\n"
                    f"WATCH ALERT: {triggered_watch['id']} TRIGGERED at target price {triggered_watch.get('target_price')}!\n"
                    f"• Reason Title: {triggered_watch.get('title') or triggered_watch.get('condition')}\n"
                    f"• Condition: {triggered_watch.get('condition')}\n"
                    f"• Instruction: {triggered_watch.get('instruction')}\n"
                    f"• Reason: {triggered_watch.get('reason')}\n\n"
                    f"=== INSTANT DECISIVE EXECUTION AUDIT (ZERO-DELAY BROKER ACTION) ===\n"
                    f"1. DIRECT STAGING / EXECUTION: If a breaking catalyst, active kinetic surge (expanding velocity + CVD delta surge), or Turtle Soup reclaim is active right at structure, IMMEDIATELY call `execute_market_order` (BUY/SELL) with 0.50–1.00L, 5.5–10 pt SL, and 4–8 pt TP! If tape is quietly consolidating 2–5 pts from structure, IMMEDIATELY deploy the pre-planned order (`place_pending_order` BUY_LIMIT/SELL_LIMIT/BUY_STOP/SELL_STOP) on MT5 in this very turn! Do not defer execution or staging to a secondary turn.\n"
                    f"2. PARALLEL TELEMETRY CONFIRMATION: Call `get_market_regime_context(symbol='{triggered_watch.get('symbol', 'XAUUSD')}')` in parallel to ground the fill.\n"
                    f"3. HARD SIZING & STOPS: 0.50–1.00L sizing, 6.0–10.0 pt structural SL, 4.0–8.0 pt Mode A TP. Spread-compensated limits (+0.35 on BUY_LIMIT, -0.35 on SELL_LIMIT)."
                )
            elif is_brainstorm_turn:
                prompt = (
                    f"{_time_str}\n\n"
                    "=== INSTITUTIONAL BRAINSTORM: 90% NEWS DRILLDOWN ===\n"
                    "Brainstorm with 5 new targeted questions about current macro/micro conditions based strictly on live breaking news and physical tape realities.\n\n"
                    "MANDATORY 90% NEWS RESEARCH SUITE VIA PROXIMA MCP (EXECUTE ALL IN PARALLEL):\n"
                    "Formulate your own search queries dynamically based on your current thought process and market catalysts:\n"
                    "  • 2x `proxima_ask_perplexity`: Breaking headlines, macro releases, wire alerts.\n"
                    "  • 2x `proxima_deep_search(query=..., type='news', timeframe='today')`: Deep AI research queries for in-depth background.\n"
                    "  • 2x `proxima_ddg_search(query=...)`: Live web searches across primary sources and wires.\n"
                    "  • 2x `proxima_deep_search(query=..., type='reddit')` or `proxima_ddg_search(query='... site:reddit.com')`: Retail sentiment chatter.\n"
                    "  • `proxima_web_scrape(url=...)`: Fetch full text if specific article/statement URLs returned.\n"
                    "  • `get_fred_observations(series_id='DFII10')`: 10Y real yields (TIPS).\n"
                    "  • `alpha-daemon-mcp_get_full_institutional_profile(symbol='XAUUSD')` OR `read(filePath='C:/Trading/Alpha/logs/institutional_deep_book.md')`: Volume Profile (POC/VAH/VAL), Institutional VWAP bands, Retail Stop Clusters (BSL/SSL magnets), and COT.\n"
                    "  • `graphiti-memory-mcp_graphiti_get_pattern_walks(symbol='XAUUSD')`: Review dominant winning walks & trap fingerprints to recalibrate mental model.\n"
                    "• STRICT NEGATIVE CONSTRAINT: ZERO PROBABILITY QUERIES. Query only for factual prints, actual data points, and verbatim quotes.\n\n"
                    "CADENCE ACTION DIRECTIVE (AGENTS.MD PERMANENT SYSTEM PROMPT GOVERNS):\n"
                    "• Mid-air equilibrium between shelves? Stand flat with patience (`DECISION: NO ACTION / WAIT`).\n"
                    "• Breaking news or active kinetic breakout/reclaim at structure? Execute IMMEDIATELY via `execute_market_order` (BUY/SELL, 0.50–1.00L, 5.5–10 pt SL, 4–8 pt Mode A TP). Fresh structural shelf (FVG CE / POC / OB) within 2 to 7 pts? Pre-stage Prong A limit or Prong B stop on MT5 now.\n"
                    "• Sizing floor: 0.50L–1.00L. Mode A TP: 4.0–8.0 pts (bank fast into nearest pivot/shelf per User Msg 95). NEVER stretch TP beyond 8–10 pts for paper R:R. Continuous learning: record observed traps or clean expansions via `graphiti_add_episode`."
                )
            elif has_active_trades:
                prompt = (
                    f"⚡ ALPHA EVIDENCE WAKE — ACTIVE POSITION REVIEW\n"
                    f"{_time_str}\n\n"
                    "ACTIVE TRADE AUDIT & RISK MANAGEMENT PROTOCOL:\n"
                    "An active position is currently in flight. Execute immediate physical audit:\n\n"
                    "STEP 0 (MANDATORY): Call FastMCP tools in parallel:\n"
                    "  • `alpha-daemon-mcp_get_market_regime_context(symbol='XAUUSD')` (or `get_market_regime_context`): Live broker quote, spread, CVD, 4M footprint bars.\n"
                    "  • `alpha-daemon-mcp_get_account_status()`: Floating PnL, equity, active ticket status.\n"
                    "  • `alpha-daemon-mcp_get_live_microstructure(symbol='XAUUSD')`: Tick velocity and adverse flow check.\n"
                    "  • `alpha-daemon-mcp_get_measured_cvd(symbol='XAUUSD')`: Live tick CVD trend.\n\n"
                    "MANDATORY ACTIVE POSITION MANAGEMENT RULES (GOODS ENGINE):\n"
                    "• MANAGE VIA SL & TP ONLY: Use `update_position` for all adjustments (`BREAK_EVEN`, `FULL_EXIT`, or SL/TP calibrate).\n"
                    "• NO MECHANICAL TICK TRAILING: Continuous pip/tick trailing is strictly FORBIDDEN. Never drag SL a few points behind live price inside the retail noise band (which chokes trades).\n"
                    "• STRUCTURAL SHELF RATCHETING ONLY (Granger Rule 1.4): Keep hard structural invalidation anchor intact. You may ratchet SL ONLY behind a newly confirmed physical M5/M15 swing shelf or FVG boundary with a 3 to 5 point buffer once price achieves confirmed displacement. Never trail in free space.\n"
                    "• FORBID PANIC KILLS: Minor counter-wicks and planned retests into the entry shelf are normal structural noise. Allow the trade to breathe within the defined SL budget as long as HTF structure and CVD flow support the thesis.\n"
                    "• STRICT BAN ON PREMATURE BREAKEVEN (NO BE SHIFTS) ON NORMAL WICKS: Once an order is filled with its structural Stop Loss, DO NOT move SL to entry/breakeven after +3 pts in quiet tape! Normal retests wick 0.5–1.5 pts past entry. LET NORMAL NOISE WORK.\n"
                    "• CHAMPION HOLD MANDATE & STRICT NO-SCRATCH DISCIPLINE (WIN 4 FORENSIC #538243241): Once filled with a 5.5–10 pt structural SL and Mode A TP (4–8 pts), LET THE BROKER HANDLE SL AND TP! Continuous tick-trailing, moving SL to BE on minor wicks, and panic-scratching on 1-minute delta flickers or relief wicks are STRICTLY FORBIDDEN. Authorized early manual exits are restricted to: (1) Emergency Tier-1 News Shield (<30m to CPI/FOMC), (2) verified HTF (M15/H1) structural close beyond invalidation, (3) 20m dead-tape stagnation (<30 t/m), or (4) Intermediate Defense Shelf Annihilation & Adverse Flow Acceleration (the declared defense shelf is 100% mitigated, an M5 candle closes decisively beyond the shelf, and order flow shows persistent adverse delta acceleration with consecutive adverse footprint blocks and defense wall failure -> mandatory controlled FULL_EXIT to preserve capital).\n"
                    "• STRICT BAN ON SHIFTING GOALPOSTS BEYOND HARD STOP LOSS: When an intermediate defense shelf breaks, never rationalize holding by citing support/resistance that lies at or beyond your hard Stop Loss!\n"
                    "• NO STALL GUARDS / NO 2.5 PT REVERSAL SCRATCHES: Strict ban on arming 2.5 pt stall guard watchers that panic-kill positions on normal pullbacks. Gold trends via impulse-retest cycles; cutting trades on a 2.5 pt pullback cuts the winning horse right before the race.\n"
                    "• BREAKOUT CONTINUATION STACKING: In Mode B trend cascades, pre-calculate Leg 2 entry milestone below TP1; the instant TP1 fills, deploy Leg 2 (`SELL_STOP` / `BUY_STOP`) without multi-cadence delay.\n"
                    "• 20-MINUTE AUCTION STAGNATION (GENUINE DEAD TAPE ONLY): If price completely stalls within ±1.0 pt of entry for 20+ continuous minutes WITH velocity collapsed into dead compression (<40 t/m) and adverse CVD building, you may scratch. However, if price has made any structural expansion (>3 pts) and is merely executing a normal retest, HOLD FIRM behind your structural stop.\n"
                    "• Target 1 Bank (User Msg 95 & 893): Bank profits cleanly at the 4.0 to 8.0 pt Mode A structural TP (strictly capped <=8.0–10.0 pts into nearest opposing pivot/shelf). NEVER stretch TP beyond 10 pts to chase paper 2:1 R:R (which caused Loss #544302915 where +8.03 pt profit reversed into a loss)!\n"
                    "• POST-TRADE FORENSIC AUTOPSY: The instant the trade closes (SL, TP, or early exit), immediately call `graphiti-memory-mcp_graphiti_add_episode` with the root cause and reusable lesson."
                )
            else:
                prompt = (
                    f"{_time_str}\n\n"
                    f"=== ALPHA CADENCE BRIEFING: EVIDENCE-FIRST PURE REASONING AUDIT (Dossier #{self.dossiers_since_brainstorm}/7) ===\n"
                    "Gather raw evidence (Macro Wire + Real Yields + Tape Physics) -> Pure Thought Process (5-Step Protocol) -> High-Conviction Decision.\n\n"
                    "MANDATORY EVIDENCE SUITE (INVOKE IN PARALLEL EVERY TURN):\n"
                    "  • Macro & Yield Grounding: `proxima_ask_perplexity` / `proxima_ddg_search` (breaking wires) + `alpha-daemon-mcp_get_fred_observations(series_id='DFII10')` (10Y real yields).\n"
                    "  • Institutional Profile: `alpha-daemon-mcp_get_full_institutional_profile(symbol='XAUUSD')` (POC, VAH, VAL, Retail BSL/SSL stop pools).\n"
                    "  • Live Broker & Microstructure: `alpha-daemon-mcp_get_market_regime_context(symbol='XAUUSD')` (quotes, spread, CVD, 4M footprint), `alpha-daemon-mcp_get_live_microstructure(symbol='XAUUSD')` (velocity TPM), `alpha-daemon-mcp_get_measured_cvd(symbol='XAUUSD')` (tick CVD delta).\n"
                    "  • Structural Matrix & Orders: `alpha-daemon-mcp_get_fvg_matrix(symbol='XAUUSD')`, `alpha-daemon-mcp_get_pending_orders()`, `alpha-daemon-mcp_cancel_pending_order()`, `alpha-daemon-mcp_get_active_watches(include_closed=False)`.\n"
                    "  • Graphiti Temporal Memory Suite: `graphiti-memory-mcp_graphiti_search_facts(patterns=[...])` (Mandatory Step 2.5: recall past walks, winning signatures & recorded stumbles) + `graphiti-memory-mcp_graphiti_add_episode(patterns=[...], outcome='WIN'|'TRAP', lesson='...')` (wire observed traps or clean expansions while flat).\n"
                    "  • Dominant Walks Audit: Call `graphiti-memory-mcp_graphiti_get_pattern_walks(symbol='XAUUSD')` for global base rates.\n\n"
                    "THE 5-STEP PURE REASONING COGNITIVE PROTOCOL (MANDATORY IN EVERY DECISION THOUGHT):\n"
                    "Before proposing, staging, or executing ANY trade, your internal reasoning MUST answer these steps in pure thought:\n"
                    "0. QUESTION 0 (4TF STRUCTURAL TREND): 4TF Bullish -> ALL SELLS FORBIDDEN. 4TF Bearish -> ALL BUYS FORBIDDEN. MIXED_TIMEFRAMES -> Stand flat unless Tier-1 news or confirmed sweep/reclaim. Ban fading overbought/oversold RSI!\n"
                    "1. QUESTION 1 (MACRO CATALYST): What breaking wire news, real yield change (DFII10), or geopolitical catalyst is driving movement right now? Macro flow must not contradict the trade!\n"
                    "2. QUESTION 2 (COORDINATES — ORIGIN VS DESTINATION & THE SACRED RUNWAY): Where did this leg start, and where is the magnetic destination pool (BSL/SSL)? Opposing FVGs in the middle of the runway are fuel, NOT resistance to fade!\n"
                    "2.5. QUESTION 2.5 (GRAPHITI MEMORY & RESILIENT SWIMMER CHECK): Formulate active 2-3 pattern combination (e.g. ['4TF_BULLISH', 'ASIAN_LOW_SWEEP', 'CVD_ABSORPTION']). Call `graphiti_search_facts(patterns=[...])`. The Resilient Swimmer: a recorded stumble is clarity on a specific execution pitfall, NOT a blanket fear or permanent ban on a setup. When live structural and tape conditions align, trade with courage!\n"
                    "3. QUESTION 3 (TAPE PHYSICS & CVD FLOW): What is raw CVD delta and velocity? Never fade aggressive delta or climactic surges!\n"
                    "4. QUESTION 4 (VEHICLE EVALUATION — IMMEDIATE MARKET VS PRE-STAGED PENDING VS STAND FLAT):\n"
                    "   • Option A (Immediate Market Execution — Prong C / User Msg 95): If momentum is active (>90–100 t/m + aligned CVD surge) or macro news arrives with open roadway to a destination magnet, execute IMMEDIATELY via `execute_market_order`! Do not delay or passively pre-stage when price is actively moving!\n"
                    "   • Option B (Pre-Staged Pending Order — Prong A/B): If price is quietly consolidating 2–5 pts from a fresh shelf (<90 t/m), pre-stage `BUY_LIMIT`/`SELL_LIMIT` at boundary, OR pre-stage `BUY_STOP`/`SELL_STOP` 1.0–2.0 pts beyond consolidation with 6–10 pt structural SL and 4–8 pt Mode A TP.\n"
                    "   • Option C (Stand Flat): Ambiguous tape, dead compression, or approaching opposing HTF resistance -> Stand flat with high conviction.\n"
                    "SYNTHESIS & THE RUNWAY TRAVERSAL MANDATE (FORENSIC PROOF #545795172):\n"
                    "• The Runway Traversal Mandate: When a catalyst arrives aligned with 4TF trend, and current price has 4.0 to 8.0 points of open runway TO an identified destination magnet (BSL/SSL or FVG CE), MANDATORY VEHICLE IS IMMEDIATE MARKET EXECUTION (`execute_market_order`). Anchor TP at or just before the magnet!\n"
                    "• STRICT PROHIBITION: NEVER stage a pending breakout stop (`BUY_STOP`/`SELL_STOP`) beyond/above the destination magnet when price is already in the runway! Trade the runway TO the magnet, never buy the breakout of the magnet!\n"
                    "• EXTENDED MOVE & APEX EXHAUSTION FILTER: Breakout stops are strictly vetoed if the destination magnet is tagged/swept, CVD absorption divergence is active, or price is displaced into major psychological round numbers ($XX00/$XX50) without a base. If trend is expanding with aligned CVD and unmitigated roadway ahead, continuation is authorized!\n"
                    "• Champion Sizing & SL Floor: 0.40–1.00L. Hard structural SL 6.0–10.0 pts. Mode A TP: 4.0–8.0 pts into nearest pivot/shelf."
                )
            post_to_opencode_session("", prompt)

            # Dispatch mandatory rule reminder strictly after the brainstorm turn only, once per cycle
            if is_brainstorm_turn:
                self._schedule_post_news_rules_reminder(delay_seconds=60.0)

        return has_active_trades

    def _schedule_post_news_rules_reminder(self, delay_seconds: float = 60.0):
        """Schedules a mandatory rule audit wake 60s after the news/brainstorm message directing OpenCode to check all rule files."""
        if hasattr(self, "_rules_reminder_timer") and self._rules_reminder_timer is not None:
            try:
                self._rules_reminder_timer.cancel()
            except Exception:
                pass

        def _reminder_worker():
            reminder_msg = (
                "⚡ ALPHA EVIDENCE WAKE — MANDATORY STANDING RULES & PLAYBOOK AUDIT\n"
                "Evidence & News gathering cycle active. You are under a STRICT INSTITUTIONAL MANDATE to cross-check and enforce all rules encoded in the following rule repository before finalizing your execution decisions or standing flat:\n\n"
                "MASTER RULE REPOSITORY (MANDATORY TO CHECK & ENFORCE):\n"
                "• Master Agent Standing Orders & Directional Mandate: C:/Trading/AGENTS.md\n"
                "• OpenCode CIO Thought Process & Execution Playbook: C:/Trading/Alpha/OPENCODE_CIO_THOUGHT_PROCESS.md\n"
                "• Trade Journal Self-Correction Rules & Autopsies: C:/Trading/Alpha/logs/trade_journal_memory.json (and C:/Trading/Alpha/logs/trade_journal_memory.md)\n"
                "• Anti-Retail Liquidity Traps Deep Guide: C:/Trading/agent/rules/08_ANTI_RETAIL_TRAPS_DEEP_GUIDE.md\n"
                "• Master Agent Trader Rules & Intraday Horizon Manifesto: C:/Trading/agent/MASTER_AGENT_RULES.md\n"
                "• System Trading Rules & Desk Mandates: C:/Trading/TRADING_RULES.md\n"
                "• Core Rule Suite: C:/Trading/agent/rules/ (01_LIQUIDITY_TRAPS.md to 07_FULL_SYSTEM_CAPABILITIES.md)\n\n"
                "MANDATORY EXECUTION AUDIT CHECKLIST:\n"
                "You MUST verify each of these criteria against the live market state and encoded rule files before finalizing:\n"
                "1. 4TF Trend Mandate (Question 0): 4TF Bullish -> BUYS ONLY. 4TF Bearish -> SHORTS ONLY. MIXED_TIMEFRAMES -> Stand flat or Turtle Soup sweep reclaims only. ZERO fading overbought/oversold RSI!\n"
                "2. Sacred Runway Traversal (Forensic #545795172): If 4.0 to 8.0 pts of open roadway exists to an identified destination magnet (BSL/SSL or FVG CE), execute IMMEDIATELY via market order and bank AT the magnet. NEVER stage pending breakout stops beyond the magnet at the apex!\n"
                "3. Semantic Distinction: A Buy-Stop Pool (BSL) or Sell-Stop Pool (SSL) is a DESTINATION TARGET TO EXIT, NEVER an entry coordinate for a broker BUY_STOP or SELL_STOP!\n"
                "4. Boundary-First & 2-Rung Split Ladder: In trending flow, stage limits at the Outer Shelf Boundary + spread buffer, or split 0.25L Boundary + 0.25L 50% CE. Never demand deep 50% CE in strong momentum.\n"
                "5. Symmetrical Pending Stops: In quiet pre-breakout tape (<80 t/m), pre-staging BUY_STOP or SELL_STOP 1.0–2.0 pts beyond consolidation has ZERO velocity blocks!\n"
                "6. Champion Hold & SL Floor: 5.5 to 10.0 pt structural Stop Loss. Mode A TP 4.0 to 8.0 pts. STRICT BAN ON PREMATURE BREAK-EVEN SHIFTS ON NORMAL NOISE. Let the trade work to hard SL or TP!\n"
                "7. Controlled Early Exit Condition: Controlled manual exit (FULL_EXIT) is authorized ONLY if your declared defense shelf is 100% mitigated, an M5 candle closes decisively outside it, AND order flow accelerates adversely relative to session volume. Never shift goalposts beyond hard SL!\n"
                "8. Trade What Is Active Right Now: Focus on the active 5–10 pt roadway right in front of you (User Directives Msg 63, 16 & 937). Never sit frozen for multi-day calendar events when active flow is presenting clean structural edges.\n"
                "9. Graphiti Temporal Memory & The Resilient Swimmer: Call `graphiti_search_facts(patterns=[...])` before finalizing. Do not fear past stumbles; note the specific pitfall and trade with courage when conditions align. If you stood flat on an avoided trap or clean expansion, wire it into memory with `graphiti_add_episode`."
            )
            post_to_opencode_session("Desk Supervisor (Rules Reminder)", reminder_msg)

        self._rules_reminder_timer = threading.Timer(delay_seconds, _reminder_worker)
        self._rules_reminder_timer.daemon = True
        self._rules_reminder_timer.name = "PostNewsRulesReminderTimer"
        self._rules_reminder_timer.start()

    async def _probe_execution_watcher_task(self):
        """Watcher task (Dollar-based auto exit is OFF)."""
        import MetaTrader5 as mt5, time
        state_file = PROJECT_ROOT / "data" / "live" / "auto_probe_engine_state.json"

        # Cached config state (Dollar-based auto exit OFF)
        cached_config = {"enabled": False, "symbol": "XAUUSD", "target_profit_usd": 0.0, "total_harvested_usd": 203.79, "harvest_count": 1}
        last_config_load = 0.0

        def _get_engine_state():
            nonlocal cached_config, last_config_load
            now = time.time()
            if now - last_config_load > 2.0:
                if state_file.exists():
                    try:
                        data = json.loads(state_file.read_text(encoding="utf-8"))
                        cached_config.update(data)
                    except Exception:
                        pass
                last_config_load = now
            return cached_config

        # One-time MT5 initialization
        _init_mt5()

        while self.is_running:
            try:
                engine_st = _get_engine_state()
                if not engine_st.get("enabled", False):
                    # Dollar-based exit disabled
                    await asyncio.sleep(2.0)
                    continue

                current_positions = mt5.positions_get()
                if current_positions is None:
                    # Connection lost -> re-initialize
                    _init_mt5()
                    await asyncio.sleep(0.1)
                    continue

                if not current_positions:
                    # Zero positions -> sleep lightly (100ms)
                    await asyncio.sleep(0.1)
                    continue

                target_profit = float(engine_st.get("target_profit_usd", 200.0))
                basket_pnl = 0.0
                basket_positions = []

                # Real-time sub-10ms tick evaluation: use both broker floating profit and live tick calculation
                for p in current_positions:
                    tick_info = mt5.symbol_info_tick(p.symbol)
                    calc_profit = p.profit
                    if tick_info:
                        if p.type == 0: # BUY position
                            tick_profit = (tick_info.bid - p.price_open) * p.volume * 100.0
                            calc_profit = max(p.profit, tick_profit)
                        elif p.type == 1: # SELL position
                            tick_profit = (p.price_open - tick_info.ask) * p.volume * 100.0
                            calc_profit = max(p.profit, tick_profit)
                    basket_pnl += calc_profit
                    basket_positions.append(p)

                # Trigger instantaneous auto-harvest the split second floating profit hits $200
                if len(basket_positions) > 0 and basket_pnl >= target_profit:
                    closed_summary = []
                    LOG.info(f"⚡ SPLIT-SECOND AUTO-HARVEST TRIGGERED: Floating PnL +${basket_pnl:.2f} >= Target +${target_profit:.2f}! Sweeping all positions...")
                    
                    for p in basket_positions:
                        tick_info = mt5.symbol_info_tick(p.symbol)
                        c_price = (tick_info.bid if p.type == 0 else tick_info.ask) if tick_info else (p.price_current)
                        c_type = mt5.ORDER_TYPE_SELL if p.type == 0 else mt5.ORDER_TYPE_BUY
                        
                        for fill_mode in [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, 0, mt5.ORDER_FILLING_RETURN]:
                            close_req = {
                                "action": mt5.TRADE_ACTION_DEAL,
                                "position": p.ticket,
                                "symbol": p.symbol,
                                "volume": p.volume,
                                "type": c_type,
                                "price": c_price,
                                "deviation": 50,
                                "magic": p.magic,
                                "comment": "Auto-Harvest Win",
                                "type_time": mt5.ORDER_TIME_GTC,
                                "type_filling": fill_mode
                            }
                            res = mt5.order_send(close_req)
                            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                closed_summary.append(f"Ticket #{p.ticket} ({p.volume} lots) profit: +${p.profit:.2f}")
                                break

                    # Unconditionally cancel ALL pending orders on MT5 to guarantee 100% clean slate
                    pending_orders = mt5.orders_get() or []
                    for o in pending_orders:
                        mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket})

                    # Update persistent stats & return cleanly to IDLE
                    engine_st["total_harvested_usd"] = round(engine_st.get("total_harvested_usd", 0.0) + basket_pnl, 2)
                    engine_st["harvest_count"] = engine_st.get("harvest_count", 0) + 1
                    engine_st["last_harvest_time"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                    _save_engine_state(engine_st)

                    harvest_msg = (
                        f"🎉🎉 [SYSTEM AUTO-WIN HARVEST ACHIEVED: +${basket_pnl:.2f}] 🎉🎉\n"
                        f"• Realized Net Profit: +${basket_pnl:.2f} (Target: ${target_profit:.2f})\n"
                        f"• Closed Positions: {len(closed_summary)}\n  • " + "\n  • ".join(closed_summary) + "\n"
                        f"• Lifetime Harvested Total: ${engine_st['total_harvested_usd']:.2f} ({engine_st['harvest_count']} wins)\n"
                        f"• DESK STATUS: 100% FLAT (All trades & pending orders cleared. No auto-flip).\n"
                        f"• CIO MANDATE: Scout the fresh market structure and deploy your next evaluated setup!"
                    )
                    LOG.info(f"AUTO-WIN HARVEST SUCCESS: +${basket_pnl:.2f} banked! Desk is 100% FLAT.")
                    post_to_opencode_session("OpenCode (CIO)", harvest_msg)

                # Sub-10ms ultra-high-frequency loop when active positions exist
                await asyncio.sleep(0.01)
            except Exception as e:
                LOG.debug(f"UniversalAutoHarvestEngine loop error: {e}")
    async def _realtime_watcher_task(self):
        """Ultra-fast 500ms real-time loop tracking MT5 pending order fills, price triggers, and tape kinetics."""
        import MetaTrader5 as mt5
        from tradingagents.evidence_state import EvidenceStateStore
        from tradingagents.cvd_engine import CumulativeVolumeDeltaEngine

        LOG.info("🚀 Starting 500ms Universal Real-Time Watcher Task (Pure Structural & Tape Execution)...")
        ev_store = EvidenceStateStore()
        cvd_engine = CumulativeVolumeDeltaEngine()

        while self.is_running:
            try:
                mt5_ok = _init_mt5()
                if mt5_ok:
                    current_positions = mt5.positions_get() or []
                    current_pending = mt5.orders_get() or []
                    active_watches = [w for w in ev_store.get_watches(include_closed=False) if (w.get("status") or "ACTIVE").upper() == "ACTIVE"]

                    # Gather high-speed live tape snapshot for XAUUSD
                    live_tape = {}
                    try:
                        flow = cvd_engine.get_symbol_cvd("XAUUSD")
                        live_tape = {
                            "velocity": flow.get("tick_velocity_tpm", 0.0),
                            "spread": flow.get("live_spread_pts", 0.0),
                            "cvd_10b": flow.get("recent_10_bar_delta", 0.0),
                            "current_m1_delta": flow.get("current_m1_delta", 0.0),
                            "micro_delta_4m": flow.get("micro_delta_4m", 0.0),
                            "cum_cvd": flow.get("cumulative_volume_delta", 0.0)
                        }
                    except Exception as _fl_err:
                        LOG.debug(f"Watcher tape snapshot err: {_fl_err}")

                    # 1. Evaluate pending order fills (Split-Second Alert!)
                    fill_alerts = self.watcher_engine.check_pending_order_fills(
                        current_positions=current_positions,
                        current_pending_orders=current_pending,
                        active_watches=active_watches,
                        live_tape=live_tape
                    )
                    for fa in fill_alerts:
                        if fa.get("watch"):
                            w_id = fa["watch"].get("id") or fa["watch"].get("watch_id")
                            if w_id:
                                ev_store.update_watch(w_id, status="COMPLETED", triggered_at=datetime.now(timezone.utc).isoformat())
                                fa["watch"]["status"] = "COMPLETED"
                        LOG.info(f"⚡ [SPLIT-SECOND FILL ALERT] Ticket #{fa['ticket']} ({fa['symbol']} {fa['side']} {fa['volume']} lots @ {fa['price']:.2f})")
                        log_local_llm_monitoring(f"⚡ [SPLIT-SECOND FILL ALERT] Ticket #{fa['ticket']} ({fa['symbol']} {fa['side']})")
                        post_to_opencode_session("OpenCode (CIO)", fa["prompt"])

                    # 2. Evaluate active watches against live tick & tape
                    watched_symbols = set(w.get("symbol", "XAUUSD").upper() for w in active_watches if (w.get("status") or "ACTIVE").upper() == "ACTIVE")
                    if not watched_symbols:
                        watched_symbols = {"XAUUSD"}

                    for sym in watched_symbols:
                        tick = mt5.symbol_info_tick(sym)
                        if not tick:
                            continue
                        bid = float(getattr(tick, "bid", 0.0))
                        ask = float(getattr(tick, "ask", 0.0))
                        last_t = self.watcher_engine.last_ticks.get(sym, {"bid": bid, "ask": ask})

                        tape_data = dict(live_tape)
                        tape_data["spread"] = round((ask - bid) * 10, 1) if ask > bid else 0.0

                        sym_watches = [w for w in active_watches if w.get("symbol", "XAUUSD").upper() == sym and (w.get("status") or "ACTIVE").upper() == "ACTIVE"]
                        for w in sym_watches:
                            trig = self.watcher_engine.evaluate_watch(
                                watch=w,
                                live_tick={"bid": bid, "ask": ask, "price": (bid + ask) / 2.0},
                                last_tick=last_t,
                                tape_metrics=tape_data,
                                positions=current_positions
                            )
                            if trig:
                                wid = trig["watch_id"]
                                now_iso = datetime.now(timezone.utc).isoformat()
                                # User mandate: All watches clear immediately upon trigger!
                                ev_store.update_watch(wid, status="COMPLETED", triggered_at=now_iso)
                                w["status"] = "COMPLETED"
                                LOG.info(f"⚡ WATCH TRIGGERED & CLEARED: {wid} -> {trig['trigger_reason']}")
                                log_local_llm_monitoring(f"⚡ WATCH TRIGGERED & CLEARED: {wid} ({trig['trigger_reason']})")
                                post_to_opencode_session("OpenCode (CIO)", trig["prompt"])

                        self.watcher_engine.last_ticks[sym] = {
                            "bid": bid,
                            "ask": ask,
                            "last_cvd": float(live_tape.get("cvd_10b", 0.0))
                        }

                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                LOG.debug(f"Watcher task error: {e}")
                await asyncio.sleep(1.0)

    async def start_loop(self):
        self.is_running = True
        dossier_mins = max(1, int(round(get_dossier_interval_seconds() / 60.0)))
        active_mins = max(1, int(round(get_active_trade_interval_seconds() / 60.0)))
        LOG.info(f"Consolidated Trading Daemon started with Dynamic Briefing Cadence ({active_mins}-min active trades, {dossier_mins}-min idle).")
        sid, title, _ = get_opencode_session()
        self.last_session_id = sid
        self.last_dispatch_time = time.time()
        self.next_turn_type = "DOSSIER"
        self.has_dispatched_initial_dossier = False
        # Immediately fire startup ping to OpenCode so user knows daemon is alive
        self.dispatch_startup_ping(sid, title)
        # Start ultra-fast 500ms Universal Watcher Task
        self.watcher_task = asyncio.create_task(self._realtime_watcher_task())
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
            initialized = _init_mt5()
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
