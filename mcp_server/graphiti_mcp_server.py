"""
======================================================================
         ALPHA V1 - STANDALONE GRAPHITI MEMORY MCP SERVER
======================================================================
Server Name: graphiti-memory-mcp
Purpose: Standalone FastMCP server providing Graphiti temporal knowledge
         graph memory, associative pattern sequence recall, and continuous
         observational learning to OpenCode.

Completely decoupled from broker daemon (alpha-daemon-mcp).
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
from tradingagents.pattern_memory_engine import PatternMemoryEngine

mcp = FastMCP("graphiti-memory-mcp")
_engine = PatternMemoryEngine()


@mcp.tool()
def graphiti_search_facts(patterns: list, symbol: str = "XAUUSD", limit: int = 5) -> str:
    """
    Search Graphiti temporal pattern memory for past walks matching the active combination of patterns.
    Returns a dense, non-bloated executive fact card (<100 tokens) detailing top winning signatures,
    recorded stumbles, and the Resilient Swimmer contextual pitfall.
    """
    try:
        p_list = list(patterns) if isinstance(patterns, (list, tuple)) else [str(patterns)]
        return _engine.search_facts(patterns=p_list, symbol=symbol, limit=limit)
    except Exception as e:
        LOG.error(f"Error in graphiti_search_facts: {e}")
        return f"Graphiti memory search error: {e}"


@mcp.tool()
def graphiti_add_episode(patterns: list, outcome: str, lesson: str = "", symbol: str = "XAUUSD") -> str:
    """
    Record a pattern walk episode into Graphiti memory.
    Call this:
    1. When any MT5 trade closes (outcome='WIN' or 'TRAP').
    2. When standing flat and an avoided trap collapses (outcome='TRAP').
    3. When standing flat and an explosive clean move launches (outcome='WIN').
    Strengthens the synaptic weight of the walk and updates pattern entity nodes.
    """
    try:
        p_list = list(patterns) if isinstance(patterns, (list, tuple)) else [str(patterns)]
        res = _engine.add_episode(patterns=p_list, outcome=outcome, lesson=lesson, symbol=symbol)
        return json.dumps(res, indent=2)
    except Exception as e:
        LOG.error(f"Error in graphiti_add_episode: {e}")
        return json.dumps({"status": "ERROR", "error": str(e)}, indent=2)


@mcp.tool()
def graphiti_record_observation(patterns: list, observation: str = "", outcome: str = "STUDY", symbol: str = "XAUUSD") -> str:
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
        p_list = list(patterns) if isinstance(patterns, (list, tuple)) else [str(patterns)]
        res = _engine.add_episode(patterns=p_list, outcome=outcome, lesson=observation, symbol=symbol, source="PER_CYCLE_OBSERVATION")
        return json.dumps(res, indent=2)
    except Exception as e:
        LOG.error(f"Error in graphiti_record_observation: {e}")
        return json.dumps({"status": "ERROR", "error": str(e)}, indent=2)


@mcp.tool()
def record_pattern_observation(symbol: str = "XAUUSD", pattern_name: str = "", observation: str = "", outcome: str = "STUDY", ticket: str = None, r_value=None, patterns: list = None) -> str:
    """
    Record pattern observation into Graphiti Temporal Memory (Backward-compatible drop-in alias).
    Accepts either pattern_name (single tag) or patterns (list of tags).
    MANDATORY ON EVERY CYCLE: Call this on each cadence turn to ensure continuous institutional memory.
    """
    try:
        p_list = []
        if patterns:
            p_list = list(patterns) if isinstance(patterns, (list, tuple)) else [str(patterns)]
        elif pattern_name:
            p_list = [pattern_name]
        else:
            p_list = ["MARKET_OBSERVATION"]
        res = _engine.add_episode(patterns=p_list, outcome=outcome, lesson=observation, symbol=symbol or "XAUUSD", source="PER_CYCLE_OBSERVATION")
        return json.dumps(res, indent=2)
    except Exception as e:
        LOG.error(f"Error in record_pattern_observation: {e}")
        return json.dumps({"status": "ERROR", "error": str(e)}, indent=2)



@mcp.tool()
def graphiti_get_pattern_walks(symbol: str = "XAUUSD", limit: int = 6) -> str:
    """
    Retrieve the top dominant winning walks and documented trap fingerprints currently
    strengthened in Graphiti memory. Use during 4-minute brainstorm cycles or session transitions
    to recalibrate your mental model.
    """
    try:
        return _engine.get_pattern_walks(symbol=symbol, limit=limit)
    except Exception as e:
        LOG.error(f"Error in graphiti_get_pattern_walks: {e}")
        return f"Error retrieving pattern walks: {e}"


@mcp.tool()
def graphiti_prune_decayed(decay_rate: float = 0.90) -> str:
    """
    Apply natural forgetting / synaptic attenuation to stale, unreinforced one-off noise.
    Keeps memory clean and prevents ancient obsolete patterns from cluttering recall.
    """
    try:
        return _engine.prune_decayed(decay_rate=decay_rate)
    except Exception as e:
        LOG.error(f"Error in graphiti_prune_decayed: {e}")
        return f"Error applying decay: {e}"


if __name__ == "__main__":
    LOG.info("Starting standalone graphiti-memory-mcp server...")
    mcp.run()
