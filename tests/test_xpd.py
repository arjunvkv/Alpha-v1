import sys
import asyncio
from pathlib import Path

ALPHA_ROOT = Path(__file__).resolve().parent.parent
if str(ALPHA_ROOT) not in sys.path:
    sys.path.insert(0, str(ALPHA_ROOT))

from tradingagents.agent_graph import TradingAgentsDesk

async def check_xpd():
    desk = TradingAgentsDesk()
    res = await desk.run_analysis_cycle("XPDUSD")
    print("--- XPDUSD ANALYST DIAGNOSIS ---")
    print("Technical Analyst:", res.get("technical"))
    print("Bull/Bear Debate:", res.get("debate"))
    print("Risk Assessment:", res.get("risk"))

if __name__ == "__main__":
    asyncio.run(check_xpd())
