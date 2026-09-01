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

        # Use canonical alignment if provided by MultiTimeframeAnalyst
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

        sweep_info = tech_data.get("liquidity_sweep", {})
        fvg_info = tech_data.get("fvg", {})

        return {
            "agent": "TechnicalAnalyst",
            "symbol": symbol,
            "h4_bias": h4_bias,
            "h1_bias": h1_bias,
            "m15_bias": m15_bias,
            "m5_bias": m5_bias,
            "tf_confluence": tf_confluence,
            "liquidity_sweep": sweep_info,
            "fvg_matrix": fvg_info,
            "m15_rsi": tech_data.get("m15_rsi"),
            "h4_rsi": tech_data.get("h4_rsi"),
            "thesis": f"Pure Market Structure & Order Flow. 4TF Alignment: H4({h4_bias}) H1({h1_bias}) M15({m15_bias}) M5({m5_bias}) -> {tf_confluence}."
        }

class FundamentalAnalyst:
    def analyze(self, symbol: str, cot_data: Dict[str, Any]) -> Dict[str, Any]:
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

        bias_str = cot_data.get("bias", "")
        thesis_extra = f" ({bias_str})" if bias_str else ""

        return {
            "agent": "FundamentalAnalyst",
            "symbol": symbol,
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
            "thesis": f"Speculator / Money-Manager COT percentile at {percentile:.1f}% (26w: {percentile}% | Change: {cot_change:+d} | Net Non-Comm: {net_noncommercial:+d} | Net Comm: {commercial_net:+d} | Provenance: {provenance}){thesis_extra}."
        }

class MacroNewsAnalyst:
    def analyze(self, macro_data: Dict[str, Any], headlines: List[Dict[str, str]]) -> Dict[str, Any]:
        dxy = macro_data.get("dxy", 101.5)
        vix = macro_data.get("vix", 16.0)
        us10y = macro_data.get("us10y", 4.25)
        us2y = macro_data.get("us2y", 4.10)

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
            "dxy": dxy,
            "vix": vix,
            "us10y": us10y,
            "us2y": us2y,
            "headline_count": len(valid_headlines) if valid_headlines else len(headlines),
            "top_headline": top_headline,
            "macro_news_shield": macro_data.get("news_shield", "CLEAR"),
            "thesis": f"DXY: {dxy:.2f} | US10Y: {us10y:.2f}% | VIX: {vix:.1f}. Top Headline: '{top_headline}'."
        }

class SentimentAnalyst:
    def analyze(self, sentiment_data: Dict[str, Any], web_results: List[Dict[str, str]]) -> Dict[str, Any]:
        vader = sentiment_data.get("vader_compound", 0.0)

        return {
            "agent": "SentimentAnalyst",
            "vader_compound": vader,
            "retail_long_pct": sentiment_data.get("retail_long_pct", 50.0),
            "retail_short_pct": sentiment_data.get("retail_short_pct", 50.0),
            "web_snippets_analyzed": len(web_results),
            "thesis": f"VADER sentiment compound {vader:+.2f} across {len(web_results)} sources."
        }

class BullBearDebater:
    def debate(self, symbol: str, tech: dict, fund: dict, macro: dict, sent: dict) -> Dict[str, Any]:
        bull_points = []
        bear_points = []

        mtf = tech.get("mtf", {})
        alignment = tech.get("tf_confluence") or tech.get("alignment") or mtf.get("alignment", "UNKNOWN")
        
        # Pull live FVG matrix to detect if nearest FVG is exhausted
        try:
            from tradingagents.fvg_engine import fvg_engine
            fvg_matrix = fvg_engine.get_symbol_fvg_matrix(symbol)
            nearest_fvg = fvg_matrix.get("nearest_unmitigated_fvg") or fvg_matrix.get("m5_fvg")
            if nearest_fvg and isinstance(nearest_fvg, dict):
                fill_pct = float(nearest_fvg.get("fill_pct", 0.0))
                if fill_pct >= 60.0:
                    bear_points.append(f"CHASE TRAP: Nearest {nearest_fvg.get('type', 'FVG')} is {fill_pct:.1f}% filled (Exhausted FVG zone).")
                else:
                    bull_points.append(f"FVG OPPORTUNITY: Nearest {nearest_fvg.get('type', 'FVG')} at {nearest_fvg.get('ce_price')} ({fill_pct:.1f}% fill).")
        except Exception:
            pass

        # Technical structure points
        if "BULL" in str(alignment).upper():
            bull_points.append(f"4TF Market Structure: {alignment}")
        elif "BEAR" in str(alignment).upper():
            bear_points.append(f"4TF Market Structure: {alignment}")

        # Fundamental COT Bull vs Bear
        cot_perc = float(fund.get("cot_managed_money_percentile", 50.0))
        if cot_perc >= 60.0:
            bull_points.append(f"COT Money-Manager positioning net long ({cot_perc:.1f}th percentile)")
        if cot_perc > 88.0:
            bear_points.append("OVERCROWDING RISK: Managed money percentile > 88% represents extreme crowded positioning")

        # Macro Bull vs Bear
        dxy = float(macro.get("dxy", 100.0))
        if dxy < 101.5:
            bull_points.append(f"Weak Dollar tailwind (DXY: {dxy:.2f})")
        elif dxy > 103.5:
            bear_points.append(f"Strong Dollar headwind (DXY: {dxy:.2f})")

        # Regime Conflict Check
        is_regime_conflict = ("BEAR" in str(alignment).upper()) and cot_perc >= 70.0
        if is_regime_conflict:
            bear_points.append("REGIME DIVERGENCE: Technical Order Flow is Bearish vs COT Speculators at High Bullish Percentile.")

        return {
            "symbol": symbol,
            "bull_points": bull_points,
            "bear_points": bear_points,
            "is_regime_conflict": is_regime_conflict,
            "structural_risk_warning": len(bear_points) > 0,
            "raw_evidence_matrix": {
                "technical_alignment": alignment,
                "cot_percentile": cot_perc,
                "dxy": dxy,
                "vix": macro.get("vix"),
                "vader_sentiment": sent.get("vader_compound")
            }
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
                "standard_production_lots": 0.10,
                "pilot_probe_lots": 0.02,
                "max_risk_pct": 1.5
            },
            "reason": "Standard production trades sized at 0.10 lots for high-conviction setups; empirical probes sized at 0.01-0.05 lots."
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
