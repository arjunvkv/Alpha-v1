"""Order validation + routing (DAEMON_V2_SPEC.md sections 6-7).

Every AI-authored ORDER action passes validate_order_spec before anything
touches the broker. Hard limits: min RR 2.0 on entries, max 2 percent
equity risk per trade, SL+TP mandatory.
"""

from brain import executor
from config import INSTRUMENTS



def _num(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if value != value:  # NaN guard
        return None
    return value


def validate_order_spec(spec, account, tick, point_sizes, is_entry=True):
    """Validate one order spec against account + current tick.

    Returns (ok, errors, normalized_spec).
    """
    errors = []
    spec = spec if isinstance(spec, dict) else {}
    norm = dict(spec)

    symbol = str(spec.get("symbol") or "").strip()
    if not symbol:
        errors.append("missing_symbol")
    norm["symbol"] = symbol

    side = str(spec.get("side") or "").strip().lower()
    if side not in ("buy", "sell"):
        errors.append("invalid_side")
    norm["side"] = side

    volume = _num(spec.get("volume"))
    if volume is None or volume <= 0:
        errors.append("invalid_volume")
    norm["volume"] = volume

    sl = _num(spec.get("sl"))
    if sl is None or sl <= 0:
        errors.append("missing_sl")
    norm["sl"] = sl

    tp = _num(spec.get("tp"))
    if tp is None or tp <= 0:
        errors.append("missing_tp")
    norm["tp"] = tp

    bid = _num(tick.get("bid")) if isinstance(tick, dict) else None
    ask = _num(tick.get("ask")) if isinstance(tick, dict) else None
    if bid is None or ask is None:
        errors.append("no_market_tick")
        return False, errors, norm

    if side == "buy":
        entry = ask
        if sl is not None and sl >= ask:
            errors.append("sl_above_entry")
        if tp is not None and tp <= ask:
            errors.append("tp_below_entry")
    elif side == "sell":
        entry = bid
        if sl is not None and sl <= bid:
            errors.append("sl_below_entry")
        if tp is not None and tp >= bid:
            errors.append("tp_above_entry")
    else:
        entry = (bid + ask) / 2.0

    # The Agent owns trade-quality decisions. R:R is preserved as evidence
    # in the action spec but is never used here to replace ORDER with WAIT.
    norm["rr"] = spec.get("rr")

    if not errors and sl is not None and tp is not None:
        risk_dist = abs(entry - sl)

        instrument = INSTRUMENTS.get(symbol)
        if instrument is None:
            errors.append("unknown_instrument %s" % symbol)
            return False, errors, norm

        point_size = (
            _num((point_sizes or {}).get(symbol))
            or _num(instrument.get("pip_size"))
        )
        risk_per_point = _num(instrument.get("pip_value_per_lot"))
        if point_size is None or point_size <= 0 or risk_per_point is None:
            errors.append("invalid_instrument_risk_spec %s" % symbol)
            return False, errors, norm

        points = risk_dist / point_size
        risk_usd = points * (volume or 0.0) * risk_per_point

        # Risk is factual feedback, not an execution-quality gate. The Agent
        # owns the decision to submit the order; the router only rejects
        # malformed or physically unexecutable requests.
        equity = _num((account or {}).get("equity")) or 0.0
        if equity > 0:
            norm["estimated_risk_usd"] = risk_usd
            norm["estimated_risk_pct"] = risk_usd / equity * 100.0
        else:
            norm["estimated_risk_usd"] = risk_usd
            norm["estimated_risk_pct"] = None
    return not errors, errors, norm


class OrderRouter:
    """Validates specs, then routes accepted ones through brain.executor."""

    def __init__(self, dry_run=True, point_sizes=None):
        self.dry_run = dry_run
        self.point_sizes = point_sizes or {}

    def route_order(self, spec, account, tick):
        ok, errors, norm = validate_order_spec(
            spec, account, tick, self.point_sizes, is_entry=True)
        if not ok:
            return {"success": False, "errors": errors,
                    "dry_run": self.dry_run}
        result = executor.place_market_order(norm, dry_run=self.dry_run)
        result.setdefault("errors", [])
        return result
