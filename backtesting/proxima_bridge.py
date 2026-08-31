"""Proxima Bridge for Backtesting Query Translation.

Translates free-form OpenCode agent queries into LLM-optimized quantitative backtest rubrics.
"""

import urllib.request
import urllib.error
import json
import logging
import time
from typing import Dict, Any, Optional

LOG = logging.getLogger("alpha.backtesting.proxima")
PROXIMA_HTTP_URL = "http://127.0.0.1:3210"

class ProximaBacktestBridge:
    """Translates arbitrary agent queries into structured prompts for the Local LLM."""

    def __init__(self, http_url: str = PROXIMA_HTTP_URL, timeout: float = 65.0):
        self.http_url = http_url.rstrip("/")
        self.timeout = timeout

    def formulate_backtest_prompt(self, user_query: str, symbol: str = "XAUUSD", timeframe: str = "M5") -> Dict[str, Any]:
        """Queries Proxima to format a complete evaluation rubric and system instructions."""
        system_prompt = (
            "You are Proxima Research Quantitative Protocol Architect. "
            "Your job is to take a trader's ad-hoc backtesting question or thesis and convert it into a "
            "crystal-clear, structured analytical protocol for a Local LLM to execute against raw OHLCV candle tables."
        )

        user_prompt = (
            f"The trader wants to backtest this thesis for {symbol} on {timeframe}:\n"
            f"'{user_query}'\n\n"
            f"Format a complete backtesting evaluation prompt for the Local LLM. Your output MUST include:\n"
            f"1) Exact Structural Identification Criteria: How the LLM should spot this structure (e.g. FVG gaps, sweeps, volume velocity, order blocks) directly in an OHLCV table.\n"
            f"2) Execution Rules: Exact entry trigger bar, Stop Loss anchor price, and Take Profit target (e.g. 1:3.0 RRR or structural swing level).\n"
            f"3) Forward Resolution Method: How to evaluate forward bars sequentially until either Stop Loss or Take Profit is triggered.\n"
            f"4) Expected JSON Output Schema for the Local LLM."
        )

        models_to_try = ["perplexity"]
        full_user_prompt = f"{system_prompt}\n\n{user_prompt}"
        t0 = time.time()

        for m in models_to_try:
            payload = json.dumps({
                "model": m,
                "messages": [
                    {"role": "user", "content": full_user_prompt}
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
                    content = data["choices"][0]["message"]["content"]
                    return {
                        "status": "SUCCESS",
                        "model": m,
                        "latency_ms": lat_ms,
                        "rubric_prompt": content.strip()
                    }
            except Exception as e:
                continue

        # Robust deterministic fallback rubric if Proxima server is unreachable
        return {
            "status": "STANDBY_FALLBACK",
            "model": "local_fallback",
            "latency_ms": int((time.time() - t0) * 1000),
            "rubric_prompt": (
                f"Analyze the provided historical OHLCV candle table for {symbol} ({timeframe}) to backtest this thesis:\n"
                f"'{user_query}'\n\n"
                f"EVALUATION PROTOCOL:\n"
                f"1. Identify every Bar # where the thesis structure forms (e.g. Fair Value Gap 3-bar imbalance, liquidity sweep, or velocity acceleration).\n"
                f"2. Note the exact Entry Price, Stop Loss (anchored to swing high/low), and Take Profit (1:3.0 RRR).\n"
                f"3. Trace forward bars sequentially from the entry bar: check whether price hits TP (Win) or SL (Loss) first.\n"
                f"4. Provide output in clean JSON format."
            )
        }
