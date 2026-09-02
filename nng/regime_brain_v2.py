# -*- coding: utf-8 -*-
# nng/regime_brain_v2.py - Full Quantitative Market Regime Brain v2
#
# Integrates 9 research-backed analytical modules:
#   1. Hurst Exponent (Peters 1994) - trending vs mean-reverting
#   2. OFI / Microstructure (Cont 2014, Kyle 1985, Roll 1984) - order flow
#   3. Volatility Regime (Garman-Klass 1980, Parkinson 1980, Andersen 2001)
#   4. Momentum Analytics (Moskowitz 2012, Elder 1995, Wilder 1978)
#   5. Session Analytics (ICT/Huddleston - AMD, Killzones, Liquidity Sweeps)
#   6. Intermarket (Murphy 1999, Briese 2008 COT)
#   7. Structure Analytics (ICT OB/Breaker, PDArray, NR7 Crabel 1990)
#   8. Statistical Analytics (OU half-life Chan 2013, Z-scores)
#   9. Wyckoff + Dalton AMT (carried from v1)
#
# Resolves into 32 named market conditions. Each condition owns its trade geometry.

import math
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional

# Import all analytical modules
from nng.regime_brain import (
    compute_hurst, compute_ofi, detect_wyckoff_phase,
    classify_amt_day_type, classify_vwap_regime, CONDITION_CATALOG as V1_CONDITIONS
)
from nng.microstructure import microstructure_regime
from nng.volatility_regime import full_volatility_analysis
from nng.momentum_analytics import full_momentum_analysis
from nng.session_analytics import session_analysis
from nng.intermarket import cot_regime, dxy_correlation_bias, real_yields_bias, intermarket_bias
from nng.structure_analytics import structure_analysis
from nng.statistical_analytics import statistical_analysis

# New modules — imported with fallback so brain works even while modules are being written
try:
    from nng.order_block_engine import find_order_blocks, find_breaker_blocks, get_nearest_ob, ob_confluence
    _HAS_OB = True
except ImportError:
    _HAS_OB = False

try:
    from nng.liquidity_map import (find_equal_highs_lows, detect_bsl_ssl_sweep,
                                    fibonacci_levels, find_fibonacci_confluence,
                                    detect_abcd_harmonic, find_multi_tf_fvg_stack,
                                    full_liquidity_analysis)
    _HAS_LIQUIDITY = True
except ImportError:
    _HAS_LIQUIDITY = False

try:
    from nng.wyckoff_full import classify_wyckoff_phase_full
    _HAS_WYCKOFF_FULL = True
except ImportError:
    _HAS_WYCKOFF_FULL = False

try:
    from nng.elliott_wave import elliott_wave_analysis
    _HAS_ELLIOTT = True
except ImportError:
    _HAS_ELLIOTT = False


# ===================================================================
# FULL CONDITION CATALOG - 32 Named Conditions
# ===================================================================
FULL_CONDITIONS = {
    # ---- MICROSTRUCTURE ----
    "KYLE_LAMBDA_INFORMED_FLOW": {
        "name": "Kyle Lambda Institutional Informed Flow",
        "literature": "Kyle (1985) Continuous Auctions + Bouchaud (2018) LOB",
        "when": "Lambda spike detected: informed institutional order flow is moving price. High price impact per unit volume.",
        "direction": "WITH_INFORMED_FLOW",
        "entry_anchor": "FVG_CE_OR_NEAREST_LEVEL_IN_FLOW_DIRECTION",
        "stop_anchor": "BEYOND_LAST_SWING",
        "target_anchor": "NEXT_LIQUIDITY_POOL",
    },

    # ---- VOLATILITY ----
    "VOLATILITY_COMPRESSION_BREAKOUT_LONG": {
        "name": "Garman-Klass Volatility Compression Breakout Long",
        "literature": "Garman-Klass (1980) + Engle ARCH (1982) + Crabel NR7 (1990)",
        "when": "GK vol at extreme low (Z<-1.5) + NR7 coil + price breaks above range high with velocity burst.",
        "direction": "LONG",
        "entry_anchor": "RANGE_HIGH_RETEST",
        "stop_anchor": "BELOW_RANGE_HIGH",
        "target_anchor": "MEASURED_MOVE_RANGE_WIDTH_UP",
    },
    "VOLATILITY_COMPRESSION_BREAKOUT_SHORT": {
        "name": "Garman-Klass Volatility Compression Breakout Short",
        "literature": "Garman-Klass (1980) + Engle ARCH (1982) + Crabel NR7 (1990)",
        "when": "GK vol at extreme low (Z<-1.5) + NR7 coil + price breaks below range low with velocity burst.",
        "direction": "SHORT",
        "entry_anchor": "RANGE_LOW_RETEST",
        "stop_anchor": "ABOVE_RANGE_LOW",
        "target_anchor": "MEASURED_MOVE_RANGE_WIDTH_DOWN",
    },
    "VOLATILITY_EXPANSION_CONTINUATION": {
        "name": "Realized Volatility Expansion Trend Continuation",
        "literature": "Andersen, Bollerslev, Diebold (2001) Realized Volatility",
        "when": "RV Z-score >2 + displacement BOS confirmed. Real breakout with expanding institutional volume.",
        "direction": "WITH_DISPLACEMENT",
        "entry_anchor": "FVG_CE_FORMED_BY_DISPLACEMENT",
        "stop_anchor": "BELOW_DISPLACEMENT_CANDLE_LOW",
        "target_anchor": "NEXT_SESSION_LIQUIDITY",
    },

    # ---- MOMENTUM ----
    "TSMOM_LONG_SIGNAL": {
        "name": "Time Series Momentum Long (Moskowitz-Ooi-Pedersen 2012)",
        "literature": "Moskowitz, Ooi & Pedersen (2012) JFE Time Series Momentum",
        "when": "Vol-scaled TSMOM positive + EMA alignment bullish 3/4 TFs + RSI not overbought.",
        "direction": "LONG",
        "entry_anchor": "PULLBACK_TO_M15_EMA20",
        "stop_anchor": "BELOW_SWING_LOW",
        "target_anchor": "NEXT_RESISTANCE_OR_VAH",
    },
    "TSMOM_SHORT_SIGNAL": {
        "name": "Time Series Momentum Short (Moskowitz-Ooi-Pedersen 2012)",
        "literature": "Moskowitz, Ooi & Pedersen (2012) JFE Time Series Momentum",
        "when": "Vol-scaled TSMOM negative + EMA alignment bearish 3/4 TFs + RSI not oversold.",
        "direction": "SHORT",
        "entry_anchor": "PULLBACK_TO_M15_EMA20_FROM_BELOW",
        "stop_anchor": "ABOVE_SWING_HIGH",
        "target_anchor": "NEXT_SUPPORT_OR_VAL",
    },
    "REGULAR_DIVERGENCE_REVERSAL_LONG": {
        "name": "Regular RSI Divergence Bullish Reversal",
        "literature": "Elder (1995) Trading for a Living - divergence signals",
        "when": "Price makes lower low, RSI makes higher low (bullish divergence). Exhaustion of sellers.",
        "direction": "LONG",
        "entry_anchor": "FIRST_FVG_CE_ABOVE_DIVERGENCE_LOW",
        "stop_anchor": "BELOW_DIVERGENCE_LOW",
        "target_anchor": "PREVIOUS_SWING_HIGH",
    },
    "REGULAR_DIVERGENCE_REVERSAL_SHORT": {
        "name": "Regular RSI Divergence Bearish Reversal",
        "literature": "Elder (1995) Trading for a Living - divergence signals",
        "when": "Price makes higher high, RSI makes lower high (bearish divergence). Exhaustion of buyers.",
        "direction": "SHORT",
        "entry_anchor": "FIRST_FVG_CE_BELOW_DIVERGENCE_HIGH",
        "stop_anchor": "ABOVE_DIVERGENCE_HIGH",
        "target_anchor": "PREVIOUS_SWING_LOW",
    },
    "HIDDEN_DIVERGENCE_CONTINUATION_LONG": {
        "name": "Hidden RSI Divergence Trend Continuation Long",
        "literature": "Elder (1995) - hidden divergence = trend continuation",
        "when": "Price makes higher low, RSI makes lower low. Trend continuation signal long.",
        "direction": "LONG",
        "entry_anchor": "HIGHER_LOW_OR_EMA20",
        "stop_anchor": "BELOW_HIGHER_LOW",
        "target_anchor": "TREND_NEXT_HIGH",
    },
    "HIDDEN_DIVERGENCE_CONTINUATION_SHORT": {
        "name": "Hidden RSI Divergence Trend Continuation Short",
        "literature": "Elder (1995) - hidden divergence = trend continuation",
        "when": "Price makes lower high, RSI makes higher high. Trend continuation signal short.",
        "direction": "SHORT",
        "entry_anchor": "LOWER_HIGH_OR_EMA20",
        "stop_anchor": "ABOVE_LOWER_HIGH",
        "target_anchor": "TREND_NEXT_LOW",
    },

    # ---- ICT SESSION ----
    "ICT_LONDON_SWEEP_LONG": {
        "name": "ICT London Open Asian Low Sweep Reversal Long",
        "literature": "ICT/Huddleston - AMD Power of Three + London Killzone",
        "when": "London KZ active. Asian Low swept (stops run below). Displacement up. FVG formed. Enter on FVG CE.",
        "direction": "LONG",
        "entry_anchor": "FVG_CE_INSIDE_RANGE_AFTER_SWEEP",
        "stop_anchor": "BELOW_ASIAN_LOW_SWEEP",
        "target_anchor": "ASIAN_HIGH_OR_PDH",
    },
    "ICT_LONDON_SWEEP_SHORT": {
        "name": "ICT London Open Asian High Sweep Reversal Short",
        "literature": "ICT/Huddleston - AMD Power of Three + London Killzone",
        "when": "London KZ active. Asian High swept (stops run above). Displacement down. FVG formed. Enter on FVG CE.",
        "direction": "SHORT",
        "entry_anchor": "FVG_CE_INSIDE_RANGE_AFTER_SWEEP",
        "stop_anchor": "ABOVE_ASIAN_HIGH_SWEEP",
        "target_anchor": "ASIAN_LOW_OR_PDL",
    },
    "ICT_NY_REVERSAL_LONG": {
        "name": "ICT NY Open London Downmove Reversal Long",
        "literature": "ICT/Huddleston - New York Reversal + IPDA Delivery",
        "when": "NY KZ active. London created bearish FVG below. NY reverses. OFI turns positive. Enter FVG CE.",
        "direction": "LONG",
        "entry_anchor": "BULLISH_FVG_CE_BELOW_CURRENT_PRICE",
        "stop_anchor": "BELOW_NY_OPEN_LOW",
        "target_anchor": "LONDON_OPEN_PRICE_OR_PDH",
    },
    "ICT_NY_REVERSAL_SHORT": {
        "name": "ICT NY Open London Upmove Reversal Short",
        "literature": "ICT/Huddleston - New York Reversal + IPDA Delivery",
        "when": "NY KZ active. London created bullish FVG above. NY reverses. OFI turns negative. Enter FVG CE.",
        "direction": "SHORT",
        "entry_anchor": "BEARISH_FVG_CE_ABOVE_CURRENT_PRICE",
        "stop_anchor": "ABOVE_NY_OPEN_HIGH",
        "target_anchor": "LONDON_OPEN_PRICE_OR_PDL",
    },

    # ---- COT / INTERMARKET ----
    "COT_COMMERCIAL_EXTREME_LONG": {
        "name": "COT Commercial Extreme Net Long Setup",
        "literature": "Briese (2008) Commitments of Traders Bible - COT Index >90",
        "when": "Commercials at extreme net long (COT index >90). Historically predicts price rises. Confirmed by bullish FVG.",
        "direction": "LONG",
        "entry_anchor": "NEAREST_BULLISH_FVG_CE_OR_VAL",
        "stop_anchor": "BELOW_VAL",
        "target_anchor": "MEASURED_MOVE_EQUAL_TO_VA_WIDTH",
    },
    "COT_COMMERCIAL_EXTREME_SHORT": {
        "name": "COT Commercial Extreme Net Short Setup",
        "literature": "Briese (2008) Commitments of Traders Bible - COT Index <10",
        "when": "Commercials at extreme net short (COT index <10). Historically predicts price falls. Confirmed by bearish FVG.",
        "direction": "SHORT",
        "entry_anchor": "NEAREST_BEARISH_FVG_CE_OR_VAH",
        "stop_anchor": "ABOVE_VAH",
        "target_anchor": "MEASURED_MOVE_DOWN_EQUAL_TO_VA_WIDTH",
    },

    # ---- STRUCTURE ----
    "PDARRAY_TRIPLE_CONFLUENCE_LONG": {
        "name": "PD Array Triple Confluence Long Zone",
        "literature": "ICT PD Arrays + Dalton Value Area + FVG Anatomy",
        "when": "3+ institutional reference levels (VAL, POC, FVG CE, Swing Low) stacked within 3pts below price.",
        "direction": "LONG",
        "entry_anchor": "CONFLUENCE_ZONE_TOP",
        "stop_anchor": "BELOW_CONFLUENCE_ZONE_BOTTOM",
        "target_anchor": "VAH_OR_NEXT_LIQUIDITY",
    },
    "PDARRAY_TRIPLE_CONFLUENCE_SHORT": {
        "name": "PD Array Triple Confluence Short Zone",
        "literature": "ICT PD Arrays + Dalton Value Area + FVG Anatomy",
        "when": "3+ institutional reference levels (VAH, POC, FVG CE, Swing High) stacked within 3pts above price.",
        "direction": "SHORT",
        "entry_anchor": "CONFLUENCE_ZONE_BOTTOM",
        "stop_anchor": "ABOVE_CONFLUENCE_ZONE_TOP",
        "target_anchor": "VAL_OR_NEXT_SUPPORT",
    },

    # ---- STATISTICAL ----
    "STATISTICAL_EXTREME_REVERSAL_LONG": {
        "name": "Statistical Z-Score Extreme Reversal Long",
        "literature": "Price Z-score + OU half-life Chan (2013) Algorithmic Trading",
        "when": "Price Z-score <-2 (2 standard deviations below rolling mean) + institutional volume spike + fast OU half-life.",
        "direction": "LONG",
        "entry_anchor": "CURRENT_PRICE_OR_NEAREST_FVG_CE",
        "stop_anchor": "BELOW_RECENT_LOW",
        "target_anchor": "ROLLING_MEAN_OR_POC",
    },
    "STATISTICAL_EXTREME_REVERSAL_SHORT": {
        "name": "Statistical Z-Score Extreme Reversal Short",
        "literature": "Price Z-score + OU half-life Chan (2013) Algorithmic Trading",
        "when": "Price Z-score >+2 (2 standard deviations above rolling mean) + institutional volume spike + fast OU half-life.",
        "direction": "SHORT",
        "entry_anchor": "CURRENT_PRICE_OR_NEAREST_FVG_CE",
        "stop_anchor": "ABOVE_RECENT_HIGH",
        "target_anchor": "ROLLING_MEAN_OR_POC",
    },


    # ---- ORDER BLOCK CONDITIONS ----
    "OB_BULLISH_MITIGATION": {
        "name": "Bullish Order Block Mitigation Long",
        "literature": "ICT/Huddleston Order Block Theory - Last bearish candle before bullish impulse",
        "when": "Price retesting a fresh bullish order block zone (last bearish candle before up-impulse). High-probability bounce expected.",
        "direction": "LONG",
        "entry_anchor": "OB_TOP_OR_CE",
        "stop_anchor": "BELOW_OB_BOTTOM",
        "target_anchor": "NEXT_BEARISH_OB_OR_SWING_HIGH",
    },
    "OB_BEARISH_MITIGATION": {
        "name": "Bearish Order Block Mitigation Short",
        "literature": "ICT/Huddleston Order Block Theory - Last bullish candle before bearish impulse",
        "when": "Price retesting a fresh bearish order block zone (last bullish candle before down-impulse). High-probability rejection expected.",
        "direction": "SHORT",
        "entry_anchor": "OB_BOTTOM_OR_CE",
        "stop_anchor": "ABOVE_OB_TOP",
        "target_anchor": "NEXT_BULLISH_OB_OR_SWING_LOW",
    },
    "BREAKER_BLOCK_LONG": {
        "name": "Bearish Order Block Broken - Breaker Block Long",
        "literature": "ICT/Huddleston Breaker Block - broken OB flips to support",
        "when": "A bearish OB was violated by price (broken). Price returns to test the former OB zone as support. Flip = bullish breaker.",
        "direction": "LONG",
        "entry_anchor": "BREAKER_ZONE_TOP",
        "stop_anchor": "BELOW_BREAKER_ZONE_BOTTOM",
        "target_anchor": "NEXT_RESISTANCE_OR_SWING_HIGH",
    },
    "BREAKER_BLOCK_SHORT": {
        "name": "Bullish Order Block Broken - Breaker Block Short",
        "literature": "ICT/Huddleston Breaker Block - broken OB flips to resistance",
        "when": "A bullish OB was violated by price (broken). Price returns to test the former OB zone as resistance. Flip = bearish breaker.",
        "direction": "SHORT",
        "entry_anchor": "BREAKER_ZONE_BOTTOM",
        "stop_anchor": "ABOVE_BREAKER_ZONE_TOP",
        "target_anchor": "NEXT_SUPPORT_OR_SWING_LOW",
    },

    # ---- LIQUIDITY CONDITIONS ----
    "BSL_SWEEP_REVERSAL": {
        "name": "Buyside Liquidity (Equal Highs) Sweep Reversal Short",
        "literature": "ICT/Huddleston BSL/SSL - Equal highs = resting stop orders above",
        "when": "Equal highs swept (BSL taken). Market swept stop orders above equal highs. Reversal expected short into range.",
        "direction": "SHORT",
        "entry_anchor": "NEAREST_BEARISH_FVG_OR_OB_AFTER_SWEEP",
        "stop_anchor": "ABOVE_EQUAL_HIGH_LEVEL",
        "target_anchor": "EQUAL_LOWS_OR_VAL",
    },
    "SSL_SWEEP_REVERSAL": {
        "name": "Sellside Liquidity (Equal Lows) Sweep Reversal Long",
        "literature": "ICT/Huddleston BSL/SSL - Equal lows = resting stop orders below",
        "when": "Equal lows swept (SSL taken). Market swept stop orders below equal lows. Reversal expected long into range.",
        "direction": "LONG",
        "entry_anchor": "NEAREST_BULLISH_FVG_OR_OB_AFTER_SWEEP",
        "stop_anchor": "BELOW_EQUAL_LOW_LEVEL",
        "target_anchor": "EQUAL_HIGHS_OR_VAH",
    },
    "FVG_MULTI_TF_STACK_LONG": {
        "name": "Balanced Price Range (Multi-TF FVG Stack) Long",
        "literature": "ICT Balanced Price Range (BPR) - overlapping FVGs from multiple timeframes",
        "when": "FVGs from M15 and H1 overlap (Balanced Price Range). Institutional reference confluence. Highest probability support zone.",
        "direction": "LONG",
        "entry_anchor": "BPR_BOTTOM_CE",
        "stop_anchor": "BELOW_BPR_BOTTOM",
        "target_anchor": "BPR_TOP_PLUS_MEASURED_MOVE",
    },
    "FVG_MULTI_TF_STACK_SHORT": {
        "name": "Balanced Price Range (Multi-TF FVG Stack) Short",
        "literature": "ICT Balanced Price Range (BPR) - overlapping FVGs from multiple timeframes",
        "when": "FVGs from M15 and H1 overlap above price (Balanced Price Range). Institutional reference confluence. Highest probability resistance zone.",
        "direction": "SHORT",
        "entry_anchor": "BPR_TOP_CE",
        "stop_anchor": "ABOVE_BPR_TOP",
        "target_anchor": "BPR_BOTTOM_MINUS_MEASURED_MOVE",
    },

    # ---- FIBONACCI CONDITIONS ----
    "FIBONACCI_GOLDEN_ZONE_LONG": {
        "name": "Fibonacci Golden Zone 61.8-78.6 Retracement Long",
        "literature": "Pesavento 'Fibonacci Ratios with Pattern Recognition' (1997) + Carney harmonic context",
        "when": "Price retracing into 61.8%-78.6% Fibonacci zone of prior bullish swing with confluence (FVG/OB/VA level). Golden pocket = highest reversal probability.",
        "direction": "LONG",
        "entry_anchor": "FIBONACCI_61_8_LEVEL",
        "stop_anchor": "BELOW_78_6_LEVEL",
        "target_anchor": "PRIOR_SWING_HIGH_OR_127_EXTENSION",
    },
    "FIBONACCI_GOLDEN_ZONE_SHORT": {
        "name": "Fibonacci Golden Zone 61.8-78.6 Retracement Short",
        "literature": "Pesavento 'Fibonacci Ratios with Pattern Recognition' (1997)",
        "when": "Price retracing up into 61.8%-78.6% Fibonacci zone of prior bearish swing with confluence. Highest reversal probability zone.",
        "direction": "SHORT",
        "entry_anchor": "FIBONACCI_61_8_LEVEL",
        "stop_anchor": "ABOVE_78_6_LEVEL",
        "target_anchor": "PRIOR_SWING_LOW_OR_127_EXTENSION",
    },

    # ---- HARMONIC CONDITIONS ----
    "HARMONIC_ABCD_LONG": {
        "name": "AB=CD Harmonic Completion Long",
        "literature": "Carney 'Harmonic Trading Vol 1' (2010) - AB=CD the most fundamental harmonic",
        "when": "AB=CD completion at D point in discount (below VAL or at key support). CD leg equals AB leg. Price has completed the pattern. Reversal up expected.",
        "direction": "LONG",
        "entry_anchor": "ABCD_D_POINT",
        "stop_anchor": "BELOW_D_POINT_BY_BUFFER",
        "target_anchor": "A_POINT_OR_B_RETRACEMENT",
    },
    "HARMONIC_ABCD_SHORT": {
        "name": "AB=CD Harmonic Completion Short",
        "literature": "Carney 'Harmonic Trading Vol 1' (2010)",
        "when": "AB=CD completion at D point in premium (above VAH or at key resistance). Reversal down expected.",
        "direction": "SHORT",
        "entry_anchor": "ABCD_D_POINT",
        "stop_anchor": "ABOVE_D_POINT_BY_BUFFER",
        "target_anchor": "A_POINT_OR_B_RETRACEMENT",
    },

    # ---- WYCKOFF FULL PHASE CONDITIONS ----
    "WYCKOFF_PHASE_C_SECONDARY_TEST_LONG": {
        "name": "Wyckoff Phase C Secondary Test of Spring Long",
        "literature": "Wyckoff (1930), Pruden (2007) - Phase C secondary test = lower-risk Spring re-entry",
        "when": "After Spring (Phase C), price returns to test the Spring low at higher low (secondary test). Lower risk entry than the Spring itself. Accumulation confirmed.",
        "direction": "LONG",
        "entry_anchor": "SECONDARY_TEST_LOW_PLUS_BUFFER",
        "stop_anchor": "BELOW_SPRING_LOW",
        "target_anchor": "VAH_OR_RESISTANCE",
    },
    "WYCKOFF_PHASE_C_SECONDARY_TEST_SHORT": {
        "name": "Wyckoff Phase C Secondary Test of UTAD Short",
        "literature": "Wyckoff (1930), Pruden (2007) - Phase C secondary test of UTAD = lower-risk distribution entry",
        "when": "After UTAD (Phase C), price rallies to test UTAD high at lower high (secondary test). Distribution confirmed. Short into markup failure.",
        "direction": "SHORT",
        "entry_anchor": "SECONDARY_TEST_HIGH_MINUS_BUFFER",
        "stop_anchor": "ABOVE_UTAD_HIGH",
        "target_anchor": "VAL_OR_SUPPORT",
    },
    "WYCKOFF_PHASE_D_MARKUP_LONG": {
        "name": "Wyckoff Phase D Sign of Strength (SOS) Pullback Long",
        "literature": "Wyckoff (1930) - Phase D SOS = first impulsive move up from accumulation. Pull back to Last Point of Support (LPS).",
        "when": "Phase D markup begun (SOS BOS confirmed). Price pulling back to Last Point of Support. Enter long on LPS retest.",
        "direction": "LONG",
        "entry_anchor": "LAST_POINT_OF_SUPPORT_LPS",
        "stop_anchor": "BELOW_LPS",
        "target_anchor": "MEASURED_MOVE_EQUAL_TO_CAUSE",
    },
    "WYCKOFF_PHASE_D_MARKDOWN_SHORT": {
        "name": "Wyckoff Phase D Sign of Weakness (SOW) Pullback Short",
        "literature": "Wyckoff (1930) - Phase D SOW = first impulsive move down from distribution. Pull back to Last Point of Supply (LPSY).",
        "when": "Phase D markdown begun (SOW BOS confirmed). Price pulling back up to Last Point of Supply. Enter short on LPSY retest.",
        "direction": "SHORT",
        "entry_anchor": "LAST_POINT_OF_SUPPLY_LPSY",
        "stop_anchor": "ABOVE_LPSY",
        "target_anchor": "MEASURED_MOVE_DOWN_EQUAL_TO_CAUSE",
    },

    # ---- ELLIOTT WAVE CONDITIONS ----
    "ELLIOTT_WAVE3_LONG": {
        "name": "Elliott Wave 3 Long - Strongest Wave",
        "literature": "Prechter & Frost 'Elliott Wave Principle' (2005) - Wave 3 = extended impulse, never shortest",
        "when": "Wave 3 of bullish impulse identified. Wave 3 is the strongest, fastest wave. Enter after Wave 2 correction completes at Fibonacci retracement.",
        "direction": "LONG",
        "entry_anchor": "WAVE2_BOTTOM_OR_FIB_RETRACEMENT",
        "stop_anchor": "BELOW_WAVE1_TOP",
        "target_anchor": "WAVE3_PROJECTION_161_EXTENSION",
    },
    "ELLIOTT_WAVE3_SHORT": {
        "name": "Elliott Wave 3 Short - Strongest Bearish Wave",
        "literature": "Prechter & Frost (2005) - Wave 3 bearish impulse",
        "when": "Wave 3 of bearish impulse identified. Strongest move down. Enter after Wave 2 correction at Fibonacci retracement.",
        "direction": "SHORT",
        "entry_anchor": "WAVE2_TOP_OR_FIB_RETRACEMENT",
        "stop_anchor": "ABOVE_WAVE1_BOTTOM",
        "target_anchor": "WAVE3_PROJECTION_161_EXTENSION",
    },
    "ELLIOTT_WAVE_C_COMPLETION_LONG": {
        "name": "Elliott Wave C Completion - Corrective End Long",
        "literature": "Prechter & Frost (2005) - Wave C = final leg of A-B-C correction, reversal follows",
        "when": "Wave C of A-B-C corrective structure completing at support. End of correction = new impulse beginning long.",
        "direction": "LONG",
        "entry_anchor": "WAVE_C_COMPLETION_LEVEL",
        "stop_anchor": "BELOW_WAVE_C_BY_BUFFER",
        "target_anchor": "PRIOR_WAVE_A_HIGH_OR_EQUIVALENT",
    },
    "ELLIOTT_WAVE_C_COMPLETION_SHORT": {
        "name": "Elliott Wave C Completion - Corrective End Short",
        "literature": "Prechter & Frost (2005)",
        "when": "Wave C of bearish A-B-C corrective structure completing at resistance. End of correction = new impulse beginning short.",
        "direction": "SHORT",
        "entry_anchor": "WAVE_C_COMPLETION_LEVEL",
        "stop_anchor": "ABOVE_WAVE_C_BY_BUFFER",
        "target_anchor": "PRIOR_WAVE_A_LOW_OR_EQUIVALENT",
    },

    # ---- LEGACY V1 CONDITIONS (enhanced) ----
    "TREND_BOS_PULLBACK": V1_CONDITIONS["TREND_BOS_PULLBACK"],
    "LIQUIDITY_SWEEP_REVERSAL": V1_CONDITIONS["LIQUIDITY_SWEEP_REVERSAL"],
    "FVG_MITIGATION_RETURN": V1_CONDITIONS["FVG_MITIGATION_RETURN"],
    "VALUE_AREA_ROTATION_SHORT": V1_CONDITIONS["VALUE_AREA_ROTATION_SHORT"],
    "VALUE_AREA_ROTATION_LONG": V1_CONDITIONS["VALUE_AREA_ROTATION_LONG"],
    "VWAP_2SD_MEAN_REVERSION_SHORT": V1_CONDITIONS["VWAP_2SD_MEAN_REVERSION_SHORT"],
    "VWAP_2SD_MEAN_REVERSION_LONG": V1_CONDITIONS["VWAP_2SD_MEAN_REVERSION_LONG"],
    "WYCKOFF_SPRING_REVERSAL": V1_CONDITIONS["WYCKOFF_SPRING_REVERSAL"],
    "WYCKOFF_UTAD_REVERSAL": V1_CONDITIONS["WYCKOFF_UTAD_REVERSAL"],
    "COMPRESSION_BREAKOUT_LONG": V1_CONDITIONS["COMPRESSION_BREAKOUT_LONG"],
    "COMPRESSION_BREAKOUT_SHORT": V1_CONDITIONS["COMPRESSION_BREAKOUT_SHORT"],

    # ---- NO TRADE ----
    "DEAD_ZONE_NO_CONDITION": V1_CONDITIONS["DEAD_ZONE_NO_CONDITION"],
}


class RegimeBrainV2:
    """
    Full quantitative market regime brain v2.
    9 analytical modules. 32 named conditions.
    No hand-written heuristics — every condition backed by published research.
    """

    def classify(self, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        # ---- Extract all telemetry ----
        price = float(telemetry.get("live_price", 0.0))
        bid = float(telemetry.get("bid", price))
        ask = float(telemetry.get("ask", price))
        vah = float(telemetry.get("vah", price + 5))
        val = float(telemetry.get("val", price - 5))
        poc = float(telemetry.get("poc", price))
        vwap = float(telemetry.get("vwap", poc))
        v1su = float(telemetry.get("vwap_1sd_upper", vwap + 5))
        v1sl = float(telemetry.get("vwap_1sd_lower", vwap - 5))
        v2su = float(telemetry.get("vwap_2sd_upper", vwap + 10))
        v2sl = float(telemetry.get("vwap_2sd_lower", vwap - 10))
        cvd_10b = float(telemetry.get("cvd_10b", 0.0))
        cvd_cum = float(telemetry.get("cvd_cumulative", 0.0))
        velocity_tpm = float(telemetry.get("velocity_tpm", 80.0))
        displacement = bool(telemetry.get("displacement", False))
        choch = str(telemetry.get("choch", ""))
        mtf_alignment = str(telemetry.get("mtf_alignment", ""))
        h4_rsi = float(telemetry.get("h4_rsi", 50.0))
        h1_rsi = float(telemetry.get("h1_rsi", 50.0))
        m15_rsi = float(telemetry.get("m15_rsi", 50.0))
        m5_rsi = float(telemetry.get("m5_rsi", 50.0))
        h4_ema20 = float(telemetry.get("h4_ema20", price))
        h4_ema50 = float(telemetry.get("h4_ema50", price))
        m15_ema20 = float(telemetry.get("m15_ema20", price))
        m15_ema50 = float(telemetry.get("m15_ema50", price))
        h1_ema20 = float(telemetry.get("h1_ema20", price))
        h1_ema50 = float(telemetry.get("h1_ema50", price))
        nearest_fvg = telemetry.get("nearest_fvg", {}) or {}
        price_history = telemetry.get("price_history", [price] * 50)
        asian_high = float(telemetry.get("asian_high", vah + 3))
        asian_low = float(telemetry.get("asian_low", val - 3))
        pdh = float(telemetry.get("pdh", vah + 8))
        pdl = float(telemetry.get("pdl", val - 8))
        live_spread_pts = float(telemetry.get("live_spread_pts", 40))
        cot_commercial_net = float(telemetry.get("cot_commercial_net", 0.0))
        cot_history = telemetry.get("cot_commercial_net_history", [cot_commercial_net] * 10)
        cot_large_spec_net = float(telemetry.get("cot_large_spec_net", 0.0))
        dxy_direction = str(telemetry.get("dxy_direction", "FLAT"))
        tips_change = float(telemetry.get("tips_yield_change", 0.0))

        fvg_type = str(nearest_fvg.get("type", "")).upper()
        fvg_ce = float(nearest_fvg.get("consequent_encroachment", 0.0) or 0.0)
        fvg_fill = float(nearest_fvg.get("fill_pct", 100.0) or 100.0)
        fvg_fresh = fvg_fill < 30.0 and fvg_ce > 0

        # ============================================================
        # RUN ALL 9 ANALYTICAL MODULES
        # ============================================================

        # 1. Hurst + OFI (v1 core)
        hurst = compute_hurst(price_history)
        ofi = compute_ofi(cvd_10b, velocity_tpm, cvd_cum)
        is_trending = hurst > 0.55
        is_mean_reverting = hurst < 0.45
        strong_buy_ofi = ofi > 0.25
        strong_sell_ofi = ofi < -0.25

        # 2. Wyckoff + AMT (v1 core)
        wyckoff = detect_wyckoff_phase(price, vah, val, poc, cvd_10b, velocity_tpm, displacement, choch)
        amt_day = classify_amt_day_type(price, vah, val, poc, vwap, v2su, v2sl, mtf_alignment, h4_rsi)
        vwap_regime, vwap_dev = classify_vwap_regime(price, vwap, v1su, v1sl, v2su, v2sl)

        # 3. Microstructure
        micro = microstructure_regime(cvd_10b, velocity_tpm, live_spread_pts, price_history)

        # 4. Volatility
        vol_analysis = full_volatility_analysis(price_history)
        vol_compressing = vol_analysis["is_compressing"]
        vol_expanding = vol_analysis["is_expanding"]

        # 5. Momentum
        mom = full_momentum_analysis(
            price_history,
            rsi_m15=m15_rsi, rsi_h1=h1_rsi, rsi_h4=h4_rsi,
            m5_ema20=price, m5_ema50=price,
            m15_ema20=m15_ema20, m15_ema50=m15_ema50,
            h1_ema20=h1_ema20, h1_ema50=h1_ema50,
            h4_ema20=h4_ema20, h4_ema50=h4_ema50,
        )
        div = mom["divergence"]
        tsmom = mom["tsmom_signal"]
        ema_align = mom["ema_alignment"]["ema_alignment"]

        # 6. Session (ICT)
        utc_now = datetime.now(timezone.utc)
        sess = session_analysis(
            price, cvd_10b, velocity_tpm, displacement, utc_now,
            asian_high=asian_high, asian_low=asian_low,
            pdh=pdh, pdl=pdl,
            session_open=poc,
            session_high=vah,
            session_low=val,
        )
        in_kz = sess["in_killzone"]
        kz = sess["killzone"]
        swept = sess["sweeps"]
        amd = sess["amd_phase"]

        # 7. Intermarket
        cot_data = cot_regime(cot_commercial_net, cot_large_spec_net, cot_history)
        dxy_bias = dxy_correlation_bias(dxy_direction)
        ry_bias = real_yields_bias(0.0, tips_change)
        macro = intermarket_bias(cot_data["cot_signal"], dxy_bias, ry_bias)

        # 8. Structure
        struct = structure_analysis(price_history, price, vah, val, poc, fvg_ce, fvg_type, fvg_fill)
        confluence = struct["pdarray_confluence"]
        nr7 = struct["nr7_coil"]
        last_sh = struct["last_swing_high"]
        last_sl = struct["last_swing_low"]

        # 9. Statistical
        stats = statistical_analysis(price, price_history, velocity_tpm)

        # 10. Order Blocks & Breakers (Real OHLC rates)
        rates_list = []
        opens = telemetry.get("open_history", [])
        highs = telemetry.get("high_history", [])
        lows = telemetry.get("low_history", [])
        closes = telemetry.get("price_history", [])
        vols = telemetry.get("volume_history", [])
        for k in range(min(len(opens), len(highs), len(lows), len(closes))):
            rates_list.append({
                "open": opens[k], "high": highs[k], "low": lows[k], "close": closes[k],
                "tick_volume": vols[k] if k < len(vols) else 100
            })

        order_blocks = find_order_blocks(rates_list, price) if _HAS_OB and rates_list else []
        breaker_blocks = find_breaker_blocks(order_blocks, price) if _HAS_OB else []
        nearest_bull_ob, nearest_bear_ob = get_nearest_ob(order_blocks, price) if _HAS_OB else (None, None)

        # 11. Liquidity & Fibonacci Map
        all_fvgs = telemetry.get("all_fvgs", [])
        liq_map = full_liquidity_analysis(price_history, price, all_fvgs, vah, val, poc, last_sh, last_sl) if _HAS_LIQUIDITY else {}
        swept_eq = liq_map.get("sweeps", {})
        fib_conf = liq_map.get("fib_confluence", {})
        bpr_stacks = liq_map.get("bpr_stacks", [])

        # 12. Full Wyckoff Analysis (Phases A-E)
        wyckoff_full = classify_wyckoff_phase_full(
            price_history, highs, lows, vah, val, poc, cvd_10b, velocity_tpm, displacement, choch, last_sh, last_sl
        ) if _HAS_WYCKOFF_FULL else {}

        # 13. Elliott Wave Structure
        ew_analysis = elliott_wave_analysis(price_history) if _HAS_ELLIOTT else {}

        # ============================================================
        # CONDITION RESOLUTION TREE — 32 Conditions, Priority Order
        # ============================================================
        cid = None

        # === TIER 0: LIQUIDITY SWEEP & BREAKER REVERSALS (Highest Confluence Stops Run) ===
        if _HAS_LIQUIDITY and swept_eq.get("is_swept", False):
            for sw in swept_eq.get("swept_details", []):
                if sw["type"] == "BSL_SWEPT" and (strong_sell_ofi or cvd_10b < -50):
                    cid = "BSL_SWEEP_REVERSAL"
                    break
                elif sw["type"] == "SSL_SWEPT" and (strong_buy_ofi or cvd_10b > 50):
                    cid = "SSL_SWEEP_REVERSAL"
                    break

        # Breaker Block Reclaims
        elif _HAS_OB and breaker_blocks:
            for brk in breaker_blocks:
                if brk["type"] == "BULLISH_BREAKER" and abs(price - brk["support_level"]) <= 2.5 and not strong_sell_ofi:
                    cid = "BREAKER_BLOCK_LONG"
                    break
                elif brk["type"] == "BEARISH_BREAKER" and abs(price - brk["resistance_level"]) <= 2.5 and not strong_buy_ofi:
                    cid = "BREAKER_BLOCK_SHORT"
                    break

        # Balanced Price Range (Multi-TF FVG Stack)
        elif _HAS_LIQUIDITY and bpr_stacks and not cid:
            for bpr in bpr_stacks:
                if abs(price - bpr["ce_avg"]) <= 3.0:
                    cid = "FVG_MULTI_TF_STACK_LONG" if price >= bpr["ce_avg"] else "FVG_MULTI_TF_STACK_SHORT"
                    break

        # Order Block Mitigation
        elif _HAS_OB and nearest_bull_ob and abs(price - nearest_bull_ob["top"]) <= 2.0 and not strong_sell_ofi:
            cid = "OB_BULLISH_MITIGATION"
        elif _HAS_OB and nearest_bear_ob and abs(price - nearest_bear_ob["bottom"]) <= 2.0 and not strong_buy_ofi:
            cid = "OB_BEARISH_MITIGATION"

        # Full Wyckoff Phase C & D
        elif _HAS_WYCKOFF_FULL and wyckoff_full.get("phase") == "PHASE_C_SPRING":
            cid = "WYCKOFF_SPRING_REVERSAL"
        elif _HAS_WYCKOFF_FULL and wyckoff_full.get("phase") == "PHASE_C_UTAD":
            cid = "WYCKOFF_UTAD_REVERSAL"
        elif _HAS_WYCKOFF_FULL and wyckoff_full.get("phase") == "PHASE_D_MARKUP":
            cid = "WYCKOFF_PHASE_D_MARKUP_LONG"
        elif _HAS_WYCKOFF_FULL and wyckoff_full.get("phase") == "PHASE_D_MARKDOWN":
            cid = "WYCKOFF_PHASE_D_MARKDOWN_SHORT"

        # Elliott Wave Impulse / Correction
        elif _HAS_ELLIOTT and ew_analysis.get("is_wave3_opportunity", False) and ew_analysis.get("direction") == "BULLISH" and not strong_sell_ofi:
            cid = "ELLIOTT_WAVE3_LONG"
        elif _HAS_ELLIOTT and ew_analysis.get("is_wave3_opportunity", False) and ew_analysis.get("direction") == "BEARISH" and not strong_buy_ofi:
            cid = "ELLIOTT_WAVE3_SHORT"
        elif _HAS_ELLIOTT and ew_analysis.get("is_wave_c_complete", False) and price < val and not strong_sell_ofi:
            cid = "ELLIOTT_WAVE_C_COMPLETION_LONG"
        elif _HAS_ELLIOTT and ew_analysis.get("is_wave_c_complete", False) and price > vah and not strong_buy_ofi:
            cid = "ELLIOTT_WAVE_C_COMPLETION_SHORT"

        # Fibonacci Golden Zone (61.8% - 78.6%)
        elif _HAS_LIQUIDITY and fib_conf.get("in_golden_zone", False) and price < val and not strong_sell_ofi:
            cid = "FIBONACCI_GOLDEN_ZONE_LONG"
        elif _HAS_LIQUIDITY and fib_conf.get("in_golden_zone", False) and price > vah and not strong_buy_ofi:
            cid = "FIBONACCI_GOLDEN_ZONE_SHORT"

        # === TIER 1: ICT SESSION (highest intraday specificity) ===
        london_kz = "LONDON" in kz
        ny_kz = "NY" in kz

        if london_kz and swept.get("swept_asian_low") and fvg_fresh and (strong_buy_ofi or cvd_10b > 200):
            cid = "ICT_LONDON_SWEEP_LONG"
        elif london_kz and swept.get("swept_asian_high") and fvg_fresh and (strong_sell_ofi or cvd_10b < -200):
            cid = "ICT_LONDON_SWEEP_SHORT"
        elif ny_kz and displacement and fvg_fresh and strong_buy_ofi and h1_rsi < 65:
            cid = "ICT_NY_REVERSAL_LONG"
        elif ny_kz and displacement and fvg_fresh and strong_sell_ofi and h1_rsi > 35:
            cid = "ICT_NY_REVERSAL_SHORT"

        # === TIER 2: VOLATILITY BREAKOUT (clear structural signals) ===
        elif vol_compressing and nr7 and displacement and velocity_tpm > 130 and price > vah:
            cid = "VOLATILITY_COMPRESSION_BREAKOUT_LONG"
        elif vol_compressing and nr7 and displacement and velocity_tpm > 130 and price < val:
            cid = "VOLATILITY_COMPRESSION_BREAKOUT_SHORT"
        elif vol_expanding and displacement and fvg_fresh:
            cid = "VOLATILITY_EXPANSION_CONTINUATION"

        # === TIER 3: WYCKOFF (structural extremes) ===
        elif wyckoff == "WYCKOFF_ACCUMULATION_SPRING":
            cid = "WYCKOFF_SPRING_REVERSAL"
        elif wyckoff == "WYCKOFF_DISTRIBUTION_UTAD":
            cid = "WYCKOFF_UTAD_REVERSAL"

        # === TIER 4: DIVERGENCE (momentum exhaustion) ===
        elif div["regular_bullish"] and (price < val or vwap_regime == "VWAP_EXTREME_DISCOUNT_BUY"):
            cid = "REGULAR_DIVERGENCE_REVERSAL_LONG"
        elif div["regular_bearish"] and (price > vah or vwap_regime == "VWAP_EXTREME_PREMIUM_SELL"):
            cid = "REGULAR_DIVERGENCE_REVERSAL_SHORT"
        elif div["hidden_bullish"] and is_trending and not strong_sell_ofi:
            cid = "HIDDEN_DIVERGENCE_CONTINUATION_LONG"
        elif div["hidden_bearish"] and is_trending and not strong_buy_ofi:
            cid = "HIDDEN_DIVERGENCE_CONTINUATION_SHORT"

        # === TIER 5: VWAP 2-SIGMA EXTREME ===
        elif vwap_regime == "VWAP_EXTREME_PREMIUM_SELL" and is_mean_reverting and not strong_buy_ofi:
            cid = "VWAP_2SD_MEAN_REVERSION_SHORT"
        elif vwap_regime == "VWAP_EXTREME_DISCOUNT_BUY" and is_mean_reverting and not strong_sell_ofi:
            cid = "VWAP_2SD_MEAN_REVERSION_LONG"

        # === TIER 6: TSMOM TREND (multi-bar directional momentum) ===
        elif tsmom == "TSMOM_LONG" and ema_align in ("FULL_BULL_4TF", "BULL_LEANING_3TF") and not strong_sell_ofi:
            cid = "TSMOM_LONG_SIGNAL"
        elif tsmom == "TSMOM_SHORT" and ema_align in ("FULL_BEAR_4TF", "BEAR_LEANING_3TF") and not strong_buy_ofi:
            cid = "TSMOM_SHORT_SIGNAL"

        # === TIER 7: COT EXTREME (macro positioning, highest trust) ===
        elif cot_data["cot_index"] > 85 and macro["net_macro_bias"] != "MACRO_BEARISH" and fvg_fresh:
            cid = "COT_COMMERCIAL_EXTREME_LONG"
        elif cot_data["cot_index"] < 15 and macro["net_macro_bias"] != "MACRO_BULLISH" and fvg_fresh:
            cid = "COT_COMMERCIAL_EXTREME_SHORT"

        # === TIER 8: STATISTICAL EXTREME ===
        elif stats["statistical_long_signal"] and stats["fast_mean_reversion"]:
            cid = "STATISTICAL_EXTREME_REVERSAL_LONG"
        elif stats["statistical_short_signal"] and stats["fast_mean_reversion"]:
            cid = "STATISTICAL_EXTREME_REVERSAL_SHORT"

        # === TIER 9: CONFLUENCE STACK ===
        elif confluence["is_high_confluence"] and confluence["confluence_bias"] == "LONG" and not strong_sell_ofi:
            cid = "PDARRAY_TRIPLE_CONFLUENCE_LONG"
        elif confluence["is_high_confluence"] and confluence["confluence_bias"] == "SHORT" and not strong_buy_ofi:
            cid = "PDARRAY_TRIPLE_CONFLUENCE_SHORT"

        # === TIER 10: TREND BOS + FVG (displacement + retest) ===
        elif displacement and fvg_fresh and is_trending:
            cid = "TREND_BOS_PULLBACK"

        # === TIER 11: FRESH FVG MITIGATION ===
        elif fvg_fresh and abs(price - fvg_ce) <= 8.0:
            cid = "FVG_MITIGATION_RETURN"

        # === TIER 12: VALUE AREA ROTATION (Dalton 80%) ===
        elif price > vah and is_mean_reverting and not strong_buy_ofi:
            cid = "VALUE_AREA_ROTATION_SHORT"
        elif price < val and is_mean_reverting and not strong_sell_ofi:
            cid = "VALUE_AREA_ROTATION_LONG"

        # === DEAD ZONE ===
        else:
            cid = "DEAD_ZONE_NO_CONDITION"

        meta = FULL_CONDITIONS.get(cid, FULL_CONDITIONS["DEAD_ZONE_NO_CONDITION"])

        return {
            "condition_id": cid,
            "condition_name": meta["name"],
            "literature": meta["literature"],
            "when_description": meta["when"],
            "direction": meta["direction"],
            "entry_anchor": meta["entry_anchor"],
            "stop_anchor": meta["stop_anchor"],
            "target_anchor": meta["target_anchor"],
            "brain_modules": {
                "hurst": round(hurst, 3),
                "hurst_regime": "TRENDING" if is_trending else ("MEAN_REVERTING" if is_mean_reverting else "RANDOM_WALK"),
                "ofi": round(ofi, 3),
                "ofi_signal": "BUY_PRESSURE" if ofi > 0.15 else ("SELL_PRESSURE" if ofi < -0.15 else "NEUTRAL"),
                "wyckoff": wyckoff,
                "amt_day": amt_day,
                "vwap_regime": vwap_regime,
                "vol_regime": vol_analysis["vol_regime"],
                "vol_z": vol_analysis["vol_z_score"],
                "tsmom": tsmom,
                "ema_alignment": ema_align,
                "divergence": div["divergence_type"],
                "killzone": kz,
                "in_killzone": in_kz,
                "amd_phase": amd,
                "cot_index": cot_data["cot_index"],
                "macro_bias": macro["net_macro_bias"],
                "confluence_count": confluence["confluence_count"],
                "nr7_coil": nr7,
                "price_zscore": stats["price_zscore"],
                "ou_halflife": stats["ou_halflife_bars"],
            },
        }
