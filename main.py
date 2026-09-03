"""
ALPHA — Entry Point.

Starts the daemon (the body). The AI brain lives in the Alethia v4
session and is woken by daemon triggers via opencode run -s.

Usage:
    python main.py
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make all Alpha packages importable when run from anywhere
sys.path.insert(0, str(Path(__file__).parent))

from config import LOG_FORMAT, LOG_LEVEL  # noqa: E402

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
log = logging.getLogger("alpha.main")


def _write_startup_capabilities():
    from sensors.evidence_sources import capability_snapshot
    path = Path(__file__).parent / "data" / "live" / "startup_capabilities.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "daemon_started_at": datetime.now(timezone.utc).isoformat(),
        "daemon_version": "evidence-first",
        "config_version": "1",
        "mt5_state": "PENDING_DAEMON_INITIALIZATION",
        "instrument_states": {},
        "adapter_states": capability_snapshot(),
        "enabled_capabilities": [],
        "disabled_capabilities": [],
        "startup_errors": [],
    }
    for name, state in payload["adapter_states"].items():
        (payload["enabled_capabilities"] if state.get("state") in ("SUCCESS", "READY") else payload["disabled_capabilities"]).append(name)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)
    return payload

def main():
    capabilities = _write_startup_capabilities()
    log.info("=" * 60)
    log.info("ALPHA starting — daemon mode (body only; AI decides)")
    log.info("=" * 60)
    log.info("Optional evidence capabilities: %s", capabilities["adapter_states"])

    from daemon.daemon import AlphaDaemon
    daemon = AlphaDaemon()
    daemon.start()


if __name__ == "__main__":
    main()
