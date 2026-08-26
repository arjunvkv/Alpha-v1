"""TradingAgents Multi-Agent Desk Implementation.

Adapted from TauricResearch/TradingAgents for Granger 7-Layer & Alpha Framework.
Features:
- Technical, Fundamental/COT, Macro/News, and Sentiment Analysts
- Bull vs. Bear Researcher Debate (Bear armed with RETAIL_TRAP_RULES.md)
- Risk Officer (Account Heat + memory/__init__.py mistake log prevention)
- Trader Agent (Structural order parameters R:R >= 2:1)
"""

import sys
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

TRADING_ROOT = Path(__file__).resolve().parent.parent.parent
if str(TRADING_ROOT) not in sys.path:
    sys.path.insert(0, str(TRADING_ROOT))
ALPHA_ROOT = Path(__file__).resolve().parent.parent
if str(ALPHA_ROOT) not in sys.path:
    sys.path.insert(0, str(ALPHA_ROOT))

from sensors.granger_adapter import GrangerAdapter
from sensors.global_news_crawler import GlobalNewsCrawler
from sensors.openbb_macro_adapter import OpenBBMacroAdapter
from memory import DecisionMemory

LOG = logging.getLogger("alpha.tradingagents.graph")

class TechnicalAnalyst:
    def analyze(self, symbol: str, tech_data: Dict[str, Any]) -> Dict[str, Any]:
        # Multi-timeframe 4TF (H4 / H1 / M15 / M5) structural alignment
        h4_bias = tech_data.get("h4_bias", "NEUTRAL")
        h1_bias = tech_data.get("h1_bias", "NEUTRAL")
        m15_bias = tech_data.get("m15_bias", "NEUTRAL")
        m5_bias = tech_data.get("m5_bias", "NEUTRAL")

        tf_list = [h4_bias, h1_bias, m15_bias, m5_bias]
        bull_count = sum(1 for b in tf_list if "BULL" in str(b).upper())
        bear_count = sum(1 for b in tf_list if "BEAR" in str(b).upper())

        score = 5.0
        tf_confluence = "MIXED_TIMEFRAMES"
        if bull_count >= 3:
            tf_confluence = "4TF_STRONG_BULLISH_CONFLUENCE"
            score += 3.0
        elif bear_count >= 3:
            tf_confluence = "4TF_STRONG_BEARISH_CONFLUENCE"
            score -= 3.0

        # Liquidity Sweep Interaction Bonus/Penalty
        sweep_flag = tech_data.get("liquidity_sweep", {}).get("flag", "NORMAL_RANGE")
        if "LOW_SWEPT" in sweep_flag:
            score += 1.5  # Bullish liquidity grab reversal potential
        elif "HIGH_SWEPT" in sweep_flag:
            score -= 1.5  # Bearish liquidity grab reversal potential

        return {
            "agent": "TechnicalAnalyst",
            "symbol": symbol,
            "score": round(score, 1),
            "h4_bias": h4_bias,
            "tf_confluence": tf_confluence,
            "thesis": f"Pure Market Structure & Order Flow. 4TF Alignment: H4({h4_bias}) H1({h1_bias}) M15({m15_bias}) M5({m5_bias}) -> {tf_confluence}."
        }

class FundamentalAnalyst:
    def analyze(self, symbol: str, cot_data: Dict[str, Any]) -> Dict[str, Any]:
        percentile = cot_data.get("managed_money_percentile", 50.0)
        comm_net = cot_data.get("commercial_net", 0)

        # Institutional alignment check
        institutional_long = percentile > 60.0
        extreme_overcrowded = percentile > 90.0

        score = 5.0
        if institutional_long: score += 2.5
        if extreme_overcrowded: score -= 3.0  # Contrarian risk

        return {
            "agent": "FundamentalAnalyst",
            "symbol": symbol,
            "score": round(score, 1),
            "cot_managed_money_percentile": percentile,
            "commercial_net": comm_net,
            "thesis": f"Managed money COT percentile at {percentile:.1f}%. Institutional support {'STRONG' if institutional_long else 'WEAK'}."
        }

class MacroNewsAnalyst:
    def analyze(self, macro_data: Dict[str, Any], headlines: List[Dict[str, str]]) -> Dict[str, Any]:
        dxy = macro_data.get("dxy", 101.5)
        vix = macro_data.get("vix", 16.0)

        weak_usd = dxy < 102.0
        low_fear = vix < 20.0

        score = 5.0
        if weak_usd: score += 2.0
        if low_fear: score += 1.0

        return {
            "agent": "MacroNewsAnalyst",
            "score": round(score, 1),
            "dxy": dxy,
            "vix": vix,
            "headline_count": len(headlines),
            "top_headline": headlines[0]["title"] if headlines else "No headline",
            "thesis": f"DXY at {dxy:.2f}, VIX at {vix:.1f}. Macro environment {'FAVORABLE' if score >= 6.5 else 'HOSTILE'}."
        }

class SentimentAnalyst:
    def analyze(self, sentiment_data: Dict[str, Any], web_results: List[Dict[str, str]]) -> Dict[str, Any]:
        vader = sentiment_data.get("vader_compound", 0.0)
        score = 5.0 + (vader * 4.0)

        return {
            "agent": "SentimentAnalyst",
            "score": round(min(10.0, max(0.0, score)), 1),
            "vader": vader,
            "web_snippets_analyzed": len(web_results),
            "thesis": f"VADER sentiment compound {vader:+.2f}. Market mood is {'POSITIVE' if vader > 0.05 else 'NEGATIVE' if vader < -0.05 else 'NEUTRAL'}."
        }

class BullBearDebater:
    def debate(self, symbol: str, tech: dict, fund: dict, macro: dict, sent: dict) -> Dict[str, Any]:
        # Bull thesis
        bull_points = []
        if tech["score"] >= 6.0: bull_points.append("4TF Market Structure shows strong institutional alignment")
        if fund["score"] >= 6.0: bull_points.append("Institutional COT positioning is net long")
        if macro["score"] >= 6.0: bull_points.append("Weak DXY provides macro tailwind")

        # Bear thesis - Pure Institutional Liquidity & Crowded Risk Checks
        bear_points = []
        if fund["cot_managed_money_percentile"] > 88.0:
            bear_points.append("INSTITUTIONAL RISK: Managed money percentile > 88% represents extreme crowded long risk")
        if macro["dxy"] > 104.0:
            bear_points.append("Strong Dollar headwind opposes bullish commodity thesis")

        # Calculate consensus score
        avg_analyst_score = (tech["score"] + fund["score"] + macro["score"] + sent["score"]) / 4.0
        penalty = len(bear_points) * 1.5
        consensus_score = round(max(0.0, min(10.0, avg_analyst_score - penalty + (len(bull_points) * 0.8))), 1)

        return {
            "symbol": symbol,
            "consensus_score": consensus_score,
            "bull_points": bull_points,
            "bear_points": bear_points,
            "retail_trap_warning": len(bear_points) > 0,
            "conviction": "HIGH" if consensus_score >= 8.0 else "MEDIUM" if consensus_score >= 6.0 else "LOW"
        }

class RiskManager:
    def __init__(self):
        self.memory = DecisionMemory()

    def evaluate_risk(self, symbol: str, debate: Dict[str, Any], account_heat_pct: float) -> Dict[str, Any]:
        # Check hard heat limit
        if account_heat_pct >= 6.0:
            return {"approved": False, "reason": f"Account heat {account_heat_pct:.1f}% exceeds max heat limit of 6.0%"}

        # Check memory for historical mistake anti-patterns
        mistakes = self.memory.get_mistakes()
        blocking_mistake = None
        for m in mistakes:
            if m.get("symbol") == symbol and m.get("pattern") in debate.get("bear_points", []):
                blocking_mistake = m
                break

        if blocking_mistake:
            return {
                "approved": False,
                "reason": f"Historical Memory Block: Past mistake logged for {symbol} pattern '{blocking_mistake.get('pattern')}'"
            }

        return {
            "approved": debate["consensus_score"] >= 7.5,
            "max_volume_lots": 0.10,
            "max_risk_pct": 1.5,
            "reason": "Risk checks passed cleanly."
        }

from tradingagents.multitimeframe import MultiTimeframeAnalyst, OrderBlockEngine
from tradingagents.news_shield import NewsShield

class TradingAgentsDesk:
    """Orchestrates all agents into a unified trading decision graph."""

    def __init__(self):
        self.granger = GrangerAdapter()
        self.news = GlobalNewsCrawler()
        self.macro = OpenBBMacroAdapter()
        self.memory = DecisionMemory()

        self.tech_analyst = TechnicalAnalyst()
        self.fund_analyst = FundamentalAnalyst()
        self.macro_analyst = MacroNewsAnalyst()
        self.sent_analyst = SentimentAnalyst()
        self.debater = BullBearDebater()
        self.risk_officer = RiskManager()

        # Institutional Upgrades
        self.mtf_analyst = MultiTimeframeAnalyst()
        self.order_blocks = OrderBlockEngine()
        self.news_shield = NewsShield()

    async def run_analysis_cycle(self, symbol: str = "XAUUSD", account_heat_pct: float = 1.2) -> Dict[str, Any]:
        """Run complete multi-agent analysis, debate, and risk evaluation."""
        # 1. Fetch live Granger + Global Eyes data
        snapshot = await self.granger.fetch_full_snapshot()
        tech_data = self.granger.get_technical_data(symbol)
        cot_data = self.granger.get_cot_positioning_data(symbol)
        macro_data = self.granger.get_macro_signals_data()
        sentiment_data = self.granger.get_sentiment_data("gold" if "XAU" in symbol else "silver")
        headlines = self.news.fetch_rss_headlines()
        web_results = self.news.search_live_web(f"{symbol} market price analysis")

        # Institutional Upgrades Data
        mtf_data = self.mtf_analyst.analyze_mtf(symbol)
        ob_data = self.order_blocks.calculate_levels(symbol)
        news_status = self.news_shield.evaluate_news_freeze()

        # 2. Run Analyst Team
        tech_report = self.tech_analyst.analyze(symbol, tech_data)
        fund_report = self.fund_analyst.analyze(symbol, cot_data)
        macro_report = self.macro_analyst.analyze(macro_data, headlines)
        sent_report = self.sent_analyst.analyze(sentiment_data, web_results)

        # Enhance Analyst Reports with Institutional Upgrades
        tech_report["mtf"] = mtf_data
        tech_report["order_blocks"] = ob_data
        macro_report["news_shield"] = news_status

        # Update Technical Thesis with MTF & Pivots
        mtf_str = f"MTF Alignment: H1 ({mtf_data['h1_trend']}) | M15 ({mtf_data['m15_trend']}) | M5 ({mtf_data['m5_trend']}) -> {mtf_data['alignment']}"
        ob_str = f"Pivots: PP {ob_data['pivot_point']} | Demand: {ob_data['demand_zone']} | Supply: {ob_data['supply_zone']}"
        tech_report["thesis"] = f"{tech_report.get('thesis', '')} | {mtf_str} | {ob_str}"

        # 3. Run Bull vs. Bear Debate
        debate_report = self.debater.debate(symbol, tech_report, fund_report, macro_report, sent_report)

        # 4. Run Risk Officer
        risk_report = self.risk_officer.evaluate_risk(symbol, debate_report, account_heat_pct)
        if news_status.get("freeze_active"):
            risk_report["approved"] = False
            risk_report["reason"] = f"TRADE HALTED BY NEWS SHIELD: {news_status.get('event_name')}"

        # 5. Formulate Trade Proposal if High Conviction
        proposal = None
        if risk_report["approved"] and debate_report["consensus_score"] >= 8.0:
            price = tech_report.get("prices", {}).get("current_price", 0.0)
            if price == 0.0:
                try:
                    import MetaTrader5 as mt5
                    tick = mt5.symbol_info_tick(symbol) or mt5.symbol_info_tick(symbol.upper())
                    price = getattr(tick, "ask", 0.0)
                except Exception:
                    price = 0.0
            sl = round(price * 0.985, 2)
            tp = round(price * 1.035, 2)
            rr = round((tp - price) / (price - sl), 2) if (price - sl) > 0 else 2.0

            proposal = {
                "symbol": symbol,
                "side": "buy",
                "volume": risk_report["max_volume_lots"],
                "entry_price": price,
                "sl": sl,
                "tp": tp,
                "structural_rr": rr,
                "conviction_score": debate_report["consensus_score"],
                "reason": f"Multi-Agent Consensus Score {debate_report['consensus_score']}/10. Bull points: {', '.join(debate_report['bull_points'])}"
            }

        return {
            "symbol": symbol,
            "analyst_reports": {
                "technical": tech_report,
                "fundamental": fund_report,
                "macro": macro_report,
                "sentiment": sent_report
            },
            "debate": debate_report,
            "risk": risk_report,
            "proposal": proposal,
            "mtf": mtf_data,
            "order_blocks": ob_data,
            "news_shield": news_status
        }
