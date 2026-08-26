"""Pytest configuration for Alpha daemon v2 test suite.

Inserts the Alpha root on sys.path so daemon.* and brain.* packages resolve.
Keeps collection limited to v2 tests via pytest.ini testpaths; legacy scripts
in tests/ execute MT5 code at import time and must never be collected here.
"""

import sys
from pathlib import Path

ALPHA_ROOT = Path(r"C:\Trading\Alpha")
if str(ALPHA_ROOT) not in sys.path:
    sys.path.insert(0, str(ALPHA_ROOT))
