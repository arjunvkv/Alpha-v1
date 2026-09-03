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

def test_mcp_discovery_excludes_competing_decision_abstractions():
    text=Path("mcp_server/alpha_mcp_server.py").read_text(encoding="utf-8")
    start=text.index("def list_desk_tools")
    end=text.index("def call_desk_tool", start)
    section=text[start:end]
    assert '"name":"get_full_book"' not in section
    assert '"name":"query_analyst_desk"' not in section
    assert '"name":"configure_probe_trigger_engine"' not in section
    assert '"name":"place_probe_grid"' not in section

def test_universal_dispatcher_has_no_probe_engine_or_full_book():
    text=Path("mcp_server/alpha_mcp_server.py").read_text(encoding="utf-8")
    start=text.index("def call_desk_tool")
    section=text[start:]
    assert '"get_full_book":' not in section
    assert '"query_analyst_desk":' not in section
    assert '"configure_probe_trigger_engine":' not in section
    assert '"place_probe_grid":' not in section
    assert 'args.get("volume", 0.05)' not in section
    assert 'args.get("volume", 0.01)' not in section
