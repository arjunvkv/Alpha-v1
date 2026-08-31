"""Local LLM Runner for Pure Natural Backtesting.

Passes raw MT5 candle tables and the Proxima evaluation rubric to the LLM.
The LLM evaluates structural patterns and forward trade resolution naturally without hardcoded formulas.
"""

import urllib.request
import urllib.error
import json
import logging
import re
import time
from typing import Dict, Any, Optional

LOG = logging.getLogger("alpha.backtesting.runner")
PROXIMA_HTTP_URL = "http://127.0.0.1:3210"

class LocalLLMBacktestRunner:
    """Executes natural pattern discovery and trade simulation on raw OHLCV candle tables."""

    def __init__(self, http_url: str = PROXIMA_HTTP_URL, timeout: float = 90.0):
        self.http_url = http_url.rstrip("/")
        self.timeout = timeout

    def evaluate_backtest(self, rubric_prompt: str, candle_table_str: str, symbol: str = "XAUUSD", timeframe: str = "M5") -> Dict[str, Any]:
        """Dispatches candle table and evaluation rubric to the LLM for natural backtesting."""
        system_prompt = (
            "You are an Elite Institutional Quantitative Analyst and Expert Price Action Backtester. "
            "You analyze raw OHLCV candle tables, identify institutional structural setups naturally "
            "(Fair Value Gaps, Liquidity Sweeps, Order Blocks, Velocity Acceleration), and track their forward "
            "bar-by-bar progression to determine exact trade outcomes.\n"
            "Respond strictly in valid JSON format."
        )

        user_content = (
            f"=== BACKTESTING PROTOCOL ===\n{rubric_prompt}\n\n"
            f"=== RAW HISTORICAL CANDLE DATA ({symbol} {timeframe}) ===\n{candle_table_str}\n\n"
            "TASK:\n"
            "1. Read through the chronological candle table bar by bar.\n"
            "2. Find all instances where the requested pattern/thesis forms.\n"
            "3. For each instance: determine the Entry Bar #, Entry Price, Stop Loss, and Take Profit (1:3.0 RRR or structural target).\n"
            "4. Trace the subsequent bars to see if price hit Take Profit (WIN) or Stop Loss / Invalidation (LOSS) first.\n"
            "5. Return your evaluation strictly in the following JSON format:\n"
            "{\n"
            '  "thesis_summary": "<summary of what was tested>",\n'
            '  "total_setups_found": <int>,\n'
            '  "wins": <int>,\n'
            '  "losses": <int>,\n'
            '  "win_rate_pct": <float>,\n'
            '  "net_realized_r": <float>,\n'
            '  "trades": [\n'
            '    {\n'
            '      "trade_id": <int>,\n'
            '      "formation_bar": <int>,\n'
            '      "entry_timestamp": "<UTC string>",\n'
            '      "entry_price": <float>,\n'
            '      "stop_loss": <float>,\n'
            '      "take_profit": <float>,\n'
            '      "exit_bar": <int>,\n'
            '      "exit_timestamp": "<UTC string>",\n'
            '      "exit_reason": "<TP_HIT | SL_HIT | INVALIDATION>",\n'
            '      "realized_r": <float>,\n'
            '      "analysis": "<short explanation of setup formation and forward price reaction>"\n'
            '    }\n'
            '  ],\n'
            '  "failure_clusters": ["<key reason why losing setups failed>"],\n'
            '  "key_edge_takeaways": ["<actionable institutional lessons>"]\n'
            "}"
        )

        models_to_try = ["3.5-flash", "perplexity", "gemini", "auto"]
        t0 = time.time()

        for m in models_to_try:
            for attempt in range(2):
                payload = json.dumps({
                    "model": m,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ]
                }).encode("utf-8")

                req = urllib.request.Request(
                    f"{self.http_url}/v1/chat/completions",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )

                try:
                    with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                        lat_ms = int((time.time() - t0) * 1000)
                        data = json.loads(resp.read().decode("utf-8"))
                        raw_reply = data["choices"][0]["message"]["content"]
                        
                        # Extract JSON object from LLM response
                        parsed = self._extract_json(raw_reply)
                        if parsed and isinstance(parsed, dict):
                            return {
                                "status": "SUCCESS",
                                "model_used": m,
                                "latency_ms": lat_ms,
                                "backtest_results": parsed
                            }
                except Exception as e:
                    time.sleep(0.3)

        return {
            "status": "EVALUATION_ERROR",
            "model_used": "none",
            "latency_ms": int((time.time() - t0) * 1000),
            "error": "Failed to complete natural backtesting through Local LLM after retries."
        }

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extracts and parses JSON object from LLM markdown fences or raw text."""
        if not text:
            return None
        text_clean = text.strip()
        
        # 1. Try direct parse
        try:
            return json.loads(text_clean)
        except Exception:
            pass

        # 2. Try markdown code fences ```json ... ``` or ``` ... ```
        fence_m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text_clean)
        if fence_m:
            try:
                return json.loads(fence_m.group(1))
            except Exception:
                pass

        # 3. Try finding outermost { and }
        start = text_clean.find("{")
        end = text_clean.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_substr = text_clean[start:end+1]
            try:
                return json.loads(json_substr)
            except Exception as e:
                LOG.error(f"JSON extraction error from substring: {e}")

        return None
