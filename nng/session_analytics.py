# -*- coding: utf-8 -*-
# nng/session_analytics.py - ICT Session Analysis and IPDA Model
#
# Sources:
#   Huddleston, M.J. (ICT) - Inner Circle Trader educational content
#   IPDA = Interbank Price Delivery Algorithm (conceptual model)
#   AMD = Accumulation, Manipulation, Distribution (Power of Three)
#   Killzones: Asia 22:00-01:00 UTC, London 02:00-05:00 UTC, NY 07:00-10:00 UTC

from datetime import datetime, timezone, time
from typing import Dict, Any, Optional, Tuple


# UTC killzone windows
KILLZONES = {
    "ASIA": (time(22, 0), time(1, 0)),       # 22:00-01:00 UTC (crosses midnight)
    "LONDON_OPEN": (time(2, 0), time(5, 0)),  # 02:00-05:00 UTC
    "LONDON_CLOSE": (time(10, 0), time(12, 0)), # 10:00-12:00 UTC
    "NY_OPEN": (time(7, 0), time(10, 0)),     # 07:00-10:00 UTC
    "NY_PM": (time(13, 0), time(16, 0)),      # 13:00-16:00 UTC
}


def get_active_killzone(utc_dt: Optional[datetime] = None) -> Tuple[str, bool]:
    """
    Identify current active ICT killzone.
    Returns (killzone_name, is_active).
    """
    if utc_dt is None:
        utc_dt = datetime.now(timezone.utc)
    t = utc_dt.time().replace(tzinfo=None)
    hour_min = t.hour * 60 + t.minute

    # Asia (crosses midnight: 22:00-01:00)
    asia_active = (hour_min >= 22 * 60) or (hour_min < 1 * 60)
    # London Open: 02:00-05:00
    london_active = 2 * 60 <= hour_min < 5 * 60
    # NY Open: 07:00-10:00
    ny_active = 7 * 60 <= hour_min < 10 * 60
    # London Close: 10:00-12:00
    lc_active = 10 * 60 <= hour_min < 12 * 60
    # NY PM: 13:00-16:00
    nypm_active = 13 * 60 <= hour_min < 16 * 60

    if london_active:
        return "LONDON_OPEN_KZ", True
    elif ny_active:
        return "NY_OPEN_KZ", True
    elif asia_active:
        return "ASIA_KZ", True
    elif lc_active:
        return "LONDON_CLOSE_KZ", True
    elif nypm_active:
        return "NY_PM_KZ", True
    else:
        return "OFF_SESSION", False


def classify_amd_phase(
    price: float,
    session_open: float,
    session_high: float,
    session_low: float,
    cvd_10b: float,
    velocity_tpm: float,
    displacement: bool,
) -> str:
    """
    ICT AMD Cycle: Accumulation -> Manipulation -> Distribution.
    Accumulation: price near open, low velocity, balanced delta
    Manipulation: price extends beyond session high/low (sweep), velocity spike
    Distribution: post-sweep, displacement candle, directional move
    """
    session_range = max(session_high - session_low, 0.1)
    price_position = (price - session_low) / session_range  # 0=low, 1=high

    if displacement:
        return "AMD_DISTRIBUTION"
    elif velocity_tpm > 120 and (price > session_high or price < session_low):
        return "AMD_MANIPULATION_SWEEP"
    elif velocity_tpm < 60 and abs(price - session_open) < session_range * 0.2:
        return "AMD_ACCUMULATION"
    elif velocity_tpm > 100:
        return "AMD_EXPANSION"
    else:
        return "AMD_UNCLEAR"


def detect_liquidity_sweeps(
    price: float,
    asian_high: float,
    asian_low: float,
    pdh: float,
    pdl: float,
    sweep_threshold_pts: float = 3.0
) -> Dict[str, Any]:
    """
    Detect if current price has swept key liquidity levels.
    Asian High/Low, Previous Day High/Low are primary sweep targets.
    """
    swept_asian_high = price > asian_high + sweep_threshold_pts
    swept_asian_low = price < asian_low - sweep_threshold_pts
    swept_pdh = price > pdh + sweep_threshold_pts
    swept_pdl = price < pdl - sweep_threshold_pts

    any_swept = any([swept_asian_high, swept_asian_low, swept_pdh, swept_pdl])
    sweep_direction = None
    if swept_asian_high or swept_pdh:
        sweep_direction = "ABOVE_SWEPT"  # Stop hunt above, expect reversal down
    elif swept_asian_low or swept_pdl:
        sweep_direction = "BELOW_SWEPT"  # Stop hunt below, expect reversal up

    return {
        "swept_asian_high": swept_asian_high,
        "swept_asian_low": swept_asian_low,
        "swept_pdh": swept_pdh,
        "swept_pdl": swept_pdl,
        "any_liquidity_swept": any_swept,
        "sweep_direction": sweep_direction,
    }


def session_analysis(
    price: float,
    cvd_10b: float,
    velocity_tpm: float,
    displacement: bool,
    utc_dt: Optional[datetime] = None,
    asian_high: float = 0.0,
    asian_low: float = 0.0,
    pdh: float = 0.0,
    pdl: float = 0.0,
    session_open: float = 0.0,
    session_high: float = 0.0,
    session_low: float = 0.0,
) -> Dict[str, Any]:
    """Full session analysis combining killzone + AMD + liquidity sweeps."""
    if utc_dt is None:
        utc_dt = datetime.now(timezone.utc)
    killzone, in_kz = get_active_killzone(utc_dt)
    amd = classify_amd_phase(price, session_open or price, session_high or price + 5, session_low or price - 5, cvd_10b, velocity_tpm, displacement)
    sweeps = detect_liquidity_sweeps(price, asian_high or price + 10, asian_low or price - 10, pdh or price + 15, pdl or price - 15)

    # ICT Setup: In killzone + sweep occurred + displacement = highest probability trade
    ict_setup_active = in_kz and sweeps["any_liquidity_swept"] and amd in ("AMD_DISTRIBUTION", "AMD_EXPANSION")

    return {
        "killzone": killzone,
        "in_killzone": in_kz,
        "amd_phase": amd,
        "sweeps": sweeps,
        "ict_setup_active": ict_setup_active,
        "utc_hour": utc_dt.hour,
    }
