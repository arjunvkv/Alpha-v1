"""
======================================================================
               ALPHA V1 - CATALYST & MARKET REGIME ARBITER
======================================================================
Transparent, Real-Time Market Driver Classification Engine.
Determines whether the market is currently driven by:
1. MACRO_EVENT_ACTIVE: Active scheduled high-impact macro release window (T-30m to T+15m)
2. ACTIVE_SESSION_FLOW: Normal active session flow (>=80 t/m) with two-way liquidity
3. MACRO_DIRECTIONAL_PRESSURE: Dominant macro anchor (DFII10 Real Yields > 2.35%) providing HTF drift
4. PURE_TECHNICAL_ORDERFLOW: Calm tape, balanced macro; price is driven by VAH/VAL/FVG and liquidity sweeps

Exposes BOTH the high-level regime label AND the exact raw numbers/formulas
behind it to eliminate black-box hallucinations without context bloat.
======================================================================
"""

import os
import json
import time
import datetime
import logging
import urllib.request
from pathlib import Path
from typing import Dict, Any, List, Optional
import MetaTrader5 as mt5

LOG = logging.getLogger("alpha.catalyst_arbiter")

PROJECT_ROOT = Path(r"C:\Trading\Alpha")
CALENDAR_CACHE_FILE = PROJECT_ROOT / "data" / "live" / "economic_calendar_ff.json"
PROXY_URL = "http://127.0.0.1:40001"

# High-impact economic release keywords that cause volatility shocks
HIGH_IMPACT_TERMS = [
    "CPI", "CONSUMER PRICE INDEX", "NON-FARM PAYROLLS", "NFP",
    "FOMC", "FED RATE", "INTEREST RATE", "POWELL", "PPI",
    "GDP", "UNEMPLOYMENT", "RETAIL SALES", "CORE CPI", "PCE", "ECB RATE"
]

class CatalystArbiterEngine:
    """
    Transparent, real-time classifier combining:
    1. Pre-scheduled macro calendar distance (T_event)
    2. Real-time MT5 tick velocity & CVD shock verification (V_tape)
    3. Fundamental macro yields & DXY regime (M_yield)
    """

    def __init__(self, cache_ttl_seconds: int = 300):
        self.cache_ttl = cache_ttl_seconds
        self._cached_macro_ts = 0.0
        self._cached_yields = {}
        CALENDAR_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    def fetch_calendar_events(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Fetch weekly institutional economic releases via Cloudflare proxy bridge or return cache."""
        now_ts = time.time()
        if not force_refresh and CALENDAR_CACHE_FILE.exists():
            try:
                with open(CALENDAR_CACHE_FILE, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    if now_ts - cache_data.get("updated_at_ts", 0) < self.cache_ttl:
                        return cache_data.get("events", [])
            except Exception as err:
                LOG.debug(f"Calendar cache read warning: {err}")

        # Fetch live via local Cloudflare WARP proxy bridge
        events = []
        try:
            req = urllib.request.Request(
                "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AlphaDesk/1.0"}
            )
            # Route through local Cloudflare bridge to avoid 429
            req.set_proxy("127.0.0.1:40001", "http")
            req.set_proxy("127.0.0.1:40001", "https")
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status == 200:
                    raw_json = json.loads(resp.read().decode("utf-8"))
                    for ev in raw_json:
                        c = ev.get("country", "").upper()
                        imp = ev.get("impact", "")
                        if c in ("USD", "EUR", "ALL") and imp in ("High", "Holiday", "Medium"):
                            events.append(ev)
                    
                    # Update cache
                    with open(CALENDAR_CACHE_FILE, "w", encoding="utf-8") as f:
                        json.dump({
                            "updated_at_ts": now_ts,
                            "updated_at_iso": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                            "events": events
                        }, f, indent=2)
                    return events
        except Exception as err:
            LOG.warning(f"Live calendar fetch failed (fallback to cache): {err}")
            if CALENDAR_CACHE_FILE.exists():
                try:
                    with open(CALENDAR_CACHE_FILE, "r", encoding="utf-8") as f:
                        return json.load(f).get("events", [])
                except Exception:
                    pass

        return events

    def get_market_regime(self, symbol: str = "XAUUSD") -> Dict[str, Any]:
        """
        Calculates the definitive real-time market regime, exposing both
        the category label and the exact raw metrics behind the decision.
        """
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        sym = symbol.strip().upper()

        # 1. Fetch raw calendar data & calculate distance to events
        all_events = self.fetch_calendar_events()
        today_iso = now_utc.strftime("%Y-%m-%d")
        
        events_today = []
        next_event = None
        min_seconds_to_next = float("inf")
        last_event = None
        min_seconds_since_last = float("inf")

        for ev in all_events:
            d_str = ev.get("date", "")
            if not d_str:
                continue
            try:
                # ISO parsing with timezone offset (e.g. 2026-09-10T08:30:00-04:00)
                ev_dt = datetime.datetime.fromisoformat(d_str).astimezone(datetime.timezone.utc)
                diff_sec = (ev_dt - now_utc).total_seconds()
                
                # Check if event is today (UTC or local trading day)
                if ev_dt.strftime("%Y-%m-%d") == today_iso:
                    events_today.append({
                        "title": ev.get("title"),
                        "country": ev.get("country"),
                        "impact": ev.get("impact"),
                        "time_utc": ev_dt.strftime("%H:%M UTC"),
                        "diff_minutes": round(diff_sec / 60.0, 1)
                    })

                # Nearest upcoming event
                if diff_sec > 0 and diff_sec < min_seconds_to_next:
                    if ev.get("impact") in ("High", "Holiday"):
                        min_seconds_to_next = diff_sec
                        next_event = {
                            "title": ev.get("title"),
                            "country": ev.get("country"),
                            "impact": ev.get("impact"),
                            "time_utc": ev_dt.strftime("%Y-%m-%d %H:%M UTC"),
                            "minutes_away": round(diff_sec / 60.0, 1),
                            "hours_away": round(diff_sec / 3600.0, 1)
                        }

                # Nearest past event (within last 4 hours)
                if diff_sec <= 0 and abs(diff_sec) < min_seconds_since_last and abs(diff_sec) < 14400:
                    if ev.get("impact") in ("High",):
                        min_seconds_since_last = abs(diff_sec)
                        last_event = {
                            "title": ev.get("title"),
                            "country": ev.get("country"),
                            "minutes_ago": round(abs(diff_sec) / 60.0, 1)
                        }
            except Exception:
                continue

        # Filter high-impact events specifically for today
        high_impact_today = [e for e in events_today if e.get("impact") == "High"]
        is_holiday_today = any("HOLIDAY" in e.get("title", "").upper() or e.get("impact") == "Holiday" for e in events_today)

        # 2. Raw Tape & Microstructure Metrics from MT5
        curr_bid = 0.0
        curr_ask = 0.0
        tick_velocity_tpm = 0.0
        live_spread_pts = 0
        cvd_10b_pressure = 0.0
        cvd_divergence = "NO_DIVERGENCE"
        cvd_5m_ratio = 0.0
        disp_4m_pts = 0.0
        range_4m_pts = 0.0
        eurusd_5m_pct = 0.0
        xagusd_5m_pct = 0.0
        poc_price = 0.0
        air_pocket_below = []
        air_pocket_above = []
        pdh_price = 0.0
        pdl_price = 0.0
        dist_pdh_pts = 0.0
        dist_pdl_pts = 0.0
        nearest_fvg_below = None
        nearest_fvg_above = None
        roadway_100b = {}
        highway_trail_m5 = []
        raw_ohlc_60b = {}

        # 30-value 4-minute aggregated footprint horizon (120 minutes of tape)
        deltas_4m = []
        disp_4m = []
        ranges_4m = []
        vols_4m = []
        low_wicks_4m = []
        high_wicks_4m = []

        # 30-bar M1 raw series (last 30 minutes minute-by-minute)
        m1_prices = []
        m1_deltas = []
        m1_volumes = []
        m1_ranges = []
        m1_lower_wicks = []
        m1_upper_wicks = []

        try:
            from tradingagents.cvd_engine import CumulativeVolumeDeltaEngine
            cvd_eng = CumulativeVolumeDeltaEngine()
            cvd_res = cvd_eng.get_symbol_cvd(sym)
            tick_velocity_tpm = cvd_res.get("tick_velocity_tpm", 0.0)
            live_spread_pts = cvd_res.get("live_spread_pts", 0)
            cvd_10b_pressure = cvd_res.get("delta_pressure_pct", 0.0)
            cvd_divergence = cvd_res.get("exhaustion_signal", "NO_DIVERGENCE")
        except Exception as err:
            LOG.debug(f"Tape sensor read error: {err}")

        # Extract 120 M1 rates for 30-block 4m horizon, cross-asset deltas, POC & air pockets
        try:
            import numpy as np
            if mt5.terminal_info() is not None or mt5.initialize():
                curr_tick = mt5.symbol_info_tick(sym)
                if curr_tick:
                    curr_bid = round(float(getattr(curr_tick, "bid", 0.0)), 2)
                    curr_ask = round(float(getattr(curr_tick, "ask", 0.0)), 2)

                # Fetch 120 M1 rates for the 30-block 4-minute horizon (120 minutes)
                r_m1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 120)
                if r_m1 is not None and len(r_m1) >= 4:
                    num_blocks = min(30, len(r_m1) // 4)
                    usable_rates = r_m1[-(num_blocks * 4):]
                    blocks = [usable_rates[i:i+4] for i in range(0, len(usable_rates), 4)]

                    for b in blocks:
                        d = sum(r['tick_volume'] * ((r['close'] - r['open']) / max(r['high'] - r['low'], 1e-6)) for r in b)
                        deltas_4m.append(round(float(d), 0))
                        disp = b[-1]['close'] - b[0]['open']
                        disp_4m.append(round(float(disp), 2))
                        b_high = max(r['high'] for r in b)
                        b_low = min(r['low'] for r in b)
                        ranges_4m.append(round(float(b_high - b_low), 2))
                        vols_4m.append(int(sum(r['tick_volume'] for r in b)))
                        body_low = min(b[0]['open'], b[-1]['close'])
                        body_high = max(b[0]['open'], b[-1]['close'])
                        low_wicks_4m.append(round(float(body_low - b_low), 2))
                        high_wicks_4m.append(round(float(b_high - body_high), 2))

                    # Trailing 4m displacement & range from most recent block
                    disp_4m_pts = disp_4m[-1] if disp_4m else 0.0
                    range_4m_pts = ranges_4m[-1] if ranges_4m else 0.0

                    # 30-bar M1 raw series
                    m1_tail = r_m1[-30:]
                    for r in m1_tail:
                        m1_prices.append(round(float(r['close']), 2))
                        m1_deltas.append(round(float(r['tick_volume'] * ((r['close'] - r['open']) / max(r['high'] - r['low'], 1e-6))), 0))
                        m1_volumes.append(int(r['tick_volume']))
                        m1_ranges.append(round(float(r['high'] - r['low']), 2))
                        b_low = min(r['open'], r['close'])
                        b_high = max(r['open'], r['close'])
                        m1_lower_wicks.append(round(float(b_low - r['low']), 2))
                        m1_upper_wicks.append(round(float(r['high'] - b_high), 2))

                    # CVD 5m signed ratio (-1.0 to +1.0) from last 5 M1 bars
                    r_last5 = r_m1[-5:]
                    deltas_5m = [r['tick_volume'] * ((r['close'] - r['open']) / max(r['high'] - r['low'], 1e-6)) for r in r_last5]
                    sum_v_5m = sum(r['tick_volume'] for r in r_last5)
                    cvd_5m_ratio = round(sum(deltas_5m) / max(sum_v_5m, 1.0), 2)

                # Cross-asset 5m % deltas (EURUSD & XAGUSD)
                r_eur = mt5.copy_rates_from_pos("EURUSD", mt5.TIMEFRAME_M5, 0, 3)
                if r_eur is not None and len(r_eur) >= 2:
                    eurusd_5m_pct = round(float((r_eur[-1]['close'] - r_eur[-2]['close']) / r_eur[-2]['close'] * 100.0), 3)

                r_xag = mt5.copy_rates_from_pos("XAGUSD", mt5.TIMEFRAME_M5, 0, 3)
                if r_xag is not None and len(r_xag) >= 2:
                    xagusd_5m_pct = round(float((r_xag[-1]['close'] - r_xag[-2]['close']) / r_xag[-2]['close'] * 100.0), 3)

                # PDH & PDL from D1 rates
                d1_rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_D1, 0, 3)
                if d1_rates is not None and len(d1_rates) >= 2:
                    pdh_price = round(float(d1_rates[-2]['high']), 2)
                    pdl_price = round(float(d1_rates[-2]['low']), 2)
                    if curr_bid > 0:
                        dist_pdh_pts = round(pdh_price - curr_bid, 2)
                        dist_pdl_pts = round(curr_bid - pdl_price, 2)

                # Volume POC and Low Volume Nodes (Air Pockets) from M5 distribution
                r_m5 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 150)
                if r_m5 is not None and len(r_m5) >= 20:
                    p_points, v_points = [], []
                    for r in r_m5:
                        steps = 5
                        prices = np.linspace(r['low'], r['high'], steps)
                        v_step = r['tick_volume'] / steps
                        p_points.extend(prices)
                        v_points.extend([v_step] * steps)
                    p_arr, v_arr = np.array(p_points), np.array(v_points)
                    bins = np.linspace(p_arr.min(), p_arr.max(), 35)
                    hist, bin_edges = np.histogram(p_arr, bins=bins, weights=v_arr)
                    poc_idx = np.argmax(hist)
                    poc_price = round(float((bin_edges[poc_idx] + bin_edges[poc_idx+1]) / 2.0), 2)
                    
                    # Low Volume Nodes (< 35% median volume)
                    med_v = np.median(hist[hist > 0])
                    c_price = float(r_m5[-1]['close'])
                    for i, h in enumerate(hist):
                        b_mid = (bin_edges[i] + bin_edges[i+1]) / 2.0
                        if h < 0.35 * med_v:
                            pocket = [round(float(bin_edges[i]), 2), round(float(bin_edges[i+1]), 2)]
                            if b_mid < c_price and not air_pocket_below:
                                air_pocket_below = pocket
                            elif b_mid > c_price and not air_pocket_above:
                                air_pocket_above = pocket

                # Institutional FVGs (Nearest Unmitigated Below and Above)
                try:
                    from tradingagents.fair_value_gap import FairValueGapEngine
                    fvg_eng = FairValueGapEngine()
                    fvg_res = fvg_eng.get_symbol_fvg_matrix(sym)
                    ref_price = curr_bid if curr_bid > 0 else (float(r_m1[-1]['close']) if r_m1 is not None and len(r_m1) > 0 else 0.0)
                    below_fvgs, above_fvgs = [], []
                    for tf, tf_data in fvg_res.get("timeframes", {}).items():
                        for f in tf_data.get("unmitigated_fvgs", []):
                            top = float(f.get("top", 0.0))
                            bot = float(f.get("bottom", 0.0))
                            if top < ref_price:
                                below_fvgs.append(f)
                            elif bot > ref_price:
                                above_fvgs.append(f)
                    if below_fvgs:
                        nb = max(below_fvgs, key=lambda x: float(x.get("top", 0.0)))
                        nearest_fvg_below = {
                            "tf": nb.get("timeframe"),
                            "type": nb.get("type"),
                            "bot": round(float(nb.get("bottom", 0)), 1),
                            "top": round(float(nb.get("top", 0)), 1),
                            "ce": round(float(nb.get("consequent_encroachment", 0)), 1),
                            "fill_pct": round(float(nb.get("fill_pct", 0)), 1)
                        }
                    if above_fvgs:
                        na = min(above_fvgs, key=lambda x: float(x.get("bottom", 0.0)))
                        nearest_fvg_above = {
                            "tf": na.get("timeframe"),
                            "type": na.get("type"),
                            "bot": round(float(na.get("bottom", 0)), 1),
                            "top": round(float(na.get("top", 0)), 1),
                            "ce": round(float(na.get("consequent_encroachment", 0)), 1),
                            "fill_pct": round(float(na.get("fill_pct", 0)), 1)
                        }
                except Exception as _fvg_err:
                    LOG.debug(f"FVG matrix query error: {_fvg_err}")

                # 4-Timeframe Real MT5 Data Ingestion (M5, M15, H1, H4): 100b Roadway Rails & 60-Bar OHLC
                tf_specs = [
                    ("M5", mt5.TIMEFRAME_M5, 0.8),
                    ("M15", mt5.TIMEFRAME_M15, 0.8),
                    ("H1", mt5.TIMEFRAME_H1, 1.5),
                    ("H4", mt5.TIMEFRAME_H4, 1.5)
                ]
                for tf_name, tf_id, tol in tf_specs:
                    r_100 = mt5.copy_rates_from_pos(sym, tf_id, 0, 100)
                    if r_100 is not None and len(r_100) > 0:
                        highs_100 = [float(r['high']) for r in r_100]
                        lows_100 = [float(r['low']) for r in r_100]
                        up_rail = round(max(highs_100), 1)
                        low_rail = round(min(lows_100), 1)
                        n_bars = len(r_100) - 1
                        up_ago = n_bars - max(i for i, h in enumerate(highs_100) if h == max(highs_100))
                        low_ago = n_bars - min(i for i, l in enumerate(lows_100) if l == min(lows_100))
                        up_touches = sum(1 for h in highs_100 if abs(h - up_rail) <= tol)
                        low_touches = sum(1 for l in lows_100 if abs(l - low_rail) <= tol)
                        w_pts = round(up_rail - low_rail, 1)
                        ref_p = curr_bid if curr_bid > 0 else float(r_100[-1]['close'])
                        p_pct = round((ref_p - low_rail) / max(w_pts, 0.1) * 100.0, 1)

                        roadway_100b[tf_name] = {
                            "up": up_rail,
                            "up_t": up_touches,
                            "up_ago": up_ago,
                            "low": low_rail,
                            "low_t": low_touches,
                            "low_ago": low_ago,
                            "w": w_pts,
                            "pos": p_pct
                        }

                        # 60 Real Physical OHLC bars (rounded to 1 decimal place: 0.10)
                        raw_ohlc_60b[tf_name] = [
                            [round(float(r['open']), 1), round(float(r['high']), 1), round(float(r['low']), 1), round(float(r['close']), 1)]
                            for r in r_100[-60:]
                        ]

                        # M5 Highway Trail (4 Checkpoints: 60b, 40b, 20b, Now)
                        if tf_name == "M5":
                            for cp in [40, 60, 80, 100]:
                                if len(r_100) >= cp:
                                    sub = r_100[:cp]
                                    f_val = round(min(float(x['low']) for x in sub[-40:]), 1)
                                    c_val = round(max(float(x['high']) for x in sub[-40:]), 1)
                                    w_val = round(c_val - f_val, 1)
                                    highway_trail_m5.append({'ago': 100 - cp, 'floor': f_val, 'ceil': c_val, 'w': w_val})
        except Exception as _detail_err:
            LOG.debug(f"Extended tape and volume profiling error: {_detail_err}")

        # 2.1 In-Between Breaking News Extraction & Tape Verification
        in_between_news_info = {
            "latest_headline": "None",

            "category": "NONE",
            "minutes_ago": 999.0,
            "tape_velocity_tpm": tick_velocity_tpm,
            "velocity_surge_ratio": round(tick_velocity_tpm / 22.0, 2),
            "post_headline_cvd_ratio": cvd_5m_ratio,
            "post_headline_displacement_pts": disp_4m_pts,
            "market_absorption_state": "NO_ACTIVE_CATALYST"
        }

        try:
            from tradingagents.world_events import LiveWorldEventsEngine
            w_events = LiveWorldEventsEngine().fetch_live_events()
            if w_events:
                # Find most relevant breaking headline for commodities / central banks / geopolitics
                top_ev = None
                for ev in w_events:
                    cat = ev.get("category", "")
                    if cat in ("CENTRAL_BANKS_FED", "COMMODITIES_ENERGY", "GEOPOLITICAL_GLOBAL"):
                        top_ev = ev
                        break
                if not top_ev and len(w_events) > 0:
                    top_ev = w_events[0]

                if top_ev:
                    h_title = top_ev.get("title", "")
                    h_cat = top_ev.get("category", "MACRO")
                    h_time_str = top_ev.get("pub_date", "")
                    h_mins = 30.0  # default approximation
                    try:
                        import email.utils
                        parsed_t = email.utils.parsedate_to_datetime(h_time_str)
                        h_mins = round(abs((now_utc - parsed_t).total_seconds()) / 60.0, 1)
                    except Exception:
                        pass

                    # High-impact breaking keywords specifically indicating immediate real-time market shocks
                    CRITICAL_SHOCK_KEYWORDS = [
                        "EMERGENCY", "MISSILE", "STRIKE", "INVASION", "DECLARES WAR", "EXPLOSION",
                        "SURPRISE RATE", "INTERVENE", "SANCTION BAN", "SHUTDOWN"
                    ]
                    title_upper = h_title.upper()
                    is_critical_headline = any(kw in title_upper for kw in CRITICAL_SHOCK_KEYWORDS)

                    # Physical Verification: Did the tape react to this headline?
                    # Baseline tick velocity in normal session is ~40-60 t/m.
                    surge_ratio = round(tick_velocity_tpm / 45.0, 2)
                    
                    if is_critical_headline and (tick_velocity_tpm >= 180.0 or abs(disp_4m_pts) >= 6.0):
                        abs_state = "CONFIRMED_BREAKING_SHOCK"
                    elif surge_ratio >= 1.8 and abs(disp_4m_pts) >= 4.0:
                        abs_state = "SESSION_MOMENTUM_SURGE"
                    elif surge_ratio < 1.2 and abs(disp_4m_pts) < 2.0:
                        abs_state = "IGNORED_BY_TAPE"
                    else:
                        abs_state = "ROUTINE_FLOW"

                    in_between_news_info = {
                        "latest_headline": h_title,
                        "category": h_cat,
                        "minutes_ago": h_mins,
                        "is_critical_breaking": is_critical_headline,
                        "tape_velocity_tpm": tick_velocity_tpm,
                        "velocity_surge_ratio": surge_ratio,
                        "post_headline_cvd_ratio": cvd_5m_ratio,
                        "post_headline_displacement_pts": disp_4m_pts,
                        "market_absorption_state": abs_state
                    }
        except Exception as _news_err:
            LOG.debug(f"In-between news extraction error: {_news_err}")


        # 3. Macro Yields & Dominant Anchor (Live Real Yields from Official FREDAdapter with 5-minute cache)

        now_epoch = time.time()
        if self._cached_yields and (now_epoch - self._cached_macro_ts < 300):
            dfii10_yield = self._cached_yields.get("dfii10", 0.0)
            us10y = self._cached_yields.get("us10y", 0.0)
            breakeven_10y = self._cached_yields.get("breakeven_10y", 0.0)
            dxy = self._cached_yields.get("dxy", 100.0)
        else:
            dfii10_yield = 0.0
            us10y = 0.0
            breakeven_10y = 0.0
            dxy = 100.0
            try:
                from sensors.evidence_sources import FREDAdapter
                fred = FREDAdapter()
                dfii_obs = fred.observations("DFII10", limit=1)
                if dfii_obs.get("status") == "SUCCESS" and dfii_obs.get("data", {}).get("observations"):
                    dfii10_yield = float(dfii_obs["data"]["observations"][0].get("value", 0.0))

                dgs_obs = fred.observations("DGS10", limit=1)
                if dgs_obs.get("status") == "SUCCESS" and dgs_obs.get("data", {}).get("observations"):
                    us10y = float(dgs_obs["data"]["observations"][0].get("value", 0.0))

                t10y_obs = fred.observations("T10YIE", limit=1)
                if t10y_obs.get("status") == "SUCCESS" and t10y_obs.get("data", {}).get("observations"):
                    breakeven_10y = float(t10y_obs["data"]["observations"][0].get("value", 0.0))
            except Exception as _fred_err:
                LOG.debug(f"FRED live yield read warning: {_fred_err}")

            # Live DXY & VIX from institutional analytics
            try:
                from tradingagents.institutional_analytics import InstitutionalAnalyticsEngine
                inst_eng = InstitutionalAnalyticsEngine()
                macro_data = inst_eng.get_macro_and_gamma_feeds()
                if not us10y:
                    us10y = float(macro_data.get("us_10y", 0.0))
                dxy = float(macro_data.get("dxy", 100.0))
            except Exception:
                pass

            self._cached_yields = {
                "dfii10": dfii10_yield,
                "us10y": us10y,
                "breakeven_10y": breakeven_10y,
                "dxy": dxy
            }
            self._cached_macro_ts = now_epoch

        # ==================================================================
        # DYNAMIC ECONOMETRIC PRICING POWER FORMULATION
        # ==================================================================
        # Calculates mathematical variance share:
        # 1. Macro Force Score (z_macro): Real Yield deviation from neutral anchor (2.10%)
        #    Yield elasticity: Gold-Real Yield historical correlation is -0.82.
        # 2. Calendar Event Closeness (w_calendar): Cauchy-Lorentz decay function: 1 / (1 + (dt/30)^2)
        # 3. Tape Momentum Force (z_tape): M1 Tick Velocity normalized against baseline (40 t/m)
        # 4. Technical Structure Share: Residual variance governing exact turning points (POC/VAH/VAL/FVG)
        
        # 1. Macro Z-score: neutral baseline is 2.10% (standard dev = 0.15%)
        z_macro = max(0.0, (dfii10_yield - 2.10) / 0.15) if dfii10_yield > 0 else 0.0
        macro_force = z_macro * 1.2  # Fundamental backdrop pressure

        # 2. Calendar Proximity Weight
        min_dt_min = min(next_event["minutes_away"] if next_event else 9999.0, last_event["minutes_ago"] if last_event else 9999.0)
        w_event_shock = 10.0 / (1.0 + (min_dt_min / 15.0)**2)  # Explodes to ~10.0 at T-0, decays to <0.05 past 3h

        # 3. Tape Volatility Force (Baseline active session velocity is ~60-80 t/m)
        tape_force = max(0.2, tick_velocity_tpm / 55.0)

        # 4. Base Technical Structural Weight (Orderflow auctions always govern entries/exits)
        base_tech = 1.5

        # Sum of competing dynamic forces
        total_forces = macro_force + w_event_shock + tape_force + base_tech
        
        # Exact real-time percentages
        pct_event = round((w_event_shock / total_forces) * 100.0, 1)
        pct_macro = round((macro_force / total_forces) * 100.0, 1)
        pct_tape = round((tape_force / total_forces) * 100.0, 1)
        pct_tech = round(100.0 - pct_event - pct_macro - pct_tape, 1)
        if pct_tech < 0.0:
            pct_tech = 0.0

        # ==================================================================
        # REGIME FORMATION LOGIC (Transparent, Deterministic, Factual)
        # ==================================================================
        regime = "PURE_TECHNICAL_ORDERFLOW"
        label_justification = ""
        actionable_directive = ""

        # Rule 1: High-Impact Macro Release Active (T-30m to T+15m)
        if next_event and next_event["minutes_away"] <= 30.0:
            regime = "MACRO_EVENT_ACTIVE"
            label_justification = f"High-Impact release '{next_event['title']}' ({next_event['country']}) is imminent in {next_event['minutes_away']}m (Calendar Shock: {pct_event}%)."
            actionable_directive = "HIGH VOLATILITY WINDOW: Macro release imminent. Expect sudden spread expansion and slippage. Anchor pending orders outside immediate noise or wait for release prints."
            pricing_power = f"EVENT_SHOCK_{pct_event:.0f}%_TECHNICALS_{pct_tech:.0f}%"
        elif last_event and last_event["minutes_ago"] <= 15.0:
            regime = "MACRO_EVENT_ACTIVE"
            label_justification = f"High-Impact release '{last_event['title']}' occurred {last_event['minutes_ago']}m ago. Post-release volatility settling (Post-Shock: {pct_event}%)."
            actionable_directive = "POST-RELEASE SETTLEMENT: Let initial 15-minute whipsaw settle before entering structural retest trades."
            pricing_power = f"POST_RELEASE_SETTLEMENT_{pct_event:.0f}%_TECHNICALS_{pct_tech:.0f}%"

        # Rule 2: Active Session Flow / Normal Liquid Expansion (velocity >= 80 t/m)
        elif tick_velocity_tpm >= 80.0:
            regime = "ACTIVE_SESSION_FLOW"
            label_justification = f"Normal active session tape velocity {tick_velocity_tpm:.1f} t/m with spread {live_spread_pts} pts (Tape: {pct_tape}%, Tech: {pct_tech}%)."
            actionable_directive = f"ACTIVE AUCTION: Normal session liquidity. CVD ratio {cvd_5m_ratio:+.2f}. Trade both sides freely: align with initiative flow if 10-bar delta is persistent, or trade responsive mean-reversion at structural extremes (POC {poc_price:.2f}, VAH/VAL) if price sweeps liquidity with absorption."
            pricing_power = f"SESSION_FLOW_{pct_tape:.0f}%_TECHNICALS_{pct_tech:.0f}%"

        # Rule 3: High Real Yield Gravity without upcoming scheduled shock
        elif dfii10_yield >= 2.35 and (not next_event or next_event.get("hours_away", 99) > 4.0):
            regime = "MACRO_DIRECTIONAL_PRESSURE"
            holiday_note = " (US Bank Holiday / Quiet Calendar)" if is_holiday_today else ""
            label_justification = f"Background macro influenced by DFII10 Real Yields at {dfii10_yield}% (+{z_macro:.1f}sigma deviation){holiday_note}. Background macro share: {pct_macro}%."
            actionable_directive = f"ASYMMETRIC AUCTION BIAS: Real yield overhang provides structural tailwind for shorts, but counter-trend scalps remain fully valid at extreme demand (VAL, PDL sweeps, Wyckoff springs). Size by setup quality and maintain explicit structural SL."
            pricing_power = f"MACRO_YIELD_{pct_macro:.0f}%_TECHNICALS_{pct_tech:.0f}%"

        # Rule 5: Pure Technical Orderflow
        elif len(high_impact_today) == 0:
            regime = "PURE_TECHNICAL_ORDERFLOW"
            label_justification = f"Zero high-impact releases today. Real yields baseline. Tape velocity {tick_velocity_tpm:.0f} t/m. Pure auction orderflow dominates."
            actionable_directive = f"STRUCTURE-DRIVEN AUCTION: Price navigating between Value Area (VAH/VAL) and liquidity pools. Trade responsive mean-reversion at extremes or breakout expansions with CVD confirmation."
            pricing_power = f"TECHNICALS_{pct_tech:.0f}%_TAPE_{pct_tape:.0f}%"

        else:
            # High impact event later today, but >30m away
            regime = "PRE_EVENT_ANTICIPATION"
            label_justification = f"High-impact event '{high_impact_today[0]['title']}' scheduled for today in {next_event['hours_away']}h."
            actionable_directive = "RANGE BOUND COMPRESSION: Expect technical equilibrium until release window. Target modest intraday targets (1:2 R:R)."
            pricing_power = f"ANTICIPATION_{pct_event:.0f}%_TECHNICALS_{pct_tech:.0f}%"

        # Construct comprehensive, raw footstep prompt badge (zero fluff, pure raw tape physics)
        deltas_4m_str = "[" + ", ".join(f"{int(d):+d}" for d in deltas_4m) + "]" if deltas_4m else "[]"
        disp_4m_str = "[" + ", ".join(f"{d:+.2f}" for d in disp_4m) + "]" if disp_4m else "[]"
        ranges_4m_str = "[" + ", ".join(f"{r:.2f}" for r in ranges_4m) + "]" if ranges_4m else "[]"
        low_wicks_4m_str = "[" + ", ".join(f"{w:.2f}" for w in low_wicks_4m) + "]" if low_wicks_4m else "[]"
        high_wicks_4m_str = "[" + ", ".join(f"{w:.2f}" for w in high_wicks_4m) + "]" if high_wicks_4m else "[]"

        # Format last 10 M1 deltas & prices
        m1_recent_deltas_str = "[" + ", ".join(f"{int(d):+d}" for d in m1_deltas[-10:]) + "]" if m1_deltas else "[]"
        m1_recent_prices_str = "[" + ", ".join(f"{p:.1f}" for p in m1_prices[-10:]) + "]" if m1_prices else "[]"

        fvg_below_str = f"[{nearest_fvg_below.get('tf', '')} {nearest_fvg_below.get('type', '')} {float(nearest_fvg_below.get('bot', 0)):.1f}-{float(nearest_fvg_below.get('top', 0)):.1f} CE:{float(nearest_fvg_below.get('ce', 0)):.1f}]" if nearest_fvg_below else "None"
        fvg_above_str = f"[{nearest_fvg_above.get('tf', '')} {nearest_fvg_above.get('type', '')} {float(nearest_fvg_above.get('bot', 0)):.1f}-{float(nearest_fvg_above.get('top', 0)):.1f} CE:{float(nearest_fvg_above.get('ce', 0)):.1f}]" if nearest_fvg_above else "None"
        air_below_str = f"[{air_pocket_below[0]}-{air_pocket_below[1]}]" if air_pocket_below else "None"
        air_above_str = f"[{air_pocket_above[0]}-{air_pocket_above[1]}]" if air_pocket_above else "None"
        next_ev_str = f"{next_event['title']} in {next_event['hours_away']}h" if next_event else "None today"

        roadway_badge_str = " | ".join(f"{tf}: [{v['up']}({v['up_t']}x,{v['up_ago']}b)|{v['low']}({v['low_t']}x,{v['low_ago']}b)|W:{v['w']}|{v['pos']}%]" for tf, v in roadway_100b.items()) if roadway_100b else "None"
        trail_m5_str = " -> ".join(f"[{t['floor']:.0f}-{t['ceil']:.0f}](W:{t['w']:.0f})" for t in highway_trail_m5) if highway_trail_m5 else "None"

        badge_line1 = f"[REGIME & FOOTPRINT] {regime} | Power: {pricing_power} | Bid: {curr_bid:.1f} (Spr {live_spread_pts}) | Vel: {tick_velocity_tpm:.0f} t/m"
        badge_line2 = f"- Coordinates: POC {poc_price:.1f} | PDL {pdl_price:.1f} ({dist_pdl_pts:+.1f}) | PDH {pdh_price:.1f} ({dist_pdh_pts:+.1f}) | FVG Below: {fvg_below_str} | FVG Above: {fvg_above_str}"
        badge_line3 = f"- 100b Roadways: {roadway_badge_str}"
        badge_line3b = f"- M5 Highway Trail (60b->Now): {trail_m5_str}"
        badge_line4 = f"- 4M Footprint Deltas (30b=120m): {deltas_4m_str}"
        badge_line5 = f"- 4M Displacements (pts): {disp_4m_str}"
        badge_line6 = f"- M1 Recent (Last 10m): Deltas {m1_recent_deltas_str} | Prices {m1_recent_prices_str}"
        badge_line7 = f"- Macro & Flows: Real Yield {dfii10_yield}% | 10Y {us10y}% | DXY {dxy} | EURUSD 5m {eurusd_5m_pct:+.3f}% | Next: {next_ev_str}"
        badge_line8 = f"- Directive: {actionable_directive} (Audit full raw metrics via get_market_regime_context)."
        compact_badge = f"{badge_line1}\n{badge_line2}\n{badge_line3}\n{badge_line3b}\n{badge_line4}\n{badge_line5}\n{badge_line6}\n{badge_line7}\n{badge_line8}"

        return {
            "symbol": sym,
            "regime": regime,
            "pricing_power": pricing_power,
            "label_justification": label_justification,
            "actionable_directive": actionable_directive,
            "compact_prompt_badge": compact_badge,
            "raw_metrics": {
                "high_impact_events_today_count": len(high_impact_today),
                "is_holiday_today": is_holiday_today,
                "curr_bid": curr_bid,
                "curr_ask": curr_ask,
                "interval_4m_displacement_pts": disp_4m_pts,
                "interval_4m_range_pts": range_4m_pts,
                "tick_velocity_tpm": tick_velocity_tpm,
                "live_spread_pts": live_spread_pts,
                "cvd_5m_ratio": cvd_5m_ratio,
                "cvd_10b_pressure_pct": cvd_10b_pressure,
                "cvd_divergence": cvd_divergence,
                "in_between_catalysts": in_between_news_info,
                "cross_asset_5m_deltas": {
                    "eurusd_pct": eurusd_5m_pct,
                    "xagusd_pct": xagusd_5m_pct
                },
                "structural_auction": {
                    "poc_price": poc_price,
                    "nearest_air_pocket_below": air_pocket_below,
                    "nearest_air_pocket_above": air_pocket_above,
                    "pdh_price": pdh_price,
                    "pdl_price": pdl_price,
                    "distance_to_pdh_pts": dist_pdh_pts,
                    "distance_to_pdl_pts": dist_pdl_pts,
                    "nearest_fvg_below": nearest_fvg_below,
                    "nearest_fvg_above": nearest_fvg_above
                },
                "roadway_100b": roadway_100b,
                "highway_trail_m5": highway_trail_m5,
                "raw_ohlc_60b": raw_ohlc_60b,
                "raw_footprints_4m_horizon": {
                    "description": "30 rolling non-overlapping 4-minute blocks covering trailing 120 minutes of tape (FIFO, index 29 is most recent)",
                    "deltas": deltas_4m,
                    "displacements_pts": disp_4m,
                    "ranges_pts": ranges_4m,
                    "volumes": vols_4m,
                    "lower_wicks_pts": low_wicks_4m,
                    "upper_wicks_pts": high_wicks_4m
                },
                "raw_footprints_30_m1": {
                    "description": "Trailing 30 1-minute bars minute-by-minute (index 29 is most recent)",
                    "prices": m1_prices,
                    "deltas": m1_deltas,
                    "volumes": m1_volumes,
                    "ranges_pts": m1_ranges,
                    "lower_wicks_pts": m1_lower_wicks,
                    "upper_wicks_pts": m1_upper_wicks
                },
                "macro_yields": {
                    "dfii10_real_yield_pct": dfii10_yield,
                    "us10y_yield_pct": us10y,
                    "dxy_index": dxy,
                    "real_yield_z_score": round(z_macro, 2)
                },
                "econometric_variance_breakdown": {
                    "macro_yield_share_pct": pct_macro,
                    "event_shock_share_pct": pct_event,
                    "tape_momentum_share_pct": pct_tape,
                    "technical_structure_share_pct": pct_tech,
                    "tape_force_scalar": round(tape_force, 2)
                },
                "next_scheduled_event": next_event,
                "last_scheduled_event": last_event,
                "all_events_today": events_today
            },
            "timestamp_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        }

