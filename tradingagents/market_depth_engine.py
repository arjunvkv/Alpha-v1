"""
ALPHA V1 - LEVEL 2 MARKET DEPTH & ORDER BOOK ENGINE
Provides institutional Level 2 resting limit order book vision:
1. Local Broker DOM (FTMO MT5 native C-IPC, zero network latency)
2. Global Central Resting Order Book (Binance PAXG/USDT 1:1 Physical Gold)
"""

import os
import time
import json
import logging
import urllib.request
import concurrent.futures
from typing import Dict, Any, List, Optional
import MetaTrader5 as mt5

LOG = logging.getLogger("alpha.market_depth")
FTMO_PATH = r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"

_GLOBAL_DEPTH_CACHE: Optional[Dict[str, Any]] = None
_GLOBAL_DEPTH_TS: float = 0.0
_DEPTH_CACHE_TTL: float = 4.0


class MarketDepthEngine:
    """Combines local broker MT5 Level 2 DOM with global centralized order book depth."""

    def __init__(self, ftmo_path: Optional[str] = None):
        self.ftmo_path = ftmo_path or FTMO_PATH
        self._dom_subscribed: Dict[str, bool] = {}

    def _ensure_mt5(self) -> bool:
        try:
            if mt5.terminal_info() is not None:
                return True
            if os.path.exists(self.ftmo_path):
                return mt5.initialize(path=self.ftmo_path)
            return mt5.initialize()
        except Exception as err:
            LOG.error(f"MT5 init failed in MarketDepthEngine: {err}")
            return False

    def get_broker_dom(self, symbol: str = "XAUUSD") -> Dict[str, Any]:
        """Fetch local Level 2 Depth of Market directly from MT5 RAM via C-IPC."""
        sym = symbol.strip().upper()
        if not self._ensure_mt5():
            return {"status": "MT5_UNAVAILABLE", "dom_imbalance": 0.0}

        try:
            if not self._dom_subscribed.get(sym):
                res = mt5.market_book_add(sym)
                self._dom_subscribed[sym] = bool(res)
                if res:
                    time.sleep(0.08)

            book = mt5.market_book_get(sym)
            if not book:
                time.sleep(0.05)
                book = mt5.market_book_get(sym)

            if not book:
                return {
                    "status": "NO_DOM_DATA",
                    "total_bid_lots": 0.0,
                    "total_ask_lots": 0.0,
                    "dom_imbalance": 0.0,
                    "top_bid_wall": None,
                    "top_ask_wall": None,
                    "bids": [],
                    "asks": []
                }

            bids = []
            asks = []
            for b in book:
                if b.type == 2:  # BOOK_TYPE_BUY
                    bids.append({"price": round(float(b.price), 2), "lots": round(float(b.volume_dbl), 2)})
                elif b.type == 1:  # BOOK_TYPE_SELL
                    asks.append({"price": round(float(b.price), 2), "lots": round(float(b.volume_dbl), 2)})

            total_bid_lots = sum(b["lots"] for b in bids)
            total_ask_lots = sum(a["lots"] for a in asks)
            tot = total_bid_lots + total_ask_lots
            imbalance = (total_bid_lots - total_ask_lots) / tot if tot > 0 else 0.0

            top_bid_wall = max(bids, key=lambda x: x["lots"]) if bids else None
            top_ask_wall = max(asks, key=lambda x: x["lots"]) if asks else None

            return {
                "status": "LIVE_MT5_DOM",
                "total_bid_lots": round(total_bid_lots, 2),
                "total_ask_lots": round(total_ask_lots, 2),
                "dom_imbalance": round(imbalance, 3),
                "top_bid_wall": top_bid_wall,
                "top_ask_wall": top_ask_wall,
                "bids": bids,
                "asks": asks
            }
        except Exception as e:
            LOG.debug(f"Broker DOM error for {sym}: {e}")
            return {
                "status": "ERROR",
                "total_bid_lots": 0.0,
                "total_ask_lots": 0.0,
                "dom_imbalance": 0.0,
                "error": str(e),
                "bids": [],
                "asks": []
            }

    def get_global_central_depth(self) -> Dict[str, Any]:
        """Fetch global centralized resting order book depth from Binance PAXG/USDT (100% free, 0 keys)."""
        global _GLOBAL_DEPTH_CACHE, _GLOBAL_DEPTH_TS
        now_ts = time.time()

        if _GLOBAL_DEPTH_CACHE and (now_ts - _GLOBAL_DEPTH_TS < _DEPTH_CACHE_TTL):
            return dict(_GLOBAL_DEPTH_CACHE)

        fallback = {
            "source": "GLOBAL_CENTRAL_BOOK_PAXG",
            "spot_price": 4382.0,
            "levels": 20,
            "total_bid_oz": 20.0,
            "total_ask_oz": 20.0,
            "book_imbalance": 0.0,
            "top_bid_wall": None,
            "top_ask_wall": None,
            "is_live": False
        }

        try:
            url = "https://api.binance.com/api/v3/depth?symbol=PAXGUSDT&limit=20"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=1.8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_bids = data.get("bids", [])
                raw_asks = data.get("asks", [])
                bids = [{"price": round(float(p), 2), "oz": round(float(q), 3)} for p, q in raw_bids]
                asks = [{"price": round(float(p), 2), "oz": round(float(q), 3)} for p, q in raw_asks]
                total_bid_oz = sum(b["oz"] for b in bids)
                total_ask_oz = sum(a["oz"] for a in asks)
                tot = total_bid_oz + total_ask_oz
                imbalance = (total_bid_oz - total_ask_oz) / tot if tot > 0 else 0.0

                top_bid_wall = max(bids, key=lambda x: x["oz"]) if bids else None
                top_ask_wall = max(asks, key=lambda x: x["oz"]) if asks else None

                res = {
                    "source": "GLOBAL_CENTRAL_BOOK_PAXG",
                    "spot_price": bids[0]["price"] if bids else 0.0,
                    "levels": len(bids),
                    "total_bid_oz": round(total_bid_oz, 2),
                    "total_ask_oz": round(total_ask_oz, 2),
                    "book_imbalance": round(imbalance, 3),
                    "top_bid_wall": top_bid_wall,
                    "top_ask_wall": top_ask_wall,
                    "is_live": True
                }
                _GLOBAL_DEPTH_CACHE = res
                _GLOBAL_DEPTH_TS = now_ts
                return res
        except Exception as e:
            LOG.debug(f"Global PAXG depth read warning: {e}")
            if _GLOBAL_DEPTH_CACHE:
                return dict(_GLOBAL_DEPTH_CACHE)
            return fallback

    def get_full_market_depth(self, symbol: str = "XAUUSD") -> Dict[str, Any]:
        """Fetch synchronized dual-layer L2 order book (Broker DOM + Global PAXG Depth) in parallel."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f_dom = executor.submit(self.get_broker_dom, symbol)
            f_global = executor.submit(self.get_global_central_depth)
            dom_data = f_dom.result()
            global_data = f_global.result()

        dom_imb = float(dom_data.get("dom_imbalance", 0.0))
        glob_imb = float(global_data.get("book_imbalance", 0.0))

        if dom_imb > 0.25 and glob_imb > 0.15:
            book_posture = "AGGRESSIVE_BID_ABSORPTION (Institutional Buy Walls)"
        elif dom_imb < -0.25 and glob_imb < -0.15:
            book_posture = "AGGRESSIVE_ASK_RESISTANCE (Institutional Sell Walls)"
        elif dom_imb > 0.10:
            book_posture = "MODERATE_BID_SUPPORT"
        elif dom_imb < -0.10:
            book_posture = "MODERATE_ASK_PRESSURE"
        else:
            book_posture = "BALANCED_EQUILIBRIUM"

        bid_wall = dom_data.get("top_bid_wall")
        ask_wall = dom_data.get("top_ask_wall")
        bid_wall_str = f"{bid_wall['lots']}L @ {bid_wall['price']}" if bid_wall else "None"
        ask_wall_str = f"{ask_wall['lots']}L @ {ask_wall['price']}" if ask_wall else "None"

        badge_line = (
            f"- Level 2 Order Book: DOM Imb: {dom_imb:+.2f} (Bids: {dom_data.get('total_bid_lots', 0.0):.1f}L | "
            f"Asks: {dom_data.get('total_ask_lots', 0.0):.1f}L) | Bid Wall: [{bid_wall_str}] | "
            f"Ask Wall: [{ask_wall_str}] | Global L2 (PAXG): {glob_imb:+.2f} ({book_posture.split()[0]})"
        )

        return {
            "symbol": symbol,
            "badge_line": badge_line,
            "book_posture": book_posture,
            "dom_imbalance": dom_imb,
            "global_imbalance": glob_imb,
            "broker_dom": dom_data,
            "global_central_depth": global_data
        }