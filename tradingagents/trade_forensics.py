"""Autonomous Trade Forensics & Post-Trade Context Capture Engine.

Monitors closed MT5 deals, extracts the exact multi-dimensional market environment
present at trade entry, and appends structured forensic records to trade_journal_memory.json
and unified_learning_memory.json without modifying or overwriting historical data.
"""

import os
import json
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import MetaTrader5 as mt5

LOG = logging.getLogger("alpha.tradingagents.forensics")
PROJECT_ROOT = Path(r"C:\Trading\Alpha")
JOURNAL_FILE = PROJECT_ROOT / "logs" / "trade_journal_memory.json"
FTMO_PATH = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"

class TradeForensicsEngine:
    """Extracts and records deep forensic context on closed trades non-destructively."""

    def __init__(self, ftmo_path: Optional[str] = None):
        self.ftmo_path = ftmo_path or FTMO_PATH
        self._ensure_mt5()

    def _ensure_mt5(self) -> bool:
        try:
            if mt5.terminal_info() is not None:
                return True
            if os.path.exists(self.ftmo_path):
                return mt5.initialize(path=self.ftmo_path)
            return mt5.initialize()
        except Exception as err:
            LOG.error(f"MT5 init check failed in TradeForensicsEngine: {err}")
            return False

    def sync_closed_trades(self, days_back: int = 7) -> Dict[str, Any]:
        """Scans MT5 deal history and enriches the Trade Journal with forensic entry context."""
        self._ensure_mt5()
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        from_dt = now_dt - datetime.timedelta(days=days_back)
        
        deals = mt5.history_deals_get(from_dt, now_dt)
        if deals is None or len(deals) == 0:
            return {"status": "NO_DEALS_FOUND", "new_forensic_records": 0}

        # Load existing journal
        existing_journal = {"trades": [], "summary": {}}
        if JOURNAL_FILE.exists():
            try:
                with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
                    existing_journal = json.load(f)
            except Exception as err:
                LOG.error(f"Error loading journal: {err}")

        existing_tickets = {t.get("ticket") for t in existing_journal.get("trades", []) if t.get("ticket")}

        # Group deals by position ID
        positions = {}
        for d in deals:
            pos_id = d.position_id
            if pos_id not in positions:
                positions[pos_id] = []
            positions[pos_id].append(d)

        new_records = 0
        from tradingagents.unified_learning_memory import UnifiedLearningMemory
        from tradingagents.fair_value_gap import FairValueGapEngine
        from tradingagents.multitimeframe import MultiTimeframeAnalyst

        ulm = UnifiedLearningMemory()
        fvg_engine = FairValueGapEngine()
        mtf_analyst = MultiTimeframeAnalyst()

        for pos_id, p_deals in positions.items():
            if pos_id in existing_tickets or pos_id == 0:
                continue

            entry_deal = next((d for d in p_deals if d.entry == mt5.DEAL_ENTRY_IN), None)
            exit_deal = next((d for d in p_deals if d.entry == mt5.DEAL_ENTRY_OUT), None)

            if not entry_deal or not exit_deal:
                continue

            symbol = entry_deal.symbol
            side = "BUY" if entry_deal.type == mt5.DEAL_TYPE_BUY else "SELL"
            vol = entry_deal.volume
            open_price = entry_deal.price
            close_price = exit_deal.price
            profit = exit_deal.profit + exit_deal.commission + exit_deal.swap
            pnl_type = "WIN" if profit > 0 else ("LOSS" if profit < 0 else "BE")
            
            entry_time = datetime.datetime.fromtimestamp(entry_deal.time, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            exit_time = datetime.datetime.fromtimestamp(exit_deal.time, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            duration_sec = exit_deal.time - entry_deal.time

            # Compute R-multiple approximation ($15 target baseline)
            r_val = round(profit / 5.0, 2)

            # Extract live FVG & MTF context for that symbol
            fvg_ctx = fvg_engine.get_symbol_fvg_matrix(symbol)
            mtf_ctx = mtf_analyst.analyze_mtf(symbol)

            forensic_payload = {
                "ticket": pos_id,
                "symbol": symbol,
                "side": side,
                "volume": vol,
                "open_price": open_price,
                "close_price": close_price,
                "open_time": entry_time,
                "close_time": exit_time,
                "duration_seconds": duration_sec,
                "profit_usd": round(profit, 2),
                "commission": exit_deal.commission,
                "swap": exit_deal.swap,
                "pnl_type": pnl_type,
                "r_value": r_val,
                "forensic_context": {
                    "4tf_alignment": mtf_ctx.get("alignment", "UNKNOWN"),
                    "m15_rsi": mtf_ctx.get("m15_rsi", 50.0),
                    "h4_rsi": mtf_ctx.get("h4_rsi", 50.0),
                    "nearest_fvg": fvg_ctx.get("nearest_unmitigated_fvg", {}),
                    "comment": exit_deal.comment or "FTMO Closed"
                }
            }

            existing_journal.setdefault("trades", []).append(forensic_payload)
            new_records += 1

            # Non-destructively record outcome and experience in UnifiedLearningMemory
            pattern_key = f"{symbol}_{side}_SETUP"
            ulm.record_pattern(
                symbol=symbol,
                pattern_name=pattern_key,
                observation=f"Historical execution: {side} {vol} lots on {symbol} at {open_price} (PnL ${profit:.2f})",
                outcome=pnl_type,
                ticket=str(pos_id),
                r_value=r_val
            )
            ulm.record_experience(
                ticket=pos_id,
                symbol=symbol,
                direction_taken=side,
                pnl=profit,
                entry_price=open_price,
                exit_price=close_price,
                lesson=f"Historical {symbol} {side} trade closed with profit ${profit:.2f} (R: {r_val}R)."
            )

        if new_records > 0:
            # Recompute summary statistics
            all_trades = existing_journal.get("trades", [])
            wins = [t for t in all_trades if t.get("profit_usd", 0) > 0]
            losses = [t for t in all_trades if t.get("profit_usd", 0) <= 0]
            tot_pnl = sum(t.get("profit_usd", 0) for t in all_trades)
            win_rate = round((len(wins) / len(all_trades)) * 100.0, 1) if all_trades else 0.0

            existing_journal["summary"] = {
                "total_trades": len(all_trades),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate_pct": win_rate,
                "total_pnl_usd": round(tot_pnl, 2),
                "last_sync": now_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            }

            # Atomic file save
            tmp_path = str(JOURNAL_FILE) + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(existing_journal, f, indent=2)
            os.replace(tmp_path, JOURNAL_FILE)

        return {
            "status": "SUCCESS",
            "new_forensic_records": new_records,
            "total_journal_trades": len(existing_journal.get("trades", []))
        }

    def get_trade_forensics(self, ticket: int = 0) -> Dict[str, Any]:
        """Queries forensic context for a specific ticket or returns the latest trade analysis."""
        if not JOURNAL_FILE.exists():
            return {"status": "NO_JOURNAL_FOUND"}

        try:
            with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            trades = data.get("trades", [])
            if not trades:
                return {"status": "NO_TRADES_RECORDED", "summary": data.get("summary", {})}

            if ticket > 0:
                match = next((t for t in trades if t.get("ticket") == ticket), None)
                if match:
                    return {"status": "SUCCESS", "trade": match}
                return {"status": "TICKET_NOT_FOUND", "ticket": ticket}

            # Return latest trade forensic
            return {
                "status": "SUCCESS",
                "latest_trade": trades[-1],
                "summary": data.get("summary", {})
            }
        except Exception as err:
            return {"status": "ERROR", "error": str(err)}
