"""
======================================================================
               ALPHA V1 - GENERAL MARKET TIME AND SESSION HELPER
======================================================================
General, non-event-specific temporal awareness module.
Provides:
1. Live synchronized clocks for all global financial centers (UTC, NY, London, Tokyo, Sydney).
2. Live active session classification and next session transitions.
3. General target time parser and countdown calculator for arbitrary times/events.
======================================================================
"""

import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
from zoneinfo import ZoneInfo

TZ_NY = ZoneInfo("America/New_York")
TZ_LONDON = ZoneInfo("Europe/London")
TZ_TOKYO = ZoneInfo("Asia/Tokyo")
TZ_SYDNEY = ZoneInfo("Australia/Sydney")
TZ_UTC = timezone.utc

def format_timedelta(td: timedelta) -> str:
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        return f"{abs(total_seconds)}s ago"
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)

def parse_target_time(time_str: str, default_tz: str = "America/New_York", reference_utc: Optional[datetime] = None) -> Optional[datetime]:
    if not time_str or not isinstance(time_str, str):
        return None
    s = time_str.strip()
    ref = reference_utc or datetime.now(TZ_UTC)
    selected_tz = ZoneInfo(default_tz)
    s_upper = s.upper()
    if "UTC" in s_upper or "GMT" in s_upper or s.endswith("Z"):
        selected_tz = TZ_UTC
        s = re.sub(r"\b(UTC|GMT|Z)\b", "", s, flags=re.IGNORECASE).strip()
    elif "EDT" in s_upper or "EST" in s_upper or " ET" in s_upper or "NY" in s_upper:
        selected_tz = TZ_NY
        s = re.sub(r"\b(EDT|EST|ET|NY)\b", "", s, flags=re.IGNORECASE).strip()
    elif "BST" in s_upper or "LON" in s_upper:
        selected_tz = TZ_LONDON
        s = re.sub(r"\b(BST|LONDON|LON)\b", "", s, flags=re.IGNORECASE).strip()
    elif "JST" in s_upper or "TOKYO" in s_upper:
        selected_tz = TZ_TOKYO
        s = re.sub(r"\b(JST|TOKYO)\b", "", s, flags=re.IGNORECASE).strip()
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=selected_tz)
        return dt.astimezone(TZ_UTC)
    except Exception:
        pass
    date_patterns = [
        ("%Y-%m-%d %H:%M:%S", False),
        ("%Y-%m-%d %H:%M", False),
        ("%Y-%m-%d %I:%M %p", True),
        ("%Y-%m-%d %I:%M:%S %p", True),
    ]
    for fmt, _ in date_patterns:
        try:
            dt = datetime.strptime(s, fmt)
            dt = dt.replace(tzinfo=selected_tz)
            return dt.astimezone(TZ_UTC)
        except Exception:
            pass
    time_patterns = [
        ("%I:%M %p", True),
        ("%I:%M:%S %p", True),
        ("%I %p", True),
        ("%H:%M:%S", False),
        ("%H:%M", False),
    ]
    for fmt, _ in time_patterns:
        try:
            t = datetime.strptime(s, fmt).time()
            ref_local = ref.astimezone(selected_tz)
            dt_local = datetime.combine(ref_local.date(), t, tzinfo=selected_tz)
            dt_utc = dt_local.astimezone(TZ_UTC)
            return dt_utc
        except Exception:
            pass
    return None

def get_market_time_context(target_time: str = "", target_timezone: str = "America/New_York") -> Dict[str, Any]:
    now_utc = datetime.now(TZ_UTC)
    now_ny = now_utc.astimezone(TZ_NY)
    now_lon = now_utc.astimezone(TZ_LONDON)
    now_tok = now_utc.astimezone(TZ_TOKYO)
    now_syd = now_utc.astimezone(TZ_SYDNEY)
    clocks = {
        "utc": {
            "iso": now_utc.isoformat(),
            "formatted": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "hour": now_utc.hour,
            "minute": now_utc.minute
        },
        "new_york_et": {
            "iso": now_ny.isoformat(),
            "formatted": now_ny.strftime("%Y-%m-%d %I:%M:%S %p %Z"),
            "tz_abbr": now_ny.tzname(),
            "hour_24": now_ny.hour,
            "hour_12": int(now_ny.strftime("%I")),
            "minute": now_ny.minute
        },
        "london_bst": {
            "iso": now_lon.isoformat(),
            "formatted": now_lon.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "tz_abbr": now_lon.tzname()
        },
        "tokyo_jst": {
            "iso": now_tok.isoformat(),
            "formatted": now_tok.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "tz_abbr": now_tok.tzname()
        },
        "sydney_aest": {
            "iso": now_syd.isoformat(),
            "formatted": now_syd.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "tz_abbr": now_syd.tzname()
        }
    }
    weekday = now_utc.weekday()
    utc_hour = now_utc.hour
    utc_minute = now_utc.minute
    utc_dec_hour = utc_hour + utc_minute / 60.0
    is_weekend = (weekday == 5) or (weekday == 4 and utc_hour >= 22) or (weekday == 6 and utc_hour < 21)
    if is_weekend:
        active_session = "WEEKEND_MARKET_CLOSED"
        session_description = "Global interbank and broker markets closed for the weekend (Re-opens Sunday 21:00 UTC)."
        is_market_open = False
    elif 7.0 <= utc_dec_hour < 13.0:
        active_session = "LONDON_SESSION"
        session_description = "European Institutional Morning Session (High FX / Gold Liquidity)."
        is_market_open = True
    elif 13.0 <= utc_dec_hour < 16.0:
        active_session = "LONDON_NY_OVERLAP"
        session_description = "Peak Global Liquidity and Momentum Window (London Afternoon + NY Morning)."
        is_market_open = True
    elif 16.0 <= utc_dec_hour < 21.0:
        active_session = "NEW_YORK_SESSION"
        session_description = "US Institutional Session (US Equity and Fixed Income Hours)."
        is_market_open = True
    else:
        active_session = "ASIAN_SESSION"
        session_description = "Asian Session Range and Consolidation Window (Tokyo / Sydney)."
        is_market_open = True
    today_date_utc = now_utc.date()
    def make_today_utc(h, m=0):
        return datetime(today_date_utc.year, today_date_utc.month, today_date_utc.day, h, m, tzinfo=TZ_UTC)
    session_anchors = {
        "london_open_0700_utc": make_today_utc(7, 0),
        "us_macro_release_window_1230_utc": make_today_utc(12, 30),
        "us_equity_open_1330_utc": make_today_utc(13, 30),
        "london_close_1600_utc": make_today_utc(16, 0),
        "ny_close_2100_utc": make_today_utc(21, 0),
        "daily_roll_2200_utc": make_today_utc(22, 0)
    }
    transitions = {}
    for name, dt_anchor in session_anchors.items():
        diff = (dt_anchor - now_utc).total_seconds()
        transitions[name] = {
            "utc_time": dt_anchor.strftime("%H:%M UTC"),
            "ny_time": dt_anchor.astimezone(TZ_NY).strftime("%I:%M %p %Z"),
            "seconds_remaining": round(diff, 1),
            "minutes_remaining": round(diff / 60.0, 1),
            "hours_remaining": round(diff / 3600.0, 2),
            "is_past_today": diff < 0,
            "status": "COMPLETED_TODAY" if diff < 0 else f"in {format_timedelta(timedelta(seconds=diff))}"
        }
    res = {
        "status": "SUCCESS",
        "current_clocks": clocks,
        "active_session": active_session,
        "is_market_open": is_market_open,
        "session_description": session_description,
        "session_transitions": transitions
    }
    if target_time:
        parsed_utc = parse_target_time(target_time, default_tz=target_timezone, reference_utc=now_utc)
        if parsed_utc:
            diff_sec = (parsed_utc - now_utc).total_seconds()
            parsed_ny = parsed_utc.astimezone(TZ_NY)
            parsed_lon = parsed_utc.astimezone(TZ_LONDON)
            cd_text = format_timedelta(timedelta(seconds=abs(diff_sec)))
            timing_status = f"occurred {cd_text} ago" if diff_sec < 0 else f"occurs in {cd_text}"
            res["target_time_evaluation"] = {
                "input_query": target_time,
                "parsed_utc": parsed_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "parsed_new_york_et": parsed_ny.strftime("%Y-%m-%d %I:%M:%S %p %Z"),
                "parsed_london": parsed_lon.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "is_past": diff_sec < 0,
                "seconds_remaining": round(diff_sec, 1),
                "minutes_remaining": round(diff_sec / 60.0, 1),
                "hours_remaining": round(diff_sec / 3600.0, 2),
                "formatted_countdown": cd_text,
                "summary": f"Target '{target_time}' corresponds to {parsed_utc.strftime('%H:%M UTC')} / {parsed_ny.strftime('%I:%M %p %Z')} ({timing_status})."
            }
        else:
            res["target_time_evaluation"] = {
                "input_query": target_time,
                "error": f"Could not parse time '{target_time}'. Please provide standard format (e.g. '8:30 AM ET', '12:30 UTC', '14:00')."
            }
    return res
