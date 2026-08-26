"""
ALPHA — Entry Point.

Starts the daemon (the body). The AI brain lives in the Alethia v4
session and is woken by daemon triggers via opencode run -s.

Usage:
    python main.py
"""

import logging
import sys
from pathlib import Path

# Make all Alpha packages importable when run from anywhere
sys.path.insert(0, str(Path(__file__).parent))

from config import LOG_FORMAT, LOG_LEVEL  # noqa: E402

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
log = logging.getLogger("alpha.main")


def main():
    log.info("=" * 60)
    log.info("ALPHA starting — daemon mode (body only; AI decides)")
    log.info("=" * 60)

    from daemon.daemon import AlphaDaemon
    daemon = AlphaDaemon()
    daemon.start()


if __name__ == "__main__":
    main()
