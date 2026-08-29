"""
======================================================================
MARKET CLOSE SHUTDOWN SCHEDULER
======================================================================
Shuts down this PC at the WEEKLY market close for the retail CFD
instruments traded here (XAUUSD / XAGUSD / XPTUSD / XPDUSD / XCUUSD /
USOIL.cash).

Market close default: FRIDAY 22:00 (local system time, ~ = broker server
close for these metals/oil CFDs). This is persisted as a recurring
Windows Task Scheduler job so it re-arms every week (the market halts for
the weekend and reopens Sunday evening).

Design / safety:
  - Uses a graceful `shutdown /s /t <delay>` with a cancel window so an
    operator can abort with `shutdown /a` if needed.
  - A single, clearly-named scheduled task: "AlphaMarketCloseShutdown".
  - `--status`  -> show current schedule + computed next fire time.
  - `--remove`  -> remove the scheduled task (undo).
  - `--close 22:00 --day FRIDAY` -> customise close time/day.

Usage:
  python market_close_shutdown.py            # register the weekly task
  python market_close_shutdown.py --status   # inspect
  python market_close_shutdown.py --remove   # undo
======================================================================
"""

import argparse
import datetime
import platform
import subprocess
import sys
from typing import Optional

TASK_NAME = "AlphaMarketCloseShutdown"
SHUTDOWN_DELAY_SEC = 60  # grace window before actual OS shutdown (abort via `shutdown /a`)

# Defaults: weekly close on Friday at 22:00 local (broker server close
# for these CFD instruments sits very close to local wall-clock for most
# retail setups). Override via CLI.
DEFAULT_DAY = "FRIDAY"
DEFAULT_CLOSE_TIME = "22:00"

# Day name -> schtasks numeric DayOfWeek token.
SCHTASKS_DAY_TOKENS = {
    "SUNDAY": "SUN", "MONDAY": "MON", "TUESDAY": "TUE", "WEDNESDAY": "WED",
    "THURSDAY": "THU", "FRIDAY": "FRI", "SATURDAY": "SAT",
}


def _parse_day(day: str) -> str:
    return day.strip().upper()


def _iso_weekday(day: str) -> int:
    """Map day name to Python weekday() (Mon=0 ... Sun=6)."""
    names = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    return names.index(_parse_day(day))


def next_close_datetime(day: str, close_time: str, now: Optional[datetime.datetime] = None) -> datetime.datetime:
    """Return the next occurrence of the weekly close as a naive local datetime."""
    now = now or datetime.datetime.now()
    target_weekday = _iso_weekday(day)
    hh, mm = (int(x) for x in close_time.split(":"))
    target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    days_ahead = (target_weekday - now.weekday()) % 7
    if days_ahead == 0 and target <= now:
        days_ahead = 7  # this week's close already passed -> next week
    return target + datetime.timedelta(days=days_ahead)


def task_exists() -> bool:
    if platform.system() != "Windows":
        return False
    r = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME],
                       capture_output=True, text=True)
    return r.returncode == 0


def register_task(day: str, close_time: str) -> None:
    if platform.system() != "Windows":
        print("[!] This scheduler targets Windows (uses schtasks + shutdown).")
        sys.exit(1)

    token = SCHTASKS_DAY_TOKENS[_parse_day(day)]
    # schtasks /ST expects 24-hour HH:MM WITH the colon (e.g. 22:00).
    hhmm = close_time  # keep "22:00" form

    # Run a small python shim that invokes the graceful shutdown.
    # /TN name /TR command /SC WEEKLY /D token /ST time /F (force if exists)
    command = (f'schtasks /Create /TN "{TASK_NAME}" '
               f'/TR "shutdown.exe /s /t {SHUTDOWN_DELAY_SEC} /c AlphaMarketClose" '
               f'/SC WEEKLY /D {token} /ST {hhmm} /F')

    print(f"[>] Command: {command}")
    r = subprocess.run(command, shell=True, capture_output=True, text=True)
    if r.returncode == 0:
        nxt = next_close_datetime(day, close_time)
        print(f"[OK] Registered weekly task '{TASK_NAME}'.")
        print(f"     Shuts down EVERY {_parse_day(day)} at {close_time} local.")
        print(f"     Next scheduled fire: {nxt:%Y-%m-%d %H:%M} local.")
        print(f"     Cancel window: {SHUTDOWN_DELAY_SEC}s (run `shutdown /a` to abort).")
    else:
        print("[!] Failed to register task.")
        print(r.stderr or r.stdout)


def remove_task() -> None:
    if platform.system() != "Windows":
        print("[!] This scheduler targets Windows.")
        sys.exit(1)
    r = subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
                       capture_output=True, text=True)
    if r.returncode == 0:
        print(f"[OK] Removed task '{TASK_NAME}'.")
    else:
        print("[!] Could not remove task (may not exist).")
        print(r.stderr or r.stdout)


def show_status(day: str, close_time: str) -> None:
    nxt = next_close_datetime(day, close_time)
    print(f"Task name           : {TASK_NAME}")
    print(f"Existence           : {task_exists()}")
    print(f"Schedule            : every {_parse_day(day)} @ {close_time} local")
    print(f"Next scheduled fire : {nxt:%Y-%m-%d %H:%M} local ({(nxt - datetime.datetime.now()).days}d "
          f"{(nxt - datetime.datetime.now()).seconds // 3600}h "
          f"{((nxt - datetime.datetime.now()).seconds // 60) % 60}m from now)")
    print(f"Shutdown delay      : {SHUTDOWN_DELAY_SEC}s")
    print(f"Cancel command      : shutdown /a")


def main() -> None:
    ap = argparse.ArgumentParser(description="Weekly market-close PC shutdown scheduler (Windows).")
    ap.add_argument("--day", default=DEFAULT_DAY, help=f"Close day, default {DEFAULT_DAY}")
    ap.add_argument("--close", default=DEFAULT_CLOSE_TIME, help=f"Close time HH:MM local, default {DEFAULT_CLOSE_TIME}")
    ap.add_argument("--status", action="store_true", help="Show schedule + next fire time")
    ap.add_argument("--remove", action="store_true", help="Remove the scheduled task")
    args = ap.parse_args()

    day = _parse_day(args.day)
    if day not in SCHTASKS_DAY_TOKENS:
        print(f"[!] Invalid day '{day}'. Use one of: {', '.join(SCHTASKS_DAY_TOKENS)}")
        sys.exit(1)

    if args.remove:
        remove_task()
    elif args.status:
        show_status(day, args.close)
    else:
        register_task(day, args.close)


if __name__ == "__main__":
    main()
