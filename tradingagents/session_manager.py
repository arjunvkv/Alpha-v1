"""
Centralized OpenCode Session Configuration Manager.

Single source of truth for the active OpenCode session ID, session title,
and API endpoint across all desk components, MCP servers, and daemons.
Backed by C:\\Trading\\Alpha\\config\\opencode_session_config.json with zero-restart hot-reloading.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple

LOG = logging.getLogger("alpha.session_manager")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_CONFIG_PATH = PROJECT_ROOT / "config" / "opencode_session_config.json"
OPENCODE_SESSION_CONFIG_PATH = SESSION_CONFIG_PATH

DEFAULT_SESSION_ID = "ses_fb15b2b27ffezJfLoCEJP5a95r"
DEFAULT_SESSION_TITLE = "Alpha-Gravity"
DEFAULT_API_URL = "http://127.0.0.1:4096"


def load_session_config() -> Dict[str, Any]:
    """Loads the centralized OpenCode session config with zero-restart hot-reloading."""
    if SESSION_CONFIG_PATH.exists():
        try:
            with open(SESSION_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            LOG.error(f"Error reading {SESSION_CONFIG_PATH}: {e}")

    return {
        "session_id": DEFAULT_SESSION_ID,
        "session_title": DEFAULT_SESSION_TITLE,
        "opencode_api_url": DEFAULT_API_URL,
        "dossier_streaming_enabled": True
    }


def get_opencode_session() -> Tuple[str, str, str]:
    """Returns (session_id, session_title, opencode_api_url) dynamically."""
    cfg = load_session_config()
    sid = cfg.get("session_id") or DEFAULT_SESSION_ID
    title = cfg.get("session_title") or DEFAULT_SESSION_TITLE
    api_url = cfg.get("opencode_api_url") or DEFAULT_API_URL
    return str(sid), str(title), str(api_url)


def get_opencode_session_id() -> str:
    """Returns current active session ID."""
    return get_opencode_session()[0]


def get_opencode_session_title() -> str:
    """Returns current active session title."""
    return get_opencode_session()[1]


def get_opencode_api_url() -> str:
    """Returns current OpenCode API URL."""
    return get_opencode_session()[2]


def set_opencode_session(session_id: str, session_title: str = None) -> bool:
    """Updates the centralized session configuration file on disk."""
    try:
        cfg = load_session_config()
        cfg["session_id"] = str(session_id).strip()
        if session_title:
            cfg["session_title"] = str(session_title).strip()
        from datetime import datetime, timezone
        cfg["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        SESSION_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SESSION_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        LOG.info(f"Updated OpenCode session config: {cfg.get('session_title')} ({cfg.get('session_id')})")
        return True
    except Exception as e:
        LOG.error(f"Failed to write session config: {e}")
        return False


def is_dossier_streaming_enabled() -> bool:
    """Checks whether live dossier prompt dispatch to OpenCode is active or paused."""
    cfg = load_session_config()
    return bool(cfg.get("dossier_streaming_enabled", True))


def set_dossier_streaming(enabled: bool) -> bool:
    """Pauses or resumes dossier prompt streaming with zero-restart hot-reloading."""
    try:
        cfg = load_session_config()
        cfg["dossier_streaming_enabled"] = bool(enabled)
        from datetime import datetime, timezone
        cfg["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        SESSION_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SESSION_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        LOG.info(f"Updated dossier streaming: {enabled}")
        return True
    except Exception as e:
        LOG.error(f"Failed to update dossier streaming toggle: {e}")
        return False


def get_dossier_interval_seconds() -> int:
    """Returns dynamic scheduled dossier interval in seconds (default 300s = 5 min)."""
    cfg = load_session_config()
    try:
        return int(cfg.get("dossier_interval_seconds", 300))
    except Exception:
        return 300


def set_dossier_interval_seconds(seconds: int) -> bool:
    """Updates dynamic scheduled dossier interval in seconds with zero-restart hot-reloading."""
    try:
        cfg = load_session_config()
        cfg["dossier_interval_seconds"] = max(30, int(seconds))
        from datetime import datetime, timezone
        cfg["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        SESSION_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SESSION_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        LOG.info(f"Updated dossier interval to {seconds} seconds")
        return True
    except Exception as e:
        LOG.error(f"Failed to update dossier interval: {e}")
        return False


def get_active_trade_interval_seconds() -> int:
    """Returns dynamic active trade review interval in seconds (default 60s = 1 min)."""
    cfg = load_session_config()
    try:
        return int(cfg.get("active_trade_interval_seconds", 60))
    except Exception:
        return 60


def set_active_trade_interval_seconds(seconds: int) -> bool:
    """Updates dynamic active trade review interval in seconds with zero-restart hot-reloading."""
    try:
        cfg = load_session_config()
        cfg["active_trade_interval_seconds"] = max(10, int(seconds))
        from datetime import datetime, timezone
        cfg["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        SESSION_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SESSION_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        LOG.info(f"Updated active trade interval to {seconds} seconds")
        return True
    except Exception as e:
        LOG.error(f"Failed to update active trade interval: {e}")
        return False
