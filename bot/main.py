"""Application bootstrap: build the dispatcher and run the polling loop."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand

from bot.config import Settings, get_settings
from bot.filters import AllowedUserFilter
from bot.handlers import register_all
from bot.openai_client import OpenAIService
from bot.storage import MemoryStorage

log = logging.getLogger(__name__)


async def _set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Начать работу"),
            BotCommand(command="help", description="Показать справку"),
            BotCommand(command="reset", description="Очистить историю диалога"),
            BotCommand(command="model", description="Выбрать модель чата"),
            BotCommand(command="image_model", description="Выбрать модель картинок"),
            BotCommand(command="image", description="Сгенерировать картинку"),
        ]
    )


def _build_dispatcher(settings: Settings) -> tuple[Dispatcher, MemoryStorage, OpenAIService]:
    storage = MemoryStorage(
        default_chat_model=settings.default_model,
        default_image_model=settings.default_image_model,
    )
    openai = OpenAIService(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        default_chat_model=settings.default_model,
        whisper_model=settings.whisper_model,
        default_image_model=settings.default_image_model,
    )

    dispatcher = Dispatcher()
    # Inject services into every handler via aiogram's "workflow data".
    dispatcher["storage"] = storage
    dispatcher["settings"] = settings
    dispatcher["openai"] = openai

    # Restrict access at the router level for both messages and callbacks.
    allowed = AllowedUserFilter(settings.allowed_user_ids)
    dispatcher.message.filter(allowed)
    dispatcher.callback_query.filter(allowed)

    register_all(dispatcher)
    return dispatcher, storage, openai


async def _amain() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    settings = get_settings()
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )
    dispatcher, _, _ = _build_dispatcher(settings)

    await _set_commands(bot)
    log.info("Bot is starting (polling)…")
    try:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        await bot.session.close()


def run() -> None:
    """Synchronous entry point used by ``python -m bot`` and the console script."""

    try:
        asyncio.run(_amain())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot stopped")


if __name__ == "__main__":
    run()
