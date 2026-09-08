# -*- coding: utf-8 -*-
"""
crowd_trap_feeder.py
100% Raw, Zero-Hardcode Crowd & Analyst Technical Plans / Liquidity Trap Engine.
Extracts live MT5 prices, real swings, actual FVGs, and real session ranges.
Synthesizes 6 distinct technical setups across different market participant styles:
1. Classical Breakout Momentum (Session & Daily Highs/Lows)
2. Channel & Trendline Traders (Dynamic support/resistance breaks)
3. Pattern & Neckline Retest (Double Tops/Bottoms)
4. ICT / Liquidity Concept (FVG 50% CE & Order Blocks)
5. Range Extremes & Equal Highs/Lows (BSL/SSL Sweep Hunters)
6. Mean Reversion & POC Fade (Volume Profile Traders)
"""

import os
import sys
import json
import time
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

ALPHA_DIR = Path(r"C:\Trading\Alpha")
if str(ALPHA_DIR) not in sys.path:
    sys.path.insert(0, str(ALPHA_DIR))

from tradingagents.crowd_trap_store import (
    insert_batch_crowd_plans, get_crowd_trap_plans,
    get_total_plans_count, init_db, get_connection
)

LOG = logging.getLogger("alpha.crowd_trap_feeder")
PROXIMA_HTTP_URL = "http://127.0.0.1:3210/v1/chat/completions"

def _ensure_mt5_connected():
    import MetaTrader5 as mt5
    if mt5.terminal_info() is not None:
        return True
    creds_path = ALPHA_DIR / "config" / "mt5_credentials.json"
    if creds_path.exists():
        try:
            with open(creds_path, "r", encoding="utf-8") as f:
                creds = json.load(f)
            return mt5.initialize(
                login=creds.get("login"),
                password=creds.get("password"),
                server=creds.get("server", "FTMO-Demo"),
                timeout=5000
            )
        except Exception:
            pass
    return mt5.initialize(timeout=5000)

def get_live_market_snapshot(symbol: str = "XAUUSD") -> Dict[str, Any]:
    """Extract 100% real-time technical levels from live MT5 terminal without hardcoding."""
    import MetaTrader5 as mt5
    _ensure_mt5_connected()
    
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        raise RuntimeError(f"Cannot obtain live MT5 tick for {symbol}")
    
    cur_p = round(float(tick.bid), 2)
    bid = round(float(tick.bid), 2)
    ask = round(float(tick.ask), 2)
    spread = round(float(tick.ask - tick.bid), 2)
    
    d1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 5)
    if d1 is not None and len(d1) >= 2:
        pdh = round(float(d1[-2]["high"]), 2)
        pdl = round(float(d1[-2]["low"]), 2)
        today_h = round(float(d1[-1]["high"]), 2)
        today_l = round(float(d1[-1]["low"]), 2)
    else:
        pdh = cur_p
        pdl = cur_p
        today_h = cur_p
        today_l = cur_p

    m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 60)
    if m5 is not None and len(m5) > 0:
        m5_h = round(float(max(r["high"] for r in m5[-30:])), 2)
        m5_l = round(float(min(r["low"] for r in m5[-30:])), 2)
        
        # Calculate Volume POC across recent M5 bars
        prices = [round((r["high"] + r["low"] + r["close"]) / 3.0, 1) for r in m5]
        vols = [r["tick_volume"] for r in m5]
        profile = {}
        for p_val, v_val in zip(prices, vols):
            profile[p_val] = profile.get(p_val, 0) + v_val
        poc = max(profile, key=profile.get) if profile else cur_p
    else:
        m5_h = cur_p
        m5_l = cur_p
        poc = cur_p

    # Extract M15 Fair Value Gaps
    m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 40)
    bull_fvgs = []
    bear_fvgs = []
    if m15 is not None and len(m15) >= 3:
        for i in range(2, len(m15)):
            if m15[i]["low"] > m15[i-2]["high"]:
                gap_top = float(m15[i]["low"])
                gap_bottom = float(m15[i-2]["high"])
                bull_fvgs.append({
                    "top": round(gap_top, 2),
                    "bottom": round(gap_bottom, 2),
                    "ce": round((gap_top + gap_bottom) / 2.0, 2)
                })
            elif m15[i]["high"] < m15[i-2]["low"]:
                gap_top = float(m15[i-2]["low"])
                gap_bottom = float(m15[i]["high"])
                bear_fvgs.append({
                    "top": round(gap_top, 2),
                    "bottom": round(gap_bottom, 2),
                    "ce": round((gap_top + gap_bottom) / 2.0, 2)
                })

    nearest_bull_ce = bull_fvgs[-1]["ce"] if bull_fvgs else round(m5_l - 1.0, 2)
    nearest_bear_ce = bear_fvgs[-1]["ce"] if bear_fvgs else round(m5_h + 1.0, 2)

    return {
        "symbol": symbol,
        "price": cur_p,
        "bid": bid,
        "ask": ask,
        "spread": spread,
        "pdh": pdh,
        "pdl": pdl,
        "today_high": today_h,
        "today_low": today_l,
        "m5_high": m5_h,
        "m5_low": m5_l,
        "poc": poc,
        "bull_fvg_ce": nearest_bull_ce,
        "bear_fvg_ce": nearest_bear_ce
    }

def query_proxima(prompt: str, model: str = "3.1-flash-lite", timeout: float = 30.0) -> Optional[str]:
    """Query Proxima API for real market participant synthesis."""
    payload = json.dumps({
        "model": model,
        "message": prompt
    }).encode("utf-8")
    
    req = urllib.request.Request(
        PROXIMA_HTTP_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if content:
                return content
    except Exception as e:
        LOG.warning(f"[CROWD_TRAP_FEEDER] Proxima request error: {e}")
    return None

def clean_json_response(raw_text: str) -> str:
    """Extract clean JSON array from response."""
    import re
    m = re.search(r"```(?:json)?\s*(\[\s*\{.*\}\s*\])\s*```", raw_text, re.DOTALL)
    if m:
        return m.group(1).strip()
    s = raw_text.find("[")
    e = raw_text.rfind("]")
    if s != -1 and e != -1 and e > s:
        return raw_text[s:e+1].strip()
    return raw_text

def build_algorithmic_trap_plans(mkt: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Deterministic mathematical crowd plans built strictly from live MT5 technical geometry without hardcoded values."""
    p = mkt["price"]
    pdh = mkt["pdh"]
    pdl = mkt["pdl"]
    th = mkt["today_high"]
    tl = mkt["today_low"]
    m5_h = mkt["m5_high"]
    m5_l = mkt["m5_low"]
    poc = mkt["poc"]
    bull_ce = mkt["bull_fvg_ce"]
    bear_ce = mkt["bear_fvg_ce"]
    spr = max(mkt.get("spread", 0.5), 0.5)

    plans = [
        # Setup 1: Classical Intraday Breakout Momentum
        {
            "symbol": mkt["symbol"],
            "headline": f"Intraday High/Low Breakout Momentum ({th:.2f} / {tl:.2f})",
            "bull_trigger": round(th + spr, 2),
            "bear_trigger": round(tl - spr, 2),
            "bull_stops": round(th + (spr * 6), 2),
            "bear_stops": round(tl - (spr * 6), 2),
            "trader_narrative": f"Momentum breakout chasers stage BUY STOP orders above today high {th:.2f} targeting psychological expansion, and SELL STOP breakdown orders below today low {tl:.2f}.",
            "trap_summary": f"Smart money harvest: Institutional limit sellers absorb breakout buyers at {th:.2f}, sweeping buy stops into liquidity before initiating aggressive mean reversion.",
            "source": "ALGORITHMIC_RAW"
        },
        # Setup 2: PDH / PDL Retest Trap
        {
            "symbol": mkt["symbol"],
            "headline": f"Previous Day High / Low Structural Retest ({pdh:.2f} / {pdl:.2f})",
            "bull_trigger": round(pdh + (spr * 1.5), 2),
            "bear_trigger": round(pdl - (spr * 1.5), 2),
            "bull_stops": round(pdh + (spr * 7), 2),
            "bear_stops": round(pdl - (spr * 7), 2),
            "trader_narrative": f"Daily timeframe chartists treat {pdh:.2f} as the critical pivot. Sustained closes above {pdh:.2f} trigger retail trendline and swing breakout algorithms.",
            "trap_summary": f"If macro yields hold strong, sweeps above PDH {pdh:.2f} represent false expansions where retail stops provide liquidity for institutional short positioning.",
            "source": "ALGORITHMIC_RAW"
        },
        # Setup 3: M5 Range Boundary Scalp & Squeeze
        {
            "symbol": mkt["symbol"],
            "headline": f"M5 Tactical Range Extremes ({m5_h:.2f} / {m5_l:.2f})",
            "bull_trigger": round(m5_h + spr, 2),
            "bear_trigger": round(m5_l - spr, 2),
            "bull_stops": round(m5_h + (spr * 4), 2),
            "bear_stops": round(m5_l - (spr * 4), 2),
            "trader_narrative": f"Scalpers and short-term range traders place tight stop-loss orders just outside the recent M5 swing range ({m5_l:.2f} - {m5_h:.2f}).",
            "trap_summary": f"Quick liquidity sweep above {m5_h:.2f} or below {m5_l:.2f} tags retail stops, offering prime risk-to-reward for mean-reverting limit fills.",
            "source": "ALGORITHMIC_RAW"
        },
        # Setup 4: ICT Fair Value Gap Consequent Encroachment
        {
            "symbol": mkt["symbol"],
            "headline": f"M15 Fair Value Gap Consequent Encroachment ({bear_ce:.2f} / {bull_ce:.2f})",
            "bull_trigger": round(bear_ce, 2),
            "bear_trigger": round(bull_ce, 2),
            "bull_stops": round(bear_ce + (spr * 5), 2),
            "bear_stops": round(bull_ce - (spr * 5), 2),
            "trader_narrative": f"ICT and smart money concept traders look to sell the 50% Consequent Encroachment (CE) of the overhead bearish FVG at {bear_ce:.2f} and buy the bullish FVG CE at {bull_ce:.2f}.",
            "trap_summary": f"Institutions utilize the FVG CE zones ({bear_ce:.2f} / {bull_ce:.2f}) as high-probability execution shelves, protecting stop losses behind the outer gap boundaries.",
            "source": "ALGORITHMIC_RAW"
        },
        # Setup 5: Volume Point of Control (POC) Gravity Fade
        {
            "symbol": mkt["symbol"],
            "headline": f"Volume POC Equilibrium Magnet (POC: {poc:.2f})",
            "bull_trigger": round(poc + (spr * 4), 2),
            "bear_trigger": round(poc - (spr * 4), 2),
            "bull_stops": round(poc + (spr * 10), 2),
            "bear_stops": round(poc - (spr * 10), 2),
            "trader_narrative": f"Volume profile traders observe the Point of Control at {poc:.2f}. Price deviations beyond {poc + (spr * 4):.2f} or {poc - (spr * 4):.2f} are classified as stretched auction states.",
            "trap_summary": f"Air pockets on either side of POC {poc:.2f} trigger rapid kinetic snap-backs into high volume acceptance once retail stops are swept.",
            "source": "ALGORITHMIC_RAW"
        },
        # Setup 6: Liquidity Pool Sweep (BSL / SSL Hunt)
        {
            "symbol": mkt["symbol"],
            "headline": f"Buy-Side & Sell-Side Liquidity Pool Sweep (BSL {max(th, pdh):.2f} / SSL {min(tl, pdl):.2f})",
            "bull_trigger": round(max(th, pdh) + spr, 2),
            "bear_trigger": round(min(tl, pdl) - spr, 2),
            "bull_stops": round(max(th, pdh) + (spr * 8), 2),
            "bear_stops": round(min(tl, pdl) - (spr * 8), 2),
            "trader_narrative": f"Stop clusters have accumulated above major highs {max(th, pdh):.2f} (BSL) and below major lows {min(tl, pdl):.2f} (SSL). Breakout algorithms are armed at these levels.",
            "trap_summary": f"The definitive macro harvest zone. Probing into BSL {max(th, pdh):.2f} provides the counterparty volume needed for large institutional distribution.",
            "source": "ALGORITHMIC_RAW"
        }
    ]
    return plans

def fetch_fresh_crowd_plans(symbol: str = "XAUUSD") -> List[Dict[str, Any]]:
    """Synthesize 6 live crowd technical plans via Proxima or pure algorithmic raw fallback."""
    mkt = get_live_market_snapshot(symbol)
    cur_p = mkt["price"]
    pdh = mkt["pdh"]
    pdl = mkt["pdl"]
    th = mkt["today_high"]
    tl = mkt["today_low"]
    m5_h = mkt["m5_high"]
    m5_l = mkt["m5_low"]
    poc = mkt["poc"]
    bull_ce = mkt["bull_fvg_ce"]
    bear_ce = mkt["bear_fvg_ce"]
    
    prompt = f"""You are the Senior Market Microstructure & Crowd Sentiment Analyst for institutional Gold (XAUUSD).
REAL MT5 LIVE METRICS (NO HARDCODES):
- Spot Gold: ${cur_p} (Bid: {mkt['bid']}, Ask: {mkt['ask']}, Spread: {mkt['spread']} pts)
- Today High: ${th} | Today Low: ${tl}
- Previous Day High (PDH): ${pdh} | Previous Day Low (PDL): ${pdl}
- Recent M5 Swing Range: ${m5_l} - ${m5_h}
- Intraday Volume POC: ${poc}
- Nearest Bearish FVG CE: ${bear_ce} | Nearest Bullish FVG CE: ${bull_ce}

Generate exactly 6 distinct, realistic technical setups that different retail trader cohorts, Telegram signal groups, and TradingView chartists are actively debating right now:
1. Classical Breakout Momentum (Trading breaks of today's high ${th} or low ${tl})
2. Ascending/Descending Channel & Trendlines (Trading channel boundaries within ${m5_l}-${m5_h})
3. Classical Pattern / Neckline Retest (Double tops/bottoms around PDH ${pdh} or M5 pivots)
4. ICT / Smart Money Concept (Fair Value Gap 50% CE touches at ${bear_ce} or ${bull_ce})
5. Range Extremes & BSL/SSL Sweep Hunters (Equal highs/lows and stop hunts)
6. Mean Reversion / Volume Profile (Scalping deviations back to POC ${poc})

CRITICAL REQUIREMENTS:
- Use exact, realistic price levels derived from the real MT5 data above.
- Return ONLY a valid JSON array of exactly 6 objects (no conversational text, no markdown fences):
[
  {{
    "symbol": "{symbol}",
    "headline": "Punchy name of the technical setup & pattern",
    "bull_trigger": float,
    "bear_trigger": float,
    "bull_stops": float,
    "bear_stops": float,
    "trader_narrative": "Detailed breakdown of the crowd narrative, chart pattern, and participant rationale",
    "trap_summary": "Actionable institutional harvest strategy: where the crowd is trapped and how smart money will exploit their stops",
    "source": "PROXIMA_RAW"
  }}
]
"""
    raw = query_proxima(prompt, model="3.1-flash-lite", timeout=30.0)
    if not raw:
        raw = query_proxima(prompt, model="perplexity", timeout=25.0)
        
    if raw:
        cleaned = clean_json_response(raw)
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list) and len(parsed) >= 4:
                for item in parsed:
                    item.setdefault("symbol", symbol)
                    item.setdefault("source", "PROXIMA_RAW")
                    item.setdefault("raw_content", "")
                return parsed[:6]
        except Exception as e:
            LOG.warning(f"[CROWD_TRAP_FEEDER] Proxima parse error: {e}")
            
    LOG.info("[CROWD_TRAP_FEEDER] Using 100% raw algorithmic structural calculations.")
    return build_algorithmic_trap_plans(mkt)

def ensure_fresh_crowd_plans(symbol: str = "XAUUSD", max_age_seconds: int = 240, max_drift_pts: float = 3.0) -> int:
    """Ensure the store has fresh crowd plans. Populates if empty, older than max_age_seconds, or if spot price drifted > max_drift_pts."""
    existing = get_crowd_trap_plans(symbol=symbol, limit=1)
    need_refresh = False
    
    if not existing or len(existing) < 6:
        need_refresh = True
    else:
        latest = existing[0]
        # 1. Time-based cadence check (default: 4 mins / 240s)
        created_at_str = latest.get("created_at")
        if created_at_str:
            try:
                clean_str = created_at_str.replace("Z", "").replace(" ", "T")
                if "+" not in clean_str:
                    clean_str += "+00:00"
                ts = datetime.fromisoformat(clean_str).timestamp()
                if time.time() - ts > max_age_seconds:
                    need_refresh = True
            except Exception:
                need_refresh = True
        else:
            need_refresh = True
            
        # 2. Dynamic market condition / price drift check
        if not need_refresh:
            try:
                import MetaTrader5 as mt5
                _ensure_mt5_connected()
                tick = mt5.symbol_info_tick(symbol)
                if tick:
                    cur_spot = float(tick.bid)
                    b_trig = latest.get("bull_trigger")
                    be_trig = latest.get("bear_trigger")
                    if b_trig is not None and be_trig is not None:
                        ref_price = (float(b_trig) + float(be_trig)) / 2.0
                        if abs(cur_spot - ref_price) > max_drift_pts:
                            LOG.info(f"[CROWD_TRAP_FEEDER] Market price moved {abs(cur_spot - ref_price):.2f} pts (> {max_drift_pts} pts); triggering immediate fresh crowd plan refresh for {symbol}.")
                            need_refresh = True
            except Exception:
                pass
            
    if need_refresh:
        plans = fetch_fresh_crowd_plans(symbol)
        inserted = insert_batch_crowd_plans(plans, symbol=symbol)
        LOG.info(f"[CROWD_TRAP_FEEDER] Refreshed and inserted {inserted} raw crowd trap plans for {symbol}.")
        return inserted
    return 0

if __name__ == "__main__":
    init_db()
    inserted = ensure_fresh_crowd_plans("XAUUSD", max_age_seconds=0)
    print(f"Inserted plans: {inserted}")
    recent = get_crowd_trap_plans("XAUUSD", limit=6)
    print(f"Retrieved {len(recent)} plans from store:")
    for p in recent:
        print(f" - [{p['id']}] {p['headline']} | Bull: {p['bull_trigger']} | Bear: {p['bear_trigger']}")
