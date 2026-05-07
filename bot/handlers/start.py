"""``/start``, ``/help``, ``/menu`` and ``/about`` commands."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from .menu import (
    HELP_HTML,
    SITES_HTML,
    back_keyboard,
    main_menu_keyboard,
    welcome_html,
)


async def cmd_start(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    user = update.effective_user
    name = user.first_name if user is not None else None
    await message.reply_text(
        welcome_html(name),
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=main_menu_keyboard(),
    )


async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def cmd_help(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(
        HELP_HTML,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=back_keyboard(),
    )


async def cmd_about(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(
        SITES_HTML,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=back_keyboard(),
    )
