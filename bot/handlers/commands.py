"""Slash-command handlers: /start, /help, /reset, /model, /image_model."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.config import Settings
from bot.keyboards import chat_model_keyboard, image_model_keyboard
from bot.storage import MemoryStorage

router = Router(name="commands")


WELCOME = (
    "Привет! Я Telegram-бот на базе OpenAI GPT.\n\n"
    "Что я умею:\n"
    "• Отвечать на любые сообщения с учётом истории диалога\n"
    "• /image <описание> — сгенерировать картинку (DALL-E)\n"
    "• Голосовые сообщения — расшифрую (Whisper) и отвечу\n"
    "• /model — выбрать модель чата\n"
    "• /image_model — выбрать модель генерации картинок\n"
    "• /reset — очистить историю диалога\n"
    "• /help — показать эту справку"
)


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(WELCOME)


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    await message.answer(WELCOME)


@router.message(Command("reset"))
async def handle_reset(message: Message, storage: MemoryStorage) -> None:
    if message.from_user is None:
        return
    storage.reset(message.from_user.id)
    await message.answer("История диалога очищена. Поехали с чистого листа!")


@router.message(Command("model"))
async def handle_model(message: Message, storage: MemoryStorage, settings: Settings) -> None:
    if message.from_user is None:
        return
    session = storage.get(message.from_user.id)
    await message.answer(
        f"Текущая модель чата: <b>{session.chat_model}</b>\nВыберите новую:",
        reply_markup=chat_model_keyboard(session.chat_model),
        parse_mode="HTML",
    )
    # `settings` is unused here but keeps the dependency-injection signature
    # consistent with other handlers.
    _ = settings


@router.message(Command("image_model"))
async def handle_image_model(message: Message, storage: MemoryStorage) -> None:
    if message.from_user is None:
        return
    session = storage.get(message.from_user.id)
    await message.answer(
        f"Текущая модель картинок: <b>{session.image_model}</b>\nВыберите новую:",
        reply_markup=image_model_keyboard(session.image_model),
        parse_mode="HTML",
    )
