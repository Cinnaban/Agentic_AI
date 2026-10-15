"""Telegram-only Robinhood commands: portfolio analysis and guarded order proposals.

Authorization: the sender's Telegram user ID must be in TELEGRAM_ROBINHOOD_USER_IDS (comma-separated), and when
TELEGRAM_ROBINHOOD_CHAT_IDS is set the chat must be listed too. Nothing here is reachable from Discord.
"""
import asyncio
import os
import re
import sys
from pathlib import Path

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

TRADER_DIR = Path(__file__).resolve().parents[2] / "Agentic_Trader"
if str(TRADER_DIR) not in sys.path:
    sys.path.append(str(TRADER_DIR))

PORTFOLIO_PHRASE = re.compile(r"\b(my|robinhood)\b.*\b(portfolio|positions|holdings|account)\b", re.I)

HELP = (
    "Robinhood (Telegram only, MCP account)\n"
    "/portfolio - balances, allocation %, growth, concentration, live quant\n"
    "/positions - same report\n"
    "/review - full analysis of every holding (all accounts); /review NVDA VOO for specific symbols\n"
    "/paper - internal paper-trading account status\n"
    "/buy NVDA $5 | /buy NVDA 0.02 | /buy NVDA 0.02 @ 215.5\n"
    "/sell NVDA 0.02\n"
    "/confirm CODE - submit the proposed order\n"
    "/myid - show your Telegram user and chat ID\n"
    "Equities only: no options, margin or crypto."
)


def _ids(name):
    return {x.strip() for x in os.getenv(name, "").split(",") if x.strip()}


def identity(update):
    """Authorized identity, or None. Channel posts have no user, so an admin-only channel ID is the identity."""
    user, chat = update.effective_user, update.effective_chat
    chats = _ids("TELEGRAM_ROBINHOOD_CHAT_IDS")
    if chat is None:
        return None
    if update.channel_post is not None:
        return f"channel:{chat.id}" if str(chat.id) in chats else None
    if user and str(user.id) in _ids("TELEGRAM_ROBINHOOD_USER_IDS") and (not chats or str(chat.id) in chats):
        return str(user.id)
    return None


def authorized(update):
    return identity(update) is not None


async def _send(update, text):
    from orchestrator.table_format import split_message, to_telegram_html
    for part in split_message(text, 3500):
        try:
            await update.effective_message.reply_text(to_telegram_html(part), parse_mode="HTML")
        except Exception:
            await update.effective_message.reply_text(part)


async def _run(update, fn, *args):
    try:
        await _send(update, await asyncio.to_thread(fn, *args))
    except Exception as exc:
        print("TELEGRAM ROBINHOOD ERROR:", repr(exc))
        await _send(update, f"Robinhood request failed: {str(exc)[:200]}")


async def _guard(update):
    if authorized(update):
        return True
    await _send(update, "Not authorized for Robinhood commands.")
    return False


def _portfolio():
    from agentic_trader.robinhood import portfolio
    return portfolio.report()


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send(update, f"user id: {update.effective_user.id if update.effective_user else 'n/a (channel post)'}\nchat id: {update.effective_chat.id}")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _guard(update):
        await _send(update, HELP)


async def cmd_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _guard(update):
        await _run(update, _portfolio)


def _review(symbols):
    from agentic_trader.robinhood import review
    return review.review(symbols or None)


async def cmd_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _guard(update):
        syms = [a.strip(",").upper() for a in context.args if re.fullmatch(r"[A-Za-z.\-,]{1,12}", a)]
        await _run(update, _review, syms)


def _paper():
    from agentic_trader import paper_live
    return paper_live.status_text()


async def cmd_paper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _guard(update):
        await _run(update, _paper)


def _order(text, user_id):
    from agentic_trader.robinhood import orders
    return orders.propose(text, user_id)


async def cmd_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _guard(update):
        await _run(update, _order, re.sub(r"^(/\w+)@\w+", r"\1", update.effective_message.text),
                   identity(update))


def _confirm(code, user_id):
    from agentic_trader.robinhood import orders
    return orders.confirm(code, user_id)


async def cmd_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await _guard(update):
        code = context.args[0] if context.args else ""
        await _run(update, _confirm, code, identity(update))


async def phrase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Natural-language portfolio asks; non-matching text falls through to the normal bot handler."""
    text = (update.effective_message.text or "") if update.effective_message else ""
    if not PORTFOLIO_PHRASE.search(text):
        return False
    if await _guard(update):
        await _run(update, _portfolio)
    return True


ALL = filters.UpdateType.MESSAGES | filters.UpdateType.CHANNEL_POSTS


def register(application, fallback):
    """Register commands, and wrap the general text handler so portfolio phrases are handled here first."""
    application.add_handler(CommandHandler(["rh", "robinhood", "help_rh"], cmd_help, filters=ALL))
    application.add_handler(CommandHandler(["portfolio", "positions"], cmd_portfolio, filters=ALL))
    application.add_handler(CommandHandler(["buy", "sell"], cmd_order, filters=ALL))
    application.add_handler(CommandHandler("review", cmd_review, filters=ALL))
    application.add_handler(CommandHandler("paper", cmd_paper, filters=ALL))
    application.add_handler(CommandHandler("confirm", cmd_confirm, filters=ALL))
    application.add_handler(CommandHandler("myid", cmd_myid, filters=ALL))

    async def text_handler(update, context):
        if await phrase(update, context):
            return
        await fallback(update, context)

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
