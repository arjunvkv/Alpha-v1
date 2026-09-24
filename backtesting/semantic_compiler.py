"""Semantic Query Compiler for Quantitative Structural Backtesting.

Parses arbitrary natural-language trading theses into exact mathematical execution parameters.
Handles both:
  1. Explicit Candidate Order Replay (exact entry price, SL price, TP price, or point buffers)
  2. Institutional Pattern Discovery:
     - FVG Mitigation (CE 50% vs boundary)
     - Order Block & Breaker Block Retests
     - Liquidity Sweeps & Turtle Soup Reclaims (Session high/low, BSL/SSL)
     - Breakout Expansion & Stop Runs (BOS / swing breakouts)
     - Trend EMA Pullbacks (EMA20 / EMA50 continuation)
     - Custom Level Reversals & Rejections
"""

import re
from typing import Dict, Any, Optional

class SemanticThesisCompiler:
    """Translates free-form trading queries into structured backtest configurations."""

    @staticmethod
    def _has_token(tokens: list, text: str) -> bool:
        """Robust token search preventing false substring collisions on short acronyms like 'ob' or 'ce'."""
        for t in tokens:
            if len(t) <= 3:
                if re.search(r'\b' + re.escape(t) + r'\b', text, re.IGNORECASE):
                    return True
            else:
                if t.lower() in text.lower():
                    return True
        return False

    @classmethod
    def compile_thesis(cls, query: str) -> Dict[str, Any]:
        q_lower = query.lower()

        # 1. Determine Direction
        bullish_tokens = [
            "bull", "long", "buy", "demand", "sweep low", "asian low",
            "expansion up", "bounce", "spring", "support", "rally", "discount", "hammer"
        ]
        bearish_tokens = [
            "bear", "short", "sell", "supply", "sweep high", "asian high",
            "expansion down", "rejection", "utad", "resistance", "drop", "premium", "shooting star"
        ]

        has_bull = cls._has_token(bullish_tokens, q_lower)
        has_bear = cls._has_token(bearish_tokens, q_lower)

        if has_bull and not has_bear:
            direction = "BULLISH"
        elif has_bear and not has_bull:
            direction = "BEARISH"
        else:
            if "short" in q_lower or "sell" in q_lower:
                direction = "BEARISH"
            elif "long" in q_lower or "buy" in q_lower:
                direction = "BULLISH"
            else:
                direction = "BOTH"

        # 2. Determine Entry Style
        entry_style = "LIMIT"
        if cls._has_token(["breakout", "breakdown", "stop order", "buy stop", "sell stop", "buy_stop", "sell_stop", "buy-stop", "sell-stop"], q_lower):
            entry_style = "STOP"
        elif cls._has_token(["market", "immediate", "close", "instant", "at market", "pin bar", "pinbar", "rejection wick", "hammer", "shooting star"], q_lower):
            entry_style = "MARKET"

        # 3. Robust Coordinate & Level Extraction
        # Look for explicit absolute entry price (e.g. at 4273.2, @ 4480, entry 4265.5, below 4270)
        entry_price = None
        entry_patterns = [
            r'(?:at|@|entry|price|level|below|above|breakout|breakdown)\s*[:=]?\s*(\d{3,5}(?:\.\d+)?)',
            r'\b(?:buy|sell)\s+(?:limit|stop|order)\s+(?:at\s+|@\s*)?(\d{3,5}(?:\.\d+)?)',
            r'\b(?:limit|stop)\s+(?:at\s+|@\s*)?(\d{3,5}(?:\.\d+)?)'
        ]
        for ep in entry_patterns:
            m = re.search(ep, q_lower)
            if m:
                try:
                    entry_price = float(m.group(1))
                    break
                except ValueError:
                    pass

        # Look for Stop Loss (distinguishing point buffers vs absolute prices)
        sl_points = None
        sl_price = None

        sl_pts_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:pt|pts|point|points)\s*(?:of\s*)?sl\b', q_lower) or \
                   re.search(r'\bsl\b\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:pt|pts|point|points)\b', q_lower) or \
                   re.search(r'(\d+(?:\.\d+)?)\s*(?:pt|pts|point|points)\s*(?:stop|buffer)\b', q_lower)
        if sl_pts_m:
            try:
                sl_points = float(sl_pts_m.group(1))
            except ValueError:
                pass

        sl_price_m = re.search(r'\b(?:sl|stop loss|stop|invalidation)\b\s*[:=]?\s*(\d{3,5}(?:\.\d+)?)', q_lower)
        if sl_price_m and not sl_pts_m:
            try:
                cand_sl = float(sl_price_m.group(1))
                # Validate it looks like an absolute price level
                if cand_sl > 500:
                    sl_price = cand_sl
                elif cand_sl > 0:
                    sl_points = cand_sl
            except ValueError:
                pass

        # Look for Take Profit (distinguishing point buffers vs absolute prices)
        tp_points = None
        tp_price = None

        tp_pts_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:pt|pts|point|points)\s*(?:of\s*)?tp\b', q_lower) or \
                   re.search(r'\btp\b\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:pt|pts|point|points)\b', q_lower) or \
                   re.search(r'(\d+(?:\.\d+)?)\s*(?:pt|pts|point|points)\s*(?:target)\b', q_lower)
        if tp_pts_m:
            try:
                tp_points = float(tp_pts_m.group(1))
            except ValueError:
                pass

        tp_price_m = re.search(r'\b(?:tp|take profit|target)\b\s*[:=]?\s*(\d{3,5}(?:\.\d+)?)', q_lower)
        if tp_price_m and not tp_pts_m:
            try:
                cand_tp = float(tp_price_m.group(1))
                if cand_tp > 500:
                    tp_price = cand_tp
                elif cand_tp > 0:
                    tp_points = cand_tp
            except ValueError:
                pass

        # 4. Reconcile Absolute Coordinates & Point Buffers
        if entry_price is not None:
            if sl_price is not None and sl_points is None:
                sl_points = round(abs(entry_price - sl_price), 2)
                if direction == "BOTH":
                    direction = "BULLISH" if entry_price > sl_price else "BEARISH"
            elif sl_points is not None and sl_price is None:
                sl_price = round(entry_price - sl_points, 2) if direction == "BULLISH" else round(entry_price + sl_points, 2)

            if tp_price is not None and tp_points is None:
                tp_points = round(abs(tp_price - entry_price), 2)
            elif tp_points is not None and tp_price is None:
                tp_price = round(entry_price + tp_points, 2) if direction == "BULLISH" else round(entry_price - tp_points, 2)

        # 5. Determine Setup Family
        if entry_price is not None:
            setup_type = "EXPLICIT_ORDER_REPLAY"
        elif cls._has_token(["breaker", "breaker block", "s/r flip", "flip"], q_lower):
            setup_type = "BREAKER_BLOCK"
        elif cls._has_token(["pin bar", "pinbar", "rejection wick", "hammer", "shooting star", "wick rejection", "absorption pin"], q_lower):
            setup_type = "REJECTION_WICK"
        elif cls._has_token(["order block", "orderblock", "ob", "demand zone", "supply zone", "demand shelf", "supply shelf", "order block retest"], q_lower):
            setup_type = "ORDER_BLOCK"
        elif cls._has_token(["sweep", "turtle soup", "liquidity hunt", "stop run", "spring", "utad", "asian low", "asian high"], q_lower):
            setup_type = "TURTLE_SOUP_SWEEP"
        elif cls._has_token(["breakout", "breakdown", "expansion", "bos", "choch", "momentum", "break"], q_lower):
            setup_type = "BREAKOUT_EXPANSION"
        elif cls._has_token(["ema", "moving average", "trend pullback", "20ema", "50ema"], q_lower):
            setup_type = "TREND_EMA_PULLBACK"
        elif cls._has_token(["fvg", "fair value", "imbalance", "consequent encroachment", "ce"], q_lower):
            setup_type = "FVG_MITIGATION"
        else:
            setup_type = "FVG_MITIGATION"

        # 6. Extract Target R:R
        target_rr = 2.0
        if sl_points and tp_points and sl_points > 0:
            target_rr = round(tp_points / sl_points, 2)
        else:
            rr_match = re.search(r"(\d+(?:\.\d+)?)\s*(?::\s*1|r|rrr)", q_lower)
            if rr_match:
                try:
                    target_rr = float(rr_match.group(1))
                except ValueError:
                    pass
            else:
                inv_rr = re.search(r"1\s*:\s*(\d+(?:\.\d+)?)", q_lower)
                if inv_rr:
                    try:
                        target_rr = float(inv_rr.group(1))
                    except ValueError:
                        pass

        # 7. Clamp & Sanitize Point Buffers for Pattern Setups
        # Prevents accidental absolute price contamination into pattern scanners
        sanitized_sl_points = sl_points
        if sanitized_sl_points is not None and sanitized_sl_points > 50.0:
            sanitized_sl_points = None

        sanitized_tp_points = tp_points
        if sanitized_tp_points is not None and sanitized_tp_points > 150.0:
            sanitized_tp_points = None

        return {
            "query": query,
            "direction": direction,
            "setup_type": setup_type,
            "entry_style": entry_style,
            "entry_price": entry_price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "target_rr": max(1.5, target_rr),
            "sl_points": sanitized_sl_points,
            "tp_points": sanitized_tp_points,
            "max_fill_bars": 25,
            "max_hold_bars": 35
        }
