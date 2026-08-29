"""
ALPHA — Configuration

Single source of truth for ALL settings.
Every module imports from here. No hardcoded values elsewhere.

Read VISION.md before modifying any setting.
"""

import os
from pathlib import Path

# ============================================================
# PATHS
# ============================================================

ALPHA_DIR = Path(r"C:\Trading\Alpha")
GRANGER_DIR = Path(r"C:\Trading\Granger")

# Directories
DATA_DIR = ALPHA_DIR / "data"
LIVE_DATA_DIR = DATA_DIR / "live"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
MEMORY_DIR = ALPHA_DIR / "memory"
ZONES_DIR = MEMORY_DIR / "zones"
JOURNAL_DIR = MEMORY_DIR / "journal"
LOGS_DIR = ALPHA_DIR / "logs"
TRIGGERS_DIR = LIVE_DATA_DIR / "triggers"

# Ensure directories exist
for d in [DATA_DIR, LIVE_DATA_DIR, SNAPSHOTS_DIR, MEMORY_DIR,
          ZONES_DIR, JOURNAL_DIR, LOGS_DIR, TRIGGERS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================================
# MT5 CONNECTION
# ============================================================

MT5_TERMINAL_PATH = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
MT5_GENERIC_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"
MT5_LOGIN = os.environ.get("MT5_LOGIN")  # From env var
MT5_PASSWORD = os.environ.get("MT5_PASSWORD")
MT5_SERVER = os.environ.get("MT5_SERVER", "FTMO-Demo")

# ============================================================
# RISK LIMITS (Hard limits — never override)
# ============================================================

MAX_SINGLE_RISK_PCT = 2.0           # Max risk per position as % of account
MAX_PORTFOLIO_HEAT_PCT = 6.0        # Max total open risk as % of account
MAX_CORRELATED_RISK_PCT = 3.0       # Max combined risk for correlated positions
CORRELATION_THRESHOLD = 0.80        # Correlation threshold for adjustment
MAX_DRAWDOWN_MONTHLY_PCT = 10.0     # Monthly drawdown circuit breaker
MAX_DRAWDOWN_DAILY_PCT = 3.0        # Daily loss limit
DRAWDOWN_WARNING_PCT = 5.0          # Warning threshold (reduce sizes)
DRAWDOWN_CRITICAL_PCT = 7.0         # Critical threshold (no new positions)
MAX_OPEN_POSITIONS = 5              # Maximum simultaneous positions

# ============================================================
# DAEMON V2 RUNTIME
# ============================================================

DAEMON_V2_POLL_INTERVAL_SECONDS = int(
    os.environ.get("ALPHA_DAEMON_POLL_INTERVAL", "10")
)
DAEMON_V2_MIN_FREE_MARGIN_PCT = float(
    os.environ.get("ALPHA_MIN_FREE_MARGIN_PCT", "20.0")
)
DAEMON_V2_TERMINAL_SILENCE_SECONDS = int(
    os.environ.get("ALPHA_TERMINAL_SILENCE_SECONDS", "60")
)
DAEMON_V2_WATCH_SYMBOLS = tuple(
    symbol.strip()
    for symbol in os.environ.get(
        "ALPHA_WATCH_SYMBOLS",
        "XAUUSD,XAGUSD,XPTUSD,XPDUSD",
    ).split(",")
    if symbol.strip()
)
DAEMON_V2_GRANGER_SNAPSHOT_PATH = Path(
    os.environ.get(
        "ALPHA_GRANGER_SNAPSHOT_PATH",
        r"C:\Trading\data\all_layers_snapshot.json",
    )
)
DAEMON_V2_OPENCODE_CMD = os.environ.get(
    "ALPHA_OPENCODE_CMD",
    str(Path.home() / "AppData" / "Roaming" / "npm" / "opencode.cmd"),
)
DAEMON_V2_SESSION_ID_FALLBACK = os.environ.get(
    "ALPHA_AI_SESSION_ID",
    "",
)

# ============================================================
# MONITOR SETTINGS
# ============================================================

MONITOR_INTERVAL_SECONDS = 60       # How often the monitor checks
ZONE_APPROACH_PCT = 0.5             # Trigger when price within 0.5% of zone
ZONE_BREAK_PCT = 0.1                # Trigger when price breaks through zone
POSITION_ALERT_PCT = 0.3            # Trigger when position near stop/target

# ============================================================
# REGIME MONITOR THRESHOLDS
# ============================================================

DXY_MOVE_WARNING_PCT = 0.3          # DXY move in 15min triggers warning
DXY_MOVE_CRITICAL_PCT = 0.5         # DXY move in 15min triggers critical
VIX_WARNING = 18.0                  # VIX above this = warning
VIX_CRITICAL = 22.0                 # VIX above this = critical
YIELD_MOVE_WARNING_BPS = 5          # 10Y yield move in 1hr
YIELD_MOVE_CRITICAL_BPS = 10        # 10Y yield move in 1hr
GS_RATIO_MOVE_WARNING_PCT = 2.0     # Gold/Silver ratio move in 1 day
GS_RATIO_MOVE_CRITICAL_PCT = 5.0    # Gold/Silver ratio move in 1 day

# ============================================================
# NEWS / CALENDAR
# ============================================================

NEWS_BLACKOUT_MINUTES = 60          # No entries within 60min of high-impact news
CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# ============================================================
# BRAIN SETTINGS
# ============================================================

GRANGER_STALENESS_HOURS = 6         # Re-pull Granger after this many hours
MIN_CONVICTION_TO_TRADE = 8.0       # Minimum score to place a trade
MIN_CONVICTION_TO_WATCH = 6.0       # Minimum score to add a watch zone
MAX_CONVICTION = 10.0               # Maximum conviction score

# Conviction multiplier mapping (score -> position size multiplier)
CONVICTION_MULTIPLIERS = {
    (6.0, 6.9): 0.50,   # Half size — low conviction
    (7.0, 7.9): 0.75,   # Three-quarter size
    (8.0, 8.9): 1.00,   # Full size
    (9.0, 9.5): 1.25,   # Large size
    (9.6, 10.0): 1.50,  # Max size — A+ setups only
}

# Decision buckets
BUCKETS = [
    "trend_continuation",
    "mean_reversion",
    "breakout",
    "regime_shift",
    "contrarian",
    "news_reaction",
    "pairs",
    "risk_off",
]

# ============================================================
# EXECUTION
# ============================================================

SLIPPAGE_TOLERANCE_PIPS = 2.0       # Max acceptable slippage
LIMIT_ORDER_OFFSET_PIPS = 1.0       # Offset for limit orders from zone
MARKET_ORDER_THRESHOLD_PIPS = 1.0   # Within this many pips = market order

# ============================================================
# INSTRUMENTS
# ============================================================
# Maps MT5 symbol -> Granger key + point info
# Values verified against FTMO contract specs 2026-08-21:
#   pip_value_per_lot = trade_contract_size × point ($ per point per lot)
# NOTE: "pip" here means broker POINT (smallest increment).
# TODO: USDJPY value drifts with rate — refresh weekly or compute live.

INSTRUMENTS = {
    "XAGUSD": {
        "granger_key": "silver",
        "pip_value_per_lot": 5.0,     # 5000 oz × 0.001
        "pip_size": 0.001,
        "description": "Silver",
        "category": "precious_metals",
    },
    "XAUUSD": {
        "granger_key": "gold",
        "pip_value_per_lot": 1.0,     # 100 oz × 0.01
        "pip_size": 0.01,
        "description": "Gold",
        "category": "precious_metals",
    },
    "XPTUSD": {
        "granger_key": "platinum",
        "pip_value_per_lot": 1.0,     # 100 oz × 0.01
        "pip_size": 0.01,
        "description": "Platinum",
        "category": "precious_metals",
    },
    "XPDUSD": {
        "granger_key": "palladium",
        "pip_value_per_lot": 1.0,     # 100 oz × 0.01
        "pip_size": 0.01,
        "description": "Palladium",
        "category": "precious_metals",
    },
    "XCUUSD": {
        "granger_key": "copper",
        "pip_value_per_lot": 1.0,     # 100 × 0.01
        "pip_size": 0.01,
        "description": "Copper (FTMO symbol: XCUUSD)",
        "category": "industrial_metals",
    },
    "USOIL.cash": {
        "granger_key": "crude_oil",
        "pip_value_per_lot": 0.1,     # 100 bbl × 0.001
        "pip_size": 0.001,
        "description": "WTI Crude Oil (FTMO: USOIL.cash)",
        "category": "energy",
    },
    "NATGAS.cash": {
        "granger_key": "natural_gas",
        "pip_value_per_lot": 1.0,     # 1000 × 0.001
        "pip_size": 0.001,
        "description": "Natural Gas (FTMO: NATGAS.cash)",
        "category": "energy",
    },
    "EURUSD": {
        "granger_key": "eurusd",
        "pip_value_per_lot": 1.0,     # 100k × 0.00001
        "pip_size": 0.00001,
        "description": "EUR/USD",
        "category": "fx",
    },
    "USDJPY": {
        "granger_key": "usdjpy",
        "pip_value_per_lot": 6.3,     # 100k × 0.01 / USDJPY ≈ 158.7
        "pip_size": 0.01,
        "description": "USD/JPY",
        "category": "fx",
    },
    "GBPUSD": {
        "granger_key": "gbpusd",
        "pip_value_per_lot": 1.0,     # 100k × 0.00001
        "pip_size": 0.00001,
        "description": "GBP/USD",
        "category": "fx",
    },
}

# Category correlation groups (for risk adjustment)
CORRELATION_GROUPS = {
    "precious_metals": ["XAGUSD", "XAUUSD", "XPTUSD", "XPDUSD"],
    "industrial_metals": ["XCUUSD"],
    "energy": ["USOIL.cash", "NATGAS.cash"],
    "fx": ["EURUSD", "GBPUSD", "USDJPY"],
}

# ============================================================
# POSITION MANAGEMENT RULES
# ============================================================

SCALE_OUT_PCT = 0.50                # Close 50% at Target 1
BREAKEVEN_TRIGGER_R = 1.0           # Move to breakeven after +1R
TRAIL_STOP_ATR_MULTIPLE = 1.5       # Trail stop by 1.5x ATR after breakeven
TIME_STOP_DAYS = 3                  # Reassess if flat for 3 days

# ============================================================
# LOGGING
# ============================================================

LOG_LEVEL = os.environ.get("ALPHA_LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_FILE = LOGS_DIR / "alpha.log"

# ============================================================
# CENTRALIZED OPENCODE SESSION CONFIGURATION (HOT-RELOADING)
# ============================================================

OPENCODE_SESSION_CONFIG_PATH = ALPHA_DIR / "config" / "opencode_session_config.json"
DEFAULT_SESSION_ID = "ses_fb2eb6b52ffeqMc2TBOet5xjhx"
DEFAULT_SESSION_TITLE = "Alpha v5"
DEFAULT_API_URL = "http://127.0.0.1:4096"

def load_session_config():
    """Loads centralized OpenCode session configuration with zero-restart hot-reloading."""
    import json
    if OPENCODE_SESSION_CONFIG_PATH.exists():
        try:
            with open(OPENCODE_SESSION_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {
        "session_id": DEFAULT_SESSION_ID,
        "session_title": DEFAULT_SESSION_TITLE,
        "opencode_api_url": DEFAULT_API_URL
    }

def get_opencode_session():
    """Returns (session_id, session_title, api_url) dynamically."""
    cfg = load_session_config()
    return (
        str(cfg.get("session_id") or DEFAULT_SESSION_ID),
        str(cfg.get("session_title") or DEFAULT_SESSION_TITLE),
        str(cfg.get("opencode_api_url") or DEFAULT_API_URL)
    )

def get_opencode_session_id() -> str:
    return get_opencode_session()[0]

def get_opencode_session_title() -> str:
    return get_opencode_session()[1]

def get_opencode_api_url() -> str:
    return get_opencode_session()[2]

def set_opencode_session(session_id: str, session_title: str = None) -> bool:
    """Updates centralized session config on disk with zero-restart hot-reloading."""
    import json
    try:
        cfg = load_session_config()
        cfg["session_id"] = str(session_id).strip()
        if session_title:
            cfg["session_title"] = str(session_title).strip()
        OPENCODE_SESSION_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(OPENCODE_SESSION_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        return True
    except Exception:
        return False

