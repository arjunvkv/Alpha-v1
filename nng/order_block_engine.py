# -*- coding: utf-8 -*-
# nng/order_block_engine.py - Order Block and Breaker Block Engine
#
# Sources:
#   ICT (Michael J. Huddleston) - Institutional Order Block & Breaker Block concepts
#   Harris (2003) - Trading and Exchanges: Market Microstructure for Practitioners

from typing import List, Dict, Any, Optional, Tuple

def find_order_blocks(rates_list: List[Dict[str, Any]], current_price: float) -> List[Dict[str, Any]]:
    if not rates_list or len(rates_list) < 5:
        return []

    order_blocks = []
    n = len(rates_list)

    for i in range(1, n - 2):
        prev_bar = rates_list[i]
        bar1 = rates_list[i + 1]
        bar2 = rates_list[i + 2]

        o = float(prev_bar.get("open", 0.0))
        c = float(prev_bar.get("close", 0.0))
        h = float(prev_bar.get("high", 0.0))
        l = float(prev_bar.get("low", 0.0))
        vol = float(prev_bar.get("tick_volume", 1.0))

        if h <= l:
            continue

        bar_range = h - l
        ce = (h + l) / 2.0

        if c < o:
            c2 = float(bar2.get("close", 0.0))
            displacement = (c2 > h) and ((c2 - l) > bar_range * 1.5)
            if displacement:
                is_fresh = True
                is_broken = False
                for j in range(i + 3, n):
                    bj_low = float(rates_list[j].get("low", 0.0))
                    if bj_low < l:
                        is_broken = True
                        is_fresh = False
                        break
                    elif bj_low <= h:
                        is_fresh = False

                order_blocks.append({
                    "type": "BULLISH_OB",
                    "bar_index": i,
                    "top": round(h, 2),
                    "bottom": round(l, 2),
                    "ce": round(ce, 2),
                    "volume": vol,
                    "is_fresh": is_fresh,
                    "is_broken": is_broken,
                    "strength": round(vol * bar_range, 2)
                })
        elif c > o:
            c2 = float(bar2.get("close", 0.0))
            displacement = (c2 < l) and ((h - c2) > bar_range * 1.5)
            if displacement:
                is_fresh = True
                is_broken = False
                for j in range(i + 3, n):
                    bj_high = float(rates_list[j].get("high", 0.0))
                    if bj_high > h:
                        is_broken = True
                        is_fresh = False
                        break
                    elif bj_high >= l:
                        is_fresh = False

                order_blocks.append({
                    "type": "BEARISH_OB",
                    "bar_index": i,
                    "top": round(h, 2),
                    "bottom": round(l, 2),
                    "ce": round(ce, 2),
                    "volume": vol,
                    "is_fresh": is_fresh,
                    "is_broken": is_broken,
                    "strength": round(vol * bar_range, 2)
                })

    return order_blocks

def find_breaker_blocks(order_blocks: List[Dict[str, Any]], current_price: float) -> List[Dict[str, Any]]:
    breakers = []
    for ob in order_blocks:
        if not ob.get("is_broken", False):
            continue
        if ob["type"] == "BEARISH_OB":
            breakers.append({
                "type": "BULLISH_BREAKER",
                "original_type": ob["type"],
                "support_level": ob["top"],
                "zone_bottom": ob["bottom"],
                "ce": ob["ce"],
                "bar_index": ob["bar_index"]
            })
        elif ob["type"] == "BULLISH_OB":
            breakers.append({
                "type": "BEARISH_BREAKER",
                "original_type": ob["type"],
                "resistance_level": ob["bottom"],
                "zone_top": ob["top"],
                "ce": ob["ce"],
                "bar_index": ob["bar_index"]
            })
    return breakers

def get_nearest_ob(order_blocks: List[Dict[str, Any]], current_price: float) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    bullish_obs = [ob for ob in order_blocks if ob["type"] == "BULLISH_OB" and ob["top"] <= current_price and not ob["is_broken"]]
    bearish_obs = [ob for ob in order_blocks if ob["type"] == "BEARISH_OB" and ob["bottom"] >= current_price and not ob["is_broken"]]
    nearest_bull = max(bullish_obs, key=lambda x: x["top"]) if bullish_obs else None
    nearest_bear = min(bearish_obs, key=lambda x: x["bottom"]) if bearish_obs else None
    return nearest_bull, nearest_bear

def ob_confluence(ob_dict: Dict[str, Any], fvg_ce: float, vah: float, val: float, poc: float, tolerance: float = 2.0) -> bool:
    if not ob_dict:
        return False
    levels = [vah, val, poc]
    if fvg_ce > 0:
        levels.append(fvg_ce)
    ob_ce = ob_dict.get("ce", 0.0)
    for lvl in levels:
        if lvl > 0 and abs(ob_ce - lvl) <= tolerance:
            return True
    return False
