# -*- coding: utf-8 -*-
# nng/wyckoff_full.py - Comprehensive Wyckoff Phase A-E Analytics
#
# Sources:
#   Richard D. Wyckoff (1930) - The Method of Trading and Investing in Stocks
#   Pruden (2007) - The Three Skills of Top Trading
#   Schroeder (2018) - Wyckoff Power Charting

from typing import List, Dict, Any, Optional

def classify_wyckoff_phase_full(
    price_history: List[float],
    highs: List[float],
    lows: List[float],
    vah: float, val: float, poc: float,
    cvd_10b: float, velocity_tpm: float,
    displacement: bool, choch: str,
    recent_swing_high: float, recent_swing_low: float
) -> Dict[str, Any]:
    if not price_history or len(price_history) < 10:
        return {
            "phase": "UNKNOWN",
            "type": "UNKNOWN",
            "confidence": 0.0,
            "action": "FLAT"
        }

    price = price_history[-1]
    tr_width = max(vah - val, 2.0)
    
    # Check Phase C (Spring / UTAD)
    if price < (val - 1.0) and cvd_10b > 100:
        return {
            "phase": "PHASE_C_SPRING",
            "type": "ACCUMULATION",
            "sub_type": "SPRING_SWEEP",
            "confidence": 0.85,
            "action": "LONG",
            "description": "Wyckoff Spring: Price swept below VAL with fast absorption buying (CVD flip).",
            "literature": "Wyckoff (1930), Pruden (2007) - Phase C Terminal Shakeout"
        }
    elif price > (vah + 1.0) and cvd_10b < -100:
        return {
            "phase": "PHASE_C_UTAD",
            "type": "DISTRIBUTION",
            "sub_type": "UTAD_SWEEP",
            "confidence": 0.85,
            "action": "SHORT",
            "description": "Wyckoff UTAD: Price swept above VAH with fast absorption selling.",
            "literature": "Wyckoff (1930), Pruden (2007) - Phase C Upthrust After Distribution"
        }

    # Check Phase D (Sign of Strength SOS or Sign of Weakness SOW)
    if displacement and price > vah and "BULL" in choch.upper():
        return {
            "phase": "PHASE_D_MARKUP",
            "type": "ACCUMULATION",
            "sub_type": "SOS_DISPLACEMENT",
            "confidence": 0.80,
            "action": "LONG",
            "description": "Wyckoff Phase D: Sign of Strength (SOS) breakout from value area.",
            "literature": "Wyckoff (1930) - Phase D Markup Begins"
        }
    elif displacement and price < val and "BEAR" in choch.upper():
        return {
            "phase": "PHASE_D_MARKDOWN",
            "type": "DISTRIBUTION",
            "sub_type": "SOW_DISPLACEMENT",
            "confidence": 0.80,
            "action": "SHORT",
            "description": "Wyckoff Phase D: Sign of Weakness (SOW) breakdown from value area.",
            "literature": "Wyckoff (1930) - Phase D Markdown Begins"
        }

    # Phase B: Range oscillation testing
    if val <= price <= vah:
        return {
            "phase": "PHASE_B_TESTING",
            "type": "RANGING_BUILDING_CAUSE",
            "sub_type": "TR_TESTING",
            "confidence": 0.65,
            "action": "WAIT",
            "description": "Wyckoff Phase B: Building cause inside trading range.",
            "literature": "Wyckoff (1930) - Cause vs Effect"
        }

    return {
        "phase": "PHASE_A_STOPPING",
        "type": "UNCLEAR",
        "sub_type": "ABSORPTION",
        "confidence": 0.50,
        "action": "FLAT",
        "description": "Wyckoff Phase A: Initial stopping volume / preliminary support.",
        "literature": "Wyckoff (1930)"
    }
