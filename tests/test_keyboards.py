"""Tests for inline keyboards."""

from __future__ import annotations

from bot.config import CHAT_MODELS, IMAGE_MODELS
from bot.keyboards import chat_model_keyboard, image_model_keyboard


def test_chat_model_keyboard_lists_all_models() -> None:
    keyboard = chat_model_keyboard(current="gpt-4o-mini")
    flat = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
    assert flat == [f"set_chat_model:{m}" for m in CHAT_MODELS]


def test_chat_model_keyboard_marks_current_model() -> None:
    keyboard = chat_model_keyboard(current="gpt-4o")
    labels = [btn.text for row in keyboard.inline_keyboard for btn in row]
    marked = [t for t in labels if t.startswith("• ")]
    assert marked == ["• gpt-4o"]


def test_image_model_keyboard_lists_all_models() -> None:
    keyboard = image_model_keyboard(current="dall-e-3")
    flat = [btn.callback_data for row in keyboard.inline_keyboard for btn in row]
    assert flat == [f"set_image_model:{m}" for m in IMAGE_MODELS]
