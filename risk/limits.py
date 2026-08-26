"""
Hard Limits — the final gate before any order.

All 7 checks must pass. Any single failure blocks the trade.
These enforce VISION.md §Risk Management. Never override.
"""

import logging
from typing import Optional

from config import MAX_OPEN_POSITIONS, MAX_SINGLE_RISK_PCT
from risk.portfolio import PortfolioRisk

log = logging.getLogger("alpha.limits")


class RiskLimits:
    """Enforce every hard limit from VISION.md."""

    def __init__(self, portfolio: PortfolioRisk):
        self.portfolio = portfolio

    def check_all(self, proposed_trade: dict, calendar_events: Optional[list] = None) -> dict:
        """
        Run ALL checks on a proposed trade dict with keys:
        instrument, direction, lots, stop_distance_pips, risk_pct, conviction.
        Returns {passed, checks, violations}.
        """
        calendar_events = calendar_events or []
        checks = {}
        violations = []

        # 1. Single position risk ≤ 2%
        risk_pct = proposed_trade.get("risk_pct") or 0
        checks["single_position"] = risk_pct <= MAX_SINGLE_RISK_PCT
        if not checks["single_position"]:
            violations.append(f"Single risk {risk_pct}% > {MAX_SINGLE_RISK_PCT}%")

        # 2. Portfolio heat ≤ 6% after adding
        heat_check = self.portfolio.check_new_position(
            proposed_trade["instrument"],
            proposed_trade.get("lots", 0),
            proposed_trade.get("stop_distance_pips", 0),
        )
        checks["portfolio_heat"] = heat_check.get("allowed", False)
        if not checks["portfolio_heat"]:
            violations.append(heat_check.get("reason", "Heat limit"))

        # 3. Correlation adjustment already applied by sizer (verify lots exist)
        checks["correlation_sized"] = bool(proposed_trade.get("lots"))
        if not checks["correlation_sized"]:
            violations.append("Position size is zero (correlation/sizing blocked)")

        # 4. Drawdown circuit breakers
        cb = self.portfolio.check_circuit_breakers()
        checks["drawdown"] = cb["trading_allowed"]
        if not cb["trading_allowed"]:
            violations.extend(cb["alerts"])

        # 5. News blackout (redundant with decision.py but enforced here too)
        blackout = False
        for ev in calendar_events:
            mins = ev.get("minutes_until", 9999)
            if (ev.get("impact") or "").upper() == "HIGH" and -60 <= mins <= 60:
                blackout = True
                break
        checks["news_blackout"] = not blackout
        if blackout:
            violations.append("High-impact news within 60 minutes")

        # 6. Max open positions
        positions = self.portfolio.mt5.get_positions()
        checks["max_positions"] = len(positions) < MAX_OPEN_POSITIONS
        if not checks["max_positions"]:
            violations.append(f"{len(positions)} positions >= max {MAX_OPEN_POSITIONS}")

        # 7. Stop loss mandatory
        checks["stop_required"] = bool(proposed_trade.get("stop_distance_pips"))
        if not checks["stop_required"]:
            violations.append("No stop distance — refusing naked position")

        passed = all(checks.values())
        log.info(f"RiskLimits.check_all({proposed_trade.get('instrument')}): "
                 f"{'PASS' if passed else 'BLOCKED'} — {violations}")
        return {"passed": passed, "checks": checks, "violations": violations}
