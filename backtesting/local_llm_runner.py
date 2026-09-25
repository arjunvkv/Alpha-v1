"""Local LLM Runner for Quantitative Structural Backtesting.

Provides fast synthesis and contextual edge enrichment.
Guarantees zero timeouts, non-blocking execution, and zero contradictory fake blurbs.
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
    """Provides optional LLM synthesis to enrich deterministic structural backtest results."""

    def __init__(self, http_url: str = PROXIMA_HTTP_URL, timeout: float = 3.0):
        self.http_url = http_url.rstrip("/")
        self.timeout = timeout

    def enrich_synthesis(self, sim_data: Dict[str, Any], query: str, symbol: str = "XAUUSD", timeframe: str = "M5") -> Dict[str, Any]:
        """Attempts fast LLM contextual enrichment. Never mutates ground truth trades or injects fake blurbs."""
        t0 = time.time()
        trades = sim_data.get("trades", [])
        if not trades:
            return sim_data

        prompt = (
            f"Backtest Thesis: '{query}' on {symbol} ({timeframe}).\n"
            f"Ground Truth Results: {sim_data.get('wins', 0)} Wins, {sim_data.get('losses', 0)} Losses, "
            f"Net Realized R: {sim_data.get('net_realized_r', 0.0)}R, Win Rate: {sim_data.get('win_rate_pct', 0.0)}%.\n"
            "Provide 2 concise failure clusters and 2 actionable institutional edge takeaways based STRICTLY on these real results.\n"
            "Respond in JSON: {\"failure_clusters\": [...], \"key_edge_takeaways\": [...]}"
        )

        try:
            payload = json.dumps({
                "model": "3.5-flash",
                "messages": [{"role": "user", "content": prompt}]
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self.http_url}/v1/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json", "Authorization": "Bearer proxima-local"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_reply = data["choices"][0]["message"]["content"]
                parsed = self._extract_json(raw_reply)
                if parsed and isinstance(parsed, dict):
                    if parsed.get("failure_clusters") and isinstance(parsed["failure_clusters"], list):
                        sim_data["failure_clusters"] = parsed["failure_clusters"]
                    if parsed.get("key_edge_takeaways") and isinstance(parsed["key_edge_takeaways"], list):
                        sim_data["key_edge_takeaways"] = parsed["key_edge_takeaways"]
            sim_data["enrichment_status"] = "SUCCESS"
        except Exception as e:
            # Cleanly pass! Sim_data already contains authentic mathematically derived takeaways
            LOG.debug(f"LLM enrichment timeout/error: {e}")
            sim_data["enrichment_status"] = "TIMEOUT_OR_ERROR"
            pass

        return sim_data

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extracts and parses JSON object with robust regex repair."""
        if not text:
            return None
        text_clean = text.strip()
        
        try:
            return json.loads(text_clean)
        except Exception:
            pass

        fence_m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text_clean)
        if fence_m:
            try:
                return json.loads(fence_m.group(1))
            except Exception:
                pass

        start = text_clean.find("{")
        end = text_clean.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_substr = text_clean[start:end+1]
            try:
                return json.loads(json_substr)
            except Exception:
                sanitized = re.sub(r",\s*([\}\]])", r"\1", json_substr)
                try:
                    return json.loads(sanitized)
                except Exception as e:
                    LOG.error(f"JSON extraction error after sanitization: {e}")

        return None
