import sys
import asyncio
from pathlib import Path

ALPHA_ROOT = Path(__file__).resolve().parent.parent
if str(ALPHA_ROOT) not in sys.path:
    sys.path.insert(0, str(ALPHA_ROOT))

from tradingagents.agent_graph import TradingAgentsDesk

async def test_scores():
    desk = TradingAgentsDesk()
    instruments = ["XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD", "XCUUSD", "USOIL.cash"]
    for sym in instruments:
        res = await desk.run_analysis_cycle(sym)
        debate = res.get("debate", {})
        score = debate.get("consensus_score")
        bears = debate.get("bear_points")
        print(f"SYMBOL: {sym:10s} | SCORE: {score:4.1f}/10 | BEARS: {bears}")

if __name__ == "__main__":
    asyncio.run(test_scores())
