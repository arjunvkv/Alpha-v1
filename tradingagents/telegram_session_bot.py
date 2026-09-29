"""
ALPHA DESK TELEGRAM SESSION BOT
===============================
Provides autonomous OpenCode session switching, naming, and 2-seed auto-handshake
directly via Telegram commands and interactive inline buttons.

Commands:
  /newsession [name] — Switch to a new session (auto-increments or takes custom name)
  /session          — View current active session status and ID
  /help             — Show desk control center guide

Features:
  - Interactive Inline Keyboard: auto-populates 'Escanor vNext' with 1-tap confirmation.
  - Interactive Custom Naming: prompt user to reply with custom title.
  - Default Working Directory: C:\\Trading (or /trading/).
  - Thread-Safe & Async: Non-blocking execution of 2-seed handshake.
  - Dual Mode: Can run standalone or embedded inside the Alpha Desk Daemon.
"""

import asyncio
import html
import json
import logging
import re
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Configuration & Imports
PROJECT_ROOT = Path(r"C:\Trading\Alpha")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
TRADING_ROOT = Path(r"C:\Trading")
if str(TRADING_ROOT) not in sys.path:
    sys.path.insert(0, str(TRADING_ROOT))

from tradingagents.session_seeder import (
    create_and_seed_new_session,
    get_next_session_title,
    DEFAULT_API_URL,
    CONFIG_PATH,
)

LOG = logging.getLogger("alpha.telegram_session_bot")
BOT_TOKEN = "8748826581:AAEoP9rXDeINirO7rov-TcE7ikkY3rkWC1M"
DEFAULT_DIRECTORY = r"C:\Trading"

_BOT_APP: Optional[Application] = None
_BOT_THREAD: Optional[threading.Thread] = None


def get_current_session_info() -> dict:
    """Reads current active session metadata."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            LOG.error(f"Error reading session config: {e}")
    return {}


async def cmd_start_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /start and /help commands."""
    info = get_current_session_info()
    curr_title = html.escape(info.get("title", "Unknown"))
    curr_id = html.escape(info.get("session_id", "Unknown"))
    next_title = html.escape(get_next_session_title())

    help_text = (
        "👑 <b>ESCANOR AUTONOMOUS CIO — TELEGRAM CONTROL CENTER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Active Session:</b> <code>{curr_title}</code>\n"
        f"<b>Session ID:</b> <code>{curr_id}</code>\n"
        f"<b>Target Directory:</b> <code>{DEFAULT_DIRECTORY}</code>\n\n"
        "<b>Available Commands:</b>\n"
        "• <code>/newsession</code> — Interactive menu to switch and auto-seed\n"
        f"  <i>(Auto-populates: <code>{next_title}</code>)</i>\n"
        "• <code>/newsession &lt;name&gt;</code> — Immediately create session with custom name\n"
        "• <code>/session</code> — View active session health and coordinates\n"
        "• <code>/help</code> — Show this control center\n\n"
        "<i>All new sessions are created in <code>C:\\Trading</code> with the clean 2-seed handshake.</i>"
    )
    if update.message:
        await update.message.reply_text(help_text, parse_mode="HTML")


async def cmd_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler for /session and /status commands."""
    info = get_current_session_info()
    curr_title = html.escape(info.get("title", "Unknown"))
    curr_id = html.escape(info.get("session_id", "Unknown"))
    deployed = html.escape(info.get("deployed_at", "Unknown"))
    model = html.escape(info.get("model", "opencode/big-pickle"))
    streaming = "Active ✅" if info.get("dossier_streaming_enabled", True) else "Paused ⏸️"

    resp = (
        "📊 <b>CURRENT ACTIVE SESSION STATUS</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Title:</b> <code>{curr_title}</code>\n"
        f"<b>Session ID:</b> <code>{curr_id}</code>\n"
        f"<b>Directory:</b> <code>{DEFAULT_DIRECTORY}</code>\n"
        f"<b>Model:</b> <code>{model}</code>\n"
        f"<b>Deployed At:</b> <code>{deployed}</code>\n"
        f"<b>Dossier Stream:</b> <code>{streaming}</code>\n"
        f"<b>Daemon Hot-Reload:</b> Operational 🔄"
    )
    if update.message:
        await update.message.reply_text(resp, parse_mode="HTML")


async def execute_session_creation(
    target_title: str,
    status_msg,
    directory: str = DEFAULT_DIRECTORY,
) -> None:
    """Asynchronously runs create_and_seed_new_session and updates status message."""
    try:
        esc_title = html.escape(target_title)
        await status_msg.edit_text(
            f"⏳ <b>Deploying & Seeding Session...</b>\n\n"
            f"<b>Title:</b> <code>{esc_title}</code>\n"
            f"<b>Directory:</b> <code>{directory}</code>\n\n"
            f"<i>• Creating OpenCode session container...\n"
            f"• Ingesting Seed 1 (Autonomous CIO Authority & 5-Pod Protocol)...\n"
            f"• Ingesting Seed 2 (Execution Blueprint & Dynamic Guardian)...\n"
            f"• Awaiting assistant text acknowledgment...</i>",
            parse_mode="HTML",
        )

        # Run synchronous seeder workflow in threadpool
        session_id, session_title = await asyncio.to_thread(
            create_and_seed_new_session,
            session_title=target_title,
            directory=directory,
        )

        esc_sid = html.escape(session_id)
        esc_stitle = html.escape(session_title)

        await status_msg.edit_text(
            f"🚀 <b>SESSION SWITCH & AUTO-SEED COMPLETE!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>New Title:</b> <code>{esc_stitle}</code>\n"
            f"<b>Session ID:</b> <code>{esc_sid}</code>\n"
            f"<b>Working Directory:</b> <code>{directory}</code>\n"
            f"<b>Handshake:</b> 2-Seed Protocol Completed ✅\n"
            f"<b>Daemon Status:</b> Hot-reloaded on next tick 🔄\n\n"
            f"<i>The desk daemon is now streaming Turn A & Turn B briefings into this session.</i>",
            parse_mode="HTML",
        )
    except Exception as e:
        LOG.error(f"Error executing session creation: {e}", exc_info=True)
        err_text = html.escape(str(e))
        await status_msg.edit_text(
            f"❌ <b>Session Creation Failed</b>\n\nError: <code>{err_text}</code>",
            parse_mode="HTML",
        )


async def cmd_newsession(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler for /newsession command.
    If argument provided: creates immediately with that name.
    If no argument: prompts with auto-incremented name and buttons.
    """
    if not update.message:
        return

    # Check if custom name was passed as argument: e.g. /newsession Escanor v102 (Special)
    if context.args and len(context.args) > 0:
        custom_name = " ".join(context.args).strip()
        status_msg = await update.message.reply_text(
            f"⏳ Received request to create: <code>{html.escape(custom_name)}</code>...",
            parse_mode="HTML",
        )
        asyncio.create_task(execute_session_creation(custom_name, status_msg))
        return

    # No arguments passed -> Auto-populate incremented version
    next_title = get_next_session_title()
    esc_next = html.escape(next_title)

    keyboard = [
        [
            InlineKeyboardButton(
                f"✅ Create {next_title.split(' ')[1]} (Auto)",
                callback_data="session_create_auto",
            )
        ],
        [
            InlineKeyboardButton("✏️ Custom Name", callback_data="session_custom_prompt"),
            InlineKeyboardButton("❌ Cancel", callback_data="session_cancel"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🤖 <b>SWITCH OPENCODE SESSION & AUTO-SEED</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Auto-Incremented Title:</b>\n"
        f"👉 <code>{esc_next}</code>\n\n"
        f"<b>Default Directory:</b> <code>{DEFAULT_DIRECTORY}</code>\n\n"
        "<i>Click below to create with the auto-populated name, or choose 'Custom Name' to specify a title:</i>",
        parse_mode="HTML",
        reply_markup=reply_markup,
    )


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles inline button clicks for session switching."""
    query = update.callback_query
    if not query:
        return

    await query.answer()
    data = query.data

    if data == "session_cancel":
        await query.edit_message_text("❌ Session switch cancelled.", parse_mode="HTML")
        return

    if data == "session_custom_prompt":
        context.user_data["awaiting_custom_session_title"] = True
        await query.edit_message_text(
            "✍️ <b>Enter Custom Session Title</b>\n\n"
            "Please send a reply message with your desired session title\n"
            "<i>(or send <code>/newsession &lt;title&gt;</code> directly)</i>:",
            parse_mode="HTML",
        )
        return

    if data == "session_create_auto":
        next_title = get_next_session_title()
        # Use query.message to show in-place status updates
        asyncio.create_task(execute_session_creation(next_title, query.message))


async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Captures custom session name when user is prompted."""
    if not update.message or not update.message.text:
        return

    if context.user_data.get("awaiting_custom_session_title"):
        context.user_data["awaiting_custom_session_title"] = False
        custom_name = update.message.text.strip()
        status_msg = await update.message.reply_text(
            f"⏳ Setting custom session title: <code>{html.escape(custom_name)}</code>...",
            parse_mode="HTML",
        )
        asyncio.create_task(execute_session_creation(custom_name, status_msg))


def build_telegram_app() -> Application:
    """Builds and configures python-telegram-bot application."""
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler(["start", "help"], cmd_start_help))
    app.add_handler(CommandHandler(["session", "status"], cmd_session))
    app.add_handler(CommandHandler(["newsession", "createsession", "switchsession"], cmd_newsession))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))

    return app


def start_telegram_bot_thread() -> Application:
    """
    Starts Telegram bot polling in a resilient background daemon thread.
    Can be safely called multiple times; ensures only one polling instance runs.
    """
    global _BOT_APP, _BOT_THREAD

    if _BOT_THREAD is not None and _BOT_THREAD.is_alive():
        LOG.info("Telegram bot listener thread is already running.")
        return _BOT_APP

    app = build_telegram_app()
    _BOT_APP = app

    def _worker():
        LOG.info("Starting Telegram Bot Command Listener polling (@EscanorDeskbot)...")
        # Run polling with stop_signals=() so it runs cleanly inside background thread
        app.run_polling(
            allowed_updates=Update.ALL_TYPES,
            stop_signals=(),
            close_loop=False,
        )

    t = threading.Thread(target=_worker, name="TelegramSessionBotThread", daemon=True)
    _BOT_THREAD = t
    t.start()
    LOG.info("Telegram session bot listener successfully spawned in daemon thread.")
    return app


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    print("=" * 60)
    print("STARTING ESCANOR TELEGRAM SESSION BOT (@EscanorDeskbot)")
    print("Commands: /newsession, /session, /help")
    print(f"Default Directory: {DEFAULT_DIRECTORY}")
    print("=" * 60)
    app = build_telegram_app()
    app.run_polling(allowed_updates=Update.ALL_TYPES)
