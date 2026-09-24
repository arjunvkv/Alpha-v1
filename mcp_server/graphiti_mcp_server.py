"""
======================================================================
         ALPHA V1 - STANDALONE GRAPHITI MEMORY MCP SERVER
======================================================================
Server Name: graphiti
Purpose: Standalone FastMCP server providing Graphiti temporal knowledge
         graph memory, associative pattern sequence recall, and continuous
         observational learning to OpenCode.

Sub-5ms local SQLite execution, zero external API costs.
======================================================================
"""

import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

# Ensure project root is on sys.path
ALPHA_ROOT = Path(__file__).resolve().parent.parent
if str(ALPHA_ROOT) not in sys.path:
    sys.path.insert(0, str(ALPHA_ROOT))

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s [%(levelname)s] graphiti-mcp: %(message)s")
LOG = logging.getLogger("alpha.graphiti.mcp")

from mcp.server.fastmcp import FastMCP
from tradingagents.pattern_memory_engine import PatternMemoryEngine, parse_and_normalize_tags

mcp = FastMCP("graphiti")
_engine = PatternMemoryEngine()


def _extract_tags(patterns: Any = None, **kwargs) -> List[str]:
    """Extract and normalize pattern tags from direct arg or any known kwarg variant."""
    p = patterns
    if p is None:
        p = (
            kwargs.get("patterns") or
            kwargs.get("tags") or
            kwargs.get("tag") or
            kwargs.get("pattern") or
            kwargs.get("patterns_list") or
            kwargs.get("obs_patterns")
        )
    parsed = parse_and_normalize_tags(p)
    return parsed if parsed else ["4TF_BEARISH"]


def _extract_text(text: str = "", **kwargs) -> str:
    """Extract lesson or observation text from direct arg or any known kwarg variant."""
    if text:
        return str(text)
    for k in ("observation", "lesson", "note", "content", "obs", "msg", "message"):
        if k in kwargs and kwargs[k]:
            return str(kwargs[k])
    return ""


@mcp.tool()
def search_facts(patterns: Any = None, symbol: str = "XAUUSD", limit: int = 5, **kwargs) -> str:
    """
    Search Graphiti temporal pattern memory for past walks matching the active combination of patterns.
    Returns a dense, non-bloated executive fact card (<100 tokens) detailing top winning signatures,
    recorded stumbles, and the Resilient Swimmer contextual pitfall.
    """
    try:
        p_list = _extract_tags(patterns, **kwargs)
        sym = kwargs.get("symbol", symbol) or "XAUUSD"
        lim = int(kwargs.get("limit", limit) or 5)
        return _engine.search_facts(patterns=p_list, symbol=sym, limit=lim)
    except Exception as e:
        LOG.error(f"Error in search_facts: {e}")
        return f"Graphiti memory search error: {e}"


@mcp.tool()
def record_observation(patterns: Any = None, observation: str = "", outcome: str = "STUDY", symbol: str = "XAUUSD", **kwargs) -> str:
    """
    Record an active pattern combination and market observation into Graphiti Temporal Memory.
    MANDATORY ON EVERY CYCLE: Call this on routine cadence turns and brainstorm turns to record the
    active pattern walk, order flow state, and observational thesis.
    Outcomes:
    - 'STUDY': Routine per-cycle market observation, equilibrium, or standing-flat audit.
    - 'WIN': Clean directional expansion or executed winning trade.
    - 'TRAP': Avoided retail trap, fake breakout, or stop hunt collapse.
    Updates pattern occurrence counts, last_seen timestamps, and reinforces temporal walk weights.
    """
    try:
        p_list = _extract_tags(patterns, **kwargs)
        obs = _extract_text(observation, **kwargs)
        out = kwargs.get("outcome", outcome) or "STUDY"
        sym = kwargs.get("symbol", symbol) or "XAUUSD"
        res = _engine.record_observation(patterns=p_list, observation=obs, outcome=str(out), symbol=str(sym))
        return json.dumps(res, indent=2)
    except Exception as e:
        LOG.error(f"Error in record_observation: {e}")
        return json.dumps({"status": "ERROR", "error": str(e)}, indent=2)


@mcp.tool()
def add_episode(patterns: Any = None, outcome: str = "STUDY", lesson: str = "", symbol: str = "XAUUSD", **kwargs) -> str:
    """
    Record a pattern walk episode into Graphiti memory.
    Call this:
    1. When any MT5 trade closes (outcome='WIN' or 'TRAP').
    2. When standing flat and an avoided trap collapses (outcome='TRAP').
    3. When standing flat and an explosive clean move launches (outcome='WIN').
    Strengthens the synaptic weight of the walk and updates pattern entity nodes.
    """
    try:
        p_list = _extract_tags(patterns, **kwargs)
        les = _extract_text(lesson, **kwargs)
        out = kwargs.get("outcome", outcome) or "STUDY"
        sym = kwargs.get("symbol", symbol) or "XAUUSD"
        res = _engine.add_episode(patterns=p_list, outcome=str(out), lesson=les, symbol=str(sym))
        return json.dumps(res, indent=2)
    except Exception as e:
        LOG.error(f"Error in add_episode: {e}")
        return json.dumps({"status": "ERROR", "error": str(e)}, indent=2)


@mcp.tool()
def get_pattern_walks(symbol: str = "XAUUSD", limit: int = 6, **kwargs) -> str:
    """
    Retrieve dominant proven winning walks and documented trap fingerprints for a symbol.
    Call this on brainstorm turns and periodically to calibrate mental models against global base rates.
    """
    try:
        sym = kwargs.get("symbol", symbol) or "XAUUSD"
        lim = int(kwargs.get("limit", limit) or 6)
        return _engine.get_pattern_walks(symbol=sym, limit=lim)
    except Exception as e:
        LOG.error(f"Error in get_pattern_walks: {e}")
        return f"Graphiti walks retrieval error: {e}"


# ======================================================================
# BACKWARD COMPATIBILITY & LLM HALLUCINATION ALIASES
# ======================================================================
@mcp.tool()
def graphiti_search_facts(patterns: Any = None, symbol: str = "XAUUSD", limit: int = 5, **kwargs) -> str:
    """Backward-compatible alias for search_facts."""
    return search_facts(patterns=patterns, symbol=symbol, limit=limit, **kwargs)


@mcp.tool()
def graphiti_record_observation(patterns: Any = None, observation: str = "", outcome: str = "STUDY", symbol: str = "XAUUSD", **kwargs) -> str:
    """Backward-compatible alias for record_observation."""
    return record_observation(patterns=patterns, observation=observation, outcome=outcome, symbol=symbol, **kwargs)


@mcp.tool()
def graphiti_add_episode(patterns: Any = None, outcome: str = "STUDY", lesson: str = "", symbol: str = "XAUUSD", **kwargs) -> str:
    """Backward-compatible alias for add_episode."""
    return add_episode(patterns=patterns, outcome=outcome, lesson=lesson, symbol=symbol, **kwargs)


@mcp.tool()
def graphiti_get_pattern_walks(symbol: str = "XAUUSD", limit: int = 6, **kwargs) -> str:
    """Backward-compatible alias for get_pattern_walks."""
    return get_pattern_walks(symbol=symbol, limit=limit, **kwargs)


@mcp.tool()
def graphiti_memory_mcp_search_facts(patterns: Any = None, symbol: str = "XAUUSD", limit: int = 5, **kwargs) -> str:
    """Fallback alias for search_facts when model calls graphiti_memory_mcp_search_facts."""
    return search_facts(patterns=patterns, symbol=symbol, limit=limit, **kwargs)


@mcp.tool()
def graphiti_memory_mcp_record_observation(patterns: Any = None, observation: str = "", outcome: str = "STUDY", symbol: str = "XAUUSD", **kwargs) -> str:
    """Fallback alias for record_observation when model calls graphiti_memory_mcp_record_observation."""
    return record_observation(patterns=patterns, observation=observation, outcome=outcome, symbol=symbol, **kwargs)


if __name__ == "__main__":
    LOG.info("Starting Graphiti Temporal Pattern Memory FastMCP server on stdio...")
    mcp.run(transport="stdio")
