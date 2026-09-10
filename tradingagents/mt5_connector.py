"""Robust centralized MT5 connection helper for Alpha trading stack."""
import os
import json
import logging

LOG = logging.getLogger("alpha.mt5_connector")
FTMO_PATH = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"

def ensure_mt5_connected(timeout: int = 5000) -> bool:
    """Ensures MetaTrader5 is initialized with active FTMO credentials.
    Returns True if connected and ready, False otherwise.
    """
    try:
        import MetaTrader5 as mt5
        t_info = mt5.terminal_info()
        if t_info is not None and getattr(t_info, "connected", False):
            return True

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        creds_path = os.path.join(base_dir, "config", "mt5_credentials.json")
        creds = {}
        if os.path.exists(creds_path):
            try:
                with open(creds_path, "r", encoding="utf-8") as f:
                    creds = json.load(f)
            except Exception as e:
                LOG.warning(f"Could not load mt5_credentials.json: {e}")

        kwargs = {"timeout": timeout}
        if os.path.exists(FTMO_PATH):
            kwargs["path"] = FTMO_PATH
        if creds.get("login"):
            kwargs["login"] = creds["login"]
        if creds.get("password"):
            kwargs["password"] = creds["password"]
        if creds.get("server"):
            kwargs["server"] = creds["server"]

        ok = mt5.initialize(**kwargs)
        if not ok:
            ok = mt5.initialize(timeout=timeout)
        return bool(ok)
    except Exception as err:
        LOG.error(f"ensure_mt5_connected failed: {err}")
        return False
