"""``/image`` command — generate an image with DALL-E."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, Message

from bot.openai_client import OpenAIService
from bot.storage import MemoryStorage

log = logging.getLogger(__name__)

router = Router(name="image")


@router.message(Command("image", "img"))
async def handle_image(
    message: Message,
    command: CommandObject,
    storage: MemoryStorage,
    openai: OpenAIService,
) -> None:
    if message.from_user is None:
        return
    prompt = (command.args or "").strip()
    if not prompt:
        await message.answer(
            "Использование: /image <описание картинки>\n"
            "Пример: <code>/image космонавт играет в шахматы с котом, акварель</code>",
            parse_mode="HTML",
        )
        return

    session = storage.get(message.from_user.id)
    await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)

    try:
        url = await openai.generate_image(prompt=prompt, model=session.image_model)
        photo_bytes = await openai.fetch_image_bytes(url)
    except Exception:
        log.exception("Image generation failed for user %s", message.from_user.id)
        await message.answer(
            "Не получилось сгенерировать картинку. Возможно, описание было отклонено фильтром "
            "или сервис временно недоступен."
        )
        return

    await message.answer_photo(
        BufferedInputFile(photo_bytes.getvalue(), filename="image.png"),
        caption=f"<b>{session.image_model}</b>: {prompt}"[:1024],
        parse_mode="HTML",
    )
