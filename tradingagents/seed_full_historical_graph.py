"""
======================================================================
     ALPHA V1 - FULL HISTORICAL SEEDING FOR GRAPHITI PATTERN MEMORY
======================================================================
Ingests 100% of historical trading knowledge:
1. All 385 patterns and observations from unified_learning_memory.json
2. All 60 historical closed trades and autopsies from trade_journal_memory.json
3. Documented retail traps from 08_ANTI_RETAIL_TRAPS_DEEP_GUIDE.md
4. Master winning blueprints (the 5 Master Wins)

Seeds graphiti_pattern_memory.db with Day-1 synaptic experience.
======================================================================
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

PROJECT_ROOT = Path(r"C:\Trading\Alpha")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tradingagents.pattern_memory_engine import PatternMemoryEngine, _normalize_pattern_tag

LOG = logging.getLogger("alpha.seed_graphiti")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

PROJECT_ROOT = Path(r"C:\Trading\Alpha")
ULM_FILE = PROJECT_ROOT / "logs" / "unified_learning_memory.json"
JOURNAL_FILE = PROJECT_ROOT / "logs" / "trade_journal_memory.json"
TRAPS_FILE = Path(r"C:\Trading\agent\rules\08_ANTI_RETAIL_TRAPS_DEEP_GUIDE.md")


def extract_keywords_as_tags(text: str) -> List[str]:
    """Extracts meaningful structural pattern tags from free-form text."""
    tags = []
    text_upper = text.upper()
    
    # Trend tags
    if "4TF BULLISH" in text_upper or "4TF_BULLISH" in text_upper:
        tags.append("4TF_BULLISH")
    elif "4TF BEARISH" in text_upper or "4TF_BEARISH" in text_upper:
        tags.append("4TF_BEARISH")
    elif "MIXED" in text_upper:
        tags.append("MIXED_TIMEFRAMES")

    # Sweep & Liquidity tags
    if "TURTLE" in text_upper or "SWEEP" in text_upper:
        if "ASIAN LOW" in text_upper or "ASIA LOW" in text_upper:
            tags.append("ASIAN_LOW_SWEEP")
        elif "ASIAN HIGH" in text_upper or "ASIA HIGH" in text_upper:
            tags.append("ASIAN_HIGH_SWEEP")
        elif "PDL" in text_upper:
            tags.append("PDL_SWEEP")
        elif "PDH" in text_upper:
            tags.append("PDH_SWEEP")
        else:
            tags.append("LIQUIDITY_SWEEP")

    # Structure & Shelves
    if "BULLISH FVG" in text_upper or "BULL_FVG" in text_upper:
        tags.append("BULLISH_FVG_SHELF")
    elif "BEARISH FVG" in text_upper or "BEAR_FVG" in text_upper:
        tags.append("BEARISH_FVG_SHELF")
    elif "FVG" in text_upper:
        tags.append("FVG_SHELF")
        
    if "POC" in text_upper:
        tags.append("POC_RETEST")
    if "ORDER_BLOCK" in text_upper or "OB" in text_upper:
        tags.append("ORDER_BLOCK")

    # Order Flow & Tape Physics
    if "ABSORPTION" in text_upper:
        tags.append("CVD_ABSORPTION")
    if "DELTA" in text_upper:
        if "POSITIVE" in text_upper or "SURGE" in text_upper:
            tags.append("POSITIVE_CVD_DELTA")
        elif "NEGATIVE" in text_upper or "DUMP" in text_upper:
            tags.append("NEGATIVE_CVD_DELTA")
    if "VELOCITY" in text_upper:
        if "HIGH" in text_upper or ">100" in text_upper or "KINETIC" in text_upper:
            tags.append("KINETIC_VELOCITY")
        elif "LOW" in text_upper or "<60" in text_upper or "COMPRESSION" in text_upper:
            tags.append("QUIET_COMPRESSION")

    # Specific Traps & Stumbles
    if "ROUND NUMBER" in text_upper or "XX00" in text_upper or "4400" in text_upper:
        tags.append("APEX_ROUND_NUMBER")
    if "SQUEEZED STOP" in text_upper or "TIGHT STOP" in text_upper:
        tags.append("SQUEEZED_STOP_PITFALL")
    if "PANIC SCRATCH" in text_upper or "EARLY EXIT" in text_upper:
        tags.append("PANIC_SCRATCH_PITFALL")
    if "OVERBOUGHT" in text_upper or "RSI > 70" in text_upper:
        tags.append("FADING_OVERBOUGHT_RSI_PITFALL")

    return list(set(tags))


def seed_all():
    engine = PatternMemoryEngine()
    LOG.info(f"Starting 100% full historical seeding into {engine.db_path}...")

    # ------------------------------------------------------------------
    # 1. Ingest Master Champion Wins
    # ------------------------------------------------------------------
    master_wins = [
        {
            "patterns": ["4TF_BULLISH", "BULLISH_FVG_SHELF", "POC_RETEST", "QUIET_COMPRESSION"],
            "outcome": "WIN",
            "lesson": "Pre-staged BUY_LIMIT at POC/FVG boundary + spread buffer. Price wicked entry and expanded +16 pts cleanly. No micromanagement."
        },
        {
            "patterns": ["4TF_BULLISH", "BULLISH_FVG_SHELF", "POSITIVE_CVD_DELTA"],
            "outcome": "WIN",
            "lesson": "Champion Hold Through Noise (#538243241). Gold pulled back 3.5 pts against entry; structural SL held firmly and blasted +35 pts."
        },
        {
            "patterns": ["4TF_BEARISH", "PDL_SWEEP", "BEARISH_FVG_SHELF", "NEGATIVE_CVD_DELTA"],
            "outcome": "WIN",
            "lesson": "Directional breakdown continuation (#539779137). Pre-staged SELL_STOP below consolidation with 9 pt SL / 7.4 pt TP into roadway."
        },
        {
            "patterns": ["4TF_BULLISH", "ASIAN_LOW_SWEEP", "CVD_ABSORPTION", "POSITIVE_CVD_DELTA"],
            "outcome": "WIN",
            "lesson": "Turtle Soup sweep of Asian Low with aggressive CVD absorption flip back into Value Area. Rocketed straight into target."
        },
        {
            "patterns": ["4TF_BULLISH", "KINETIC_VELOCITY", "POSITIVE_CVD_DELTA", "BULLISH_FVG_SHELF"],
            "outcome": "WIN",
            "lesson": "Immediate Momentum Entry (User Msg 95). Entered active impulse with 0.50L sizing; banked +8.0 pts into destination magnet."
        }
    ]

    for mw in master_wins:
        res = engine.add_episode(
            patterns=mw["patterns"],
            outcome=mw["outcome"],
            lesson=mw["lesson"],
            symbol="XAUUSD",
            source="MASTER_CHAMPION_BLUEPRINT"
        )
        LOG.info(f"Seeded Master Win Walk: {res['canonical_key']}")

    # ------------------------------------------------------------------
    # 2. Ingest Documented Retail Traps (Anti-Trauma: specific pitfalls)
    # ------------------------------------------------------------------
    documented_traps = [
        {
            "patterns": ["APEX_ROUND_NUMBER", "KINETIC_VELOCITY", "FADING_OVERBOUGHT_RSI_PITFALL"],
            "outcome": "TRAP",
            "lesson": "Staged breakout stop at major $XX00 round number without an intermediate base; CVD absorption rolled over and dumped -14 pts."
        },
        {
            "patterns": ["4TF_BULLISH", "FADING_OVERBOUGHT_RSI_PITFALL"],
            "outcome": "TRAP",
            "lesson": "Attempted to fade a strong bullish 4TF trend because RSI > 70. Trend steamrolled resistance for +30 pts."
        },
        {
            "patterns": ["4TF_BULLISH", "SQUEEZED_STOP_PITFALL"],
            "outcome": "TRAP",
            "lesson": "Cramped Stop Loss into 2.0 pts in gold. Normal 5m ATR wicks clipped stop 1 minute before gold rocketed +25 pts in intended direction."
        },
        {
            "patterns": ["4TF_BULLISH", "PANIC_SCRATCH_PITFALL"],
            "outcome": "TRAP",
            "lesson": "Panicked on a routine 3-point equilibrium pullback on 1m delta flicker; exited at -$140 and watched gold blast +35 pts 2 minutes later."
        },
        {
            "patterns": ["MIXED_TIMEFRAMES", "KINETIC_VELOCITY"],
            "outcome": "TRAP",
            "lesson": "Staged breakout stop in multi-timeframe chop without confirmed liquidity sweep. Got chopped up in equilibrium wicks."
        }
    ]

    for dt in documented_traps:
        res = engine.add_episode(
            patterns=dt["patterns"],
            outcome=dt["outcome"],
            lesson=dt["lesson"],
            symbol="XAUUSD",
            source="ANTI_RETAIL_TRAPS_GUIDE"
        )
        LOG.info(f"Seeded Documented Trap Walk: {res['canonical_key']}")

    # ------------------------------------------------------------------
    # 3. Ingest All 60 Historical Trades from trade_journal_memory.json
    # ------------------------------------------------------------------
    trades_seeded = 0
    if JOURNAL_FILE.exists():
        try:
            with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
                tj_data = json.load(f)
            trades = tj_data.get("trades", [])
            for t in trades:
                pnl = t.get("profit_usd", t.get("profit", t.get("pnl", 0.0)))
                is_win = float(pnl) > 0.0
                outcome = "WIN" if is_win else "TRAP"
                
                f_ctx = t.get("forensic_context", t.get("f_context", {}))
                alignment = f_ctx.get("4tf_alignment", "UNKNOWN") if isinstance(f_ctx, dict) else "UNKNOWN"
                side = t.get("side", t.get("direction", "BUY"))
                symbol = t.get("symbol", "XAUUSD")
                critique = t.get("critique", t.get("notes", t.get("comment", "")))
                dur = t.get("duration_seconds", 0)

                tags = []
                if "BULLISH" in alignment.upper():
                    tags.append("4TF_BULLISH")
                elif "BEARISH" in alignment.upper():
                    tags.append("4TF_BEARISH")
                elif "MIXED" in alignment.upper():
                    tags.append("MIXED_TIMEFRAMES")
                else:
                    tags.append("INTRADAY_DIRECTIONAL_FLOW")

                if side.upper() == "BUY":
                    tags.append("LONG_EXECUTION")
                else:
                    tags.append("SHORT_EXECUTION")

                if dur < 900:
                    tags.append("MOMENTUM_EXPANSION_ENTRY")
                else:
                    tags.append("STRUCTURAL_SHELF_HOLD")

                # Extract pattern tags from critique text
                extra_tags = extract_keywords_as_tags(critique)
                tags.extend(extra_tags)
                tags = list(set(tags))

                clean_lesson = critique[:120] if critique else f"MT5 trade ticket #{t.get('ticket')} {outcome} ({float(pnl):+.2f})"

                engine.add_episode(
                    patterns=tags,
                    outcome=outcome,
                    lesson=clean_lesson,
                    symbol=symbol,
                    source="HISTORICAL_TRADE_JOURNAL"
                )
                trades_seeded += 1
            LOG.info(f"Seeded {trades_seeded} historical trades from Trade Journal.")
        except Exception as e:
            LOG.error(f"Error seeding trade journal: {e}")

    # ------------------------------------------------------------------
    # 4. Ingest All 385 Patterns from unified_learning_memory.json
    # ------------------------------------------------------------------
    ulm_seeded = 0
    if ULM_FILE.exists():
        try:
            with open(ULM_FILE, "r", encoding="utf-8") as f:
                ulm_data = json.load(f)
            patterns = ulm_data.get("patterns", {})
            for p_id, pat in patterns.items():
                p_name = pat.get("pattern_name") or p_id
                sym = pat.get("symbol") or "XAUUSD"
                desc = pat.get("description") or ""
                outcomes = pat.get("outcomes", [])
                
                base_tag = _normalize_pattern_tag(p_name)
                tags = [base_tag]
                
                # Contextual tags from description
                desc_tags = extract_keywords_as_tags(desc)
                tags.extend(desc_tags)
                tags = list(set(tags))

                # Determine outcome from linked outcomes
                if outcomes:
                    wins = sum(1 for o in outcomes if "WIN" in str(o.get("outcome", "")).upper())
                    losses = sum(1 for o in outcomes if "LOSS" in str(o.get("outcome", "")).upper() or "TRAP" in str(o.get("outcome", "")).upper())
                    primary_outcome = "WIN" if wins > losses else ("TRAP" if losses > wins else "STUDY")
                else:
                    primary_outcome = "STUDY"

                clean_lesson = desc[:120] if desc else f"Documented setup from ULM: {p_name}"
                
                engine.add_episode(
                    patterns=tags,
                    outcome=primary_outcome,
                    lesson=clean_lesson,
                    symbol=sym,
                    source="UNIFIED_LEARNING_MEMORY"
                )
                ulm_seeded += 1
            LOG.info(f"Seeded {ulm_seeded} patterns from Unified Learning Memory.")
        except Exception as e:
            LOG.error(f"Error seeding ULM patterns: {e}")

    # Display final summary
    walks_summary = engine.get_pattern_walks("XAUUSD", limit=5)
    LOG.info(f"\nSeeding Complete! Summary:\n{walks_summary}")


if __name__ == "__main__":
    seed_all()
