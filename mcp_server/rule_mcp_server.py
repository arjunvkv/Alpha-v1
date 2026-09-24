"""
======================================================================
         ALPHA V1 - GRAPHITI-BACKED CONSTITUTIONAL RULE ENGINE MCP
======================================================================
Server Name: rules
Purpose: FastMCP server providing OpenCode with direct access to the
         Graphiti-backed Constitutional 2-Tier Rule Engine.
         Enables continuous evolutionary calibration, evidence-backed
         rule promotions/demotions, parameter tuning, and execution gating.

Backed directly by Graphiti Temporal Knowledge Graph (graphiti_pattern_memory.db).
Sub-5ms local execution, zero external API costs.
======================================================================
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure project root is on sys.path
ALPHA_ROOT = Path(__file__).resolve().parent.parent
if str(ALPHA_ROOT) not in sys.path:
    sys.path.insert(0, str(ALPHA_ROOT))

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s [%(levelname)s] rules-mcp: %(message)s")
LOG = logging.getLogger("alpha.rules.mcp")

from mcp.server.fastmcp import FastMCP
from tradingagents.rule_engine import RuleEngine

mcp = FastMCP("rules")
_engine = RuleEngine()


@mcp.tool()
def get_active_playbook(tier: str = "ALL", category: str = "ALL") -> str:
    """
    Get the high-density executive rule playbook card (<150 tokens) for OpenCode.
    Call this on every dossier turn to review active Champion setups (85-100 pts),
    active rules (60-84 pts), probation setups, and active deterministic vetoes.
    
    Args:
        tier: 'ALL', 'TIER_1_CONSTITUTIONAL', or 'TIER_2_ADAPTIVE'
        category: 'ALL', 'WINNING_PATTERN', 'DETERMINISTIC_VETO', 'RISK_SAFETY', 'TACTICAL'
    """
    try:
        return _engine.get_active_playbook(tier=tier, category=category)
    except Exception as e:
        LOG.error(f"Error in get_active_playbook: {e}")
        return f"Rule matrix playbook error: {e}"


@mcp.tool()
def query_rule(rule_id: str) -> str:
    """
    Fetch complete specifications, logic descriptions, and tunable parameter
    thresholds for a specific rule by ID (e.g. 'RULE_PATTERN_A_TURTLE_SOUP', 'VETO_4_SYMMETRICAL_ZONE').
    
    Args:
        rule_id: The unique canonical rule ID
    """
    try:
        res = _engine.query_rule(rule_id=rule_id)
        return json.dumps(res, indent=2)
    except Exception as e:
        LOG.error(f"Error in query_rule: {e}")
        return json.dumps({"status": "ERROR", "error": str(e)}, indent=2)


@mcp.tool()
def promote_rule(rule_id: str, delta_points: int = 5, reason: str = "", evidence_ticket_or_walk: str = "") -> str:
    """
    Promote an adaptive Tier 2 rule by increasing its confidence score (+5 to +15 pts, max 100).
    MANDATORY: You must cite empirical evidence (MT5 winning Ticket # or Graphiti Walk ID).
    Tier 1 Constitutional Laws are IMMUTABLE and cannot be promoted or demoted.
    
    Args:
        rule_id: The rule to promote (e.g. 'RULE_PATTERN_A_TURTLE_SOUP')
        delta_points: Point increase (default: 5, max 15)
        reason: Justification explaining the market edge confirmation
        evidence_ticket_or_walk: MT5 Ticket # or Graphiti Walk ID proving the win
    """
    try:
        res = _engine.promote_rule(
            rule_id=rule_id,
            delta_points=delta_points,
            reason=reason,
            evidence_ticket_or_walk=evidence_ticket_or_walk
        )
        return json.dumps(res, indent=2)
    except Exception as e:
        LOG.error(f"Error in promote_rule: {e}")
        return json.dumps({"status": "ERROR", "error": str(e)}, indent=2)


@mcp.tool()
def demote_rule(rule_id: str, delta_points: int = 10, reason: str = "", evidence_ticket_or_walk: str = "") -> str:
    """
    Demote an adaptive Tier 2 rule by decreasing its confidence score (-10 to -25 pts, min 0).
    If a rule drops below 40 pts, it enters PROBATION (0.25L half-size + confirmation required).
    If below 20 pts, it is RETIRED (execution disabled).
    MANDATORY: You must cite empirical evidence (MT5 loss Ticket # or Graphiti trap Walk ID).
    Tier 1 Constitutional Laws are IMMUTABLE and cannot be demoted.
    
    Args:
        rule_id: The rule to demote (e.g. 'RULE_PATTERN_C_KINETIC_EXPANSION')
        delta_points: Point decrease (default: 10, max 25)
        reason: Autopsy explaining the trap, breakdown, or degraded expectancy
        evidence_ticket_or_walk: MT5 Ticket # or Graphiti Walk ID proving the loss/trap
    """
    try:
        res = _engine.demote_rule(
            rule_id=rule_id,
            delta_points=delta_points,
            reason=reason,
            evidence_ticket_or_walk=evidence_ticket_or_walk
        )
        return json.dumps(res, indent=2)
    except Exception as e:
        LOG.error(f"Error in demote_rule: {e}")
        return json.dumps({"status": "ERROR", "error": str(e)}, indent=2)


@mcp.tool()
def amend_parameter(rule_id: str, parameter_key: str, new_value: Any, reason: str = "", evidence: str = "") -> str:
    """
    Amend a tunable parameter threshold inside an adaptive Tier 2 rule (e.g. tuning min_sl_pts,
    min_velocity_tpm, or short_discount_ceiling).
    Maintains a permanent audit log of all parameter calibrations.
    
    Args:
        rule_id: Target rule ID
        parameter_key: Name of parameter to update
        new_value: New value (number, string, or boolean)
        reason: Context rationale for calibration
        evidence: Evidence walk or trade ticket
    """
    try:
        res = _engine.amend_rule_parameter(
            rule_id=rule_id,
            parameter_key=parameter_key,
            new_value=new_value,
            reason=reason,
            evidence=evidence
        )
        return json.dumps(res, indent=2)
    except Exception as e:
        LOG.error(f"Error in amend_parameter: {e}")
        return json.dumps({"status": "ERROR", "error": str(e)}, indent=2)


@mcp.tool()
def propose_new_rule(rule_id: str, name: str, category: str, description: str, parameters_json: str = "{}", starting_points: int = 60, justification: str = "") -> str:
    """
    Propose and register a newly discovered micro-edge into Tier 2 of the Rule Matrix.
    Starting points are capped between 40 and 75 (begins as ACTIVE or PROBATION).
    
    Args:
        rule_id: Unique canonical ID (e.g. 'RULE_ASIAN_SESSION_EXPANSION')
        name: Human-readable rule title
        category: 'WINNING_PATTERN', 'DETERMINISTIC_VETO', or 'TACTICAL'
        description: Exact execution logic and conditions
        parameters_json: JSON string of tunable parameters
        starting_points: Initial points (default: 60)
        justification: Empirical observations supporting the new rule
    """
    try:
        params = json.loads(parameters_json) if isinstance(parameters_json, str) else dict(parameters_json or {})
        res = _engine.propose_new_rule(
            rule_id=rule_id,
            name=name,
            category=category,
            description=description,
            parameters=params,
            starting_points=starting_points,
            justification=justification
        )
        return json.dumps(res, indent=2)
    except Exception as e:
        LOG.error(f"Error in propose_new_rule: {e}")
        return json.dumps({"status": "ERROR", "error": str(e)}, indent=2)


# ======================================================================
# BACKWARD COMPATIBILITY ALIASES
# ======================================================================
@mcp.tool()
def rule_mcp_get_active_playbook(tier: str = "ALL", category: str = "ALL") -> str:
    """Backward-compatible alias for get_active_playbook."""
    return get_active_playbook(tier=tier, category=category)


@mcp.tool()
def rule_mcp_query_rule(rule_id: str) -> str:
    """Backward-compatible alias for query_rule."""
    return query_rule(rule_id=rule_id)


@mcp.tool()
def rule_mcp_promote_rule(rule_id: str, delta_points: int = 5, reason: str = "", evidence_ticket_or_walk: str = "") -> str:
    """Backward-compatible alias for promote_rule."""
    return promote_rule(rule_id=rule_id, delta_points=delta_points, reason=reason, evidence_ticket_or_walk=evidence_ticket_or_walk)


@mcp.tool()
def rule_mcp_demote_rule(rule_id: str, delta_points: int = 10, reason: str = "", evidence_ticket_or_walk: str = "") -> str:
    """Backward-compatible alias for demote_rule."""
    return demote_rule(rule_id=rule_id, delta_points=delta_points, reason=reason, evidence_ticket_or_walk=evidence_ticket_or_walk)


@mcp.tool()
def rule_mcp_amend_rule_parameter(rule_id: str, parameter_key: str, new_value: Any, reason: str = "", evidence: str = "") -> str:
    """Backward-compatible alias for amend_parameter."""
    return amend_parameter(rule_id=rule_id, parameter_key=parameter_key, new_value=new_value, reason=reason, evidence=evidence)


@mcp.tool()
def rule_mcp_propose_new_rule(rule_id: str, name: str, category: str, description: str, parameters_json: str = "{}", starting_points: int = 60, justification: str = "") -> str:
    """Backward-compatible alias for propose_new_rule."""
    return propose_new_rule(rule_id=rule_id, name=name, category=category, description=description, parameters_json=parameters_json, starting_points=starting_points, justification=justification)


if __name__ == "__main__":
    LOG.info("Starting Graphiti-backed Constitutional Rule Engine FastMCP server on stdio...")
    mcp.run(transport="stdio")
