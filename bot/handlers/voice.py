"""Voice / audio handler — transcribes with Whisper, then replies via GPT."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.types import Message

from bot.config import Settings
from bot.openai_client import OpenAIService
from bot.storage import MemoryStorage
from bot.storage import Message as ChatMessage

log = logging.getLogger(__name__)

router = Router(name="voice")


@router.message(F.voice | F.audio | F.video_note)
async def handle_voice(
    message: Message,
    storage: MemoryStorage,
    settings: Settings,
    openai: OpenAIService,
) -> None:
    if message.from_user is None:
        return

    file = message.voice or message.audio or message.video_note
    if file is None:
        return

    bot = message.bot
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    # Telegram caps bot file downloads at 20 MB.
    if file.file_size and file.file_size > 20 * 1024 * 1024:
        await message.answer("Файл слишком большой (>20 МБ). Я не смогу его скачать.")
        return

    suffix = ".ogg" if message.voice else ".mp4" if message.video_note else ".mp3"

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        await bot.download(file, destination=tmp_path)
        try:
            transcript = await openai.transcribe(tmp_path)
        except Exception:
            log.exception("Whisper transcription failed for user %s", message.from_user.id)
            await message.answer("Не получилось распознать аудио. Попробуйте ещё раз.")
            return

        if not transcript:
            await message.answer("Не удалось распознать речь в этом аудио.")
            return

        await message.answer(f"<i>Распознано:</i> {transcript}", parse_mode="HTML")

        session = storage.get(message.from_user.id)
        session.add("user", transcript)
        session.trim(settings.history_limit)

        try:
            history = [
                ChatMessage(role="system", content=settings.system_prompt),
                *session.history,
            ]
            reply = await openai.chat(messages=history, model=session.chat_model)
        except Exception:
            log.exception("Chat completion (after voice) failed for user %s", message.from_user.id)
            await message.answer(
                "Распознал речь, но не смог получить ответ от модели. Попробуйте ещё раз."
            )
            if session.history and session.history[-1].role == "user":
                session.history.pop()
            return

        session.add("assistant", reply)
        session.trim(settings.history_limit)
        await message.answer(reply)
    finally:
        await asyncio.to_thread(tmp_path.unlink, missing_ok=True)
