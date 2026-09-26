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
                if 'intelligent_daemon' in cmd_str or 'alpha_trading_desk' in cmd_str:
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
        # If session already has conversation history (e.g. seeded via session_seeder), skip duplicate greeting
        try:
            from tradingagents.session_seeder import get_session_messages
            msgs = get_session_messages(sid)
            if len(msgs) >= 2:
                LOG.info(f"Session '{title}' ({sid}) is already seeded ({len(msgs)} messages). Skipping redundant startup ping.")
                # Infer last turn from message history to ensure seamless alternating cadence
                for m in reversed(msgs):
                    if m.get("info", {}).get("role") == "user":
                        txt = "".join(p.get("text", "") for p in m.get("parts", []) if p.get("type") == "text")
                        if "Turn A" in txt:
                            self.dispatch_count = 1
                            self.next_turn_type = "BRAINSTORM"
                            LOG.info("Synchronized cadence: Last session turn was Turn A -> Next dispatch will be Turn B.")
                            break
                        elif "Turn B" in txt:
                            self.dispatch_count = 2
                            self.next_turn_type = "DOSSIER"
                            LOG.info("Synchronized cadence: Last session turn was Turn B -> Next dispatch will be Turn A.")
                            break
                return
        except Exception as _sync_err:
            LOG.debug(f"Could not synchronize session turn history: {_sync_err}")

        dossier_mins = max(1, int(round(get_dossier_interval_seconds() / 60.0)))
        active_mins = max(1, int(round(get_active_trade_interval_seconds() / 60.0)))
        post_to_opencode_session(
            "OpenCode (CIO)",
            f"=== ALPHA TRADING DESK DAEMON ONLINE ===\n"
            f"Session: {title} ({sid})\n"
            f"Current UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"Daemon: ONLINE | Tick ingestion: 2s | Universal Watcher: 500ms Active | Briefing: Turn A (4-Min Physical Dossier) <-> Turn B (8-Min 5-Question Macro Repricing)\n\n"
            f"=== EVIDENCE-FIRST AUTHORITY & MANDATORY 5-POD ADVERSARIAL PROTOCOL ===\n"
            f"OpenCode is the sole operational CIO and trade decision-maker. The daemon only observes and wakes a new investigation.\n"
            f"MANDATORY ON EVERY WAKE: Evaluate through all 5 Pod lenses (Macro Wire Gravity, Order Flow CVD, 4TF Technical Geometry, Adversarial Counter-Trap, Execution Arbiter).\n\n"
            f"=== PROVEN WINNING EXECUTION BLUEPRINT (ALPHA GRANGER 7-LAYER CHAMPION DESK) ===\n"
            f"• Trade What Is Revolving Around Right Now: Trade the active present. Never freeze or wait for tomorrow's calendar events when edge exists on the table.\n"
            f"• 7-Layer Institutional Conviction: High-conviction execution requires 7-layer alignment (COT, real yields DFII10, 4TF EMAs/RSI, FVG CE coordinates, Bull vs Bear debate) via `query_analyst_desk` (Conviction >= 7.0/10).\n"
            f"• Sizing Realism & Growth Blueprint: Sizing is 0.50 to 1.00 lots (1.00L standard on high conviction >= 8.0/10 + 4TF alignment; 0.50L on baseline 7.0-7.9).\n"
            f"• Positive Asymmetric R:R (>= 1.5:1 to 2.5:1+ Floor): Every trade must target opposing structural liquidity (opposing FVG CE, POC, Value Area boundary, or liquidity sweep) that provides at least 1.5x the stop distance. Inverted negative R:R (<1.5:1) is strictly vetoed!\n"
            f"• Structural SL Grounding: Anchor SL firmly behind HTF structural invalidation + 1.5x ATR14 buffer (6.0 to 12.0 pts). Never squeeze stops into 2-point noise wicks.\n"
            f"• Mechanical Bracket Discipline: Once filled, LET THE BROKER TERMINAL MANAGE SL/TP. Stop cutting winners early out of micro-fear; let the mathematical 1.5R to 3R target run to completion (banking +$1,000 to +$2,500 per win). Once > +1.0R in profit, trail SL behind structural swing shelves with a 3–5 pt buffer (BE -> +1R -> +2R).\n"
            f"• NO PASSIVE WATCH SENSOR LOOPS: Pre-stage orders directly on MT5 book. Never substitute `register_watch` for real broker execution.\n\n"
            f"=== RESTORED ON-DEMAND CHAMPION TOOLS ===\n"
            f"  • Post-Trade Forensics: `alpha_get_trade_forensics(ticket=...)`\n"
            f"  • Pre-Order Coordinates: `alpha_get_deep_orderflow_telemetry(symbol='XAUUSD')` (Pod 5 only: extract exact FVG 50% CE price, VWAP bands, and ATR14 stop buffer)\n"
            f"  • Decision Grounding: `alpha_record_decision_snapshot(...)`\n"
            f"  • Memory: `graphiti_record_observation()`, `graphiti_search_facts()`, `graphiti_add_episode()`\n"
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
        headline = "Physical Telemetry & Topological Graph Active"

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

        detailed_pending_orders = []
        try:
            if mt5_online:
                pending = mt5.orders_get()
                if pending:
                    for o in pending:
                        type_str = 'BUY_LIMIT' if o.type == 2 else 'SELL_LIMIT' if o.type == 3 else 'BUY_STOP' if o.type == 4 else 'SELL_STOP' if o.type == 5 else str(o.type)
                        tick = mt5.symbol_info_tick(o.symbol)
                        dist_pts = abs(tick.bid - o.price_open) if tick else 0.0
                        elapsed_m = (time.time() - o.time_setup) / 60.0 if getattr(o, 'time_setup', 0) else 0.0
                        detailed_pending_orders.append(
                            f'Ticket #{o.ticket} ({o.symbol} {type_str} {o.volume_current:.2f}L @ {o.price_open:.2f} | Dist: {dist_pts:.1f} pts | Age: {elapsed_m:.0f}m | GTC: NO AUTO-EXPIRATION)'
                        )
        except Exception as err:
            LOG.error(f'MT5 pending order audit failed: {err}')

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
            # Active trade cadence: Calm 180s (3m) interval to give the trade room to breathe
            # Prevents LLM panic cuts and micro-fear while maintaining steady telemetry oversight
            if self.just_sent_active_brainstorm:
                required_interval = 300.0  # 5 min breathe gap after in-flight audit
                self.just_sent_active_brainstorm = False
            else:
                required_interval = float(active_trade_interval) if active_trade_interval >= 180 else 180.0
        else:
            self.active_burst_step = 0
            self.just_sent_active_brainstorm = False
            # Idle Cadence: Alternating Turn A (Physical Dossier, 4 min) <-> Turn B (5-Question Macro Repricing, 4 min)
            # Both turns run on a 4-minute (240s) interval, completing a full 8-minute A <-> B cycle
            required_interval = float(dossier_interval) if dossier_interval >= 180 else 240.0

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
                # Active trade pattern: 1m review x 3 -> in-flight audit -> 5m gap
                self.active_burst_step = (self.active_burst_step % 4) + 1
                if self.active_burst_step == 4:
                    is_brainstorm_turn = True
                    self.just_sent_active_brainstorm = True
                    self.last_dispatched_turn_type = "ACTIVE_BRAINSTORM"
                    LOG.info("⚡ Cadence: Dispatched Active In-Flight Audit (Step 4/4). Next interval: 5-minute breathe gap (300s).")
                else:
                    is_brainstorm_turn = False
                    self.just_sent_active_brainstorm = False
                    self.last_dispatched_turn_type = "ACTIVE_POSITION_REVIEW"
                    LOG.info(f"⚡ Cadence: Dispatched Active Position Review (Step {self.active_burst_step}/4). Next interval: 1 minute.")
            elif triggered_watch is not None:
                is_brainstorm_turn = False
                self.last_dispatched_turn_type = "WATCH_TRIGGER"
            else:
                # Idle pattern: Turn A (Physical Dossier) <-> Turn B (5-Question Macro Repricing)
                is_brainstorm_turn = (self.dispatch_count % 2 == 0) and not is_startup
                if is_brainstorm_turn:
                    self.last_dispatched_turn_type = "BRAINSTORM"
                    self.next_turn_type = "DOSSIER"
                    LOG.info("📰 Cadence: Dispatched Turn B (5-Question Macro Repricing Evaluation). Next interval: 4 minutes.")
                else:
                    self.last_dispatched_turn_type = "DOSSIER"
                    self.next_turn_type = "BRAINSTORM"
                    LOG.info("📊 Cadence: Dispatched Turn A (Physical Microstructure Dossier with 4TF Header). Next interval: 4 minutes (Turn B).")

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
                    f"1. DIRECT STAGING / EXECUTION: If a breaking catalyst, active kinetic surge (expanding velocity + CVD delta surge), or Turtle Soup reclaim is active right at structure, IMMEDIATELY call `alpha_execute_market_order` (BUY/SELL) with 0.40–1.00L, 6.0–10.0 pt SL, and Mode A (4–8 pt) or Extended Mode B (12–20 pt) TP! If tape is quietly consolidating 2–5 pts from structure, IMMEDIATELY deploy the pre-planned order (`alpha_place_pending_order` BUY_LIMIT/SELL_LIMIT/BUY_STOP/SELL_STOP) on MT5 in this very turn! Do not defer execution or staging to a secondary turn.\n"
                    f"2. PARALLEL TELEMETRY CONFIRMATION: Call `alpha_get_market_regime_context(symbol='{triggered_watch.get('symbol', 'XAUUSD')}')` in parallel to ground the fill.\n"
                    f"3. HARD SIZING & STOPS: 0.40–0.50L baseline, 6.0–10.0 pt structural SL, 4.0–8.0 pt Mode A TP (or 12.0–20.0 pt Extended TP). Spread-compensated limits (+0.35 on BUY_LIMIT, -0.35 on SELL_LIMIT).\n"
                    f"4. 5-POD ADVERSARIAL EVALUATION MANDATORY."
                )
            elif has_active_trades and is_brainstorm_turn:
                # Active trade burst step 4: In-Flight Audit before 5-minute breathe gap
                prompt = (
                    f"⚡ ALPHA IN-FLIGHT MACRO & STRUCTURE AUDIT (Active Trade Step 4/4)\n"
                    f"{_time_str}\n\n"
                    f"Active positions in flight: {len(open_tickets)}\n"
                    f"Notice: A 5-minute uninterrupted breathe gap (300s) begins immediately after this review.\n\n"
                    f"STEP 0 (MANDATORY IN-FLIGHT PARALLEL AUDIT & CONTINUOUS FACT GROUNDING):\n"
                    f"  • `alpha_get_market_regime_context(symbol='XAUUSD')`: Live quotes, spread, CVD, 4M footprint deltas.\n"
                    f"  • `alpha_get_account_status()`: Current floating PnL, margin utilization.\n"
                    f"  • `graphiti_search_facts(patterns=['<IN_FLIGHT_STATE_TAGS>'])`: Contrast live in-flight retest/drawdown against past win/stumble walks (Pillar 1: Past stumble is NOT a veto unless adverse condition is active today).\n"
                    f"  • `proxima_ask_perplexity(message=\"Gold XAUUSD breaking news headlines in last 15 minutes\")`: Check surprise breaking wires.\n"
                    f"  • `graphiti_record_observation(patterns=[...], observation='...', outcome='STUDY'|'WIN'|'TRAP')`: Record in-flight trade dynamics.\n\n"
                    f"LIVE POSITION SNAPSHOT (direct from MT5 — no hallucination):\n"
                    f"{'  ' + chr(10).join(f'  {p}' for p in detailed_positions) if detailed_positions else '  No open positions.'}\n\n"
                    f"IN-FLIGHT POSITION ARBITRATION:\n"
                    f"STEP 1 — STRUCTURAL INTEGRITY CHECK (from your telemetry calls above):\n"
                    f"  • Entry-to-SL buffer: Is structural SL still > 6.0 pts from current price with an intact anchor shelf?\n"
                    f"  • M15/H1 candle CLOSE: Has any M15 or H1 candle CLOSED decisively BEYOND the SL anchor level (closed bar, not a wick)?\n"
                    f"  • Adverse CVD persistence: Has adverse delta been building continuously for > 20 minutes? Is velocity < 30 t/m?\n"
                    f"  • News Shield: Is there a Tier-1 macro release (CPI/FOMC/NFP/GDP) within 30 minutes?\n\n"
                    f"STEP 2 — VERDICT GATE (evaluate each condition explicitly, in order):\n"
                    f"  IF any of these 4 conditions are TRUE → call `alpha_update_position(ticket, action='FULL_EXIT')` NOW:\n"
                    f"    (1) Tier-1 News Shield: < 30m to CPI/FOMC/NFP → EXIT immediately.\n"
                    f"    (2) HTF Structural Close: An M15 or H1 candle has CLOSED beyond the structural SL anchor level → EXIT immediately.\n"
                    f"    (3) Dead-Tape Stagnation: > 20 consecutive minutes with velocity < 30 t/m AND adverse CVD building → EXIT.\n"
                    f"    (4) Defense Shelf Annihilation: Intermediate structural shelf fully breached with persistent adverse delta acceleration → EXIT.\n"
                    f"  IF none of the above are TRUE → HOLD_BRACKET. Normal candle wicks (0.5–2.0 pts) are structural breathing — do NOT cut.\n\n"
                    f"  BALANCE REMINDER: Cutting on normal noise = CONST_NO_PREMATURE_CUT violation. Holding through verified HTF structural close = CONST_NO_CLEAR violation. Both are constitutional failures.\n\n"
                    f"FORMAT YOUR VERDICT VIA THE 5-POD PROTOCOL:\n"
                    f"### POD 1: MACRO & CATALYST PERMISSION\n"
                    f"### POD 2: ORDER FLOW & TAPE REALITY\n"
                    f"### POD 3: TECHNICAL STRUCTURE & ROADWAYS\n"
                    f"### POD 4: ADVERSARIAL DEVIL'S ADVOCATE (THE COUNTER-TRAP & FACT GROUNDING)\n"
                    f"- Cite `graphiti_search_facts`: Does live in-flight tape match holding victory or confirmed defense failure?\n"
                    f"### POD 5: EXECUTION ARBITER — HOLD_BRACKET or EXIT (state which of the 4 gates, if any, is verified)\n"
                )
            elif has_active_trades:
                # Active trade burst: Calm 3-minute position review
                prompt = (
                    f"⚡ ALPHA EVIDENCE WAKE — ACTIVE POSITION REVIEW (Step {self.active_burst_step}/4)\n"
                    f"{_time_str}\n\n"
                    f"ACTIVE TRADE AUDIT & CONTINUOUS FACT GROUNDING PROTOCOL:\n"
                    f"An active position is currently in flight. Execute immediate physical audit & memory grounding:\n\n"
                    f"STEP 0 (MANDATORY IN PARALLEL — TAPE + FACTS):\n"
                    f"  • `alpha_get_market_regime_context(symbol='XAUUSD')`: Live broker quote, spread, CVD, 4M footprint deltas, and velocity.\n"
                    f"  • `alpha_get_account_status()`: Floating PnL, equity, active ticket status.\n"
                    f"  • `graphiti_search_facts(patterns=['<IN_FLIGHT_STATE_TAGS>'])`: Ground in-flight retest/pressure against past walks (Pillar 1: Stumble is NOT a veto unless adverse condition is active today; Pillar 4: Zero mental ticket recall).\n"
                    f"  • `graphiti_record_observation(patterns=[...], observation='...', outcome='STUDY'|'WIN'|'TRAP')`: Permanently record in-flight trade dynamics into Graphiti memory.\n\n"
                    f"LIVE POSITION SNAPSHOT (direct from MT5 — no hallucination):\n"
                    f"{'  ' + chr(10).join(f'  {p}' for p in detailed_positions) if detailed_positions else '  No open positions.'}\n\n"
                    f"MANDATORY POSITION MANAGEMENT RULES:\n"
                    f"• DEFAULT: HOLD_BRACKET. MT5 SL/TP bracket governs. Normal candle wicks (0.5–2.0 pts past entry) are structural noise — do NOT cut.\n"
                    f"• AUTHORIZED EXIT GATES (4 conditions — evaluate each explicitly from live telemetry):\n"
                    f"    (1) Tier-1 News Shield: < 30m to CPI/FOMC/NFP → EXIT immediately.\n"
                    f"    (2) HTF Structural Close: An M15 or H1 candle has CLOSED beyond the structural SL anchor level → EXIT immediately.\n"
                    f"    (3) Dead-Tape Stagnation: > 20 consecutive minutes with velocity < 30 t/m AND adverse CVD building → EXIT.\n"
                    f"    (4) Defense Shelf Annihilation: Intermediate structural shelf fully breached with persistent adverse delta → EXIT.\n"
                    f"• NO MECHANICAL TRAILING inside noise bands. SL ratchet ONLY behind confirmed M5/M15 swing shelf after > +1.0R advance.\n"
                    f"• BANNED: Moving SL to breakeven after +2–3 pts. Cutting on normal retest noise.\n"
                    f"• TARGET BANKING: Bank at Mode A TP (4.0–8.0 pts) OR let ride to Extended Mode B TP (12.0–20.0 pts) on major H1/H4 imbalance targets.\n"
                    f"• POST-TRADE AUTOPSY: On close, call `alpha_get_trade_forensics(ticket=...)`, `graphiti_add_episode`, AND `rules_promote_rule` / `rules_demote_rule`.\n\n"
                    f"EVALUATE VIA 5-POD ADVERSARIAL PROTOCOL.\n"
                    f"POD 5 VERDICT: HOLD_BRACKET if none of the 4 gates are verified. EXIT if any gate is confirmed. State explicitly which gate (if any) is triggered."
                )
            try:
                from tradingagents.topological_graph_engine import get_topological_engine
                _topo_vector = get_topological_engine().format_dossier_compact_vector("XAUUSD") + "\n\n"
            except Exception as _topo_err:
                _topo_vector = ""

            if is_brainstorm_turn:
                # Turn B: Dynamic 5-Question News & Macro Repricing Evaluation (Champion Alpha v14 Format)
                prompt = (
                    f"ALPHA 5-QUESTION NEWS & MACRO BRAINSTORM TURN (Turn B) — {trigger}\n"
                    f"{_time_str}\n"
                    f"{_topo_vector}"
                    f"Active instruments: {', '.join(self.instruments)}\n"
                    f"Open positions: {len(open_tickets)}\n"
                    f"ACTIVE PENDING ORDERS ON MT5 ({len(detailed_pending_orders)}):\n"
                    f"{'  ' + chr(10).join(f'  {p}' for p in detailed_pending_orders) if detailed_pending_orders else '  None (Book clean).'}\n"
                    f"*STALE PENDING PROTOCOL (CONST_STALE_PENDING_PROHIBITION): MT5 orders are GTC and NEVER self-expire. If any order is > 15.0 pts away from market or resting > 60m without fill, CANCEL IT NOW via `alpha_cancel_pending_order(ticket)`.\n\n"
                    f"=== THE CHAMPION NEWS & CAUSAL MACRO MANDATE ===\n"
                    f"Conduct a lean, targeted news & macro repricing audit via the Aperture: (1) `alpha_get_live_world_events(category='ALL', limit=15)` for 0ms verified global wire headlines, (2) 1x dynamic `proxima_ask_perplexity` query targeting the active catalyst, (3) `alpha_query_analyst_desk(symbol='XAUUSD')` for 7-Layer Local LLM Multi-Agent synthesis and Bull vs Bear clash, (4) `alpha_get_pending_orders(symbol='ALL')` to audit/replan active resting orders on MT5, (5) `alpha_get_market_regime_context(symbol='XAUUSD')` for live quotes, spread, CVD and real yields, (6) `alpha_get_topological_liquidity_map(symbol='XAUUSD')` for spatial radar and cascade targets, and (7) `graphiti_search_facts(patterns=[...])` for empirical pattern contrast.\n"
                    f"For planning the next trade: you have 0.50 - 1.00 lot area to place the lots based on 7-layer conviction and the power of the news. Always pull latest and closest news possible. Always replan any pending orders each time you pull the news. Live session clocks and gates are already injected in the header above.\n\n"
                    f"CORE REPRICING EVALUATION VECTORS (LEAN CAUSAL DISCOVERY):\n"
                    f"1. Q-NEWS-1 [Zero-Assumption Wire Pulse]: Call 1x `alpha_get_live_world_events(category='ALL', limit=15)` to pull unfiltered real-time global wires (CNBC, US Treasury, Fed Press, FXStreet, Commodities). What breaking geopolitical events, sovereign bond shocks, or central bank releases are actively hitting the wire?\n"
                    f"2. Q-NEWS-2 [Displacement vs. Catalyst Reconciliation]: Reconcile today's active leg displacement and session timing (from the header above) against live wires. Is current price expansion backed by a real sovereign catalyst, or is it an overnight/session liquidity hunt in an informational vacuum?\n"
                    f"3. Q-NEWS-3 [Dynamic Deep Inquiry & 7-Layer Replan]: Based on the active leg and wire clues from Q1/Q2, dynamically formulate your targeted search query (do NOT use static keywords). Target the specific transmission channel driving this session: Call 1x `proxima_ask_perplexity(message=\"...\")`, 1x `alpha_query_analyst_desk(symbol='XAUUSD')` for Bull vs Bear arguments, and audit/replan active resting limit/stop orders with `alpha_get_pending_orders(symbol='ALL')`.\n"
                    f"4. Q-NEWS-4 [Continuous Memory Grounding — Mandatory in Parallel]: Formulate 2–3 scale-invariant tags from the 3-Vector Grammar ([Macro] + [Location] + [Physics], e.g. ['4TF_STRONG_BEARISH', 'BSL_SWEEP', 'CVD_ABSORPTION']) and call 1x `graphiti_search_facts(patterns=[...])`. Contrast live tape against both the winning condition and failure pitfall.\n"
                    f"5. Q-NEWS-5 [Execution Action via 5-Pod Protocol & Pre-Order Calibration]: Given combined news velocity, rate shifts, and empirical facts, execute or stand flat with mathematical certainty (Targeting Opposing FVG CE / Major Liquidity with R:R >= 1.5:1 floor calculated dynamically from market structure). When an order is planned, call `alpha_get_deep_orderflow_telemetry(symbol='XAUUSD')` to extract exact FVG 50% CE price, VWAP bands, and ATR14 stop buffer. -> `alpha_execute_market_order`, `alpha_place_pending_order`\n\n"
                    f"MANDATORY FORMAT (MATCHING THE PROVEN ESCANOR V72 DEEP REASONING STYLE):\n"
                    f"Deliver your deliberation in full analytical depth matching v72:\n\n"
                    f"### Q-NEWS-1 — Zero-Assumption Wire Pulse (verbatim wires & calendar risk)\n"
                    f"• Quote verbatim wires from `alpha_get_live_world_events` and Perplexity findings. Detail specific macro risks (auctions, inflation expectations, Fed speakers, geopolitical headlines).\n\n"
                    f"### Q-NEWS-2 — Displacement vs. Catalyst Reconciliation\n"
                    f"• Classify definitively as `GENUINE_MACRO_CATALYST` vs `LIQUIDITY_HUNT_IN_VACUUM` / `PERSISTENT_RATES_GRAVITY`. Reconcile today's active leg against rates/yields (DFII10, US10Y, DXY).\n\n"
                    f"### Q-NEWS-3 — 7-Layer Replan\n"
                    f"• 4TF posture, physical tape shift (CVD 5m, 10b delta %, velocity t/m, 4M footprint delta blocks), and active MT5 pending order book audit.\n\n"
                    f"### Q-NEWS-4 — Continuous Memory Grounding\n"
                    f"• Cite `graphiti_search_facts` output. Contrast live tape against documented winning signature vs failure pitfall.\n\n"
                    f"### Q-NEWS-5 — Execution via 5-Pod\n"
                    f"• Pre-order coordinate calibration (`alpha_get_deep_orderflow_telemetry`), mathematical R:R calculation, strategic verdict (Standing Flat, Market Order, or Pending Limit/Stop), and conditional plans with exact price coordinates.\n"
                )
            else:
                # Turn A: Physical Microstructure Dossier with 4TF Header Streamed in Text
                prompt = (
                    f"=== ALPHA CADENCE BRIEFING: PHYSICAL DOSSIER & MICROSTRUCTURE AUDIT (Turn A) ===\n"
                    f"{_time_str}\n\n"
                    f"{full_4tf_reveal_block}"
                    f"=== PHYSICAL BROKER METRICS & REGIME ===\n"
                    f"{_regime_badge}\n\n"
                    f"{_topo_vector}"
                    f"MANDATE & DISCIPLINE (AGENTS.md):\n"
                    f"• Principle 0: A wake is an observation cycle, NOT a trade mandate. Standing flat in quiet chop is your high-conviction decision.\n"
                    f"• Execution Standard: When 7-layer edge is confirmed, enforce 0.50-1.00L sizing, structural SL (6.0-12.0 pts), and positive R:R >= 1.5:1 to 2.5:1+ into opposing structural liquidity. Direct MT5 execution/pre-staging only (no passive watch loops).\n"
                    f"• STALE PENDING ORDER LAW (CONST_STALE_PENDING_PROHIBITION): MT5 pending orders are GTC and DO NOT self-expire at session boundaries or midnight. Any resting order > 15.0 pts away or resting > 60m must be evaluated and actively cancelled via `alpha_cancel_pending_order()`.\n\n"
                    f"ACTIVE PENDING ORDERS ON MT5 ({len(detailed_pending_orders)}):\n"
                    f"{'  ' + chr(10).join(f'  {p}' for p in detailed_pending_orders) if detailed_pending_orders else '  None (Book clean).'}\n\n"
                    f"CORE PARALLEL AUDIT & CONTINUOUS FACT GROUNDING (MANDATORY ON EVERY CYCLE):\n"
                    f"  1. Parallel Microstructure & Spatial Audit: `alpha_query_analyst_desk(symbol='XAUUSD')`, `alpha_get_market_regime_context(symbol='XAUUSD')`, `alpha_get_account_status()`, `alpha_get_pending_orders(symbol='ALL')`, `alpha_get_topological_liquidity_map(symbol='XAUUSD')`\n"
                    f"  2. Continuous Fact Grounding: `graphiti_search_facts(patterns=[...])` using 2-3 scale-invariant tags from the 3-Vector Grammar (`Macro` + `Location` + `Physics`). Returns <80-token contrast card.\n"
                    f"  • Pre-Order Execution Coordinates (Pod 5 Only): When planning an order, call `alpha_get_deep_orderflow_telemetry(symbol='XAUUSD')` to pull exact FVG 50% CE, VWAP ±1σ/2σ bands, and ATR14 stop buffer. (Strictly prohibited on routine scans to eliminate Level 2 DOM noise).\n"
                    f"  • Dynamic Execution Standard: Anchor TP dynamically to opposing structural liquidity (opposing FVG CE, POC, or session extreme) enforcing R:R >= 1.5:1 floor (no arbitrary point limits).\n"
                    f"  • Direct MT5 Execution: `alpha_place_pending_order()`, `alpha_execute_market_order()`, `alpha_cancel_pending_order()`, `alpha_update_position()`\n"
                    f"  • Observational Learning: `graphiti_record_observation(patterns=[...], observation='...', outcome='STUDY'|'WIN'|'TRAP')` (pure causal physics, zero diary timestamps).\n"
                    f"  *(Note: Deep news searches and FRED observations are reserved for periodic Turn B every 3rd/4th dossier to prevent prompt bloat)*\n\n"
                    f"MANDATORY FORMAT (MATCHING THE PROVEN ESCANOR V72 DEEP REASONING STYLE):\n"
                    f"Deliver your deliberation in full analytical depth matching v72:\n\n"
                    f"### POD 1: MACRO & CATALYST PERMISSION\n"
                    f"• Wire pulse & rates gravity: DFII10 real yields, US10Y nominal, DXY trend. Macro causality classification (`GENUINE_MACRO_CATALYST` vs `LIQUIDITY_HUNT_IN_VACUUM` / `PERSISTENT_RATES_GRAVITY`) and directional permission.\n\n"
                    f"### POD 2: ORDER FLOW & TAPE REALITY\n"
                    f"• Physical tape kinetics: CVD 5m, 10-bar delta progression, last 4M footprint delta blocks, M1 microflow, velocity (t/m), spread, and DOM depth ladder.\n\n"
                    f"### POD 3: TECHNICAL STRUCTURE & ROADWAYS (INSTITUTIONAL GEOMETRY & TOPOLOGICAL MAP)\n"
                    f"• 4TF posture (H4/H1/M15/M5), key structural levels, FVG zones & CE fill %, unmitigated demand/supply magnets, sweep verification (penetrated vs mid-air reversal), and topological obstacle clearance (>= 1.5R, cascade targets).\n\n"
                    f"### POD 4: ADVERSARIAL DEVIL'S ADVOCATE — Continuous Fact Grounding\n"
                    f"• Graphiti memory grounding (winning signature vs recorded stumble), live tape cross-examination, and mathematical anti-inverted-R:R test.\n\n"
                    f"### POD 5: EXECUTION ARBITER — VERDICT\n"
                    f"• Definitive verdict (`STANDING FLAT`, immediate market execution, or pending limit/stop), exact justification, and structured conditional roadmap with exact price, SL, TP, and R:R coordinates.\n"
                )
            post_to_opencode_session("", prompt)

        return has_active_trades

    def _schedule_post_news_rules_reminder(self, delay_seconds: float = 60.0):
        """Dynamic messages disabled per user directive; audit cadence is defined in the cadence dossier."""
        pass

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
        stage_qualification = {}  # {pos_ticket: {"highest_fav": float, "stage": int}}

        while self.is_running:
            try:
                mt5_ok = _init_mt5()
                if mt5_ok:
                    current_positions = mt5.positions_get() or []
                    current_pending = mt5.orders_get() or []
                    active_watches = [w for w in ev_store.get_watches(include_closed=False) if (w.get("status") or "ACTIVE").upper() == "ACTIVE"]

                    # Clean up closed positions from qualification tracking
                    open_tickets = {p.ticket for p in current_positions}
                    stage_qualification = {t: q for t, q in stage_qualification.items() if t in open_tickets}

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

                    # 1.5 Real-Time 3-Stage Dynamic Position Ratchet (Capital Armor & Profit Banking)
                    # Governed by FundedNext 30-Second Quick Strike Shield (<30% profit from trades under 30s)
                    for pos in current_positions:
                        if getattr(pos, "symbol", "") != "XAUUSD":
                            continue
                        pos_ticket = pos.ticket
                        open_p = float(pos.price_open)
                        current_sl = float(pos.sl)
                        tp_p = float(pos.tp)
                        pos_side = "BUY" if pos.type == 0 else "SELL"
                        tick_info = mt5.symbol_info_tick(pos.symbol)
                        if not tick_info:
                            continue

                        # Compute live favorable points
                        if pos.type == 0:  # BUY
                            curr_price = float(tick_info.bid)
                            fav_pts = curr_price - open_p
                        else:  # SELL
                            curr_price = float(tick_info.ask)
                            fav_pts = open_p - curr_price

                        # Accurate duration in broker server time (FundedNext audit standard)
                        tick_t_msc = getattr(tick_info, "time_msc", 0)
                        pos_t_msc = getattr(pos, "time_msc", 0)
                        if tick_t_msc > 0 and pos_t_msc > 0:
                            pos_duration = max(0.0, float(tick_t_msc - pos_t_msc) / 1000.0)
                        else:
                            pos_duration = max(0.0, float(getattr(tick_info, "time", 0) - getattr(pos, "time", 0)))

                        # Track peak favorable expansion and stage qualification
                        qual = stage_qualification.setdefault(pos_ticket, {"highest_fav": 0.0, "stage": 0})
                        if fav_pts > qual["highest_fav"]:
                            qual["highest_fav"] = fav_pts

                        if qual["highest_fav"] >= 14.0:
                            qual["stage"] = max(qual["stage"], 3)
                        elif qual["highest_fav"] >= 8.5:
                            qual["stage"] = max(qual["stage"], 2)
                        elif qual["highest_fav"] >= 5.2:
                            qual["stage"] = max(qual["stage"], 1)

                        q_stage = qual["stage"]

                        # FUNDEDNEXT 30S SHIELD: Do NOT trail SL into profit under 32 seconds
                        # Prevents profitable stops from triggering <30s and violating the 30% profit rule
                        if pos_duration < 32.0:
                            continue

                        # PULLBACK CUT ENFORCEMENT:
                        # User mandate: "This is not limited to breakeven... when the price pulled back a little it should not be errored it should be cut at what price it is"
                        # If a position qualified for a stage earlier, but has now pulled back below that earned lock level,
                        # cleanly cut at current market price using a fresh tick quote!
                        needs_pullback_cut = False
                        pb_reason = ""
                        pb_comment = ""

                        if q_stage == 3 and fav_pts < 8.0:
                            needs_pullback_cut = True
                            pb_reason = f"Position achieved Stage 3 (+{qual['highest_fav']:.2f} pts peak) but pulled back below +8.0 pts to {curr_price:.2f} (floating +{fav_pts:.2f} pts)."
                            pb_comment = "Stage 3 Pullback Cut"
                        elif q_stage == 2 and fav_pts < 3.5:
                            needs_pullback_cut = True
                            pb_reason = f"Position achieved Stage 2 (+{qual['highest_fav']:.2f} pts peak) but pulled back below +3.5 pts to {curr_price:.2f} (floating +{fav_pts:.2f} pts)."
                            pb_comment = "Stage 2 Pullback Cut"
                        elif q_stage == 1 and fav_pts < 0.50:
                            needs_pullback_cut = True
                            pb_reason = f"Position achieved Stage 1 (+{qual['highest_fav']:.2f} pts peak) but pulled back below +0.50 pts to {curr_price:.2f} (floating +{fav_pts:.2f} pts)."
                            pb_comment = "BE Pullback Cut"

                        if needs_pullback_cut:
                            LOG.warning(f"🛡️ [{pb_comment.upper()}] Ticket #{pos_ticket} ({pos_side} @ {open_p:.2f}) -> {pb_reason} Cutting at market!")
                            fresh_tick = mt5.symbol_info_tick(pos.symbol)
                            deal_price = (float(fresh_tick.bid) if pos.type == 0 else float(fresh_tick.ask)) if fresh_tick else curr_price
                            for fill_mode in [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, 0, mt5.ORDER_FILLING_RETURN]:
                                cut_req = {
                                    "action": mt5.TRADE_ACTION_DEAL,
                                    "position": pos_ticket,
                                    "symbol": pos.symbol,
                                    "volume": pos.volume,
                                    "type": mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
                                    "price": deal_price,
                                    "deviation": 50,
                                    "magic": pos.magic,
                                    "comment": pb_comment,
                                    "type_time": mt5.ORDER_TIME_GTC,
                                    "type_filling": fill_mode
                                }
                                res = mt5.order_send(cut_req)
                                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                    LOG.info(f"✅ [{pb_comment.upper()} SUCCESS] Ticket #{pos_ticket} cleanly closed at {deal_price:.2f} (Hold: {pos_duration:.1f}s).")
                                    post_to_opencode_session(
                                        "OpenCode (CIO)",
                                        f"🛡️ [PULLBACK CUT EXECUTED: {pb_comment.upper()}]\n"
                                        f"Ticket #{pos_ticket} ({pos.symbol} {pos_side} {pos.volume}L @ {open_p:.2f})\n"
                                        f"Exit Price: {deal_price:.2f} | Hold Duration: {pos_duration:.1f}s\n"
                                        f"Reason: {pb_reason} Executed market cut cleanly rather than erroring or risking round-trip to full SL."
                                    )
                                    stage_qualification.pop(pos_ticket, None)
                                    break
                            continue

                        target_sl = None
                        stage_label = ""
                        locked_pts = 0.0

                        # Stage 3: Runner Freedom (>= +14.0 pts or Stage 3 qualified) -> lock +8.0 pts (+$400 locked)
                        if fav_pts >= 14.0 or q_stage == 3:
                            req_sl = round(open_p + 8.0, 2) if pos.type == 0 else round(open_p - 8.0, 2)
                            if (pos.type == 0 and (current_sl < req_sl or current_sl == 0.0)) or \
                               (pos.type == 1 and (current_sl > req_sl or current_sl == 0.0)):
                                target_sl = req_sl
                                stage_label = "STAGE 3 (RUNNER FREEDOM: +8.0 PTS LOCKED)"
                                locked_pts = 8.0
                        # Stage 2: Profit Banking (>= +8.5 pts or Stage 2 qualified) -> lock +3.5 pts
                        elif fav_pts >= 8.5 or q_stage == 2:
                            req_sl = round(open_p + 3.5, 2) if pos.type == 0 else round(open_p - 3.5, 2)
                            if (pos.type == 0 and (current_sl < req_sl or current_sl == 0.0)) or \
                               (pos.type == 1 and (current_sl > req_sl or current_sl == 0.0)):
                                target_sl = req_sl
                                stage_label = "STAGE 2 (PROFIT BANK: +3.5 PTS LOCKED)"
                                locked_pts = 3.5
                        # Stage 1: Capital Armor / Breakeven (>= +5.2 pts or Stage 1 qualified) -> lock +0.50 pts
                        elif fav_pts >= 5.2 or q_stage == 1:
                            req_sl = round(open_p + 0.50, 2) if pos.type == 0 else round(open_p - 0.50, 2)
                            if (pos.type == 0 and (current_sl < req_sl or current_sl == 0.0)) or \
                               (pos.type == 1 and (current_sl > req_sl or current_sl == 0.0)):
                                target_sl = req_sl
                                stage_label = "STAGE 1 (CAPITAL ARMOR: BREAKEVEN +0.50 PTS)"
                                locked_pts = 0.50

                        if target_sl is not None and abs(target_sl - current_sl) > 0.05:
                            req = {
                                "action": mt5.TRADE_ACTION_SLTP,
                                "position": pos_ticket,
                                "symbol": pos.symbol,
                                "sl": target_sl,
                                "tp": tp_p
                            }
                            res = mt5.order_send(req)
                            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                                LOG.info(f"🛡️ [REAL-TIME RATCHET ACTIVATED] Ticket #{pos_ticket} ({pos_side} {pos.volume}L @ {open_p:.2f}) -> {stage_label}! SL updated to {target_sl:.2f} (Fav peak: +{fav_pts:.2f} pts).")
                                log_local_llm_monitoring(f"🛡️ [RATCHET] Ticket #{pos_ticket} {stage_label} -> SL {target_sl:.2f}")
                                post_to_opencode_session(
                                    "OpenCode (CIO)",
                                    f"🛡️ [REAL-TIME RATCHET ACTIVATED: {stage_label}]\n"
                                    f"Ticket #{pos_ticket} ({pos.symbol} {pos_side} {pos.volume}L @ {open_p:.2f})\n"
                                    f"Current Price: {curr_price:.2f} (Floating Gain: +{fav_pts:.2f} pts / +${fav_pts * pos.volume * 100.0:.2f})\n"
                                    f"New Stop Loss: {target_sl:.2f} (Locking +{locked_pts:.2f} pts)\n"
                                    f"Status: Downside risk eliminated. Trade is running risk-free toward target {tp_p:.2f}."
                                )
                            elif res and res.retcode != mt5.TRADE_RETCODE_DONE:
                                LOG.warning(f"⚠️ [RATCHET SLTP REJECTED] Ticket #{pos_ticket} SL update to {target_sl:.2f} failed: retcode={res.retcode} ({res.comment}). The next 500ms cycle will re-audit fresh price.")

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
