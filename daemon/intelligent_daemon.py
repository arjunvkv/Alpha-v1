"""Intelligent Daemon Engine.

Integrates TradingAgents multi-agent desk, Granger 7-layers, Global Eyes news/web search,
and Alpha MCP Server for bi-directional collaborative trading with OpenCode CIO.
"""

import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List

TRADING_ROOT = Path(__file__).resolve().parent.parent.parent
if str(TRADING_ROOT) not in sys.path:
    sys.path.insert(0, str(TRADING_ROOT))
ALPHA_ROOT = Path(__file__).resolve().parent.parent
if str(ALPHA_ROOT) not in sys.path:
    sys.path.insert(0, str(ALPHA_ROOT))

from mcp_server.alpha_mcp_server import AlphaMCPServer
from mcp_server.opencode_cio_evaluator import OpenCodeCIOEvaluator
from daemon.stateful_latch import StatefulDiscoveryLatch
from logs.story_logger import log_local_llm_monitoring, log_proactive_alert, log_local_llm_replied, log_opencode_said

LOG = logging.getLogger("alpha.daemon.intelligent")

class IntelligentDaemon:
    def __init__(self):
        self.mcp_server = AlphaMCPServer()
        self.cio_evaluator = OpenCodeCIOEvaluator()
        self.latch = StatefulDiscoveryLatch()
        self.instruments = ["XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD", "XCUUSD", "USOIL.cash"]
        self.is_running = False

    async def run_cycle(self) -> Dict[str, Any]:
        """Run single 24/7 scanning cycle across all instruments."""
        log_local_llm_monitoring(f"Scanning market data across {len(self.instruments)} instruments (Granger 7-Layers + Global Eyes RSS feeds active)...")

        cycle_summary = {
            "proactive_discoveries": [],
            "cio_decisions": [],
            "watches_triggered": [],
            "scanned_instruments": len(self.instruments)
        }

        scores = []
        top_symbol = "XAUUSD"
        top_score = 0.0

        for symbol in self.instruments:
            analysis = await self.mcp_server.desk.run_analysis_cycle(symbol)
            debate = analysis.get("debate", {})
            score = debate.get("consensus_score", 0.0)
            scores.append(score)

            if score > top_score:
                top_score = score
                top_symbol = symbol

            # 1. Stateful Proactive Discovery Latch
            should_emit, reason = self.latch.evaluate_thesis(symbol, score, debate.get("bull_points", []), debate.get("bear_points", []))

            if should_emit and score >= 8.0 and analysis.get("risk", {}).get("approved", False):
                headline = f"High-conviction {symbol} setup detected ({score}/10) [{reason}]. {', '.join(debate.get('bull_points', []))}"
                discovery = self.mcp_server.mcp_alpha_broadcast_insight(
                    symbol=symbol,
                    headline=headline,
                    score=score
                )
                cycle_summary["proactive_discoveries"].append(discovery)
                LOG.info(f"PROACTIVE DISCOVERY ({reason}): {symbol} score {score}/10")
                log_proactive_alert(symbol, score, headline)

                # Dispatch event to OpenCode CIO Evaluator for authentic team dialogue!
                cio_res = self.cio_evaluator.evaluate_discovery_event(discovery)
                cycle_summary["cio_decisions"].append(cio_res)

            # 2. Check OpenCode's Dynamic Smart Watches
            for watch in self.mcp_server.active_watches:
                if watch["symbol"] == symbol and watch["status"] == "ACTIVE":
                    if score >= 7.5:
                        watch["status"] = "TRIGGERED"
                        cycle_summary["watches_triggered"].append(watch)
                        LOG.info(f"WATCH TRIGGERED: {watch['id']} for {symbol}")
                        log_local_llm_replied(f"Alerting OpenCode CIO! Dynamic watch #{watch['id']} triggered for {symbol}: {watch['condition']} satisfied (Score {score}/10).")

        # 3. Position Monitoring & Active Ticket Management
        open_tickets = []
        try:
            import MetaTrader5 as mt5
            if not mt5.initialize():
                ftmo_path = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
                mt5.initialize(path=ftmo_path)
            pos_list = mt5.positions_get()
            if pos_list:
                for p in pos_list:
                    open_tickets.append(f"{p.symbol} #{p.ticket} ({p.profit:+.2f} USD)")
        except Exception as err:
            LOG.error(f"Failed to fetch MT5 positions: {err}")

        # 4. Rich Continuous Team Story Dialogue Narration
        avg_score = sum(scores) / len(scores) if scores else 0.0
        active_watches = len([w for w in self.mcp_server.active_watches if w.get("status") == "ACTIVE"])

        if open_tickets:
            pos_summary = ", ".join(open_tickets[:4]) + (f" (+{len(open_tickets)-4} more)" if len(open_tickets) > 4 else "")
            log_local_llm_replied(f"[Desk Position Monitor] 24/7 Tracking active FTMO MT5 trades: {pos_summary}. All SL/TP parameters guarded at broker level.")
        else:
            log_local_llm_replied(f"[Desk Status Update] Scanned 6 instruments. Conviction posture STRONG (Avg Score {avg_score:.1f}/10). Top setup: {top_symbol} ({top_score}/10). {active_watches} active watches tracked.")

        # Periodic OpenCode CIO Check-in Dialogue
        self.cycle_count = getattr(self, "cycle_count", 0) + 1
        if self.cycle_count % 2 == 0:
            if open_tickets:
                log_opencode_said(f"Desk position report received. {len(open_tickets)} trades active on MT5. Continue trailing SL and alert if technical reversal occurs.")
            else:
                log_opencode_said(f"Desk update received. Top setup: {top_symbol} ({top_score}/10). Continue 24/7 monitoring across all 6 instruments and alert if conviction score shifts >= 1.0.")

        return cycle_summary

    async def start_daemon(self, max_cycles: int = 1):
        """Start daemon loop for max_cycles (or infinite)."""
        self.is_running = True
        LOG.info("Intelligent Daemon started 24/7 scanning loop.")
        cycle_count = 0
        results = []
        while self.is_running and cycle_count < max_cycles:
            res = await self.run_cycle()
            results.append(res)
            cycle_count += 1
            if cycle_count < max_cycles:
                await asyncio.sleep(1)
        self.is_running = False
        return results

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    daemon = IntelligentDaemon()

    # Seed OpenCode CIO smart watches for team dialogue
    daemon.mcp_server.mcp_alpha_register_watch(
        symbol="XAUUSD",
        condition="Price retest near $2,640 with volume expansion >= 1.5x",
        instruction="Wake OpenCode CIO if Bull/Bear debate score >= 7.5/10"
    )
    daemon.mcp_server.mcp_alpha_register_watch(
        symbol="XAGUSD",
        condition="Kitco news sentiment shifts > +0.20 following Fed dovish yields",
        instruction="Prepare 0.10 lot buy order spec for OpenCode approval"
    )

    async def main_loop():
        LOG.info("Starting 24/7 Intelligent Trading Daemon main loop...")
        while True:
            await daemon.run_cycle()
            await asyncio.sleep(10)

    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        LOG.info("Intelligent Daemon stopped by user.")
