from pathlib import Path

def test_live_daemon_wake_is_question_driven():
    text=Path("alpha_trading_desk.py").read_text(encoding="utf-8")
    assert "Do NOT request a full dossier. Start a fresh reasoning cycle" in text
    assert "asyncio.create_task(self._probe_execution_watcher_task())" not in text

def test_launcher_uses_consolidated_runtime():
    text=Path("start_trading_system.ps1").read_text(encoding="utf-8")
    assert "alpha_trading_desk.py" in text
    assert "run" in text

def test_opencode_is_declared_sole_reasoner():
    text=Path("opencode.json").read_text(encoding="utf-8")
    assert "SOLE MARKET/TRADING REASONER" in text
    assert "DO NOT perform an all-tool sweep or request a full dossier" in text
