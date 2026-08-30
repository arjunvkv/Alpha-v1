"""Pure LLM Backtesting Pipeline Orchestrator.

Coordinates OpenCode Agent Query -> Proxima Rubric Translation -> MT5 Raw Data Stream -> Local LLM Natural Backtest Evaluation.
"""

import time
import logging
from typing import Dict, Any, Optional

from backtesting.proxima_bridge import ProximaBacktestBridge
from backtesting.data_harness import MT5DataHarness
from backtesting.local_llm_runner import LocalLLMBacktestRunner

LOG = logging.getLogger("alpha.backtesting.pipeline")

class PureLLMBacktestPipeline:
    """Master pipeline tying Proxima + MT5 Data Harness + Local LLM into an ultra-fast backtest engine."""

    def __init__(self):
        self.proxima_bridge = ProximaBacktestBridge()
        self.data_harness = MT5DataHarness()
        self.local_runner = LocalLLMBacktestRunner()

    def run_backtest(self, query: str, symbol: str = "XAUUSD", timeframe: str = "M5", bars: int = 60, offset: int = 0) -> Dict[str, Any]:
        """Executes full collaborative backtesting pipeline and tracks per-stage latency."""
        t_start = time.time()
        timings = {}

        # 1. Proxima Query Translation to Backtesting Rubric
        t0 = time.time()
        proxima_res = self.proxima_bridge.formulate_backtest_prompt(query, symbol=symbol, timeframe=timeframe)
        timings["proxima_translation_ms"] = int((time.time() - t0) * 1000)

        # 2. MT5 Raw Historical Candle Fetch
        t1 = time.time()
        data_res = self.data_harness.fetch_candle_window(symbol=symbol, timeframe=timeframe, bars=bars, offset=offset)
        timings["mt5_data_fetch_ms"] = int((time.time() - t1) * 1000)

        if data_res.get("status") != "SUCCESS":
            return {
                "status": "DATA_ERROR",
                "error": "Failed to extract historical candle window from MT5.",
                "timings": timings
            }

        # 3. Local LLM Natural Structural Pattern Discovery & Trade Simulation
        t2 = time.time()
        rubric_str = proxima_res.get("rubric_prompt", "")
        table_str = data_res.get("formatted_table", "")
        
        llm_res = self.local_runner.evaluate_backtest(rubric_str, table_str, symbol=symbol, timeframe=timeframe)
        timings["local_llm_evaluation_ms"] = int((time.time() - t2) * 1000)
        timings["total_pipeline_ms"] = int((time.time() - t_start) * 1000)

        if llm_res.get("status") == "SUCCESS":
            bt_data = llm_res.get("backtest_results", {})
            return {
                "status": "SUCCESS",
                "query": query,
                "symbol": symbol,
                "timeframe": timeframe,
                "candle_window": {
                    "bar_count": data_res.get("bar_count"),
                    "start_time": data_res.get("start_time"),
                    "end_time": data_res.get("end_time")
                },
                "proxima_model": proxima_res.get("model"),
                "local_llm_model": llm_res.get("model_used"),
                "timings": timings,
                "summary": {
                    "thesis": bt_data.get("thesis_summary", query),
                    "total_setups_found": bt_data.get("total_setups_found", 0),
                    "wins": bt_data.get("wins", 0),
                    "losses": bt_data.get("losses", 0),
                    "win_rate_pct": bt_data.get("win_rate_pct", 0.0),
                    "net_realized_r": bt_data.get("net_realized_r", 0.0)
                },
                "trades": bt_data.get("trades", []),
                "failure_clusters": bt_data.get("failure_clusters", []),
                "key_edge_takeaways": bt_data.get("key_edge_takeaways", [])
            }
        else:
            return {
                "status": "EVALUATION_ERROR",
                "query": query,
                "symbol": symbol,
                "timeframe": timeframe,
                "timings": timings,
                "error": llm_res.get("error", "Local LLM evaluation failed.")
            }
