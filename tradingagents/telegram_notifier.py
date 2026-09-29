"""
Alpha Desk Telegram Notifier
============================
Two-channel alert system wired into both MCP server and 24/7 daemon watcher.

Channel 1 — Alpha Pending Orders (@EscanorDeskPending):
  • Order placed (pending limit / stop)
  • Order modified (price / SL / TP changed)
  • Order cancelled (with reason, age)

Channel 2 — Alpha Positions (@EscanorDeskPositions):
  • Order triggered / filled (entry, SL, TP, R:R)
  • SL moved (ratchet stage 1/2/3, pullback cut, or break-even)
  • Position closed (P&L, pips, duration)
  • TP hit

Design:
  - All calls are non-blocking fire-and-forget daemon threads.
  - Dual connection path: direct internet first, fallback to proxy.
  - HTML entity safe with html.escape.
  - Persistent disk audit log at logs/telegram_alerts.log.
"""

import threading
import urllib.request
import urllib.parse
import json
import time
import logging
import html
from pathlib import Path
from datetime import datetime, timezone, timedelta

log = logging.getLogger("telegram_notifier")

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN        = "8748826581:AAEoP9rXDeINirO7rov-TcE7ikkY3rkWC1M"
PENDING_CHAT_ID  = -1003971851512   # Alpha Pending Orders  @EscanorDeskPending
POSITION_CHAT_ID = -1004324335052   # Alpha Positions       @EscanorDeskPositions

TELEGRAM_API     = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
TIMEOUT_S        = 12

LOG_DIR = Path(r"C:\Trading\Alpha\logs")
ALERT_LOG = LOG_DIR / "telegram_alerts.log"

def _append_log(line: str) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(ALERT_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{_now_ist()}] {line}\n")
    except Exception:
        pass


def _now_ist() -> str:
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S IST")


def _rr(entry: float, sl: float, tp: float) -> str:
    try:
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        if risk <= 0:
            return "N/A"
        return f"{reward / risk:.2f}R"
    except Exception:
        return "N/A"


# ── Internal send (thread-safe, dual-path, never raises) ───────────────────────
def _send(chat_id: int, text: str) -> None:
    """Fire-and-forget HTTP POST to Telegram with direct + proxy dual attempt."""
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode("utf-8")

    # Path 1: Direct connection bypassing environment proxies
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(
            TELEGRAM_API,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "EscanorTelegramBot/1.0"},
            method="POST",
        )
        with opener.open(req, timeout=TIMEOUT_S) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            _append_log(f"SENT to {chat_id} (direct) - Status {resp.status}")
            return
    except Exception as e_direct:
        _append_log(f"Direct send failed ({e_direct}), trying fallback...")

    # Path 2: Fallback with default environment proxy handler
    try:
        req = urllib.request.Request(
            TELEGRAM_API,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "EscanorTelegramBot/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            _append_log(f"SENT to {chat_id} (proxy) - Status {resp.status}")
            return
    except Exception as e_proxy:
        _append_log(f"ERROR: All send paths failed for chat {chat_id}: {e_proxy}")
        log.warning(f"[TelegramNotifier] Send failed: {e_proxy}")


def _fire(chat_id: int, text: str) -> None:
    """Launch send in a daemon thread so caller never blocks."""
    t = threading.Thread(target=_send, args=(chat_id, text), daemon=True)
    t.start()


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
    try:
        prong = "B" if "STOP" in str(order_type).upper() else "A"
        side_emoji = "🟢" if "BUY" in str(order_type).upper() else "🔴"
        rr = _rr(price, sl, tp)
        sl_pts = round(abs(price - sl), 2) if sl else 0.0
        tp_pts = round(abs(tp - price), 2) if tp else 0.0
        safe_comment = html.escape(str(comment or ""))
        safe_type = html.escape(str(order_type))
        safe_symbol = html.escape(str(symbol))
        text = (
            f"{side_emoji} <b>ORDER PLACED — Prong {prong}</b>\n"
            f"🎫 #{ticket}  |  {safe_symbol}  |  {safe_type}\n"
            f"📍 Entry: <b>{price:.2f}</b>\n"
            f"🛑 SL: {sl:.2f}  ({sl_pts} pts)\n"
            f"🎯 TP: {tp:.2f}  ({tp_pts} pts)\n"
            f"📐 R:R: <b>{rr}</b>  |  📦 {volume}L\n"
            f"💬 {safe_comment}\n"
            f"🕐 {_now_ist()}"
        )
        _append_log(f"QUEUE notify_order_placed #{ticket} ({safe_type} @ {price:.2f})")
        _fire(PENDING_CHAT_ID, text)
    except Exception as exc:
        _append_log(f"ERROR notify_order_placed: {exc}")


def notify_order_modified(
    ticket: int,
    symbol: str,
    order_type: str,
    new_price: float = 0.0,
    new_sl: float = 0.0,
    new_tp: float = 0.0,
) -> None:
    try:
        safe_type = html.escape(str(order_type))
        safe_symbol = html.escape(str(symbol))
        lines = [
            f"✏️ <b>ORDER MODIFIED</b>",
            f"🎫 #{ticket}  |  {safe_symbol}  |  {safe_type}",
        ]
        if new_price: lines.append(f"📍 New Entry: <b>{new_price:.2f}</b>")
        if new_sl:    lines.append(f"🛑 New SL: {new_sl:.2f}")
        if new_tp:    lines.append(f"🎯 New TP: {new_tp:.2f}")
        if new_price and new_sl and new_tp:
            lines.append(f"📐 R:R: <b>{_rr(new_price, new_sl, new_tp)}</b>")
        lines.append(f"🕐 {_now_ist()}")
        _append_log(f"QUEUE notify_order_modified #{ticket}")
        _fire(PENDING_CHAT_ID, "\n".join(lines))
    except Exception as exc:
        _append_log(f"ERROR notify_order_modified: {exc}")


def notify_order_cancelled(
    ticket: int,
    symbol: str,
    order_type: str,
    price: float,
    age_minutes: float,
    reason: str,
    forced: bool = False,
) -> None:
    try:
        force_tag = "  ⚠️ <b>FORCE OVERRIDE</b>" if forced else ""
        safe_reason = html.escape(str(reason or "CIO_CANCEL"))
        safe_type = html.escape(str(order_type))
        safe_symbol = html.escape(str(symbol))
        text = (
            f"❌ <b>ORDER CANCELLED</b>{force_tag}\n"
            f"🎫 #{ticket}  |  {safe_symbol}  |  {safe_type}\n"
            f"📍 Was at: {price:.2f}\n"
            f"⏱ Age: {age_minutes:.1f} min\n"
            f"📋 Reason: {safe_reason}\n"
            f"🕐 {_now_ist()}"
        )
        _append_log(f"QUEUE notify_order_cancelled #{ticket}")
        _fire(PENDING_CHAT_ID, text)
    except Exception as exc:
        _append_log(f"ERROR notify_order_cancelled: {exc}")


def notify_sanctity_gate_blocked(
    ticket: int,
    symbol: str,
    order_type: str,
    price: float,
    age_minutes: float,
    block_reason: str,
) -> None:
    """Fired when the sanctity gate REJECTS a cancel attempt (if gate active)."""
    try:
        safe_reason = html.escape(str(block_reason or ""))
        safe_type = html.escape(str(order_type))
        safe_symbol = html.escape(str(symbol))
        text = (
            f"🛡 <b>SANCTITY GATE — CANCEL BLOCKED</b>\n"
            f"🎫 #{ticket}  |  {safe_symbol}  |  {safe_type}\n"
            f"📍 Price: {price:.2f}  |  ⏱ Age: {age_minutes:.1f} min\n"
            f"🔒 Gate: {safe_reason}\n"
            f"📌 Order remains alive on MT5 book.\n"
            f"🕐 {_now_ist()}"
        )
        _append_log(f"QUEUE notify_sanctity_gate_blocked #{ticket}")
        _fire(PENDING_CHAT_ID, text)
    except Exception as exc:
        _append_log(f"ERROR notify_sanctity_gate_blocked: {exc}")


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
    try:
        side_clean = str(side).upper()
        side_emoji = "🚀" if side_clean == "BUY" else "💥"
        rr = _rr(fill_price, sl, tp)
        sl_pts = round(abs(fill_price - sl), 2) if sl else 0.0
        tp_pts = round(abs(tp - fill_price), 2) if tp else 0.0
        safe_comment = html.escape(str(comment or ""))
        safe_symbol = html.escape(str(symbol))
        text = (
            f"{side_emoji} <b>ORDER TRIGGERED — LIVE POSITION</b>\n"
            f"🎫 #{ticket}  |  {safe_symbol}  |  {side_clean}\n"
            f"📍 Fill: <b>{fill_price:.2f}</b>\n"
            f"🛑 SL: {sl:.2f}  ({sl_pts} pts risk)\n"
            f"🎯 TP: {tp:.2f}  ({tp_pts} pts target)\n"
            f"📐 R:R: <b>{rr}</b>  |  📦 {volume}L\n"
            f"💬 {safe_comment}\n"
            f"🕐 {_now_ist()}"
        )
        _append_log(f"QUEUE notify_order_filled #{ticket} ({side_clean} @ {fill_price:.2f})")
        _fire(POSITION_CHAT_ID, text)
    except Exception as exc:
        _append_log(f"ERROR notify_order_filled: {exc}")


def notify_sl_moved(
    ticket: int,
    symbol: str,
    side: str,
    old_sl: float,
    new_sl: float,
    stage: str,        # e.g. "Stage 1 — Break-Even", "Stage 2 — Profit Lock"
    entry: float = 0.0,
) -> None:
    try:
        direction = "▲" if new_sl > old_sl else "▼"
        locked = ""
        if entry:
            locked_pts = round(new_sl - entry if str(side).upper() == "BUY" else entry - new_sl, 2)
            locked = f"\n💰 Locked: {'+' if locked_pts >= 0 else ''}{locked_pts} pts"
        safe_stage = html.escape(str(stage or "SL Update"))
        safe_symbol = html.escape(str(symbol))
        safe_side = html.escape(str(side).upper())
        text = (
            f"🔧 <b>SL MOVED — {safe_stage}</b>\n"
            f"🎫 #{ticket}  |  {safe_symbol}  |  {safe_side}\n"
            f"🛑 SL: {old_sl:.2f} → <b>{new_sl:.2f}</b>  {direction}{locked}\n"
            f"🕐 {_now_ist()}"
        )
        _append_log(f"QUEUE notify_sl_moved #{ticket} ({safe_stage}: {old_sl:.2f} -> {new_sl:.2f})")
        _fire(POSITION_CHAT_ID, text)
    except Exception as exc:
        _append_log(f"ERROR notify_sl_moved: {exc}")


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
    try:
        pnl_emoji = "✅" if profit >= 0 else "❌"
        pts = round((close_price - entry) * (1 if str(side).upper() == "BUY" else -1), 2)
        duration_str = f"{duration_minutes:.0f} min" if duration_minutes else ""
        safe_reason = html.escape(str(close_reason or "Closed"))
        safe_symbol = html.escape(str(symbol))
        safe_side = html.escape(str(side).upper())
        text = (
            f"{pnl_emoji} <b>POSITION CLOSED — {safe_reason}</b>\n"
            f"🎫 #{ticket}  |  {safe_symbol}  |  {safe_side}\n"
            f"📍 Entry: {entry:.2f}  →  Close: <b>{close_price:.2f}</b>\n"
            f"📊 P&L: <b>{'+'if profit>=0 else ''}{profit:.2f} USD</b>  ({'+' if pts>=0 else ''}{pts} pts)\n"
            f"📦 {volume}L  |  ⏱ {duration_str}\n"
            f"🕐 {_now_ist()}"
        )
        _append_log(f"QUEUE notify_position_closed #{ticket} ({profit:+.2f} USD)")
        _fire(POSITION_CHAT_ID, text)
    except Exception as exc:
        _append_log(f"ERROR notify_position_closed: {exc}")


def notify_tp_hit(
    ticket: int,
    symbol: str,
    side: str,
    entry: float,
    tp: float,
    volume: float,
    profit: float,
) -> None:
    try:
        pts = round(abs(tp - entry), 2)
        safe_symbol = html.escape(str(symbol))
        safe_side = html.escape(str(side).upper())
        text = (
            f"🏆 <b>TP HIT — WINNER</b>\n"
            f"🎫 #{ticket}  |  {safe_symbol}  |  {safe_side}\n"
            f"📍 Entry: {entry:.2f}  →  TP: <b>{tp:.2f}</b>  (+{pts} pts)\n"
            f"💰 Profit: <b>+{profit:.2f} USD</b>  |  📦 {volume}L\n"
            f"🕐 {_now_ist()}"
        )
        _append_log(f"QUEUE notify_tp_hit #{ticket}")
        _fire(POSITION_CHAT_ID, text)
    except Exception as exc:
        _append_log(f"ERROR notify_tp_hit: {exc}")


def send_startup_ping() -> None:
    """Send startup message to both channels."""
    ts = _now_ist()
    _fire(PENDING_CHAT_ID,  f"⚡ <b>Alpha Desk ONLINE</b>\n🤖 Escanor | Pending Orders monitor active\n🕐 {ts}")
    _fire(POSITION_CHAT_ID, f"⚡ <b>Alpha Desk ONLINE</b>\n🤖 Escanor | Positions monitor active\n🕐 {ts}")


if __name__ == "__main__":
    print("Testing upgraded notifier directly...")
    notify_order_placed(
        ticket=552515656,
        symbol="XAUUSD",
        order_type="SELL_LIMIT",
        price=4148.00,
        sl=4156.50,
        tp=4133.39,
        volume=0.50,
        comment="TurnB AsianHigh BSL Fade / TripleDefendedCeiling 4150",
    )
    time.sleep(4)
    print("Check logs/telegram_alerts.log:")
    if ALERT_LOG.exists():
        print(ALERT_LOG.read_text(encoding="utf-8"))
