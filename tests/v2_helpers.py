"""Shared synthetic-data helpers for the daemon v2 pytest suite.

Everything here is pure stdlib. No MetaTrader5 import anywhere.
"""

from datetime import datetime, timezone

from daemon.conditions import EvalContext


def utc(y=2026, m=8, d=22, hh=13, mm=30, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=timezone.utc)


def make_tick(bid=100.0, ask=100.02, last=None, volume=100, ts=None):
    return {
        "bid": bid,
        "ask": ask,
        "last": last if last is not None else (bid + ask) / 2.0,
        "volume": volume,
        "time": (ts or utc()).isoformat(),
    }


def make_bar(close, open_=None, high=None, low=None, volume=100):
    o = open_ if open_ is not None else close
    h = high if high is not None else max(o, close)
    lo = low if low is not None else min(o, close)
    return {"open": o, "high": h, "low": lo, "close": close, "volume": volume}


def make_ctx(tick=None, prev_tick=None, bars=None, daily_bars=None,
             snapshot=None, account=None, positions=None, now=None,
             point_size=0.01, rule_direction="any", symbol="XAUUSD"):
    return EvalContext(
        symbol=symbol,
        tick=tick or make_tick(),
        prev_tick=prev_tick,
        bars=bars or [],
        daily_bars=daily_bars or [],
        snapshot=snapshot if snapshot is not None else {},
        account=account or {"balance": 100000.0, "equity": 100000.0,
                            "margin": 0.0, "free_margin": 100000.0},
        positions=positions or [],
        now_utc=now or utc(),
        point_size=point_size,
        rule_direction=rule_direction,
    )


def rising_bars(n=40, start=100.0, step=1.0, volume=100):
    """n ascending closes starting at start."""
    return [make_bar(start + i * step, volume=volume) for i in range(n)]


def falling_bars(n=40, start=140.0, step=-1.0, volume=100):
    return [make_bar(start + i * step, volume=volume) for i in range(n)]
