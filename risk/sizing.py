"""
Position Sizer — conviction × account × risk → lot size.

Formula:
    lots = (balance × risk_pct × conviction_mult × drawdown_mult) / (stop_distance × pip_value)
Correlation adjustment reduces size when stacked with correlated positions.
"""

import logging
from typing import Optional

from config import (
    CONVICTION_MULTIPLIERS, CORRELATION_GROUPS, CORRELATION_THRESHOLD,
    DRAWDOWN_WARNING_PCT, MAX_SINGLE_RISK_PCT,
)

log = logging.getLogger("alpha.sizing")


def get_conviction_multiplier(conviction: float) -> float:
    for (lo, hi), mult in CONVICTION_MULTIPLIERS.items():
        if lo <= conviction <= hi:
            return mult
    return 0.0  # below tradeable threshold → no size


def adjust_for_drawdown(monthly_pnl_pct: float, base_size: float) -> float:
    """Reduce size during drawdown: -5% → half size, beyond → quarter."""
    if monthly_pnl_pct <= -DRAWDOWN_WARNING_PCT:
        factor = 0.5 if monthly_pnl_pct > -DRAWDOWN_WARNING_PCT * 1.4 else 0.25
        log.info(f"Drawdown adjustment: {monthly_pnl_pct:.1f}% → size ×{factor}")
        return base_size * factor
    return base_size


def adjust_for_correlation(symbol: str, existing_positions: Optional[list], base_size: float) -> float:
    """Halve size per same-group position already open (max 2 reductions)."""
    existing_positions = existing_positions or []
    group = next((g for g, syms in CORRELATION_GROUPS.items() if symbol in syms), None)
    if not group:
        return base_size
    correlated = sum(1 for p in existing_positions if p.get("symbol") in CORRELATION_GROUPS[group])
    if correlated > 0:
        factor = 0.5 ** min(correlated, 2)
        log.info(f"Correlation adjustment: {correlated} {group} position(s) open → size ×{factor}")
        return base_size * factor
    return base_size


class PositionSizer:
    """Calculate final lot size with all adjustments."""

    def calculate_size(
        self,
        account_balance: float,
        risk_pct: float,
        conviction: float,
        stop_distance_pips: float,
        pip_value_per_lot: float,
        monthly_pnl_pct: float = 0.0,
        existing_positions: Optional[list] = None,
        symbol: str = "",
    ) -> dict:
        """
        Returns {lots, risk_pct_final, breakdown} or {lots: 0, reason} if blocked.
        Never exceeds MAX_SINGLE_RISK_PCT.
        """
        existing_positions = existing_positions or []
        breakdown = {}

        conv_mult = get_conviction_multiplier(conviction)
        if conv_mult <= 0:
            return {"lots": 0.0, "reason": f"Conviction {conviction} below tradeable threshold"}
        breakdown["conviction_multiplier"] = conv_mult

        risk_pct_final = min(risk_pct * conv_mult, MAX_SINGLE_RISK_PCT)
        breakdown["risk_pct"] = risk_pct_final

        risk_dollars = account_balance * risk_pct_final / 100.0
        if stop_distance_pips <= 0 or pip_value_per_lot <= 0:
            return {"lots": 0.0, "reason": "Invalid stop distance or pip value"}

        raw_lots = risk_dollars / (stop_distance_pips * pip_value_per_lot)
        breakdown["raw_lots"] = round(raw_lots, 3)

        sized = adjust_for_drawdown(monthly_pnl_pct, raw_lots)
        sized = adjust_for_correlation(symbol, existing_positions, sized)
        breakdown["final_lots"] = round(sized, 3)

        # Broker minimum 0.01 lots
        final = max(round(sized, 2), 0.01) if sized >= 0.005 else 0.0
        if final == 0.0:
            return {"lots": 0.0, "reason": "Size rounded to zero", "breakdown": breakdown}

        actual_risk = final * stop_distance_pips * pip_value_per_lot
        breakdown["actual_risk_pct"] = round(actual_risk / account_balance * 100, 2)

        return {"lots": final, "risk_pct_final": risk_pct_final, "breakdown": breakdown}
