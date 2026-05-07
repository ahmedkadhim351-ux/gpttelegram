"""Message and callback handlers for the bot."""

from __future__ import annotations

from aiogram import Dispatcher

from bot.handlers import callbacks, chat, commands, image, voice


def register_all(dispatcher: Dispatcher) -> None:
    """Register every handler module on the given dispatcher."""

    dispatcher.include_router(commands.router)
    dispatcher.include_router(image.router)
    dispatcher.include_router(voice.router)
    dispatcher.include_router(callbacks.router)
    # Chat router is last so it only handles messages no other router matched.
    dispatcher.include_router(chat.router)
