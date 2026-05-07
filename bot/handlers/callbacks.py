"""Inline-keyboard callback handlers (model switching)."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot.config import CHAT_MODELS, IMAGE_MODELS
from bot.keyboards import chat_model_keyboard, image_model_keyboard
from bot.storage import MemoryStorage

router = Router(name="callbacks")


@router.callback_query(F.data.startswith("set_chat_model:"))
async def on_set_chat_model(query: CallbackQuery, storage: MemoryStorage) -> None:
    if query.from_user is None or query.data is None:
        return
    model = query.data.removeprefix("set_chat_model:")
    if model not in CHAT_MODELS:
        await query.answer("Неизвестная модель", show_alert=True)
        return
    storage.set_chat_model(query.from_user.id, model)
    await query.answer(f"Выбрана модель: {model}")
    if query.message is not None:
        await query.message.edit_text(
            f"Текущая модель чата: <b>{model}</b>\nВыберите новую:",
            reply_markup=chat_model_keyboard(model),
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("set_image_model:"))
async def on_set_image_model(query: CallbackQuery, storage: MemoryStorage) -> None:
    if query.from_user is None or query.data is None:
        return
    model = query.data.removeprefix("set_image_model:")
    if model not in IMAGE_MODELS:
        await query.answer("Неизвестная модель", show_alert=True)
        return
    storage.set_image_model(query.from_user.id, model)
    await query.answer(f"Выбрана модель: {model}")
    if query.message is not None:
        await query.message.edit_text(
            f"Текущая модель картинок: <b>{model}</b>\nВыберите новую:",
            reply_markup=image_model_keyboard(model),
            parse_mode="HTML",
        )
