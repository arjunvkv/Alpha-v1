"""
Centralized OpenCode Session Configuration Manager.

Provides dynamic, zero-restart hot-reloading for the active OpenCode session ID,
session title, and API endpoint across all desk components, MCP servers, and daemons.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple

LOG = logging.getLogger("alpha.config.session_manager")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_CONFIG_PATH = PROJECT_ROOT / "config" / "opencode_session_config.json"

DEFAULT_SESSION_ID = "ses_fb09a8448ffeBaCTOs7uK0rVYw"
DEFAULT_SESSION_TITLE = "alpha-gravity"
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
        "opencode_api_url": DEFAULT_API_URL
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
        SESSION_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SESSION_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        LOG.info(f"Updated OpenCode session config: {cfg['session_title']} ({cfg['session_id']})")
        return True
    except Exception as e:
        LOG.error(f"Failed to write session config: {e}")
        return False
