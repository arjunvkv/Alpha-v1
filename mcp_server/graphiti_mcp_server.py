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


@mcp.tool()
def search_facts(
    patterns: Any = None,
    symbol: str = "XAUUSD",
    limit: int = 5,
    tags: Any = None,
    pattern: Any = None,
    patterns_list: Any = None,
    **kwargs: Any
) -> str:
    """
    Search Graphiti temporal pattern memory for past walks matching the active combination of patterns.
    Returns a dense, non-bloated executive fact card (<100 tokens) detailing top winning signatures,
    recorded stumbles, and the Resilient Swimmer contextual pitfall.
    """
    try:
        p = patterns if patterns is not None else (tags if tags is not None else (pattern if pattern is not None else patterns_list))
        p_list = parse_and_normalize_tags(p)
        sym = str(symbol or "XAUUSD")
        lim = int(limit or 5)
        return _engine.search_facts(patterns=p_list, symbol=sym, limit=lim)
    except Exception as e:
        LOG.error(f"Error in search_facts: {e}")
        return f"Graphiti memory search error: {e}"


@mcp.tool()
def record_observation(
    patterns: Any = None,
    observation: str = "",
    outcome: str = "STUDY",
    symbol: str = "XAUUSD",
    tags: Any = None,
    pattern: Any = None,
    patterns_list: Any = None,
    note: str = "",
    lesson: str = "",
    content: str = "",
    obs: str = "",
    message: str = "",
    **kwargs: Any
) -> str:
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
        p = patterns if patterns is not None else (tags if tags is not None else (pattern if pattern is not None else patterns_list))
        p_list = parse_and_normalize_tags(p)
        if not p_list:
            return json.dumps({"status": "ERROR", "message": "Cannot record observation without valid pattern tags. Provide 2-4 canonical tags from: [REGIME] + [LOCATION] + [PHYSICS]."}, indent=2)
        text_candidates = [observation, note, lesson, content, obs, message]
        chosen_text = next((str(c) for c in text_candidates if c), "")
        out = str(outcome or "STUDY")
        sym = str(symbol or "XAUUSD")
        res = _engine.record_observation(patterns=p_list, observation=chosen_text, outcome=out, symbol=sym)
        return json.dumps(res, indent=2)
    except Exception as e:
        LOG.error(f"Error in record_observation: {e}")
        return json.dumps({"status": "ERROR", "error": str(e)}, indent=2)


@mcp.tool()
def add_episode(
    patterns: Any = None,
    outcome: str = "STUDY",
    lesson: str = "",
    symbol: str = "XAUUSD",
    tags: Any = None,
    pattern: Any = None,
    patterns_list: Any = None,
    observation: str = "",
    note: str = "",
    content: str = "",
    **kwargs: Any
) -> str:
    """
    Record a pattern walk episode into Graphiti memory.
    Call this:
    1. When any MT5 trade closes (outcome='WIN' or 'TRAP').
    2. When standing flat and an avoided trap collapses (outcome='TRAP').
    3. When standing flat and an explosive clean move launches (outcome='WIN').
    Strengthens the synaptic weight of the walk and updates pattern entity nodes.
    """
    try:
        p = patterns if patterns is not None else (tags if tags is not None else (pattern if pattern is not None else patterns_list))
        p_list = parse_and_normalize_tags(p)
        if not p_list:
            p_list = ["4TF_BEARISH"]
        text_candidates = [lesson, observation, note, content]
        chosen_text = next((str(c) for c in text_candidates if c), "")
        out = str(outcome or "STUDY")
        sym = str(symbol or "XAUUSD")
        res = _engine.add_episode(patterns=p_list, outcome=out, lesson=chosen_text, symbol=sym)
        return json.dumps(res, indent=2)
    except Exception as e:
        LOG.error(f"Error in add_episode: {e}")
        return json.dumps({"status": "ERROR", "error": str(e)}, indent=2)


@mcp.tool()
def get_pattern_walks(symbol: str = "XAUUSD", limit: int = 6, **kwargs: Any) -> str:
    """
    Retrieve dominant proven winning walks and documented trap fingerprints for a symbol.
    Call this on brainstorm turns and periodically to calibrate mental models against global base rates.
    """
    try:
        sym = str(symbol or "XAUUSD")
        lim = int(limit or 6)
        return _engine.get_pattern_walks(symbol=sym, limit=lim)
    except Exception as e:
        LOG.error(f"Error in get_pattern_walks: {e}")
        return f"Graphiti walks retrieval error: {e}"


# ======================================================================
# BACKWARD COMPATIBILITY & LLM HALLUCINATION ALIASES
# ======================================================================
@mcp.tool()
def graphiti_search_facts(patterns: Any = None, symbol: str = "XAUUSD", limit: int = 5, tags: Any = None, pattern: Any = None, patterns_list: Any = None, **kwargs: Any) -> str:
    """Backward-compatible alias for search_facts."""
    return search_facts(patterns=patterns, symbol=symbol, limit=limit, tags=tags, pattern=pattern, patterns_list=patterns_list, **kwargs)


@mcp.tool()
def graphiti_record_observation(patterns: Any = None, observation: str = "", outcome: str = "STUDY", symbol: str = "XAUUSD", tags: Any = None, pattern: Any = None, patterns_list: Any = None, note: str = "", lesson: str = "", content: str = "", obs: str = "", message: str = "", **kwargs: Any) -> str:
    """Backward-compatible alias for record_observation."""
    return record_observation(patterns=patterns, observation=observation, outcome=outcome, symbol=symbol, tags=tags, pattern=pattern, patterns_list=patterns_list, note=note, lesson=lesson, content=content, obs=obs, message=message, **kwargs)


@mcp.tool()
def graphiti_add_episode(patterns: Any = None, outcome: str = "STUDY", lesson: str = "", symbol: str = "XAUUSD", tags: Any = None, pattern: Any = None, patterns_list: Any = None, observation: str = "", note: str = "", content: str = "", **kwargs: Any) -> str:
    """Backward-compatible alias for add_episode."""
    return add_episode(patterns=patterns, outcome=outcome, lesson=lesson, symbol=symbol, tags=tags, pattern=pattern, patterns_list=patterns_list, observation=observation, note=note, content=content, **kwargs)


@mcp.tool()
def graphiti_get_pattern_walks(symbol: str = "XAUUSD", limit: int = 6, **kwargs: Any) -> str:
    """Backward-compatible alias for get_pattern_walks."""
    return get_pattern_walks(symbol=symbol, limit=limit, **kwargs)


@mcp.tool()
def graphiti_memory_mcp_search_facts(patterns: Any = None, symbol: str = "XAUUSD", limit: int = 5, tags: Any = None, pattern: Any = None, patterns_list: Any = None, **kwargs: Any) -> str:
    """Fallback alias for search_facts when model calls graphiti_memory_mcp_search_facts."""
    return search_facts(patterns=patterns, symbol=symbol, limit=limit, tags=tags, pattern=pattern, patterns_list=patterns_list, **kwargs)


@mcp.tool()
def graphiti_memory_mcp_record_observation(patterns: Any = None, observation: str = "", outcome: str = "STUDY", symbol: str = "XAUUSD", tags: Any = None, pattern: Any = None, patterns_list: Any = None, note: str = "", lesson: str = "", content: str = "", obs: str = "", message: str = "", **kwargs: Any) -> str:
    """Fallback alias for record_observation when model calls graphiti_memory_mcp_record_observation."""
    return record_observation(patterns=patterns, observation=observation, outcome=outcome, symbol=symbol, tags=tags, pattern=pattern, patterns_list=patterns_list, note=note, lesson=lesson, content=content, obs=obs, message=message, **kwargs)


if __name__ == "__main__":
    LOG.info("Starting Graphiti Temporal Pattern Memory FastMCP server on stdio...")
    mcp.run(transport="stdio")
