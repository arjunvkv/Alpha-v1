"""
ALPHA TRADING DESK — SESSION SWITCHER & V66 ARCHETYPE PRESERVER
================================================================
Proxy to C:\\Trading\\switch_session.py
"""
import sys
from pathlib import Path

ROOT_SWITCHER = Path(r"C:\Trading\switch_session.py")
if ROOT_SWITCHER.exists():
    with open(ROOT_SWITCHER, "r", encoding="utf-8") as f:
        code = f.read()
    exec(compile(code, str(ROOT_SWITCHER), "exec"))
else:
    print(f"Error: Could not find {ROOT_SWITCHER}")
