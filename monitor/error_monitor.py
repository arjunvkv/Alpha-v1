"""
Error Monitor — captures EVERYTHING that goes wrong and reports it.

Sources captured:
    1. Uncaught Python exceptions (main + threads) via excepthooks
    2. MT5 execution failures (retcode mapping)
    3. Log-file ERROR/CRITICAL lines (tail thread)

Behavior:
    - Every error appended to data/live/errors.json (rotated at 1000 entries)
    - CRITICAL errors wake the AI session via opencode run -s (same pipeline as triggers)
    - WARNING errors wake the AI only after a 5-minute cooldown (no spam)
    - Identical messages deduplicated within 60 seconds

Usage (embedded):
    from monitor.error_monitor import error_monitor
    error_monitor.install_global_handlers()
    error_monitor.capture_mt5_result(result, context="ENTER XAGUSD")

Usage (standalone log tail):
    python monitor/error_monitor.py
"""

import json
import logging
import subprocess
import sys
import threading
import time
import traceback as tb_module
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import ALPHA_DIR, LIVE_DATA_DIR

log = logging.getLogger("alpha.error_monitor")

OPENCODE = r"C:\Users\arjun\AppData\Roaming\npm\opencode.cmd"
SESSION_ID_FILE = LIVE_DATA_DIR / "session_id.txt"
DEFAULT_SESSION_ID = "ses_feee1399cffeIkkxcPfrsT1Uhq"
ERRORS_FILE = LIVE_DATA_DIR / "errors.json"

# MT5 trade server return codes (MetaTrader5 docs)
MT5_RETCODES = {
    10004: ("REQUOTE", "WARNING"),
    10006: ("ORDER_REJECTED", "CRITICAL"),
    10007: ("CANCELED_BY_TRADER", "INFO"),
    10008: ("PLACED", "INFO"),
    10009: ("DONE", "INFO"),
    10010: ("PARTIAL_FILL", "WARNING"),
    10011: ("REQUEST_ERROR", "CRITICAL"),
    10012: ("REQUEST_TIMEOUT", "CRITICAL"),
    10013: ("INVALID_REQUEST", "CRITICAL"),
    10014: ("INVALID_VOLUME", "CRITICAL"),
    10015: ("INVALID_PRICE", "CRITICAL"),
    10016: ("INVALID_STOPS", "CRITICAL"),
    10017: ("TRADE_DISABLED", "CRITICAL"),
    10018: ("MARKET_CLOSED", "WARNING"),
    10019: ("NO_MONEY", "CRITICAL"),
    10020: ("PRICES_CHANGED", "WARNING"),
    10021: ("OFF_QUOTES", "WARNING"),
    10024: ("TOO_MANY_REQUESTS", "WARNING"),
    10026: ("AUTOTRADING_DISABLED", "CRITICAL"),
    10027: ("AUTOTRADING_NOT_ALLOWED", "CRITICAL"),
    10031: ("CONNECTION_LOST", "CRITICAL"),
}

WAKE_COOLDOWN_WARNING_S = 300   # non-critical wakes max every 5 min
DEDUP_WINDOW_S = 60             # identical message dedup window
ROTATE_AT = 1000                # rotate errors.json beyond this many entries


class ErrorMonitor:
    """Central error capture + AI reporting."""

    def __init__(self, errors_file: Path = ERRORS_FILE):
        self.errors_file = Path(errors_file)
        self._last_wake_time = 0.0
        self._recent_messages = {}  # message -> timestamp (dedup)
        self._lock = threading.Lock()
        self._tail_threads = []
        self._installed = False

    # ── Capture ──────────────────────────────────────────────────

    def capture(self, severity: str, source: str, err_type: str,
                message: str, context: Optional[dict] = None,
                trace: Optional[str] = None) -> dict:
        """
        Record any error. severity: INFO | WARNING | CRITICAL.
        Returns the stored record.
        """
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": severity.upper(),
            "source": source,
            "type": err_type,
            "message": str(message)[:2000],
            "context": context or {},
            "trace": (trace or "")[:3000],
        }
        with self._lock:
            self._append(record)
            if not self._is_duplicate(str(message)):
                self._maybe_wake(record)
            else:
                log.debug(f"Deduped error: {err_type}")
        return record

    def capture_exception(self, exc: Exception, source: str = "python",
                          context: Optional[dict] = None):
        """Convenience for caught exceptions."""
        return self.capture(
            severity="CRITICAL",
            source=source,
            err_type=type(exc).__name__,
            message=str(exc),
            context=context,
            trace=tb_module.format_exc(),
        )

    def capture_mt5_result(self, result, context: Optional[dict] = None):
        """Inspect an mt5.order_send() result; capture failures."""
        if result is None:
            import MetaTrader5 as mt5
            err = mt5.last_error()
            return self.capture(
                severity="CRITICAL", source="mt5", err_type="NULL_RESULT",
                message=f"order_send returned None — last_error={err}",
                context=context,
            )
        retcode = getattr(result, "retcode", None)
        if retcode is None:
            return None  # not an MT5 result object
        name, sev = MT5_RETCODES.get(retcode, (f"RETCODE_{retcode}", "WARNING"))
        if sev == "INFO":
            return None  # success codes — nothing to report
        comment = getattr(result, "comment", "")
        return self.capture(
            severity=sev, source="mt5_execution", err_type=name,
            message=f"MT5 order failed [{name}]: {comment or 'no comment'} "
                    f"(retcode {retcode})",
            context={"retcode": retcode, **(context or {})},
        )

    # ── Global handlers ──────────────────────────────────────────

    def install_global_handlers(self):
        """Catch uncaught exceptions in main thread + all threads."""
        if self._installed:
            return
        prev_hook = sys.excepthook

        def sys_hook(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                prev_hook(exc_type, exc_value, exc_traceback)
                return
            self.capture(
                severity="CRITICAL", source="python_uncaught",
                err_type=exc_type.__name__, message=str(exc_value),
                trace="\n".join(tb_module.format_exception(
                    exc_type, exc_value, exc_traceback)),
            )
            prev_hook(exc_type, exc_value, exc_traceback)

        sys.excepthook = sys_hook

        def thread_hook(args):
            self.capture(
                severity="CRITICAL", source="thread_uncaught",
                err_type=args.exc_type.__name__, message=str(args.exc_value),
                context={"thread": args.thread.name if args.thread else "?"},
                trace="\n".join(tb_module.format_exception(
                    args.exc_type, args.exc_value, args.exc_traceback)),
            )

        threading.excepthook = thread_hook
        self._installed = True
        log.info("ErrorMonitor global handlers installed")

    # ── Log tailing ──────────────────────────────────────────────

    def tail_log(self, log_path: Path,
                 stop_event: Optional[threading.Event] = None):
        """Background-tail a log file; capture ERROR/CRITICAL lines."""
        log_path = Path(log_path)
        stop_event = stop_event or threading.Event()

        def _tail():
            offset = 0
            if log_path.exists():
                offset = log_path.stat().st_size
            while not stop_event.is_set():
                try:
                    if log_path.exists():
                        size = log_path.stat().st_size
                        if size > offset:
                            with open(log_path, encoding="utf-8", errors="replace") as f:
                                f.seek(offset)
                                new_lines = f.read().splitlines()
                            offset = size
                            for line in new_lines:
                                self._parse_log_line(line)
                        elif size < offset:  # rotated/truncated
                            offset = 0
                except Exception as e:  # never die from tailing
                    log.debug(f"Tail error on {log_path}: {e}")
                stop_event.wait(2.0)

        t = threading.Thread(target=_tail, daemon=True, name=f"tail-{log_path.name}")
        t.start()
        self._tail_threads.append((t, stop_event))
        log.info(f"Tailing {log_path}")

    def _parse_log_line(self, line: str):
        if "[ERROR]" in line:
            self.capture(severity="ERROR", source="daemon_log",
                         err_type="LOG_ERROR", message=line[:2000])
        elif "[CRITICAL]" in line:
            self.capture(severity="CRITICAL", source="daemon_log",
                         err_type="LOG_CRITICAL", message=line[:2000])

    # ── Persistence ──────────────────────────────────────────────

    def _append(self, record: dict):
        records = self._load()
        records.append(record)
        if len(records) > ROTATE_AT:
            archive = self.errors_file.with_suffix(
                f".{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json")
            archive.write_text(json.dumps(records[:-500], indent=2, default=str),
                               encoding="utf-8")
            records = records[-500:]
            log.info(f"Rotated errors archive → {archive.name}")
        tmp = self.errors_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.errors_file)

    def _load(self) -> list:
        if self.errors_file.exists():
            try:
                return json.loads(self.errors_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                log.error("Corrupt errors.json — starting fresh")
        return []

    def get_recent(self, n: int = 10, min_severity: str = "ERROR") -> list:
        sev_order = {"INFO": 0, "WARNING": 1, "ERROR": 2, "CRITICAL": 3}
        floor = sev_order.get(min_severity.upper(), 2)
        records = [r for r in self._load()
                   if sev_order.get(r["severity"], 0) >= floor]
        return records[-n:]

    # ── Wake logic ───────────────────────────────────────────────

    def _is_duplicate(self, message: str) -> bool:
        now = time.time()
        self._recent_messages = {
            m: t for m, t in self._recent_messages.items()
            if now - t < DEDUP_WINDOW_S
        }
        if message in self._recent_messages:
            return True
        self._recent_messages[message] = now
        return False

    def _maybe_wake(self, record: dict):
        sev = record["severity"]
        if sev not in ("CRITICAL", "ERROR"):
            return  # WARNING/INFO logged only
        now = time.time()
        if sev != "CRITICAL" and now - self._last_wake_time < WAKE_COOLDOWN_WARNING_S:
            log.info(f"Cooldown active — error logged only: {record['type']}")
            return
        self._last_wake_time = now
        self.report_to_session(record)

    def report_to_session(self, record: dict):
        """Wake the AI session with full error context.

        Multi-line args break through .cmd wrappers — persist the full prompt
        to disk and send only a single-line pointer into the session.
        """
        prompt = self._build_error_prompt(record)
        prompt_file = LIVE_DATA_DIR / "error_prompt.txt"
        try:
            prompt_file.write_text(prompt, encoding="utf-8")
        except OSError as e:
            log.error(f"Cannot write error prompt file: {e}")
        session_id = self._get_session_id()
        short = (f"[ALPHA DAEMON ERROR REPORT] {record['severity']}: "
                 f"{record['source']}/{record['type']} — {record['message'][:120]} | "
                 f"Full context: {prompt_file} and {self.errors_file}. "
                 f"Diagnose, fix if code bug, decide pause, write assessment to "
                 f"data/live/error_response.json.")
        try:
            subprocess.Popen(
                [OPENCODE, "run", short, "-s", session_id],
                cwd=str(ALPHA_DIR),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
            log.warning(f"Error reported to session {session_id}: {record['type']}")
        except Exception as e:
            log.error(f"Failed to report error to session: {e}")

    def _build_error_prompt(self, record: dict) -> str:
        recent = self.get_recent(10)
        recent_lines = "\n".join(
            f"- [{r['severity']}] {r['source']}/{r['type']}: {r['message'][:150]}"
            for r in recent
        ) or "- none"
        ctx = json.dumps(record.get("context", {}), indent=2, default=str)
        return f"""[ALPHA DAEMON ERROR REPORT] — automated error escalation, not a user message.

## ERROR (severity: {record['severity']})
Source: {record['source']}
Type: {record['type']}
Time: {record['timestamp']}
Message: {record['message']}

Context: {ctx}

{('TRACEBACK:' + chr(10) + record['trace']) if record['trace'] else ''}

## RECENT ERRORS (last 10)
{recent_lines}

## YOUR TASK
1. Diagnose the root cause — read the traceback and relevant code
2. Fix the code if this is a bug (MT5 symbol names, sizing math, API changes)
3. Decide: should trading PAUSE? If MT5/auth/money-related → yes, write pause flag
4. Write your assessment to C:/Trading/Alpha/data/live/error_response.json:
   {{"diagnosis": "...", "action_taken": "...", "pause_trading": false, "needs_human": false}}
5. Reply here with a one-line summary of what happened and what you did.

If this error repeats after your fix, escalate: set needs_human=true."""

    @staticmethod
    def _get_session_id() -> str:
        try:
            return SESSION_ID_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            return DEFAULT_SESSION_ID


# Module-level singleton — import anywhere without plumbing
error_monitor = ErrorMonitor()


if __name__ == "__main__":
    # Standalone mode: install hooks, tail all Alpha logs, run forever
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    error_monitor.install_global_handlers()
    logs_dir = ALPHA_DIR / "logs"
    stop = threading.Event()
    for lf in logs_dir.glob("*.log"):
        error_monitor.tail_log(lf, stop)
    log.info("ErrorMonitor standalone running — Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop.set()
