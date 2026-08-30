"""Ledger Edge & Condition Decomposition Engine for Alpha Trading Desk.

Canonical single source of truth for historical closed positions from MT5.
Groups raw MT5 deals by position_id into completed trade lifecycles.

CANONICAL_HEADLINE_SOURCE: CLOSED_COMPLETED_CYCLES
- XAUUSD: 121 completed closed cycles (Net Realized PnL: -$955.69 USD | Net Realized R: -63.56R)
- ALL Portfolio: 134 completed positions (Net Realized PnL: -$1,371.43 USD | Net Realized R: -91.28R)

Decomposes performance across full multi-dimensional base rate matrices:
1. Session Hour (Asian 00-07 UTC, London 07-13 UTC, NY 13-21 UTC, Post-Market 21-24 UTC)
2. Direction (BUY vs SELL)
3. Measured Trend Alignment (Pro-Trend vs Counter-Trend from forensic 4TF context)
4. FVG Fill% Bucket (<30% Fresh, 30-60% Equilibrium/CE, >=60% Exhausted/Chased)
5. Spread Bucket (<40 pts Tight/Normal, 40-80 pts Elevated, >80 pts High Spike)
6. RSI Regime Bucket (<30 Oversold, 30-70 Neutral, >70 Overbought)
7. Cross-Conditional Matrices (session_x_dir, alignment_x_dir, fvg_fill_x_dir, alignment_x_fvg_fill)
"""

import os
import json
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import MetaTrader5 as mt5

LOG = logging.getLogger("alpha.tradingagents.ledger")
ALPHA_ROOT = Path(r"C:\Trading\Alpha")
JOURNAL_FILE = ALPHA_ROOT / "logs" / "trade_journal_memory.json"
FTMO_PATH = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
CANONICAL_BASELINE_1R_USD = 15.0
CANONICAL_HEADLINE_SOURCE = "CLOSED_COMPLETED_CYCLES"

def compute_canonical_r(pnl: float, sl: Optional[float] = None, open_price: Optional[float] = None, volume: Optional[float] = None, point_value: float = 1.0) -> Dict[str, Any]:
    """Computes single canonical R value with provenance."""
    pnl_val = float(pnl or 0.0)
    if sl and open_price and volume and float(sl) > 0 and float(open_price) > 0:
        sl_dist = abs(float(open_price) - float(sl))
        initial_risk = sl_dist * float(volume) * point_value
        if initial_risk > 1.0:
            r_val = round(pnl_val / initial_risk, 2)
            return {"r_multiple": r_val, "initial_risk_usd": round(initial_risk, 2), "provenance": "INITIAL_SL_EXACT"}
    
    r_val = round(pnl_val / CANONICAL_BASELINE_1R_USD, 2)
    return {"r_multiple": r_val, "initial_risk_usd": CANONICAL_BASELINE_1R_USD, "provenance": "BASELINE_15_USD"}


class LedgerDecompositionEngine:
    """Extracts ground-truth deal history and calculates base-rate expectancy matrices."""

    def __init__(self, ftmo_path: Optional[str] = None):
        self.ftmo_path = ftmo_path or FTMO_PATH

    def _ensure_mt5(self) -> bool:
        try:
            if mt5.terminal_info() is not None:
                return True
            if os.path.exists(self.ftmo_path):
                return mt5.initialize(path=self.ftmo_path)
            return mt5.initialize()
        except Exception as err:
            LOG.error(f"MT5 init failed in LedgerDecompositionEngine: {err}")
            return False

    def _load_journal_context_map(self) -> Dict[int, Dict[str, Any]]:
        """Loads stored trade forensic context indexed by ticket."""
        if not JOURNAL_FILE.exists():
            return {}
        try:
            with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {t.get("ticket"): t for t in data.get("trades", []) if t.get("ticket")}
        except Exception as err:
            LOG.error(f"Error loading journal context map: {err}")
            return {}

    def get_canonical_positions(self, symbol: str = "XAUUSD", days_back: int = 90) -> List[Dict[str, Any]]:
        """Extracts deduplicated closed trade positions grouped by position_id."""
        sym = symbol.strip().upper()
        self._ensure_mt5()
        journal_map = self._load_journal_context_map()
        
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        from_dt = now_dt - datetime.timedelta(days=days_back)
        
        deals = mt5.history_deals_get(from_dt, now_dt)
        if not deals:
            return []

        # Group deals by position_id
        positions_map = {}
        for d in deals:
            p_sym = str(d.symbol).upper()
            if sym not in ("ALL", "PORTFOLIO", "*", "") and p_sym != sym:
                continue
            pos_id = d.position_id
            if pos_id == 0:
                continue
            if pos_id not in positions_map:
                positions_map[pos_id] = []
            positions_map[pos_id].append(d)

        canonical_trades = []
        for pos_id, p_deals in positions_map.items():
            entry_deal = next((d for d in p_deals if d.entry == mt5.DEAL_ENTRY_IN), None)
            exit_deal = next((d for d in p_deals if d.entry == mt5.DEAL_ENTRY_OUT), None)

            if not entry_deal or not exit_deal:
                continue

            trade_sym = str(entry_deal.symbol).upper()
            open_price = float(entry_deal.price)
            close_price = float(exit_deal.price)
            volume = float(entry_deal.volume)
            side = "BUY" if entry_deal.type == mt5.DEAL_TYPE_BUY else "SELL"
            tot_pnl = sum(float(d.profit) + float(d.commission) + float(d.swap) for d in p_deals if d.entry == mt5.DEAL_ENTRY_OUT)
            tot_pnl = round(tot_pnl, 2)

            entry_dt = datetime.datetime.fromtimestamp(entry_deal.time, datetime.timezone.utc)
            exit_dt = datetime.datetime.fromtimestamp(exit_deal.time, datetime.timezone.utc)
            duration_s = exit_deal.time - entry_deal.time
            hour = entry_dt.hour

            # Session classification
            if 0 <= hour < 7:
                session_name = "Asian (00-07 UTC)"
            elif 7 <= hour < 13:
                session_name = "London (07-13 UTC)"
            elif 13 <= hour < 21:
                session_name = "New York (13-21 UTC)"
            else:
                session_name = "Post-Market (21-24 UTC)"

            # Measured forensic context lookup (Item 2)
            j_trade = journal_map.get(pos_id, {})
            f_ctx = j_trade.get("forensic_context", {})
            raw_4tf = f_ctx.get("4tf_alignment")
            
            if raw_4tf and isinstance(raw_4tf, str):
                alignment_provenance = "MEASURED_FORENSIC_4TF"
                if side == "BUY":
                    measured_alignment = "Pro-Trend" if "BULL" in raw_4tf.upper() else ("Counter-Trend" if "BEAR" in raw_4tf.upper() else "Neutral")
                else:
                    measured_alignment = "Pro-Trend" if "BEAR" in raw_4tf.upper() else ("Counter-Trend" if "BULL" in raw_4tf.upper() else "Neutral")
            else:
                measured_alignment = "UNMEASURED"
                alignment_provenance = "UNMEASURED"

            # FVG fill% bucket lookup (Item 1a)
            n_fvg = f_ctx.get("nearest_fvg", {})
            fvg_fill_val = n_fvg.get("fill_pct") if isinstance(n_fvg, dict) else None
            if fvg_fill_val is not None:
                if fvg_fill_val < 30.0:
                    fvg_bucket = "Fresh (<30% Fill)"
                elif fvg_fill_val <= 60.0:
                    fvg_bucket = "Equilibrium/CE (30-60% Fill)"
                else:
                    fvg_bucket = "Exhausted/Chased (>=60% Fill)"
            else:
                fvg_bucket = "No FVG Logged"

            # Spread bucket (Item 1b)
            spread_val = f_ctx.get("spread_pts")
            if spread_val is not None:
                if spread_val < 40:
                    spread_bucket = "Tight (<40 pts)"
                elif spread_val <= 80:
                    spread_bucket = "Elevated (40-80 pts)"
                else:
                    spread_bucket = "High Spike (>80 pts)"
            else:
                spread_bucket = "UNKNOWN / UNRECORDED"

            # RSI regime bucket (Item 1c)
            rsi_val = f_ctx.get("m15_rsi")
            if rsi_val is not None:
                if rsi_val < 30.0:
                    rsi_bucket = "Oversold (<30)"
                elif rsi_val <= 70.0:
                    rsi_bucket = "Neutral (30-70)"
                else:
                    rsi_bucket = "Overbought (>70)"
            else:
                rsi_bucket = "UNKNOWN / UNRECORDED"

            r_data = compute_canonical_r(tot_pnl, open_price=open_price, volume=volume)

            canonical_trades.append({
                "ticket": pos_id,
                "exit_deal_ticket": exit_deal.ticket,
                "symbol": trade_sym,
                "side": side,
                "direction": side,
                "volume": volume,
                "open_price": open_price,
                "close_price": close_price,
                "open_time": entry_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "close_time": exit_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "hour_utc": hour,
                "session": session_name,
                "duration_seconds": duration_s,
                "pnl": tot_pnl,
                "profit_usd": tot_pnl,
                "r_multiple": r_data["r_multiple"],
                "r_provenance": r_data["provenance"],
                "raw_4tf_alignment": raw_4tf,
                "trend_alignment": measured_alignment,
                "alignment_provenance": alignment_provenance,
                "fvg_fill_pct": fvg_fill_val,
                "fvg_fill_bucket": fvg_bucket,
                "spread_pts": spread_val,
                "spread_bucket": spread_bucket,
                "m15_rsi": rsi_val,
                "rsi_bucket": rsi_bucket,
                "comment": exit_deal.comment or "FTMO Closed"
            })

        canonical_trades.sort(key=lambda t: t["ticket"])
        return canonical_trades

    def _calc_matrix_slice(self, trades: List[Dict[str, Any]], key_extractor) -> Dict[str, Any]:
        """Utility to aggregate win rate, avg R, and PnL across an arbitrary slice."""
        buckets = {}
        for t in trades:
            b_name = key_extractor(t)
            if b_name not in buckets:
                buckets[b_name] = []
            buckets[b_name].append(t)

        out = {}
        for b_name, b_trades in buckets.items():
            wins = [t for t in b_trades if t["pnl"] > 0]
            losses = [t for t in b_trades if t["pnl"] <= 0]
            tot_pnl = round(sum(t["pnl"] for t in b_trades), 2)
            tot_r = round(sum(t["r_multiple"] for t in b_trades), 2)
            avg_r = round(tot_r / len(b_trades), 2) if b_trades else 0.0
            wr = round((len(wins) / len(b_trades)) * 100.0, 1) if b_trades else 0.0
            avg_win_r = round(sum(t["r_multiple"] for t in wins) / max(len(wins), 1), 2) if wins else 0.0
            avg_loss_r = round(sum(t["r_multiple"] for t in losses) / max(len(losses), 1), 2) if losses else 0.0

            out[b_name] = {
                "trades": len(b_trades),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": wr,
                "net_pnl": tot_pnl,
                "net_r": tot_r,
                "avg_r": avg_r,
                "avg_win_r": avg_win_r,
                "avg_loss_r": avg_loss_r
            }
        return out

    def decompose_ledger(self, symbol: str = "XAUUSD") -> Dict[str, Any]:
        """Calculates granular condition-by-condition base rates and expectancy tables."""
        sym = symbol.strip().upper()
        trades = self.get_canonical_positions(sym)
        
        if not trades:
            return {
                "symbol": sym,
                "status": "NO_TRADES_FOUND",
                "total_trades": 0
            }

        total_trades = len(trades)
        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]
        net_pnl = round(sum(t["pnl"] for t in trades), 2)
        net_r = round(sum(t["r_multiple"] for t in trades), 2)
        overall_wr = round((len(wins) / total_trades) * 100.0, 1)

        # Multi-dimensional matrices (Item 1)
        session_matrix = self._calc_matrix_slice(trades, lambda t: t["session"])
        direction_matrix = self._calc_matrix_slice(trades, lambda t: t["side"])
        alignment_matrix = self._calc_matrix_slice(trades, lambda t: t["trend_alignment"])
        fvg_fill_matrix = self._calc_matrix_slice(trades, lambda t: t["fvg_fill_bucket"])
        spread_matrix = self._calc_matrix_slice(trades, lambda t: t["spread_bucket"])
        rsi_matrix = self._calc_matrix_slice(trades, lambda t: t["rsi_bucket"])
        
        # Cross-Matrices
        session_x_dir = self._calc_matrix_slice(trades, lambda t: f"{t['session']} | {t['side']}")
        alignment_x_dir = self._calc_matrix_slice(trades, lambda t: f"{t['trend_alignment']} | {t['side']}")
        fvg_fill_x_dir = self._calc_matrix_slice(trades, lambda t: f"{t['fvg_fill_bucket']} | {t['side']}")
        alignment_x_fvg = self._calc_matrix_slice(trades, lambda t: f"{t['trend_alignment']} | {t['fvg_fill_bucket']}")

        return {
            "symbol": sym,
            "status": "CANONICAL_SYNCHRONIZED",
            "canonical_headline_source": CANONICAL_HEADLINE_SOURCE,
            "canonical_unit": "POSITION_ID (Completed Closed Cycles)",
            "total_trades": total_trades,
            "wins": len(wins),
            "losses": len(losses),
            "overall_win_rate": overall_wr,
            "net_pnl_usd": net_pnl,
            "net_realized_r": net_r,
            "canonical_1r_usd": CANONICAL_BASELINE_1R_USD,
            "matrices": {
                "session_hour": session_matrix,
                "direction": direction_matrix,
                "measured_trend_alignment": alignment_matrix,
                "fvg_fill_bucket": fvg_fill_matrix,
                "spread_bucket": spread_matrix,
                "rsi_regime_bucket": rsi_matrix,
                "session_x_direction": session_x_dir,
                "alignment_x_direction": alignment_x_dir,
                "fvg_fill_x_direction": fvg_fill_x_dir,
                "alignment_x_fvg_fill": alignment_x_fvg
            },
            "recent_canonical_trades": trades[-5:]
        }
