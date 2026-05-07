"""Inline keyboards used by the bot."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import CHAT_MODELS, IMAGE_MODELS


def chat_model_keyboard(current: str) -> InlineKeyboardMarkup:
    """Inline keyboard listing all available chat models."""

    rows = []
    for model in CHAT_MODELS:
        marker = "• " if model == current else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{marker}{model}",
                    callback_data=f"set_chat_model:{model}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def image_model_keyboard(current: str) -> InlineKeyboardMarkup:
    """Inline keyboard listing image generation models."""

    rows = []
    for model in IMAGE_MODELS:
        marker = "• " if model == current else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{marker}{model}",
                    callback_data=f"set_image_model:{model}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)
