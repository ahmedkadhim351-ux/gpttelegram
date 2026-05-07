"""Handlers for the actual download flow."""

from __future__ import annotations

import contextlib
import html
import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    Update,
)
from telegram.constants import ChatAction
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from ..config import Settings
from ..services.cache import TokenCache
from ..services.downloader import (
    DownloadError,
    DownloadResult,
    FileTooLargeError,
    LiveStreamError,
    MediaKind,
    UnsupportedURLError,
    download,
    fetch_info,
    format_duration,
)
from ..utils.url import extract_first_url

logger = logging.getLogger(__name__)

CALLBACK_PREFIX = "dl"
ACTION_VIDEO = "v"
ACTION_AUDIO = "a"
ACTION_CANCEL = "c"

_BOT_DATA_SETTINGS = "settings"
_BOT_DATA_CACHE = "url_cache"


def get_settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    settings = context.application.bot_data.get(_BOT_DATA_SETTINGS)
    if not isinstance(settings, Settings):
        raise RuntimeError("Settings missing from application bot_data")
    return settings


def get_cache(context: ContextTypes.DEFAULT_TYPE) -> TokenCache:
    cache = context.application.bot_data.get(_BOT_DATA_CACHE)
    if not isinstance(cache, TokenCache):
        cache = TokenCache()
        context.application.bot_data[_BOT_DATA_CACHE] = cache
    return cache


def _user_id(update: Update) -> int | None:
    user = update.effective_user
    return user.id if user is not None else None


def _build_keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🎬 Видео", callback_data=f"{CALLBACK_PREFIX}:{ACTION_VIDEO}:{token}"
                ),
                InlineKeyboardButton(
                    "🎵 Аудио (MP3)", callback_data=f"{CALLBACK_PREFIX}:{ACTION_AUDIO}:{token}"
                ),
            ],
            [
                InlineKeyboardButton(
                    "✖ Отмена", callback_data=f"{CALLBACK_PREFIX}:{ACTION_CANCEL}:0"
                )
            ],
        ]
    )


def _format_choice_message(title: str, uploader: str | None, duration: int | None) -> str:
    head = f"<b>{html.escape(title)}</b>"
    parts = []
    if uploader:
        parts.append(html.escape(uploader))
    parts.append(format_duration(duration))
    meta = " · ".join(parts)
    return f"{head}\n{meta}\n\nЧто прислать?"


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    settings = get_settings(context)
    if not settings.is_user_allowed(_user_id(update)):
        await message.reply_text("У тебя нет доступа к этому боту.")
        return

    text = message.text or message.caption or ""
    url = extract_first_url(text)
    if not url:
        return

    placeholder = await message.reply_text("Ищу видео…")

    try:
        info = await fetch_info(url)
    except UnsupportedURLError:
        await placeholder.edit_text("Эта ссылка не поддерживается.")
        return
    except DownloadError as err:
        logger.warning("fetch_info failed for %s: %s", url, err)
        await placeholder.edit_text("Не удалось получить информацию о видео.")
        return

    if info.is_live:
        await placeholder.edit_text("Прямые трансляции скачивать нельзя.")
        return

    cache = get_cache(context)
    token = cache.put(url)
    keyboard = _build_keyboard(token)
    body = _format_choice_message(info.title, info.uploader, info.duration)

    try:
        await placeholder.edit_text(
            body,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except BadRequest:
        # Fallback without HTML in case the title contains weird entities
        await placeholder.edit_text(
            f"{info.title}\n\nЧто прислать?",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return
    await query.answer()

    settings = get_settings(context)
    if not settings.is_user_allowed(_user_id(update)):
        await query.edit_message_text("У тебя нет доступа к этому боту.")
        return

    parts = query.data.split(":")
    if len(parts) < 2 or parts[0] != CALLBACK_PREFIX:
        return
    action = parts[1]

    if action == ACTION_CANCEL:
        await query.edit_message_text("Отменено.")
        return

    if action not in {ACTION_VIDEO, ACTION_AUDIO} or len(parts) < 3:
        return

    token = parts[2]
    cache = get_cache(context)
    url = cache.pop(token)
    if url is None:
        await query.edit_message_text("Срок действия ссылки истёк, отправь её ещё раз.")
        return

    kind = MediaKind.VIDEO if action == ACTION_VIDEO else MediaKind.AUDIO
    chat_id = query.message.chat_id if query.message else None
    if chat_id is None:
        return

    await query.edit_message_text(f"Скачиваю {'видео' if kind is MediaKind.VIDEO else 'аудио'}…")
    chat_action = ChatAction.UPLOAD_VIDEO if kind is MediaKind.VIDEO else ChatAction.UPLOAD_VOICE
    with contextlib.suppress(TelegramError):
        await context.bot.send_chat_action(chat_id=chat_id, action=chat_action)

    try:
        result = await download(
            url,
            kind=kind,
            max_filesize_bytes=settings.max_file_size_bytes,
            max_height=settings.max_video_height,
            cookiefile=settings.cookies_file,
        )
    except UnsupportedURLError:
        await query.edit_message_text("Ссылка не поддерживается.")
        return
    except LiveStreamError:
        await query.edit_message_text("Прямые трансляции скачивать нельзя.")
        return
    except FileTooLargeError as err:
        await query.edit_message_text(
            f"Файл слишком большой: {err.size_mb:.1f} МБ > {err.limit_mb:.0f} МБ. "
            "Попробуй вариант «Аудио (MP3)» или более короткий ролик."
        )
        return
    except DownloadError as err:
        logger.warning("download failed for %s: %s", url, err)
        await query.edit_message_text("Ошибка при скачивании.")
        return

    try:
        await _send_result(context, chat_id=chat_id, result=result)
        await query.edit_message_text(f"Готово: {result.title[:200]}")
    except TelegramError:
        logger.exception("failed to send media")
        await query.edit_message_text("Не удалось отправить файл.")
    finally:
        result.cleanup()


async def _send_result(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_id: int,
    result: DownloadResult,
) -> None:
    caption = result.title[:1024]
    with open(result.path, "rb") as fh:
        if result.kind is MediaKind.VIDEO:
            await context.bot.send_video(
                chat_id=chat_id,
                video=InputFile(fh, filename=result.path.name),
                caption=caption,
                duration=result.duration,
                supports_streaming=True,
            )
        else:
            await context.bot.send_audio(
                chat_id=chat_id,
                audio=InputFile(fh, filename=result.path.name),
                title=result.title[:64],
                performer=(result.info.uploader or "")[:64] or None,
                duration=result.duration,
                caption=caption,
            )
