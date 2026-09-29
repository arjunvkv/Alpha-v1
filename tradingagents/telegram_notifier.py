"""
Alpha Desk Telegram Notifier
============================
Two-channel alert system wired into the MCP server.

Channel 1 — Alpha Pending Orders (@EscanorDeskPending):
  • Order placed (pending limit / stop)
  • Order modified (price / SL / TP changed)
  • Order cancelled (with reason, age, sanctity gate status)
  • Sanctity gate BLOCKED a cancel attempt

Channel 2 — Alpha Positions (@EscanorDeskPositions):
  • Order triggered / filled (entry, SL, TP, R:R)
  • SL moved (ratchet stage 1/2/3 or break-even)
  • Position closed (P&L, pips, duration)
  • TP hit

Design: all send_* functions are fire-and-forget. They NEVER raise.
         A Telegram outage must never block broker execution.
"""

import threading
import urllib.request
import urllib.parse
import json
import time
import logging
from datetime import datetime, timezone

log = logging.getLogger("telegram_notifier")

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN        = "8748826581:AAEoP9rXDeINirO7rov-TcE7ikkY3rkWC1M"
PENDING_CHAT_ID  = -1003971851512   # Alpha Pending Orders  @EscanorDeskPending
POSITION_CHAT_ID = -1004324335052   # Alpha Positions       @EscanorDeskPositions

TELEGRAM_API     = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
TIMEOUT_S        = 6   # hard cap — broker never waits on Telegram

# ── Internal send (thread-safe, never raises) ─────────────────────────────────
def _send(chat_id: int, text: str) -> None:
    """Fire-and-forget HTTP POST to Telegram. Called from a daemon thread."""
    try:
        payload = json.dumps({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }).encode()
        req = urllib.request.Request(
            TELEGRAM_API,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            _ = resp.read()
    except Exception as exc:
        log.warning(f"[TelegramNotifier] send failed (non-fatal): {exc}")


def _fire(chat_id: int, text: str) -> None:
    """Launch send in a daemon thread so caller never blocks."""
    t = threading.Thread(target=_send, args=(chat_id, text), daemon=True)
    t.start()


def _now_ist() -> str:
    from datetime import timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).strftime("%H:%M:%S IST")


def _rr(entry: float, sl: float, tp: float) -> str:
    try:
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        if risk <= 0:
            return "N/A"
        return f"{reward / risk:.2f}R"
    except Exception:
        return "N/A"


# ══════════════════════════════════════════════════════════════════════════════
#  PENDING ORDERS CHANNEL
# ══════════════════════════════════════════════════════════════════════════════

def notify_order_placed(
    ticket: int,
    symbol: str,
    order_type: str,   # BUY_STOP / SELL_STOP / BUY_LIMIT / SELL_LIMIT
    price: float,
    sl: float,
    tp: float,
    volume: float,
    comment: str = "",
) -> None:
    prong = "B" if "STOP" in order_type.upper() else "A"
    side_emoji = "🟢" if "BUY" in order_type.upper() else "🔴"
    rr = _rr(price, sl, tp)
    sl_pts = round(abs(price - sl), 2)
    tp_pts = round(abs(tp - price), 2)
    text = (
        f"{side_emoji} <b>ORDER PLACED — Prong {prong}</b>\n"
        f"🎫 #{ticket}  |  {symbol}  |  {order_type}\n"
        f"📍 Entry: <b>{price:.2f}</b>\n"
        f"🛑 SL: {sl:.2f}  ({sl_pts} pts)\n"
        f"🎯 TP: {tp:.2f}  ({tp_pts} pts)\n"
        f"📐 R:R: <b>{rr}</b>  |  📦 {volume}L\n"
        f"💬 {comment}\n"
        f"🕐 {_now_ist()}"
    )
    _fire(PENDING_CHAT_ID, text)


def notify_order_modified(
    ticket: int,
    symbol: str,
    order_type: str,
    new_price: float = 0.0,
    new_sl: float = 0.0,
    new_tp: float = 0.0,
) -> None:
    lines = [
        f"✏️ <b>ORDER MODIFIED</b>",
        f"🎫 #{ticket}  |  {symbol}  |  {order_type}",
    ]
    if new_price: lines.append(f"📍 New Entry: <b>{new_price:.2f}</b>")
    if new_sl:    lines.append(f"🛑 New SL: {new_sl:.2f}")
    if new_tp:    lines.append(f"🎯 New TP: {new_tp:.2f}")
    if new_price and new_sl and new_tp:
        lines.append(f"📐 R:R: <b>{_rr(new_price, new_sl, new_tp)}</b>")
    lines.append(f"🕐 {_now_ist()}")
    _fire(PENDING_CHAT_ID, "\n".join(lines))


def notify_order_cancelled(
    ticket: int,
    symbol: str,
    order_type: str,
    price: float,
    age_minutes: float,
    reason: str,
    forced: bool = False,
) -> None:
    force_tag = "  ⚠️ <b>FORCE OVERRIDE</b>" if forced else ""
    text = (
        f"❌ <b>ORDER CANCELLED</b>{force_tag}\n"
        f"🎫 #{ticket}  |  {symbol}  |  {order_type}\n"
        f"📍 Was at: {price:.2f}\n"
        f"⏱ Age: {age_minutes:.1f} min\n"
        f"📋 Reason: {reason}\n"
        f"🕐 {_now_ist()}"
    )
    _fire(PENDING_CHAT_ID, text)


def notify_sanctity_gate_blocked(
    ticket: int,
    symbol: str,
    order_type: str,
    price: float,
    age_minutes: float,
    block_reason: str,
) -> None:
    """Fired when the sanctity gate REJECTS a cancel attempt."""
    text = (
        f"🛡 <b>SANCTITY GATE — CANCEL BLOCKED</b>\n"
        f"🎫 #{ticket}  |  {symbol}  |  {order_type}\n"
        f"📍 Price: {price:.2f}  |  ⏱ Age: {age_minutes:.1f} min\n"
        f"🔒 Gate: {block_reason}\n"
        f"📌 Order remains alive on MT5 book.\n"
        f"🕐 {_now_ist()}"
    )
    _fire(PENDING_CHAT_ID, text)


# ══════════════════════════════════════════════════════════════════════════════
#  POSITIONS CHANNEL
# ══════════════════════════════════════════════════════════════════════════════

def notify_order_filled(
    ticket: int,
    symbol: str,
    side: str,         # BUY / SELL
    fill_price: float,
    sl: float,
    tp: float,
    volume: float,
    comment: str = "",
) -> None:
    side_emoji = "🚀" if side.upper() == "BUY" else "💥"
    rr = _rr(fill_price, sl, tp)
    sl_pts = round(abs(fill_price - sl), 2)
    tp_pts = round(abs(tp - fill_price), 2)
    text = (
        f"{side_emoji} <b>ORDER TRIGGERED — LIVE POSITION</b>\n"
        f"🎫 #{ticket}  |  {symbol}  |  {side}\n"
        f"📍 Fill: <b>{fill_price:.2f}</b>\n"
        f"🛑 SL: {sl:.2f}  ({sl_pts} pts risk)\n"
        f"🎯 TP: {tp:.2f}  ({tp_pts} pts target)\n"
        f"📐 R:R: <b>{rr}</b>  |  📦 {volume}L\n"
        f"💬 {comment}\n"
        f"🕐 {_now_ist()}"
    )
    _fire(POSITION_CHAT_ID, text)


def notify_sl_moved(
    ticket: int,
    symbol: str,
    side: str,
    old_sl: float,
    new_sl: float,
    stage: str,        # e.g. "Stage 1 — Break-Even", "Stage 2 — Profit Lock"
    entry: float = 0.0,
) -> None:
    direction = "▲" if new_sl > old_sl else "▼"
    locked = ""
    if entry:
        locked_pts = round(new_sl - entry if side.upper() == "BUY" else entry - new_sl, 2)
        locked = f"\n💰 Locked: {'+' if locked_pts >= 0 else ''}{locked_pts} pts"
    text = (
        f"🔧 <b>SL MOVED — {stage}</b>\n"
        f"🎫 #{ticket}  |  {symbol}  |  {side}\n"
        f"🛑 SL: {old_sl:.2f} → <b>{new_sl:.2f}</b>  {direction}{locked}\n"
        f"🕐 {_now_ist()}"
    )
    _fire(POSITION_CHAT_ID, text)


def notify_position_closed(
    ticket: int,
    symbol: str,
    side: str,
    entry: float,
    close_price: float,
    volume: float,
    profit: float,
    close_reason: str = "SL/TP",
    duration_minutes: float = 0.0,
) -> None:
    pnl_emoji = "✅" if profit >= 0 else "❌"
    pts = round((close_price - entry) * (1 if side.upper() == "BUY" else -1), 2)
    duration_str = f"{duration_minutes:.0f} min" if duration_minutes else ""
    text = (
        f"{pnl_emoji} <b>POSITION CLOSED — {close_reason}</b>\n"
        f"🎫 #{ticket}  |  {symbol}  |  {side}\n"
        f"📍 Entry: {entry:.2f}  →  Close: <b>{close_price:.2f}</b>\n"
        f"📊 P&L: <b>{'+'if profit>=0 else ''}{profit:.2f} USD</b>  ({'+' if pts>=0 else ''}{pts} pts)\n"
        f"📦 {volume}L  |  ⏱ {duration_str}\n"
        f"🕐 {_now_ist()}"
    )
    _fire(POSITION_CHAT_ID, text)


def notify_tp_hit(
    ticket: int,
    symbol: str,
    side: str,
    entry: float,
    tp: float,
    volume: float,
    profit: float,
) -> None:
    pts = round(abs(tp - entry), 2)
    text = (
        f"🏆 <b>TP HIT — WINNER</b>\n"
        f"🎫 #{ticket}  |  {symbol}  |  {side}\n"
        f"📍 Entry: {entry:.2f}  →  TP: <b>{tp:.2f}</b>  (+{pts} pts)\n"
        f"💰 Profit: <b>+{profit:.2f} USD</b>  |  📦 {volume}L\n"
        f"🕐 {_now_ist()}"
    )
    _fire(POSITION_CHAT_ID, text)


# ── Startup test ──────────────────────────────────────────────────────────────
def send_startup_ping() -> None:
    """Send a single startup message to both channels to verify connectivity."""
    ts = _now_ist()
    _fire(PENDING_CHAT_ID,  f"⚡ <b>Alpha Desk ONLINE</b>\n🤖 Escanor v98 | Pending Orders monitor active\n🕐 {ts}")
    _fire(POSITION_CHAT_ID, f"⚡ <b>Alpha Desk ONLINE</b>\n🤖 Escanor v98 | Positions monitor active\n🕐 {ts}")


if __name__ == "__main__":
    print("Sending test alerts to both channels...")
    send_startup_ping()
    time.sleep(3)
    print("Done. Check Telegram.")
