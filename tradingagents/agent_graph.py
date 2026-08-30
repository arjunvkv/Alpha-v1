"""TradingAgents Multi-Agent Desk Implementation.

Adapted from TauricResearch/TradingAgents for Granger 7-Layer & Alpha Framework.
Features:
- Technical, Fundamental/COT, Macro/News, and Sentiment Analysts
- Bull vs. Bear Researcher Debate (Pure Institutional Order Flow & Macro Risk Audit)
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

        # Use canonical alignment if provided by MultiTimeframeAnalyst, else compute with matching weighted rules
        tf_confluence = tech_data.get("alignment") or tech_data.get("tf_confluence")
        if not tf_confluence:
            tf_list = [h4_bias, h1_bias, m15_bias, m5_bias]
            bull_count = sum(1.0 if b == "BULLISH" else 0.5 if "BULL" in str(b).upper() else 0.0 for b in tf_list)
            bear_count = sum(1.0 if b == "BEARISH" else 0.5 if "BEAR" in str(b).upper() else 0.0 for b in tf_list)

            if bull_count >= 3.0:
                tf_confluence = "4TF_STRONG_BULLISH_CONFLUENCE"
            elif bear_count >= 3.0:
                tf_confluence = "4TF_STRONG_BEARISH_CONFLUENCE"
            elif bull_count > bear_count and bull_count >= 2.0:
                tf_confluence = "4TF_BULLISH_LEANING"
            elif bear_count > bull_count and bear_count >= 2.0:
                tf_confluence = "4TF_BEARISH_LEANING"
            else:
                tf_confluence = "MIXED_TIMEFRAMES"

        score = 5.0
        if "STRONG_BULLISH" in tf_confluence:
            score += 3.0
        elif "STRONG_BEARISH" in tf_confluence:
            score -= 3.0
        elif "BULLISH_LEANING" in tf_confluence:
            score += 1.5
        elif "BEARISH_LEANING" in tf_confluence:
            score -= 1.5

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
        # Support FuturesBench cot_index_26w (primary) and cot_index_52w
        percentile = cot_data.get("cot_index_26w")
        if percentile is None:
            percentile = cot_data.get("managed_money_percentile") or cot_data.get("cot_index_52w", 50.0)
        
        net_noncommercial = cot_data.get("net_noncommercial", 0)
        net_commercial = cot_data.get("net_commercial", cot_data.get("commercial_net", -net_noncommercial))
        commercial_net = cot_data.get("commercial_net", net_commercial)
        cot_change = cot_data.get("change", 0)
        provenance = cot_data.get("data_provenance", cot_data.get("source", "FUTURESBENCH_LIVE_API"))
        is_live = cot_data.get("is_live", True)
        report_date = cot_data.get("report_date", "2026-08-25")

        # Institutional alignment check (Large Speculator / Managed Money positioning)
        institutional_long = percentile > 60.0
        extreme_overcrowded = percentile > 90.0

        score = 5.0
        if institutional_long: score += 2.5
        if extreme_overcrowded: score -= 3.0  # Contrarian risk

        bias_str = cot_data.get("bias", "")
        thesis_extra = f" ({bias_str})" if bias_str else ""

        return {
            "agent": "FundamentalAnalyst",
            "symbol": symbol,
            "score": round(score, 1),
            "cot_managed_money_percentile": percentile,
            "cot_index_26w": percentile,
            "cot_index_52w": cot_data.get("cot_index_52w", percentile),
            "net_noncommercial": net_noncommercial,
            "net_commercial": net_commercial,
            "commercial_net": commercial_net,
            "change": cot_change,
            "z_score": cot_data.get("z_score", 0.0),
            "bias": bias_str,
            "data_provenance": provenance,
            "is_live": is_live,
            "report_date": report_date,
            "thesis": f"Speculator / Money-Manager COT percentile at {percentile:.1f}% (26w: {percentile}% | Change: {cot_change:+d} | Net: {net_noncommercial:+d} | Provenance: {provenance}). Institutional speculative support {'STRONG' if institutional_long else 'WEAK'}{thesis_extra}."
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

        # Filter headlines for genuine financial, macro, commodity, and central bank items
        MARKET_KEYWORDS = [
            "FED", "INFLATION", "CPI", "PCE", "YIELD", "RATE", "POWELL", "CENTRAL BANK",
            "ECB", "BOJ", "TREASURY", "GOLD", "SILVER", "OIL", "CRUDE", "OPEC", "ENERGY",
            "METALS", "GAS", "WAR", "SANCTION", "TARIFF", "GDP", "PMI", "JOBS", "S&P", "DOLLAR", "DXY"
        ]
        valid_headlines = [
            h for h in headlines
            if any(kw in str(h.get("title", "")).upper() for kw in MARKET_KEYWORDS)
        ]
        top_headline = valid_headlines[0]["title"] if valid_headlines else (headlines[0]["title"] if headlines else "No active high-impact macro headlines")

        return {
            "agent": "MacroNewsAnalyst",
            "score": round(score, 1),
            "dxy": dxy,
            "vix": vix,
            "headline_count": len(valid_headlines) if valid_headlines else len(headlines),
            "top_headline": top_headline,
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
            "institutional_risk_warning": len(bear_points) > 0,
            "conviction": "HIGH" if consensus_score >= 8.0 else "MEDIUM" if consensus_score >= 6.0 else "LOW"
        }

class RiskManager:
    """Collect account constraints and historical risk evidence without trade veto authority."""

    def __init__(self):
        self.memory = DecisionMemory()

    def evaluate_risk(self, symbol: str, debate: Dict[str, Any], account_heat_pct: float) -> Dict[str, Any]:
        mistakes = self.memory.get_mistakes()
        similar_mistakes = [
            m for m in mistakes
            if m.get("symbol") == symbol and m.get("pattern") in debate.get("bear_points", [])
        ]

        account_constraint = account_heat_pct >= 6.0
        return {
            "approved": None,
            "review_required": True,
            "decision_authority": "AGENT_ONLY",
            "execution_feasible": not account_constraint,
            "account_constraint": {
                "active": account_constraint,
                "reason": (
                    f"Account heat {account_heat_pct:.1f}% reaches the configured 6.0% account constraint"
                    if account_constraint else "No configured account-heat constraint active"
                )
            },
            "historical_risk": {
                "similar_mistakes": similar_mistakes,
                "study_required": bool(similar_mistakes),
                "veto_authority": False
            },
            "risk_guidance": {
                "max_volume_lots": 0.10,
                "max_risk_pct": 1.5
            },
            "reason": "Risk and historical evidence supplied for Agent study; no trading-quality approval or veto was issued."
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

        # Inject live 4TF trends and canonical alignment into tech_data for TechnicalAnalyst
        tech_data["h4_bias"] = mtf_data.get("h4_trend", "NEUTRAL")
        tech_data["h1_bias"] = mtf_data.get("h1_trend", "NEUTRAL")
        tech_data["m15_bias"] = mtf_data.get("m15_trend", "NEUTRAL")
        tech_data["m5_bias"] = mtf_data.get("m5_trend", "NEUTRAL")
        tech_data["alignment"] = mtf_data.get("alignment")

        # 2. Run Analyst Team
        tech_report = self.tech_analyst.analyze(symbol, tech_data)
        fund_report = self.fund_analyst.analyze(symbol, cot_data)
        macro_report = self.macro_analyst.analyze(macro_data, headlines)
        sent_report = self.sent_analyst.analyze(sentiment_data, web_results)

        # Enhance Analyst Reports with Institutional Upgrades
        tech_report["mtf"] = mtf_data
        tech_report["order_blocks"] = ob_data
        macro_report["news_shield"] = news_status

        # Update Technical Thesis with Full 4TF Confluence & Pivots (single canonical representation)
        rsi_str = f"[H4 RSI:{mtf_data['h4_rsi']} | H1 RSI:{mtf_data['h1_rsi']} | M15 RSI:{mtf_data['m15_rsi']} | M5 RSI:{mtf_data['m5_rsi']}]"
        ob_str = f"Pivots: PP {ob_data['pivot_point']} | Demand: {ob_data['demand_zone']} | Supply: {ob_data['supply_zone']}"
        tech_report["thesis"] = f"{tech_report.get('thesis', '')} {rsi_str} | {ob_str}"

        # 3. Run Bull vs. Bear Debate
        debate_report = self.debater.debate(symbol, tech_report, fund_report, macro_report, sent_report)

        # 4. Run Risk Officer as evidence/feasibility reporter
        risk_report = self.risk_officer.evaluate_risk(symbol, debate_report, account_heat_pct)
        risk_report["news_risk"] = {
            "active": bool(news_status.get("freeze_active")),
            "event_name": news_status.get("event_name"),
            "study_required": bool(news_status.get("freeze_active")),
            "veto_authority": False
        }

        # 5. No automatic proposal or order construction.
        # The Agent receives the full evidence and chooses direction, size, entry,
        # stop and target through its normal decision/execution tools.
        proposal = None

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
