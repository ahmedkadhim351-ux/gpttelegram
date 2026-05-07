"""Application factory and entrypoint."""

from __future__ import annotations

import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from .config import Settings
from .handlers import download, errors, menu, start
from .services.cache import TokenCache


def create_application(settings: Settings) -> Application:
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.bot_data["settings"] = settings
    application.bot_data["url_cache"] = TokenCache()

    application.add_handler(CommandHandler("start", start.cmd_start))
    application.add_handler(CommandHandler("menu", start.cmd_menu))
    application.add_handler(CommandHandler("help", start.cmd_help))
    application.add_handler(CommandHandler("about", start.cmd_about))
    application.add_handler(CallbackQueryHandler(menu.on_menu, pattern=r"^menu:"))
    application.add_handler(CallbackQueryHandler(download.on_callback, pattern=r"^dl:"))
    application.add_handler(
        MessageHandler(
            (filters.TEXT | filters.CAPTION) & ~filters.COMMAND,
            download.on_message,
        )
    )
    application.add_error_handler(errors.handle_error)
    return application


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    # Tame the noisy ones a touch
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext._application").setLevel(logging.INFO)


def run() -> None:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    logger.info("Starting media downloader bot…")
    application = create_application(settings)
    application.run_polling(allowed_updates=None)
