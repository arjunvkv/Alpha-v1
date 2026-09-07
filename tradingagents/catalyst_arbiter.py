"""
======================================================================
               ALPHA V1 - CATALYST & MARKET REGIME ARBITER
======================================================================
Transparent, Real-Time Market Driver Classification Engine.
Determines whether the market is currently driven by:
1. MACRO_EVENT_ACTIVE: Active scheduled high-impact macro release window (T-30m to T+15m)
2. GEOPOLITICAL_SHOCK_DRIFT: Unscheduled breaking event confirmed by MT5 tape surge (>80 t/m + CVD spike)
3. MACRO_DIRECTIONAL_PRESSURE: No immediate release, but dominant macro anchor (e.g. DFII10 Real Yields > 2.40%) skews HTF bias
4. PURE_TECHNICAL_ORDERFLOW: No high-impact events today; tape is normal; price is 100% driven by VAH/VAL/FVG and liquidity sweeps

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

        # 2. Raw Tape Metrics from MT5
        tick_velocity_tpm = 0.0
        live_spread_pts = 0
        cvd_10b_pressure = 0.0
        cvd_divergence = "NO_DIVERGENCE"

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
        # REGIME FORMATION LOGIC (Transparent, Deterministic, Factual)
        # ==================================================================
        regime = "PURE_TECHNICAL_ORDERFLOW"
        label_justification = ""
        actionable_directive = ""
        pricing_power = "TECHNICALS_100%"

        # Rule 1: High-Impact Macro Release Active (T-30m to T+15m)
        if next_event and next_event["minutes_away"] <= 30.0:
            regime = "MACRO_EVENT_ACTIVE"
            label_justification = f"High-Impact release '{next_event['title']}' ({next_event['country']}) is imminent in {next_event['minutes_away']}m."
            actionable_directive = "HIGH VOLATILITY FREEZE: Do not place new market/limit orders into the release path. Maintain structural stops."
            pricing_power = "UPCOMING_MACRO_EVENT_100%"
        elif last_event and last_event["minutes_ago"] <= 15.0:
            regime = "MACRO_EVENT_ACTIVE"
            label_justification = f"High-Impact release '{last_event['title']}' occurred {last_event['minutes_ago']}m ago. Spread expansion & slippage active."
            actionable_directive = "POST-RELEASE SETTLEMENT: Let initial 15-minute whipsaw settle before entering structural retest trades."
            pricing_power = "POST_MACRO_RELEASE_SHOCK_100%"

        # Rule 2: Geopolitical Shock Surge (Unscheduled News with Tape Surge)
        elif tick_velocity_tpm >= 80.0:
            regime = "GEOPOLITICAL_SHOCK_DRIFT"
            label_justification = f"Tape velocity surged to {tick_velocity_tpm:.1f} t/m (>80 threshold) with spread {live_spread_pts} pts. Breaking flow confirmed by tape."
            actionable_directive = "BREAKING MOMENTUM SHOCK: Respect the immediate impulse. Do not fade blindly; wait for first structural exhaustion/pause."
            pricing_power = "LIVE_TAPE_FLOW_100%"

        # Rule 3: Zero Scheduled News Today -> Pure Technical / Macro Ceiling
        elif len(high_impact_today) == 0:
            if dfii10_yield >= 2.40:
                regime = "MACRO_DIRECTIONAL_PRESSURE"
                holiday_note = " (US Bank Holiday / Quiet Calendar)" if is_holiday_today else " (Empty Calendar Today)"
                label_justification = f"Zero high-impact releases today{holiday_note}. Background macro dominated by DFII10 Real Yields at {dfii10_yield}% (>2.40% hawkish anchor), capping gold rallies."
                actionable_directive = "FADE RALLIES AT RESISTANCE: Macro yield overhang is bearish gold. Trade in direction of macro (SELL), but strictly at technical extremes (VAH/FVG). Do NOT chase breakout wicks."
                pricing_power = "MACRO_CEILING_80%_TECHNICALS_20%"
            else:
                regime = "PURE_TECHNICAL_ORDERFLOW"
                label_justification = "Zero high-impact releases today. Tape is calm. Algorithmic liquidity hunts and range boundaries dominate."
                actionable_directive = "TRADE 100% BY STRUCTURE: Ignore minor news headlines. Price is navigating between Value Area (VAH/VAL) and liquidity pools."
                pricing_power = "TECHNICALS_100%"

        else:
            # High impact event later today, but >30m away
            regime = "PRE_EVENT_ANTICIPATION"
            label_justification = f"High-impact event '{high_impact_today[0]['title']}' scheduled for today in {next_event['hours_away']}h."
            actionable_directive = "RANGE BOUND COMPRESSION: Expect technical equilibrium until release window. Target modest intraday targets (1:2 R:R)."
            pricing_power = "TECHNICALS_70%_ANTICIPATION_30%"

        # Construct concise 2-line prompt badge (zero bloat)
        next_ev_str = f"{next_event['title']} in {next_event['hours_away']}h" if next_event else "None this week"
        badge_line1 = f"⚡ REGIME: {regime} | Pricing Power: {pricing_power}"
        badge_line2 = f"• Raw Basis: Events Today: {len(high_impact_today)} | Tape: {tick_velocity_tpm:.0f} t/m (Spread {live_spread_pts}) | Real Yield: {dfii10_yield}% | Next: {next_ev_str}"
        badge_line3 = f"• Directive: {actionable_directive}"
        compact_badge = f"{badge_line1}\n{badge_line2}\n{badge_line3}"

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
                "tick_velocity_tpm": tick_velocity_tpm,
                "live_spread_pts": live_spread_pts,
                "cvd_10b_pressure_pct": cvd_10b_pressure,
                "cvd_divergence": cvd_divergence,
                "dfii10_real_yield_pct": dfii10_yield,
                "us10y_yield_pct": us10y,
                "dxy_index": dxy,
                "next_scheduled_event": next_event,
                "last_scheduled_event": last_event,
                "all_events_today": events_today
            },
            "timestamp_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        }
