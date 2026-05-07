"""Plain-text chat handler — sends the conversation to GPT and returns the reply."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.types import Message

from bot.config import Settings
from bot.openai_client import OpenAIService
from bot.storage import MemoryStorage, UserSession

log = logging.getLogger(__name__)

router = Router(name="chat")


def _build_history(session: UserSession, system_prompt: str) -> list:
    from bot.storage import Message as Msg

    return [Msg(role="system", content=system_prompt), *session.history]


@router.message(F.text)
async def handle_text(
    message: Message,
    storage: MemoryStorage,
    settings: Settings,
    openai: OpenAIService,
) -> None:
    if message.from_user is None or not message.text:
        return

    user_id = message.from_user.id
    session = storage.get(user_id)
    session.add("user", message.text)
    session.trim(settings.history_limit)

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    try:
        reply = await openai.chat(
            messages=_build_history(session, settings.system_prompt),
            model=session.chat_model,
        )
    except Exception:
        log.exception("Chat completion failed for user %s", user_id)
        await message.answer(
            "Не получилось получить ответ от модели. Попробуйте ещё раз чуть позже."
        )
        # Drop the failed user turn so retries don't pile up.
        if session.history and session.history[-1].role == "user":
            session.history.pop()
        return

    session.add("assistant", reply)
    session.trim(settings.history_limit)
    await message.answer(reply)
