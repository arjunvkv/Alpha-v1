"""
Alpha Daemon — The Brain's Body

This is NOT the brain. This is the alarm clock, the hands, and the nervous system.
It watches. It triggers. It executes. But it NEVER decides.

The AI decides. Always.
"""

import json
import os
import sys
import time
import subprocess
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Make Alpha packages importable when daemon runs from any cwd
sys.path.insert(0, str(Path(__file__).parent.parent))

from monitor.error_monitor import error_monitor

# ─── CONFIGURATION ───────────────────────────────────────────────────────────

ALPHA_ROOT = Path(r"C:\Trading\Alpha")
DATA_DIR = ALPHA_ROOT / "data" / "live"
LOGS_DIR = ALPHA_ROOT / "logs"
GRANGER_DIR = Path(r"C:\Trading\Granger")
GRANGER_SNAPSHOT = Path(r"C:\Trading\data\all_layers_snapshot.json")

TRIGGER_FILE = DATA_DIR / "trigger.json"
ACTION_FILE = DATA_DIR / "action.json"
STATE_FILE = DATA_DIR / "daemon_state.json"
SESSION_ID_FILE = DATA_DIR / "session_id.txt"

# ─── SESSION CONFIGURATION ───────────────────────────────────────────────────
# The daemon sends triggers into THIS session. The AI wakes up with full context.
# This ID must match the running opencode session.
# Resolved at import from the unified pointer file (single source of truth).
# Falls back to the legacy id only if the file is missing/corrupt.
def _resolve_session_id():
    try:
        with open(SESSION_ID_FILE, encoding="utf-8") as _f:
            _sid = _f.read().strip()
        if _sid:
            return _sid
    except Exception:
        pass
    return "ses_fd796f6e4ffevdglfweo12MmRC"  # legacy fallback

AI_SESSION_ID = _resolve_session_id()

# Monitor intervals (seconds)
FAST_INTERVAL = 5      # Position management (trailing stops)
MEDIUM_INTERVAL = 60   # Regime monitoring, zone watching
SLOW_INTERVAL = 300    # Full scan
DAILY_INTERVAL = 86400 # Daily review

# Regime shift thresholds
DXY_MOVE_THRESHOLD = 0.5     # % change that triggers regime check
VIX_SPIKE_THRESHOLD = 20.0   # % change that triggers regime check
YIELD_MOVE_THRESHOLD = 10    # bps change that triggers regime check

# Zone approach threshold
ZONE_DISTANCE_THRESHOLD = 0.5  # % distance from level to trigger

# ─── TRIGGER SUPPRESSION (material-change gate) ──────────────────────────────
# Prevents identical wake-ups when nothing changed since the last decision.
ZONE_TRIGGER_COOLDOWN = 1800     # min seconds between AI wakes for same symbol+zone
PRICE_MOVE_THRESHOLD = 0.15      # % price move vs last triggered price = material change
GRANGER_REFRESH_INTERVAL = 3600  # hourly data refresh WITHOUT waking the AI
SUPPRESSION_LOG = DATA_DIR / "suppressed_triggers.jsonl"

# Granger instrument name -> MT5 symbol (only instruments this account trades)
INSTRUMENT_SYMBOL_MAP = {
    "gold": "XAUUSD",
    "silver": "XAGUSD",
    "platinum": "XPTUSD",
    "palladium": "XPDUSD",
}

# ─── LOGGING ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "daemon.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("alpha_daemon")

# ─── STATE ───────────────────────────────────────────────────────────────────

class DaemonState:
    """Persists daemon state across restarts."""
    
    def __init__(self):
        self.last_granger_pull = None
        self.last_regime = None
        self.last_prices = {}
        self.last_trigger_time = None
        self.positions_snapshot = []
        # Per symbol+zone trigger history for material-change detection:
        # key "SYMBOL:TYPE:LEVEL" -> {"time": iso, "price": float, "side": above|below}
        self.zone_trigger_history = {}
        self.suppressed_triggers = 0
        self._load()

    def _load(self):
        if STATE_FILE.exists():
            with open(STATE_FILE, encoding='utf-8') as f:
                data = json.load(f)
            self.last_granger_pull = data.get("last_granger_pull")
            self.last_regime = data.get("last_regime")
            self.last_prices = data.get("last_prices", {})
            self.last_trigger_time = data.get("last_trigger_time")
            self.zone_trigger_history = data.get("zone_trigger_history", {})
            self.suppressed_triggers = data.get("suppressed_triggers", 0)

    def save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "last_granger_pull": self.last_granger_pull,
                "last_regime": self.last_regime,
                "last_prices": self.last_prices,
                "last_trigger_time": self.last_trigger_time,
                "zone_trigger_history": self.zone_trigger_history,
                "suppressed_triggers": self.suppressed_triggers,
            }, f, indent=2, default=str)
    
    def granger_is_stale(self, max_age_hours=6):
        if not self.last_granger_pull:
            return True
        last = datetime.fromisoformat(self.last_granger_pull)
        age = (datetime.now(timezone.utc) - last).total_seconds() / 3600
        return age > max_age_hours

# ─── MT5 INTERFACE ───────────────────────────────────────────────────────────

class MT5Interface:
    """Lightweight MT5 wrapper for the daemon."""
    
    def __init__(self):
        self.connected = False
    
    def connect(self):
        try:
            import MetaTrader5 as mt5
            # PIN TO FTMO TERMINAL (2026-08-24): dual MT5 installs on this
            # machine - bare initialize() bound the unlogged generic one.
            _ftmo = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
            import os as _os
            _path = _ftmo if _os.path.exists(_ftmo) else None
            try:
                ok = mt5.initialize(path=_path)
            except TypeError:
                ok = mt5.initialize()
            if not ok:
                log.error(f"MT5 init failed: {mt5.last_error()}")
                return False
            # Ensure every configured instrument is subscribed for quotes
            from config import INSTRUMENTS
            for sym in INSTRUMENTS:
                info = mt5.symbol_info(sym)
                if info is None:
                    log.warning(f"Symbol {sym} not available on this broker")
                elif not info.visible:
                    mt5.symbol_select(sym, True)
            self.connected = True
            log.info(f"MT5 connected: {mt5.account_info().server}")
            return True
        except ImportError:
            log.error("MetaTrader5 package not installed")
            return False
    
    def get_tick(self, symbol):
        """Get latest tick for symbol."""
        import MetaTrader5 as mt5
        tick = mt5.symbol_info_tick(symbol)
        if tick:
            return {
                "bid": tick.bid, "ask": tick.ask,
                "spread": round((tick.ask - tick.bid) * 10000, 1),
                "time": datetime.fromtimestamp(tick.time).isoformat()
            }
        return None
    
    def get_positions(self):
        """Get all open positions."""
        import MetaTrader5 as mt5
        positions = mt5.positions_get()
        if not positions:
            return []
        return [{
            "ticket": p.ticket, "symbol": p.symbol,
            "direction": "LONG" if p.type == 0 else "SHORT",
            "lots": p.volume, "entry": p.price_open,
            "current": p.price_current, "sl": p.sl, "tp": p.tp,
            "pnl": round(p.profit, 2),
            "duration_hours": round((time.time() - p.time) / 3600, 1)
        } for p in positions]
    
    def get_account(self):
        """Get account info."""
        import MetaTrader5 as mt5
        info = mt5.account_info()
        if info:
            return {
                "balance": info.balance, "equity": info.equity,
                "margin": info.margin, "free_margin": info.margin_free,
                "server": info.server
            }
        return None
    
    def execute(self, action):
        """Execute a trading decision."""
        import MetaTrader5 as mt5
        
        if action["decision"] == "ENTER":
            order_type = mt5.ORDER_TYPE_BUY if action["direction"] == "LONG" else mt5.ORDER_TYPE_SELL
            request = {
                "action": mt5.TRADE_ACTION_DEAL if action.get("entry_type") == "MARKET" else mt5.TRADE_ACTION_PENDING,
                "symbol": action["symbol"],
                "volume": action["lots"],
                "type": order_type,
                "price": action.get("entry_price") or (mt5.symbol_info_tick(action["symbol"]).ask if order_type == mt5.ORDER_TYPE_BUY else mt5.symbol_info_tick(action["symbol"]).bid),
                "sl": action["sl"],
                "tp": action.get("tp1"),
                "magic": 20260821,  # Alpha identifier
                "comment": f"Alpha:{action.get('bucket','')}:C{action.get('conviction',0)}",
            }
            result = mt5.order_send(request)
            log.info(f"ENTER {action['symbol']} {action['direction']}: {result}")
            error_monitor.capture_mt5_result(result, context={
                "op": "ENTER", "symbol": action["symbol"],
                "direction": action["direction"], "lots": action["lots"],
                "sl": action.get("sl"), "bucket": action.get("bucket")})
            return result
        
        elif action["decision"] == "EXIT":
            ticket = action["ticket"]
            position = mt5.positions_get(ticket=ticket)
            if position:
                close_type = mt5.ORDER_TYPE_SELL if position[0].type == 0 else mt5.ORDER_TYPE_BUY
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": position[0].symbol,
                    "volume": position[0].volume,
                    "type": close_type,
                    "position": ticket,
                    "price": mt5.symbol_info_tick(position[0].symbol).bid if close_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(position[0].symbol).ask,
                    "magic": 20260821,
                    "comment": f"Alpha:EXIT:{action.get('reason','')[:50]}",
                }
                result = mt5.order_send(request)
                log.info(f"EXIT ticket {ticket}: {result}")
                error_monitor.capture_mt5_result(result, context={
                    "op": "EXIT", "ticket": ticket,
                    "reason": action.get("reason", "")[:100]})
                return result
        
        elif action["decision"] == "MODIFY":
            ticket = action["ticket"]
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "sl": action.get("new_sl"),
                "tp": action.get("new_tp"),
            }
            result = mt5.order_send(request)
            log.info(f"MODIFY ticket {ticket}: {result}")
            error_monitor.capture_mt5_result(result, context={
                "op": "MODIFY", "ticket": ticket,
                "new_sl": action.get("new_sl"), "new_tp": action.get("new_tp")})
            return result
        
        return None
    
    def disconnect(self):
        import MetaTrader5 as mt5
        mt5.shutdown()
        self.connected = False

# ─── ZONE WATCHER ────────────────────────────────────────────────────────────

class ZoneWatcher:
    """Monitors price proximity to key structural levels."""
    
    def __init__(self):
        self.zones = self._load_zones()
    
    def _load_zones(self):
        """Load key levels from Granger technical data or predefined zones."""
        zones_file = DATA_DIR / "zones.json"
        if zones_file.exists():
            with open(zones_file, encoding='utf-8') as f:
                return json.load(f)
        
        # Default zones — updated daily by daily scan
        return {
            "XAGUSD": [
                {"level": 68.50, "type": "SMA20", "significance": "Dynamic support"},
                {"level": 70.94, "type": "SMA200", "significance": "Major resistance"},
                {"level": 62.13, "type": "SMA50", "significance": "Secondary support"},
            ],
            "XAUUSD": [
                {"level": 4495.91, "type": "SMA200", "significance": "Just below — reclaimed = bullish"},
                {"level": 4253.91, "type": "SMA20", "significance": "Near-term support"},
            ],
            "XPTUSD": [
                {"level": 1920.83, "type": "SMA200", "significance": "Major resistance overhead"},
                {"level": 1709.63, "type": "SMA20", "significance": "Dynamic support"},
            ],
        }
    
    def update_zones(self, granger_snapshot):
        """Rebuild zones from fresh Granger technical layer.

        Called after every Granger pull so zone levels track live market
        structure instead of freezing at whatever the last scan saw.
        Rebuild always writes lists of zone dicts (fixes legacy dict-shaped
        entries like the old XAGUSD single observation).
        """
        try:
            tech = granger_snapshot.get("layers", {}).get("technical", {})
            instruments = tech.get("data", {}).get("instruments", {})
            new_zones = {}
            for inst_name, inst in instruments.items():
                symbol = INSTRUMENT_SYMBOL_MAP.get(str(inst_name).lower())
                if not symbol:
                    continue  # not an instrument this account trades
                levels = []
                for ma_key, sig in (("sma20", "Near-term dynamic"),
                                    ("sma50", "Secondary support/resistance"),
                                    ("sma200", "Major structural level")):
                    v = inst.get(ma_key)
                    if isinstance(v, (int, float)):
                        levels.append({"level": round(v, 2), "type": ma_key.upper(),
                                       "significance": sig})
                bb = inst.get("bollinger") or {}
                for band, sig in (("upper", "Band resistance - trap zone"),
                                  ("middle", "Band midline"),
                                  ("lower", "Band support")):
                    v = bb.get(band)
                    if isinstance(v, (int, float)):
                        levels.append({"level": round(v, 2), "type": f"BB_{band.upper()}",
                                       "significance": sig})
                if levels:
                    new_zones[symbol] = levels
            if new_zones:
                self.zones = new_zones
                self._save_zones()
                counts = {s: len(z) for s, z in new_zones.items()}
                log.info(f"Zones rebuilt from Granger snapshot: {counts}")
        except Exception as e:
            log.error(f"Zone update from snapshot failed (keeping old zones): {e}")

    def _save_zones(self):
        zones_file = DATA_DIR / "zones.json"
        with open(zones_file, 'w', encoding='utf-8') as f:
            json.dump(self.zones, f, indent=2)
    
    def check_proximity(self, symbol, current_price):
        """Check if price is within threshold of any zone."""
        zones = self.zones.get(symbol, [])
        if isinstance(zones, dict):
            zones = []  # Single observation dict, not a list of zone dicts
        triggered = []
        for zone in zones:
            distance_pct = abs(current_price - zone["level"]) / zone["level"] * 100
            if distance_pct <= ZONE_DISTANCE_THRESHOLD:
                triggered.append({**zone, "distance_pct": round(distance_pct, 2)})
        return triggered

# ─── REGIME MONITOR ──────────────────────────────────────────────────────────

class RegimeMonitor:
    """Tracks macro regime changes in real-time."""
    
    def __init__(self, mt5: MT5Interface):
        self.mt5 = mt5
        self.last_dxy = None
        self.last_vix = None
    
    def check_for_shift(self, state: DaemonState):
        """Check if regime has shifted significantly."""
        shifts = []
        
        # Check DXY via MT5
        dxy_tick = self.mt5.get_tick("DXY")
        if dxy_tick and self.last_dxy:
            dxy_change_pct = (dxy_tick["bid"] - self.last_dxy) / self.last_dxy * 100
            if abs(dxy_change_pct) >= DXY_MOVE_THRESHOLD:
                direction = "STRENGTHENING" if dxy_change_pct > 0 else "WEAKENING"
                shifts.append({
                    "type": "DXY",
                    "from": self.last_dxy,
                    "to": dxy_tick["bid"],
                    "change_pct": round(dxy_change_pct, 2),
                    "direction": direction
                })
            self.last_dxy = dxy_tick["bid"]
        elif dxy_tick:
            self.last_dxy = dxy_tick["bid"]
        
        # Note: VIX doesn't trade on MT5, so we check via Granger or yfinance
        # For now, we rely on Granger daily pull for VIX
        
        return shifts

# ─── TRIGGER BUILDER ─────────────────────────────────────────────────────────

class TriggerBuilder:
    """Builds trigger.json from daemon state + live data."""
    
    def __init__(self, mt5: MT5Interface, zones: ZoneWatcher, regime: RegimeMonitor):
        self.mt5 = mt5
        self.zones = zones
        self.regime = regime
    
    def build_zone_trigger(self, symbol, zone_info, price_data):
        """Build trigger for zone approach."""
        return {
            "template": "zone_approach",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session": self._get_session(),
            "symbol": symbol,
            "price": price_data,
            "trigger": {
                "type": "zone_approach",
                "reason": f"Price within {zone_info['distance_pct']}% of {zone_info['type']} at ${zone_info['level']}",
                "zone": zone_info
            },
            "regime": self._get_regime(),
            "granger": self._get_granger_summary(),
            "positions": self.mt5.get_positions(),
            "account": self._get_account_with_risk(),
            "calendar": self._get_calendar(),
            "required_actions": [
                "1. Read this trigger — understand why you were woken",
                "2. Read or pull Granger snapshot from C:/Trading/data/all_layers_snapshot.json",
                "3. Analyze: Is the Granger thesis still valid AT THIS PRICE?",
                "4. Check calendar: Any USD news in next 30 min?",
                "5. Check regime: DXY reversing? VIX spiking?",
                "6. Decide: ENTER / WAIT / MODIFY / EXIT / HOLD",
                "7. Write decision to C:/Trading/Alpha/data/live/action.json",
            ],
            "action_file": str(ACTION_FILE)
        }
    
    def build_regime_trigger(self, shifts):
        """Build trigger for regime shift."""
        return {
            "template": "regime_shift",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session": self._get_session(),
            "symbol": "MULTIPLE",
            "regime_shifts": shifts,
            "positions": self.mt5.get_positions(),
            "account": self._get_account_with_risk(),
            "required_actions": [
                "URGENT: Regime shift detected.",
                "1. Assess which open positions are threatened",
                "2. If thesis broken → EXIT immediately",
                "3. If thesis stressed → MODIFY (tighten stop)",
                "4. DO NOT open new positions during active regime shift",
                "5. Write decision to C:/Trading/Alpha/data/live/action.json",
            ],
            "action_file": str(ACTION_FILE)
        }
    
    def build_position_trigger(self, position, trigger_reason):
        """Build trigger for position management."""
        return {
            "template": "position_management",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session": self._get_session(),
            "symbol": position["symbol"],
            "position": position,
            "trigger_reason": trigger_reason,
            "regime": self._get_regime(),
            "granger": self._get_granger_summary(),
            "required_actions": [
                f"Position {position['ticket']} needs management: {trigger_reason}",
                "1. Is original thesis still valid?",
                "2. Should you: trail stop / scale out / close / hold?",
                "3. Write decision to C:/Trading/Alpha/data/live/action.json",
            ],
            "action_file": str(ACTION_FILE)
        }
    
    def build_daily_trigger(self):
        """Build trigger for daily scan."""
        return {
            "template": "daily_scan",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session": self._get_session(),
            "positions": self.mt5.get_positions(),
            "account": self._get_account_with_risk(),
            "required_actions": [
                "Daily scan time. Full review needed.",
                "1. Pull fresh Granger 7-layer snapshot",
                "2. Scan all instruments for opportunities",
                "3. Review open positions",
                "4. Check risk limits",
                "5. Write daily report to C:/Trading/Alpha/memory/journal/",
                "6. Write decisions to C:/Trading/Alpha/data/live/action.json",
            ],
            "action_file": str(ACTION_FILE)
        }
    
    def _get_session(self):
        hour = datetime.now().hour
        if 0 <= hour < 7: return "asian"
        if 7 <= hour < 13: return "london"
        if 13 <= hour < 21: return "ny"
        return "off"
    
    def _get_regime(self):
        # Read from Granger snapshot if available
        if GRANGER_SNAPSHOT.exists():
            try:
                with open(GRANGER_SNAPSHOT, encoding='utf-8') as f:
                    snap = json.load(f)
                signals = snap.get("layers", {}).get("signals", {}).get("data", {})
                macro = signals.get("macro_regime", {})
                return {
                    "composite": macro.get("composite"),
                    "dxy": macro.get("dxy"),
                    "dxy_trend": macro.get("dxy_trend"),
                    "vix": macro.get("vix"),
                    "vix_regime": macro.get("vix_regime"),
                }
            except:
                pass
        return {"composite": "unknown"}
    
    def _get_granger_summary(self):
        if GRANGER_SNAPSHOT.exists():
            return {"snapshot_path": str(GRANGER_SNAPSHOT), "age_hours": "check snapshot"}
        return {"snapshot_path": None, "note": "No snapshot available — pull fresh Granger data"}
    
    def _get_account_with_risk(self):
        acct = self.mt5.get_account()
        if not acct:
            return {"error": "MT5 not connected"}
        # Calculate heat from open positions
        positions = self.mt5.get_positions()
        total_risk = sum(abs(p.get("pnl", 0)) for p in positions)
        heat = (total_risk / acct["balance"] * 100) if acct["balance"] > 0 else 0
        acct["heat_pct"] = round(heat, 1)
        acct["max_heat_pct"] = 6.0
        return acct
    
    def _get_calendar(self):
        """Fetch economic calendar from ForexFactory."""
        try:
            import urllib.request
            url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
            with urllib.request.urlopen(url, timeout=5) as resp:
                events = json.loads(resp.read())
            now = datetime.now(timezone.utc)
            upcoming = []
            for e in events:
                event_time = datetime.fromtimestamp(e.get("timestamp", 0), tz=timezone.utc)
                mins_until = (event_time - now).total_seconds() / 60
                if 0 < mins_until < 120:  # next 2 hours
                    upcoming.append({
                        "name": e.get("title"),
                        "currency": e.get("currency"),
                        "impact": e.get("impact"),
                        "minutes_until": round(mins_until),
                    })
            return {"next_event": upcoming[0] if upcoming else None, "upcoming_2h": upcoming}
        except:
            return {"next_event": None, "note": "Calendar unavailable"}

# ─── NOTIFICATION ────────────────────────────────────────────────────────────

def notify_user(message: str):
    """Send Windows toast notification - FIRE AND FORGET.

    FIX (2026-08-24): previous version ran PowerShell synchronously with
    5s+15s timeouts INSIDE the monitor loop. On toast failure this stalled
    _fire_trigger for up to 20s per event and contributed to wake-spawn
    failures reaching the AI session. Now spawns detached and never blocks.
    """
    try:
        ps_cmd = (
            "[Windows.UI.Notifications.ToastNotificationManager,"
            "Windows.UI.Notifications,ContentType=WindowsRuntime] | Out-Null;"
            "[Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom,"
            "ContentType=WindowsRuntime] | Out-Null;"
            "$m='" + message.replace("'", "''") + "';"
            "$t=@\"<toast><visual><binding template='ToastGeneric'>"
            "<text>Alpha Trading</text><text>$m</text>"
            "</binding></visual></toast>\"@;"
            "$x=New-Object Windows.Data.Xml.Dom.XmlDocument;"
            "$x.LoadXml($t);"
            "$n=[Windows.UI.Notifications.ToastNotification]::new($x);"
            "[Windows.UI.Notifications.ToastNotificationManager]"
            "::CreateToastNotifier('Alpha').Show($n)"
        )
        subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP
                           if os.name == 'nt' else 0),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        # Never block the trigger pipeline on cosmetic notifications.
        log.warning(f"Toast spawn skipped: {e}")

# ─── MAIN DAEMON LOOP ────────────────────────────────────────────────────────

class AlphaDaemon:
    """
    The Brain's Body.
    
    Monitors → Triggers → Executes.
    NEVER decides. The AI decides.
    """
    
    def __init__(self):
        self.mt5 = MT5Interface()
        self.state = DaemonState()
        self.zones = ZoneWatcher()
        self.regime = RegimeMonitor(self.mt5)
        self.trigger_builder = TriggerBuilder(self.mt5, self.zones, self.regime)

        # AI-authored rules engine (reads data/live/ai_triggers.json)
        self._ai_rules_cache = None
        self._ai_rules_mtime = 0
        self._ai_liveness_last = time.time()  # first heartbeat fires after `minutes`
        self._ai_fired_once = set()
        self._ai_price_buf = {}
        self._ai_prev_price = {}
        self._ai_last_price = {}
    
    def start(self):
        """Main daemon entry point."""
        log.info("Alpha Daemon starting...")

        # Error monitoring: global exception hooks + tail our own log
        error_monitor.install_global_handlers()
        error_monitor.tail_log(LOGS_DIR / "daemon.log")

        # Connect to MT5
        if not self.mt5.connect():
            log.error("Cannot start daemon — MT5 not connected")
            error_monitor.capture(severity="CRITICAL", source="mt5",
                                  err_type="CONNECT_FAILED",
                                  message="Daemon cannot start — MT5 connection failed")
            return
        
        log.info("Daemon connected to MT5. Starting monitor loop.")
        notify_user("Alpha Daemon started. Monitoring markets.")
        
        try:
            self._run_loop()
        except KeyboardInterrupt:
            log.info("Daemon shutting down...")
            notify_user("Alpha Daemon stopped.")
        finally:
            self.mt5.disconnect()
            self.state.save()
    
    def _process_actions(self):
        """Consume action.json written by the AI: execute, archive, clear.

        The AI writes its decision to ACTION_FILE. This is the ONLY place
        orders enter MT5. Every processed action is archived for audit.
        """
        if not ACTION_FILE.exists():
            return
        try:
            with open(ACTION_FILE, encoding="utf-8-sig") as f:
                action = json.load(f)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            log.error(f"Corrupt action.json — archiving and skipping: {e}")
            error_monitor.capture(severity="CRITICAL", source="action_consumer",
                                  err_type="CORRUPT_ACTION",
                                  message=f"action.json unreadable: {e}")
            ACTION_FILE.replace(DATA_DIR / f"action.corrupt.{int(time.time())}.json")
            return

        decision = action.get("decision", "?")
        log.info(f"Processing AI action: {decision}")

        # Safety gate — never execute without a stop on entries
        if decision == "ENTER" and not action.get("sl"):
            error_monitor.capture(severity="CRITICAL", source="action_consumer",
                                  err_type="NO_STOP_REFUSED",
                                  message="ENTER refused — no stop loss in action")
            result = {"refused": "no_stop"}
        elif decision in ("ENTER", "EXIT", "MODIFY"):
            result = self.mt5.execute(action)
            error_monitor.capture_mt5_result(result, context={
                "op": decision, "symbol": action.get("symbol"),
                "ticket": action.get("ticket")})
        else:
            result = {"info": f"non-executing decision {decision}"}

        # Archive audit trail
        archive = DATA_DIR / "processed_actions.jsonl"
        with open(archive, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "action": action,
                "result": str(result)[:500],
            }, default=str) + "\n")

        ACTION_FILE.unlink(missing_ok=True)
        notify_user(f"Action executed: {decision} "
                    f"{action.get('symbol', action.get('ticket', ''))}".strip())

    def _run_loop(self):
        """Infinite monitoring loop with smart intervals."""
        last_fast = 0
        last_medium = 0
        last_slow = 0
        last_daily = 0
        last_granger_refresh = 0

        while True:
            now = time.time()

            # ── FAST: Position management + action consumption (every 5s) ──
            if now - last_fast >= FAST_INTERVAL:
                self._process_actions()
                self._check_positions()
                last_fast = now

            # ── MEDIUM: Regime + zones (every 60s) ──
            if now - last_medium >= MEDIUM_INTERVAL:
                self._check_regime()
                self._check_zones()
                self._check_ai_rules()
                last_medium = now

            # ── SLOW: Full scan (every 5min) ──
            if now - last_slow >= SLOW_INTERVAL:
                self._full_scan()
                last_slow = now

            # ── DAILY: Granger pull + review (once per day) ──
            # Reset timer BEFORE running: if the Granger pull fails,
            # granger_is_stale() stays True and without the reset this
            # branch would tight-loop every second re-firing daily scans.
            if now - last_daily >= DAILY_INTERVAL or self.state.granger_is_stale():
                last_daily = now
                self._daily_scan()

            # ── HOURLY DATA REFRESH: Granger pull WITHOUT waking the AI ──
            # Keeps institutional layers fresh so any zone trigger that DOES
            # fire is evaluated against current data, not a day-old snapshot.
            elif now - last_granger_refresh >= GRANGER_REFRESH_INTERVAL:
                if self._pull_granger(critical_on_fail=False):
                    snap = self._load_snapshot()
                    if snap:
                        self.zones.update_zones(snap)
                    last_granger_refresh = now
                else:
                    # Retry in 10 min instead of waiting a full hour
                    last_granger_refresh = now - GRANGER_REFRESH_INTERVAL + 600

            time.sleep(1)  # Prevent CPU spin
    
    def _check_positions(self):
        """Fast loop: check existing positions for management needs."""
        positions = self.mt5.get_positions()
        for pos in positions:
            # Time stop: flat for too long
            if pos["duration_hours"] > 72 and abs(pos["pnl"]) < 50:
                trigger = self.trigger_builder.build_position_trigger(
                    pos, f"Time stop: {pos['duration_hours']}h with minimal movement"
                )
                self._fire_trigger(trigger)
            
            # Trailing stop: moved +1R
            if pos["sl"] > 0 and pos["direction"] == "LONG":
                risk = pos["entry"] - pos["sl"]
                if risk > 0 and (pos["current"] - pos["entry"]) >= risk:
                    trigger = self.trigger_builder.build_position_trigger(
                        pos, f"Price moved +1R ({round(risk, 2)} pips). Consider trailing stop."
                    )
                    self._fire_trigger(trigger)
    
    def _check_regime(self):
        """Medium loop: check for regime shifts."""
        shifts = self.regime.check_for_shift(self.state)
        if shifts:
            trigger = self.trigger_builder.build_regime_trigger(shifts)
            self._fire_trigger(trigger)
            self.state.last_regime = shifts
    
    def _check_zones(self):
        """Medium loop: check if price approached any zones.

        Every candidate trigger passes a material-change gate: if nothing
        materially changed since the last wake for this symbol+zone, the
        event is suppressed and logged instead of re-waking the AI.
        """
        positions = self.mt5.get_positions()
        symbols_with_positions = {p["symbol"] for p in positions}

        # Check all watched symbols
        for symbol in self.zones.zones:
            tick = self.mt5.get_tick(symbol)
            if not tick:
                continue

            price = tick["bid"]
            triggered_zones = self.zones.check_proximity(symbol, price)

            for zone in triggered_zones:
                should_fire, reason = self._should_fire_zone_trigger(
                    symbol, zone, price)
                if not should_fire:
                    self._log_suppression(symbol, zone, price, reason)
                    continue

                log.info(f"Zone trigger FIRED {symbol} {zone['type']} "
                         f"@{zone['level']} price={price} ({reason})")
                trigger = self.trigger_builder.build_zone_trigger(
                    symbol, zone, {
                    "last": price, "bid": tick["bid"], "ask": tick["ask"],
                    "spread": tick["spread"]
                })
                self._fire_trigger(trigger)

                # Record fire event for future material-change comparisons
                key = f"{symbol}:{zone['type']}:{zone['level']}"
                self.state.zone_trigger_history[key] = {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "price": price,
                    "side": "above" if price > zone["level"] else "below",
                }
                self.state.save()

    def _should_fire_zone_trigger(self, symbol, zone, price):
        """Material-change gate for zone_approach triggers.

        A trigger only fires when something MATERIAL changed since the last
        wake for this same symbol+zone:
          - first trigger ever for this zone
          - price crossed to the other side of the level (state transition,
            fires even inside cooldown — crossings are real events)
          - price moved >= PRICE_MOVE_THRESHOLD since last wake (fast market)
          - stored history is corrupt (fail-open, never stay silent on doubt)

        Otherwise returns False with a human-readable reason.
        """
        key = f"{symbol}:{zone['type']}:{zone['level']}"
        now = datetime.now(timezone.utc)
        hist = self.state.zone_trigger_history.get(key)
        if not hist:
            return True, "first_trigger_for_zone"
        try:
            last_time = datetime.fromisoformat(hist["time"])
            elapsed = (now - last_time).total_seconds()
        except (KeyError, ValueError, TypeError):
            return True, "history_corrupt_fail_open"
        last_price = hist.get("price") or price
        move_pct = abs(price - last_price) / last_price * 100 if last_price else 0.0
        side_now = "above" if price > zone["level"] else "below"
        side_last = hist.get("side") or ("above" if last_price > zone["level"]
                                         else "below")

        if side_now != side_last:
            return True, f"level_crossing_{side_last}_to_{side_now}"
        if move_pct >= PRICE_MOVE_THRESHOLD:
            return True, f"price_moved_{move_pct:.2f}pct_since_last_wake"
        if elapsed < ZONE_TRIGGER_COOLDOWN:
            return False, (f"cooldown_active_{int(elapsed)}s_"
                           f"of_{ZONE_TRIGGER_COOLDOWN}s_move_{move_pct:.2f}pct")
        return False, (f"no_material_change_elapsed_{int(elapsed)}s_"
                       f"move_{move_pct:.2f}pct_below_{PRICE_MOVE_THRESHOLD}pct")

    def _log_suppression(self, symbol, zone, price, reason):
        """Append suppressed trigger to audit log + state counter."""
        self.state.suppressed_triggers += 1
        entry = {
            "suppressed_at": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "zone_type": zone.get("type"),
            "zone_level": zone.get("level"),
            "price": price,
            "reason": reason,
        }
        try:
            with open(SUPPRESSION_LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except OSError as e:
            log.error(f"Cannot write suppression log: {e}")
    
    def _full_scan(self):
        """Slow loop: comprehensive check."""
        # Check account health
        account = self.mt5.get_account()
        if account:
            heat = sum(abs(p.get("pnl", 0)) for p in self.mt5.get_positions())
            heat_pct = heat / account["balance"] * 100 if account["balance"] > 0 else 0
            
            if heat_pct > 6.0:
                trigger = {
                    "template": "emergency",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "emergency_type": "PORTFOLIO_HEAT",
                    "emergency_details": f"Portfolio heat {heat_pct:.1f}% exceeds 6% limit",
                    "positions": self.mt5.get_positions(),
                    "account": account,
                    "action_file": str(ACTION_FILE)
                }
                self._fire_trigger(trigger)
    
    def _daily_scan(self):
        """Daily: pull Granger + full review."""
        log.info("Running daily scan...")

        # Pull fresh Granger data + rebuild zone levels
        self._pull_granger(critical_on_fail=True)
        snap = self._load_snapshot()
        if snap:
            self.zones.update_zones(snap)

        # Fire daily scan trigger
        trigger = self.trigger_builder.build_daily_trigger()
        self._fire_trigger(trigger)

    def _pull_granger(self, critical_on_fail=True):
        """Pull fresh Granger snapshot. Returns True on success.

        Hourly refreshes pass critical_on_fail=False so a transient failure
        logs an error without flooding the CRITICAL error monitor.
        """
        pull_ok = False
        granger_log = LOGS_DIR / "granger_pull.log"
        try:
            # FIX (2026-08-24): capture_output pipes replaced with file
            # redirection. On Windows, subprocess.run(timeout=...) drains
            # stdout/stderr PIPES after kill(); if the dying child leaves
            # orphaned handles open, that drain blocks FOREVER and froze the
            # whole monitor loop silently (observed 2026-08-22 ~12:36 IST).
            # Output files have no EOF dependency -> timeout can never hang.
            with open(granger_log, "w", encoding="utf-8") as out:
                proc = subprocess.run(
                    [sys.executable, "-c", """
import asyncio, json, sys
sys.path.insert(0, r'C:\\Trading\\Granger')
from core.orchestrator import get_orchestrator
result = asyncio.run(get_orchestrator().collect_all_layers())
with open(r'C:\\Trading\\data\\all_layers_snapshot.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=2, default=str)
print("Granger pull complete")
"""],
                    stdout=out, stderr=subprocess.STDOUT, timeout=180
                )
            pull_ok = (proc.returncode == 0)
            if not pull_ok:
                try:
                    tail = granger_log.read_text(
                        encoding="utf-8", errors="replace")[-300:]
                except OSError:
                    tail = "<granger_pull.log unreadable>"
                log.error(f"Granger pull rc={proc.returncode}: {tail}")
        except Exception as e:
            log.error(f"Granger pull failed: {e}")

        if pull_ok:
            self.state.last_granger_pull = datetime.now(timezone.utc).isoformat()
            self.state.save()
            log.info("Granger snapshot updated")
        elif critical_on_fail:
            error_monitor.capture(
                severity="CRITICAL", source="granger", err_type="PULL_FAILED",
                message="Daily Granger pull failed — snapshot stale, "
                        "trading decisions degraded until fixed")
        return pull_ok

    def _load_snapshot(self):
        """Read the Granger snapshot file. Returns dict or None on failure."""
        try:
            with open(GRANGER_SNAPSHOT, encoding='utf-8') as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            log.error(f"Cannot read Granger snapshot: {e}")
            return None
    
    # ─── AI-AUTHORED RULES ENGINE ──────────────────────────────────────────────
    # The AI writes conditions into data/live/ai_triggers.json; the daemon clock
    # executes them verbatim — including the liveness heartbeat that keeps the AI
    # session alive, and the market rules that monitor & alert per the AI's design.

    def _load_ai_rules(self):
        """Load ai_triggers.json with mtime-based caching."""
        p = DATA_DIR / "ai_triggers.json"
        try:
            mtime = p.stat().st_mtime
        except OSError:
            return None
        if self._ai_rules_cache is not None and self._ai_rules_mtime == mtime:
            return self._ai_rules_cache
        try:
            with open(p, encoding="utf-8-sig") as f:
                doc = json.load(f)
            self._ai_rules_cache = doc
            self._ai_rules_mtime = mtime
            log.info("Loaded AI-authored rules from ai_triggers.json")
            return doc
        except Exception as e:
            log.error(f"Failed to load ai_triggers.json: {e}")
            return self._ai_rules_cache

    @staticmethod
    def _rsi(prices, period=14):
        """Wilder's RSI from a price series. None if insufficient data."""
        if len(prices) < period + 1:
            return None
        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        deltas = deltas[-period:]
        gains = [d for d in deltas if d > 0]
        losses = [-d for d in deltas if d < 0]
        avg_gain = sum(gains) / period if gains else 0.0
        avg_loss = sum(losses) / period if losses else 0.0
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _eval_ai_conditions(self, conditions, logic, sym, price, spread):
        if not conditions:
            return True, "no_conditions"
        results = []
        for c in conditions:
            ct = c.get("type")
            if ct == "price_above":
                results.append(price > c.get("level", float("inf")))
            elif ct == "price_below":
                results.append(price < c.get("level", float("-inf")))
            elif ct == "price_cross_above":
                prev = self._ai_prev_price.get(sym)
                lvl = c.get("level", 0)
                results.append(prev is not None and prev < lvl <= price)
            elif ct == "price_cross_below":
                prev = self._ai_prev_price.get(sym)
                lvl = c.get("level", 0)
                results.append(prev is not None and prev > lvl >= price)
            elif ct == "spread_below":
                results.append(spread < c.get("max_spread_points", float("inf")))
            elif ct == "rsi_below":
                period = c.get("period", 14)
                rsi = self._rsi(self._ai_price_buf.get(sym, []), period)
                results.append(False if rsi is None else rsi < c.get("value", 100))
            else:
                results.append(False)  # unknown condition type -> not met
        if logic == "ANY":
            return any(results), f"any({results})"
        return all(results), f"all({results})"

    def _check_ai_rules(self):
        """Evaluate AI-authored rules; fire a wake when one triggers."""
        doc = self._load_ai_rules()
        if not doc:
            return
        now = time.time()
        for rule in doc.get("rules", []):
            rid = rule.get("id")
            if not rid:
                continue

            # Expiry gate
            exp = rule.get("expires_utc")
            if exp:
                try:
                    ed = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                    if ed < datetime.now(timezone.utc):
                        continue
                except Exception:
                    pass

            conditions = rule.get("conditions", [])
            logic = rule.get("logic", "ALL")
            kind = rule.get("kind")

            # Liveness heartbeat: fires every N minutes -> keeps AI alive.
            if kind == "liveness" or any(
                c.get("type") == "elapsed_minutes" for c in conditions
            ):
                minutes = 15
                for c in conditions:
                    if c.get("type") == "elapsed_minutes":
                        minutes = c.get("minutes", 15)
                if now - self._ai_liveness_last >= minutes * 60:
                    self._ai_liveness_last = now
                    self._fire_ai_rule(rule, f"liveness heartbeat ({minutes}min)")
                continue

            sym = rule.get("symbol")
            if not sym or sym in ("_SYSTEM_",):
                continue
            tick = self.mt5.get_tick(sym)
            if not tick:
                continue
            price = tick.get("bid")
            spread = tick.get("spread", 0)
            if price is None:
                continue

            # Maintain rolling buffer for RSI
            buf = self._ai_price_buf.setdefault(sym, [])
            buf.append(price)
            if len(buf) > 200:
                self._ai_price_buf[sym] = buf[-200:]

            ok, why = self._eval_ai_conditions(
                conditions, logic, sym, price, spread
            )
            self._ai_last_price[sym] = price
            self._ai_prev_price[sym] = price  # for next cross detection

            if not ok:
                continue
            if rule.get("ring_once") and rid in self._ai_fired_once:
                continue
            if rule.get("ring_once"):
                self._ai_fired_once.add(rid)
            self._fire_ai_rule(rule, why)

    def _fire_ai_rule(self, rule, why):
        """Construct a trigger from an AI-authored rule and wake the AI."""
        sym = rule.get("symbol", "?")
        trigger = {
            "template": "ai_rule",
            "symbol": sym,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session": AI_SESSION_ID,
            "rule_id": rule.get("id"),
            "rule_kind": rule.get("kind"),
            "rule_direction": rule.get("direction"),
            "price": {"last": self._ai_last_price.get(sym)},
            "trigger": {"zone": {"level": None, "type": rule.get("kind")}},
            "positions": self.mt5.get_positions(),
            "account": self.mt5.get_account(),
            "calendar": {},
            "required_actions": [
                f"AI-AUTHORED RULE FIRED: {rule.get('id')} "
                f"({rule.get('kind')}/{rule.get('direction')}). Reason: {why}.",
                "Read your conditions in C:/Trading/Alpha/data/live/ai_triggers.json "
                "and evaluate against live data.",
                "If all entry/monitor checks pass per your standing policy, write ENTER "
                f"to {ACTION_FILE}; else WAIT with reasoning.",
            ],
        }
        log.info(f"AI rule FIRED {rule.get('id')} on {sym} ({why})")
        self._fire_trigger(trigger)

    def _fire_trigger(self, trigger):
        """Write trigger + wake the AI in THIS session."""
        # Write trigger file
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(TRIGGER_FILE, 'w', encoding='utf-8') as f:
            json.dump(trigger, f, indent=2, default=str)
        
        self.state.last_trigger_time = datetime.now(timezone.utc).isoformat()
        self.state.save()
        
        # Build the wake-up prompt
        prompt = self._build_wake_prompt(trigger)
        
        # Write prompt to file (so AI can read full context if needed)
        prompt_file = DATA_DIR / "wake_prompt.txt"
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(prompt)
        
        # Notify user
        symbol = trigger.get("symbol", "?")
        ttype = trigger.get("template", trigger.get("trigger", {}).get("type", "?"))
        notify_user(f"Trigger: {ttype} on {symbol}")
        
        # Wake the AI in THIS session — not a new process
        log.info(f"Firing trigger: {ttype} on {symbol} → session {AI_SESSION_ID}")
        try:
            # NOTE: multi-line args get mangled through .cmd wrappers — send a
            # short single-line pointer; full prompt already on disk.
            opencode_path = r"C:\Users\arjun\AppData\Roaming\npm\opencode.cmd"
            short = (f"[ALPHA DAEMON TRIGGER] {ttype} on {symbol}. "
                     f"Read {prompt_file} for full context, then write your "
                     f"decision to {ACTION_FILE}.")
            cmd = [
                opencode_path, "run",
                short,               # positional: the message
                "-s", AI_SESSION_ID  # continue THIS session
            ]
            subprocess.Popen(
                cmd,
                cwd=str(ALPHA_ROOT),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
        except Exception as e:
            log.error(f"Failed to wake AI: {e}")
            # Fallback: log the trigger, user can manually check
            log.info(f"Trigger saved to {TRIGGER_FILE}. Manual intervention needed.")
    
    def _build_wake_prompt(self, trigger):
        """Build the full wake-up prompt from trigger data.
        
        This prompt is sent INTO the existing session via `opencode run -s`.
        The AI receives it as a message, reads the trigger context, and responds
        with a decision written to action.json.
        """
        template = trigger.get("template", "zone_approach")
        
        base = f"""[ALPHA DAEMON TRIGGER] — This is an automated message from the Alpha daemon, not from the user.

## WHY YOU WERE WAKED
Trigger Type: {template.upper().replace('_', ' ')}
Timestamp: {trigger.get('timestamp')}
Session: {trigger.get('session')}

"""
        if template == "zone_approach":
            zone = trigger.get("trigger", {})
            base += f"""## ZONE DETECTED
Symbol: {trigger.get('symbol')}
Price: ${trigger.get('price', {}).get('last', '?')}
Level: ${zone.get('zone', {}).get('level', '?')} ({zone.get('zone', {}).get('type', '?')})
Distance: {zone.get('zone', {}).get('distance_pct', '?')}%

"""
        elif template == "regime_shift":
            shifts = trigger.get("regime_shifts", [])
            base += "## REGIME CHANGES\n"
            for s in shifts:
                base += f"- {s['type']}: {s['from']} → {s['to']} ({s['change_pct']:+.1f}%, {s['direction']})\n"
            base += "\n"
        
        base += f"""## POSITIONS
{json.dumps(trigger.get('positions', []), indent=2)}

## ACCOUNT
{json.dumps(trigger.get('account', {}), indent=2)}

## CALENDAR
{json.dumps(trigger.get('calendar', {}), indent=2)}

## YOUR TASK
{chr(10).join(trigger.get('required_actions', []))}

## GRANGER SNAPSHOT
Read: C:/Trading/data/all_layers_snapshot.json
Or pull fresh: cd C:/Trading/Granger && python -c "import asyncio; from core.orchestrator import get_orchestrator; print(asyncio.run(get_orchestrator().collect_all_layers()))"

## RULES — RETAIL TRAP-AWARE (MANDATORY)
Read: C:/Trading/Alpha/daemon/RETAIL_TRAP_RULES.md for the full trap catalog and entry criteria.

### TRAP SCAN (Do this FIRST, before any entry consideration)
Zone proximity = WARNING, not opportunity. Before ANY trade idea:
- TRAP 1: Is price near a "known" level (BB, SMA, round #) with no institutional confirmation? → RESISTANCE BOUNCE TRAP
- TRAP 2: Did price just poke above a level for the first time? → BREAKOUT CHASE TRAP (needs daily close + volume + retest)
- TRAP 3: Are all "confirming" indicators price-derived (RSI + BB + MACD)? → INDICATOR CONFLUENCE TRAP (they're ONE source, not three)
- TRAP 4: Is there news within 30min or a recent >1% spike? → NEWS SPIKE CHASE TRAP
- TRAP 5: Is the only "level" a round number ($4500, $4600)? → ROUND NUMBER CLUSTER TRAP
- TRAP 6: Is the market in a strong trend (>10% in <30d) being faded? → MOMENTUM FADE TRAP

IF ANY TRAP DETECTED → DO NOT ENTER. Write WAIT with trap_flags explaining which traps.

### ENTRY CRITERIA (ALL 7 REQUIRED for high-conviction trade)
1. TRAP ABSENCE — Zero traps detected in scan above
2. INSTITUTIONAL ALIGNMENT — COT positioning + ETF flows support direction
3. MULTI-SOURCE CONFLUENCE — ≥3 INDEPENDENT sources (price-derived indicators = ONE source)
4. STRUCTURE CONFIRMATION — Price did something at the level (rejection/breakout+retest), not just approached
5. REGIME ALIGNMENT — Trade aligns with current macro regime
6. RISK:REWARD ≥ 2:1 — Structural stop + structural target
7. TIME QUALITY — Prefer NY session (13:00-21:00 UTC), avoid thin liquidity

### SAFETY RULES
- NEVER enter if news within 15min
- NEVER risk > 2% per trade
- NEVER exceed 6% portfolio heat
- ALWAYS have a stop loss
- ALWAYS write reasoning
- If unsure, WAIT

## OUTPUT — YOU MUST DO THIS
1. **TRAP SCAN first** — Run all 6 trap checks. List trap_flags if any detected.
2. Analyze the trigger context above
3. Pull or read Granger snapshot (C:/Trading/data/all_layers_snapshot.json)
4. Check all 7 entry criteria explicitly
5. If entering a trade: calculate size from conviction × account × risk, ensure R:R ≥ 2:1
6. Write decision as JSON to: {ACTION_FILE}
7. Your response in this chat should be a brief summary of your decision with trap scan results

Use the decision schemas from C:/Trading/Alpha/daemon/WAKEUP_PROMPTS.md
"""
        return base

# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    daemon = AlphaDaemon()
    daemon.start()
