"""Top-level error handler."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled error", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message is not None:
        try:
            await update.effective_message.reply_text(
                "Что-то пошло не так. Попробуй ещё раз чуть позже."
            )
        except Exception:
            logger.debug("Failed to notify user about error", exc_info=True)
