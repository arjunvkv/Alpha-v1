"""
Portfolio Risk — total heat, correlation, drawdown circuit breakers.

The lungs. Answers one question: can we survive this trade?
"""

import logging
from datetime import datetime

from config import (
    CORRELATION_GROUPS, CORRELATION_THRESHOLD, MAX_CORRELATED_RISK_PCT,
    MAX_DRAWDOWN_DAILY_PCT, MAX_DRAWDOWN_MONTHLY_PCT,
    DRAWDOWN_WARNING_PCT, DRAWDOWN_CRITICAL_PCT, MAX_PORTFOLIO_HEAT_PCT,
)

log = logging.getLogger("alpha.portfolio")


class PortfolioRisk:
    """Live portfolio risk from MT5 positions."""

    def __init__(self, mt5):
        self.mt5 = mt5  # daemon.MT5Interface or execution bridge with same API

    # ── Heat ─────────────────────────────────────────────────────

    def get_total_heat(self) -> float:
        """Total open risk as % of account: sum(|entry - stop| × lots × pip_value)."""
        account = self.mt5.get_account()
        positions = self.mt5.get_positions()
        if not account or account["balance"] <= 0:
            return 0.0
        total_risk = 0.0
        for p in positions:
            if not p.get("sl"):
                continue  # naked position — flagged elsewhere
            stop_dist = abs(p["entry"] - p["sl"])
            inst = self._pip_info(p["symbol"])
            total_risk += stop_dist / inst["pip_size"] * inst["pip_value"] * p["lots"]
        return round(total_risk / account["balance"] * 100, 2)

    def get_position_heat(self, position: dict) -> float:
        account = self.mt5.get_account()
        if not account or not position.get("sl"):
            return 0.0
        inst = self._pip_info(position["symbol"])
        risk = (abs(position["entry"] - position["sl"])
                / inst["pip_size"] * inst["pip_value"] * position["lots"])
        return round(risk / account["balance"] * 100, 2)

    def check_new_position(self, symbol: str, lots: float,
                           stop_distance_pips: float) -> dict:
        """Would adding this position breach the heat limit?"""
        account = self.mt5.get_account()
        if not account:
            return {"allowed": False, "reason": "No MT5 account"}
        current_heat = self.get_total_heat()
        inst = self._pip_info(symbol)
        new_risk = (stop_distance_pips * inst["pip_value"] * lots
                    / account["balance"] * 100)
        projected = current_heat + new_risk
        allowed = projected <= MAX_PORTFOLIO_HEAT_PCT
        return {
            "allowed": allowed,
            "current_heat_pct": current_heat,
            "new_risk_pct": round(new_risk, 2),
            "projected_heat_pct": round(projected, 2),
            "reason": None if allowed else
                      f"Projected heat {projected:.1f}% > {MAX_PORTFOLIO_HEAT_PCT}%",
        }

    # ── Correlation ──────────────────────────────────────────────

    def get_group_exposure(self, symbol: str) -> float:
        """Total heat in the same correlation group as symbol."""
        group = next((g for g, syms in CORRELATION_GROUPS.items() if symbol in syms), None)
        if not group:
            return 0.0
        positions = self.mt5.get_positions()
        return sum(self.get_position_heat(p) for p in positions
                   if p["symbol"] in CORRELATION_GROUPS[group])

    def check_correlated_add(self, symbol: str, new_risk_pct: float) -> dict:
        """Correlated positions combined must stay ≤ MAX_CORRELATED_RISK_PCT."""
        exposure = self.get_group_exposure(symbol)
        projected = exposure + new_risk_pct
        allowed = projected <= MAX_CORRELATED_RISK_PCT
        return {
            "allowed": allowed,
            "group_exposure_pct": exposure,
            "projected_pct": round(projected, 2),
            "threshold_pct": MAX_CORRELATED_RISK_PCT,
        }

    # ── P&L ──────────────────────────────────────────────────────

    def get_monthly_pnl_pct(self) -> float:
        """Month-to-date realized+unrealized P&L as % of month-start balance."""
        account = self.mt5.get_account()
        if not account:
            return 0.0
        start = self._month_start_balance(account["balance"],
                                          sum(p.get("pnl", 0) for p in self.mt5.get_positions()))
        if start <= 0:
            return 0.0
        return round((account["equity"] - start) / start * 100, 2)

    def get_daily_pnl_pct(self) -> float:
        account = self.mt5.get_account()
        if not account:
            return 0.0
        return round((account["equity"] - account["balance"]) / account["balance"] * 100, 2)

    @staticmethod
    def _month_start_balance(current_balance: float, open_pnl: float) -> float:
        """Approximate month-start balance (realized basis). Refine via journal later."""
        return current_balance - open_pnl  # conservative approximation

    # ── Circuit breakers ─────────────────────────────────────────

    def check_circuit_breakers(self) -> dict:
        """
        -3% daily → stop trading today.
        -5% monthly → warning (sizer halves size).
        -7% monthly → critical (no new positions).
        -10% monthly → EMERGENCY close all.
        """
        alerts = []
        daily = self.get_daily_pnl_pct()
        monthly = self.get_monthly_pnl_pct()

        trading_allowed = True
        close_all = False

        if daily <= -MAX_DRAWDOWN_DAILY_PCT:
            trading_allowed = False
            alerts.append(f"DAILY LIMIT: {daily}% ≤ -{MAX_DRAWDOWN_DAILY_PCT}% — stop trading today")
        if monthly <= -DRAWDOWN_WARNING_PCT:
            alerts.append(f"WARNING: monthly {monthly}% ≤ -{DRAWDOWN_WARNING_PCT}% — halve sizes")
        if monthly <= -DRAWDOWN_CRITICAL_PCT:
            trading_allowed = False
            alerts.append(f"CRITICAL: monthly {monthly}% ≤ -{DRAWDOWN_CRITICAL_PCT}% — no new positions")
        if monthly <= -MAX_DRAWDOWN_MONTHLY_PCT:
            trading_allowed = False
            close_all = True
            alerts.append(f"EMERGENCY: monthly {monthly}% ≤ -{MAX_DRAWDOWN_MONTHLY_PCT}% — CLOSE ALL")

        if alerts:
            log.warning("Circuit breakers: " + " | ".join(alerts))
        return {"trading_allowed": trading_allowed, "close_all": close_all,
                "alerts": alerts, "daily_pnl_pct": daily, "monthly_pnl_pct": monthly}

    # ── Helpers ──────────────────────────────────────────────────

    @staticmethod
    def _pip_info(symbol: str) -> dict:
        from config import INSTRUMENTS
        cfg = INSTRUMENTS.get(symbol, {})
        return {"pip_size": cfg.get("pip_size", 0.01),
                "pip_value": cfg.get("pip_value_per_lot", 1.0)}
