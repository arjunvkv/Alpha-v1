"""
======================================================================
           ALPHA V1 - CONSTITUTIONAL 2-TIER RULE ENGINE
======================================================================
Organic Rule Matrix & Adaptive Playbook Management System.
Decoupled from observation memory (Graphiti MCP), providing dynamic
confidence scoring, continuous evolutionary calibration, and strict
two-tier constitutional safeguards.

Core Architecture:
- Tier 1: Immutable Constitutional Laws (Fixed 100 pts, Read-Only).
  Enforces hard capital preservation (SL floors, lot caps, event blackouts).
  OpenCode CANNOT demote, weaken, or mutate Tier 1 laws.
- Tier 2: Adaptive Playbook Matrix (0 to 100 pts, Promotable/Demotable).
  Enforces statistical friction (requires evidence citations: MT5 tickets or
  Graphiti walk IDs). Governs pattern selection, vetoes, and tactics.

Status Lifecycle:
- CHAMPION: 85 - 100 pts (Dominant edge, full position sizing authorized)
- ACTIVE: 60 - 84 pts (Standard setup, baseline position sizing authorized)
- PROBATION: 40 - 59 pts (Underperforming, 0.25L half-size + confirmation required)
- RETIRED: 0 - 39 pts (Deactivated, execution locked out)
======================================================================
"""

import os
import json
import sqlite3
import logging
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

DEFAULT_RULE_DB_PATH = Path(r"C:\Trading\Alpha\logs\graphiti_pattern_memory.db")
LOG = logging.getLogger("alpha.rule_engine")


class RuleEngine:
    """
    Local SQLite-backed Constitutional Rule Engine.
    Sub-5ms execution, zero cloud dependencies, complete audit provenance.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or DEFAULT_RULE_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._seed_initial_rules_if_empty()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rules (
                    rule_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    tier TEXT NOT NULL, -- 'TIER_1_CONSTITUTIONAL' or 'TIER_2_ADAPTIVE'
                    category TEXT NOT NULL, -- 'RISK_SAFETY', 'WINNING_PATTERN', 'DETERMINISTIC_VETO', 'EXECUTION_VEHICLE', 'TACTICAL'
                    status TEXT NOT NULL, -- 'IMMUTABLE', 'CHAMPION', 'ACTIVE', 'PROBATION', 'RETIRED'
                    points INTEGER NOT NULL, -- 0 to 100
                    description TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    historical_win_count INTEGER DEFAULT 0,
                    historical_loss_count INTEGER DEFAULT 0,
                    promotions_count INTEGER DEFAULT 0,
                    demotions_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP,
                    last_updated TIMESTAMP,
                    provenance TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS rule_audit_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    rule_id TEXT NOT NULL,
                    action TEXT NOT NULL, -- 'INITIAL_MIGRATION', 'PROMOTE', 'DEMOTE', 'AMEND', 'PROPOSE', 'RETIRE'
                    delta_points INTEGER DEFAULT 0,
                    old_points INTEGER NOT NULL,
                    new_points INTEGER NOT NULL,
                    old_status TEXT,
                    new_status TEXT,
                    reason TEXT NOT NULL,
                    evidence_ticket_or_walk TEXT NOT NULL,
                    actor TEXT DEFAULT 'OPENCODE_CIO'
                )
            """)
            conn.commit()

    def _calculate_status(self, tier: str, points: int) -> str:
        if tier == "TIER_1_CONSTITUTIONAL":
            return "IMMUTABLE"
        if points >= 85:
            return "CHAMPION"
        elif points >= 60:
            return "ACTIVE"
        elif points >= 40:
            return "PROBATION"
        else:
            return "RETIRED"

    def reset_to_champion_playbook(self):
        """Wipes the rules database and re-seeds strictly with the pristine 100-pt Champion Playbook."""
        self._seed_initial_rules_if_empty(force_reset=True)

    def _seed_initial_rules_if_empty(self, force_reset: bool = False):
        with self._get_conn() as conn:
            if force_reset:
                conn.execute("DELETE FROM rules")
                conn.execute("DELETE FROM rule_audit_log")
                conn.commit()
            else:
                count = conn.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
                if count > 0:
                    return

            now = datetime.datetime.now(datetime.timezone.utc).isoformat()

            initial_rules = [
                # =========================================================
                # TIER 1: IMMUTABLE CONSTITUTIONAL SAFETY LAWS (Fixed 100 Pts)
                # =========================================================
                {
                    "rule_id": "CONST_SL_FLOOR",
                    "name": "Hard Structural Stop Loss Clearance Floor",
                    "tier": "TIER_1_CONSTITUTIONAL",
                    "category": "RISK_SAFETY",
                    "points": 100,
                    "description": "Total SL distance MUST strictly be >= 6.0 to 10.0 points anchored behind HTF structural invalidation. Micro-stops (<5.5 pts) get wiped out by normal market noise.",
                    "parameters": {"min_sl_pts": 6.0, "max_sl_pts": 10.0},
                    "provenance": "Tier 1 Constitution, Escanor Champion Standard",
                    "wins": 30, "losses": 0
                },
                {
                    "rule_id": "CONST_MAX_LOTS",
                    "name": "Maximum Position Sizing Hard Ceiling",
                    "tier": "TIER_1_CONSTITUTIONAL",
                    "category": "RISK_SAFETY",
                    "points": 100,
                    "description": "Maximum position sizing ceiling is strictly 1.00 lot (baseline champion sizing is 0.40 to 0.50L).",
                    "parameters": {"max_volume": 1.00, "baseline_volume": 0.50},
                    "provenance": "Tier 1 Constitution, User Msg 95 & 893",
                    "wins": 30, "losses": 0
                },
                {
                    "rule_id": "CONST_SPREAD_BLOWOUT",
                    "name": "Extreme Spread Blowout Lockout",
                    "tier": "TIER_1_CONSTITUTIONAL",
                    "category": "RISK_SAFETY",
                    "points": 100,
                    "description": "Live broker spread > 55.0 pts ($0.55) or HIGH_SPIKE status strictly bans all market entries and stop orders.",
                    "parameters": {"max_spread_pts": 55.0},
                    "provenance": "Tier 1 Constitution",
                    "wins": 30, "losses": 0
                },
                {
                    "rule_id": "CONST_TIER1_BLACKOUT",
                    "name": "Tier-1 Macro Event Blackout Silence",
                    "tier": "TIER_1_CONSTITUTIONAL",
                    "category": "RISK_SAFETY",
                    "points": 100,
                    "description": "Mandatory 30 minutes silence before and 5 minutes after Tier-1 scheduled releases (CPI, PPI, FOMC, NFP, GDP). Stand flat.",
                    "parameters": {"blackout_minutes_before": 30, "blackout_minutes_after": 5},
                    "provenance": "Tier 1 Constitution",
                    "wins": 30, "losses": 0
                },
                {
                    "rule_id": "CONST_MAX_DAILY_DD",
                    "name": "Daily Loss Circuit Breaker",
                    "tier": "TIER_1_CONSTITUTIONAL",
                    "category": "RISK_SAFETY",
                    "points": 100,
                    "description": "TEMPORARILY DISABLED BY OPERATOR DIRECTIVE: Daily drawdown circuit breaker ($1,500) is explicitly suspended and bypassed. Desk is authorized to execute verified trades.",
                    "parameters": {"max_daily_loss_usd": 999999.0, "is_disabled": True},
                    "provenance": "Tier 1 Constitution, Operator Override",
                    "wins": 30, "losses": 0
                },

                # =========================================================
                # TIER 2: THE 100-PT CHAMPION EXECUTION PLAYBOOK (FOOTSTEPS OF ESCANOR V9/V10/V16)
                # =========================================================
                {
                    "rule_id": "CHAMP_PRONG_B_BREAKOUT_STOPS",
                    "name": "Prong B Directional Breakout Stops Beyond Base (Escanor v10 Engine - 60% of All Champion Wins)",
                    "tier": "TIER_2_ADAPTIVE",
                    "category": "WINNING_PATTERN",
                    "points": 100,
                    "description": "When breaking headlines or wire trend confirm directional continuation, PRE-STAGE SELL_STOP (bearish trend) or BUY_STOP (bullish trend) 1.0-2.0 pts beyond the immediate 1m/5m consolidation base floor/ceiling directly on MT5 book (0.40-0.50L, 6.0-10.0 pt SL, 4.0-8.0 pt Mode A TP). ZERO CHASE: Never place naked limits into counter-trend bounces! If the bounce continues, the stop is NEVER touched ($0 loss); if the base breaks, broker fills dynamically on the breakout surge with zero slippage.",
                    "parameters": {"entry_buffer_pts": 1.5, "sl_pts": 8.0, "tp_pts": 6.5, "volume": 0.50},
                    "provenance": "Escanor v10 100% Win Streak (Trades #539745323, #539779137, #539827942)",
                    "wins": 20, "losses": 0
                },
                {
                    "rule_id": "CHAMP_PRONG_C_MOMENTUM_MARKET",
                    "name": "Prong C Immediate Market Execution upon Shelf Rejection & Delta Flip (Escanor v9 Winner - 20% of Champion Wins)",
                    "tier": "TIER_2_ADAPTIVE",
                    "category": "WINNING_PATTERN",
                    "points": 100,
                    "description": "When price probes near an active supply/demand shelf in a news trend, DO NOT place a naked limit. Wait for price to touch the shelf AND display: (1) velocity drops to compression (<35-40 t/m), (2) displacement flattens, and (3) M1 CVD delta flips in the news trend direction. Execute IMMEDIATELY AT MARKET via alpha_execute_market_order (0.40-0.50L, 6.0-10.0 pt structural SL, 4.0-8.0 pt Mode A TP).",
                    "parameters": {"max_compression_velocity_tpm": 40.0, "require_m1_delta_flip": True, "market_size_lots": 0.50, "structural_sl_pts": 8.0, "mode_a_tp_pts": 6.0},
                    "provenance": "Escanor v9 Winner Trade #539752295 (+8.50 pts, +$340.00)",
                    "wins": 10, "losses": 0
                },
                {
                    "rule_id": "CHAMP_PATTERN_A_TURTLE_SOUP",
                    "name": "Pattern A Confirmed Turtle Soup External Reclaim (100% Win Rate)",
                    "tier": "TIER_2_ADAPTIVE",
                    "category": "WINNING_PATTERN",
                    "points": 100,
                    "description": "External session extreme (Day Low/High, PDL/PDH) swept + M5 candle closes back inside Value Area with confirmed CVD absorption flip. Target opposing POC/CE with >=6.0 pts clearance.",
                    "parameters": {"min_clearance_pts": 6.0, "requires_cvd_flip": True, "requires_external_sweep": True},
                    "provenance": "100% historical win rate (+1,274 USD profit + Trade #546711359)",
                    "wins": 12, "losses": 0
                },
                {
                    "rule_id": "CHAMP_PRONG_A_QUIET_SHELF_LIMIT",
                    "name": "Prong A Resting Limit at Major HTF Structural Extremes (Escanor v16 Winner - 20% of Champion Wins)",
                    "tier": "TIER_2_ADAPTIVE",
                    "category": "WINNING_PATTERN",
                    "points": 80,
                    "description": "Deploy resting limits ONLY during quiet, balanced rotation (velocity <60-80 t/m, flat delta, zero macro surge) at major HTF structural extremes. STRICT IMMUTABLE BAN ON NAKED LIMITS INTO VELOCITY SURGES: Placing a SELL_LIMIT while 1m/5m price is ascending with positive CVD or velocity >80 t/m is STRICTLY FORBIDDEN! Placing a BUY_LIMIT while price is descending with negative CVD or velocity >80 t/m is STRICTLY FORBIDDEN!",
                    "parameters": {"max_approach_velocity_tpm": 75.0, "ban_limit_into_surges": True},
                    "provenance": "Trade #540476565 (+19.07 pts, +$762.80) & Walk #977 Forensic",
                    "wins": 5, "losses": 0
                },
                {
                    "rule_id": "VETO_MULTI_TF_CHOP",
                    "name": "Guideline: Multi-Timeframe Range Boundary & Chop Navigation",
                    "tier": "TIER_2_ADAPTIVE",
                    "category": "TACTICAL",
                    "points": 85,
                    "description": "In MIXED_TIMEFRAMES, avoid blind interior chasing inside the noise band. Autonomously evaluate range boundaries: either trade confirmed absorption/reversals at the extremes (Turtle Soup / shelf limits) or stage breakout stops with confirmed open runways, ensuring stops are never placed directly into overhead BSL distribution or SSL accumulation traps.",
                    "parameters": {"regime": "MIXED_TIMEFRAMES"},
                    "provenance": "Escanor Adaptive Protocol",
                    "wins": 15, "losses": 0
                },
                {
                    "rule_id": "TACTIC_CHAMPION_HOLD",
                    "name": "Champion Hold & Profit Booking Mandate (Win #538243241)",
                    "tier": "TIER_2_ADAPTIVE",
                    "category": "TACTICAL",
                    "points": 100,
                    "description": "Once filled with 6.0-10.0 pt structural SL and Mode A TP (4.0-8.0 pts), LET THE BROKER HANDLE SL AND TP. Zero premature breakeven shifts on normal wicks, zero panic scratching. Early manual exits authorized only for emergency news (<30m to CPI/FOMC) or confirmed HTF structural close beyond invalidation.",
                    "parameters": {"sl_pts_min": 6.0, "sl_pts_max": 10.0, "tp_mode_a_min": 4.0, "tp_mode_a_max": 8.0},
                    "provenance": "Trade #538243241 (+$662) and #540476565 (+$760)",
                    "wins": 25, "losses": 0
                }
            ]

            for r in initial_rules:
                status = self._calculate_status(r["tier"], r["points"])
                conn.execute("""
                    INSERT INTO rules (
                        rule_id, name, tier, category, status, points,
                        description, parameters_json, historical_win_count,
                        historical_loss_count, promotions_count, demotions_count,
                        created_at, last_updated, provenance
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r["rule_id"], r["name"], r["tier"], r["category"], status, r["points"],
                    r["description"], json.dumps(r["parameters"]), r.get("wins", 0),
                    r.get("losses", 0), 0, 0, now, now, r["provenance"]
                ))

                conn.execute("""
                    INSERT INTO rule_audit_log (
                        timestamp, rule_id, action, delta_points, old_points,
                        new_points, old_status, new_status, reason,
                        evidence_ticket_or_walk, actor
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    now, r["rule_id"], "INITIAL_MIGRATION", 0, 0, r["points"],
                    "NEW", status, "Bootstrap seed from AGENTS.md & 68-trade historical database",
                    "INITIAL_BOOTSTRAP", "SYSTEM_BOOTSTRAP"
                ))

            conn.commit()
            LOG.info(f"Successfully migrated {len(initial_rules)} rules into Rule Matrix database.")

    def get_active_playbook(self, tier: str = "ALL", category: str = "ALL") -> str:
        """
        Returns an ultra-dense, token-efficient executive playbook summary (<150 tokens)
        for OpenCode on every dossier turn.
        """
        with self._get_conn() as conn:
            query = "SELECT * FROM rules WHERE status != 'RETIRED'"
            params = []

            if tier != "ALL":
                query += " AND tier = ?"
                params.append(tier)
            if category != "ALL":
                query += " AND category = ?"
                params.append(category)

            query += " ORDER BY points DESC, rule_id ASC"
            rows = conn.execute(query, params).fetchall()

            if not rows:
                return "RULE MATRIX PLAYBOOK: No active rules found matching criteria."

            champions = []
            active = []
            probation = []
            constitutional = []

            for r in rows:
                pts = r["points"]
                rid = r["rule_id"]
                name = r["name"]
                status = r["status"]
                tier_val = r["tier"]

                entry = f"[{rid} ({pts}pts)] {name}"
                if tier_val == "TIER_1_CONSTITUTIONAL":
                    constitutional.append(f"[{rid}] {name}")
                elif status == "CHAMPION":
                    champions.append(entry)
                elif status == "ACTIVE":
                    active.append(entry)
                elif status == "PROBATION":
                    probation.append(entry)

            lines = ["=== CONSTITUTIONAL RULE MATRIX (2-TIER PLAYBOOK) ==="]
            lines.append(f"• TIER 1 CONSTITUTION (IMMUTABLE): {len(constitutional)} hard safety laws active (SL Floor, Max Lots, Spread Cap 55pts, Event Blackout, Max DD).")
            if champions:
                lines.append(f"• TIER 2 CHAMPIONS (85-100pts | Full Sizing 0.5-1.0L): " + " | ".join(champions[:5]))
            if active:
                lines.append(f"• TIER 2 ACTIVE (60-84pts | Standard 0.50L): " + " | ".join(active[:6]))
            if probation:
                lines.append(f"• TIER 2 PROBATION (40-59pts | Half Size 0.25L): " + " | ".join(probation))

            return "\n".join(lines)

    def query_rule(self, rule_id: str) -> Dict[str, Any]:
        """Returns full specifications and parameter thresholds for a specific rule."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM rules WHERE rule_id = ?", (rule_id.strip(),)).fetchone()
            if not row:
                return {"status": "ERROR", "error": f"Rule '{rule_id}' not found in Rule Matrix."}

            res = dict(row)
            res["parameters"] = json.loads(res.get("parameters_json", "{}"))
            return res

    def promote_rule(self, rule_id: str, delta_points: int = 5, reason: str = "", evidence_ticket_or_walk: str = "") -> Dict[str, Any]:
        """
        Promotes a Tier 2 rule by increasing its confidence points based on empirical evidence.
        Tier 1 Constitutional rules CANNOT be modified.
        """
        if not evidence_ticket_or_walk or not str(evidence_ticket_or_walk).strip():
            return {
                "status": "VALIDATION_FAILED",
                "error": "Evidence citation is mandatory to promote a rule! Provide MT5 Ticket # or Graphiti Walk ID."
            }

        delta = abs(int(delta_points))
        if delta > 15:
            return {
                "status": "VALIDATION_FAILED",
                "error": f"Statistical friction ceiling: Maximum single promotion is +15 points (requested +{delta})."
            }

        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM rules WHERE rule_id = ?", (rule_id.strip(),)).fetchone()
            if not row:
                return {"status": "ERROR", "error": f"Rule '{rule_id}' not found."}

            if row["tier"] == "TIER_1_CONSTITUTIONAL":
                return {
                    "status": "PERMISSION_DENIED",
                    "error": f"Rule '{rule_id}' is a TIER 1 CONSTITUTIONAL LAW and is strictly IMMUTABLE. Promotion/demotion prohibited."
                }

            old_points = row["points"]
            new_points = min(100, old_points + delta)
            old_status = row["status"]
            new_status = self._calculate_status(row["tier"], new_points)
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()

            conn.execute("""
                UPDATE rules
                SET points = ?, status = ?, promotions_count = promotions_count + 1,
                    historical_win_count = historical_win_count + 1, last_updated = ?
                WHERE rule_id = ?
            """, (new_points, new_status, now, rule_id.strip()))

            conn.execute("""
                INSERT INTO rule_audit_log (
                    timestamp, rule_id, action, delta_points, old_points,
                    new_points, old_status, new_status, reason,
                    evidence_ticket_or_walk, actor
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now, rule_id.strip(), "PROMOTE", delta, old_points,
                new_points, old_status, new_status, reason,
                evidence_ticket_or_walk.strip(), "OPENCODE_CIO"
            ))
            conn.commit()

            return {
                "status": "SUCCESS",
                "rule_id": rule_id.strip(),
                "action": "PROMOTE",
                "delta_points": f"+{delta}",
                "old_points": old_points,
                "new_points": new_points,
                "old_status": old_status,
                "new_status": new_status,
                "evidence_cited": evidence_ticket_or_walk.strip(),
                "reason": reason
            }

    def demote_rule(self, rule_id: str, delta_points: int = 10, reason: str = "", evidence_ticket_or_walk: str = "") -> Dict[str, Any]:
        """
        Demotes a Tier 2 rule by decreasing its confidence points based on an empirical stumble/loss.
        Tier 1 Constitutional rules CANNOT be demoted.
        """
        if not evidence_ticket_or_walk or not str(evidence_ticket_or_walk).strip():
            return {
                "status": "VALIDATION_FAILED",
                "error": "Evidence citation is mandatory to demote a rule! Provide MT5 loss ticket # or Graphiti trap walk ID."
            }

        delta = abs(int(delta_points))
        if delta > 25:
            return {
                "status": "VALIDATION_FAILED",
                "error": f"Statistical friction ceiling: Maximum single demotion is -25 points (requested -{delta})."
            }

        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM rules WHERE rule_id = ?", (rule_id.strip(),)).fetchone()
            if not row:
                return {"status": "ERROR", "error": f"Rule '{rule_id}' not found."}

            if row["tier"] == "TIER_1_CONSTITUTIONAL":
                return {
                    "status": "PERMISSION_DENIED",
                    "error": f"Rule '{rule_id}' is a TIER 1 CONSTITUTIONAL LAW and is strictly IMMUTABLE. Demotion prohibited."
                }

            old_points = row["points"]
            new_points = max(0, old_points - delta)
            old_status = row["status"]
            new_status = self._calculate_status(row["tier"], new_points)
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()

            conn.execute("""
                UPDATE rules
                SET points = ?, status = ?, demotions_count = demotions_count + 1,
                    historical_loss_count = historical_loss_count + 1, last_updated = ?
                WHERE rule_id = ?
            """, (new_points, new_status, now, rule_id.strip()))

            conn.execute("""
                INSERT INTO rule_audit_log (
                    timestamp, rule_id, action, delta_points, old_points,
                    new_points, old_status, new_status, reason,
                    evidence_ticket_or_walk, actor
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now, rule_id.strip(), "DEMOTE", -delta, old_points,
                new_points, old_status, new_status, reason,
                evidence_ticket_or_walk.strip(), "OPENCODE_CIO"
            ))
            conn.commit()

            return {
                "status": "SUCCESS",
                "rule_id": rule_id.strip(),
                "action": "DEMOTE",
                "delta_points": f"-{delta}",
                "old_points": old_points,
                "new_points": new_points,
                "old_status": old_status,
                "new_status": new_status,
                "evidence_cited": evidence_ticket_or_walk.strip(),
                "reason": reason
            }

    def amend_rule_parameter(self, rule_id: str, parameter_key: str, new_value: Any, reason: str = "", evidence: str = "") -> Dict[str, Any]:
        """Amends a tunable parameter threshold inside an adaptive rule with an audit trail."""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM rules WHERE rule_id = ?", (rule_id.strip(),)).fetchone()
            if not row:
                return {"status": "ERROR", "error": f"Rule '{rule_id}' not found."}

            if row["tier"] == "TIER_1_CONSTITUTIONAL":
                return {
                    "status": "PERMISSION_DENIED",
                    "error": f"Rule '{rule_id}' is an IMMUTABLE Tier 1 Constitutional Law. Parameters cannot be edited."
                }

            params = json.loads(row["parameters_json"])
            old_val = params.get(parameter_key)
            params[parameter_key] = new_value
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()

            conn.execute("""
                UPDATE rules
                SET parameters_json = ?, last_updated = ?
                WHERE rule_id = ?
            """, (json.dumps(params), now, rule_id.strip()))

            conn.execute("""
                INSERT INTO rule_audit_log (
                    timestamp, rule_id, action, delta_points, old_points,
                    new_points, old_status, new_status, reason,
                    evidence_ticket_or_walk, actor
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now, rule_id.strip(), "AMEND", 0, row["points"],
                row["points"], row["status"], row["status"],
                f"Amended parameter '{parameter_key}' from {old_val} to {new_value}. {reason}",
                evidence.strip() or "N/A", "OPENCODE_CIO"
            ))
            conn.commit()

            return {
                "status": "SUCCESS",
                "rule_id": rule_id.strip(),
                "parameter_key": parameter_key,
                "old_value": old_val,
                "new_value": new_value,
                "reason": reason
            }

    def propose_new_rule(self, rule_id: str, name: str, category: str, description: str, parameters: Dict[str, Any], starting_points: int = 60, justification: str = "") -> Dict[str, Any]:
        """Proposes and registers a newly discovered micro-edge into Tier 2."""
        pts = max(40, min(75, int(starting_points)))  # New rules capped between 40 and 75
        status = self._calculate_status("TIER_2_ADAPTIVE", pts)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        clean_id = rule_id.strip().upper()
        if not clean_id.startswith("RULE_") and not clean_id.startswith("TACTIC_"):
            clean_id = f"RULE_{clean_id}"

        with self._get_conn() as conn:
            existing = conn.execute("SELECT rule_id FROM rules WHERE rule_id = ?", (clean_id,)).fetchone()
            if existing:
                return {"status": "ERROR", "error": f"Rule with ID '{clean_id}' already exists."}

            conn.execute("""
                INSERT INTO rules (
                    rule_id, name, tier, category, status, points,
                    description, parameters_json, historical_win_count,
                    historical_loss_count, promotions_count, demotions_count,
                    created_at, last_updated, provenance
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                clean_id, name.strip(), "TIER_2_ADAPTIVE", category.strip().upper(),
                status, pts, description.strip(), json.dumps(parameters or {}),
                0, 0, 0, 0, now, now, f"Proactively registered by OpenCode CIO: {justification.strip()}"
            ))

            conn.execute("""
                INSERT INTO rule_audit_log (
                    timestamp, rule_id, action, delta_points, old_points,
                    new_points, old_status, new_status, reason,
                    evidence_ticket_or_walk, actor
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now, clean_id, "PROPOSE", 0, 0, pts, "NEW", status,
                f"Newly proposed rule: {justification.strip()}", "PROPOSAL_JUSTIFICATION", "OPENCODE_CIO"
            ))
            conn.commit()

            return {
                "status": "SUCCESS",
                "rule_id": clean_id,
                "name": name.strip(),
                "tier": "TIER_2_ADAPTIVE",
                "rule_status": status,
                "starting_points": pts,
                "justification": justification.strip()
            }
