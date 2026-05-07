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
    MediaInfo,
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

QUALITY_HD = "hd"
QUALITY_SD = "sd"
SD_HEIGHT = 360

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
                    "🎬 Видео HD",
                    callback_data=f"{CALLBACK_PREFIX}:{ACTION_VIDEO}:{QUALITY_HD}:{token}",
                ),
                InlineKeyboardButton(
                    "📱 Видео SD",
                    callback_data=f"{CALLBACK_PREFIX}:{ACTION_VIDEO}:{QUALITY_SD}:{token}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🎵 Аудио (MP3)",
                    callback_data=f"{CALLBACK_PREFIX}:{ACTION_AUDIO}:0:{token}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "✖ Отмена",
                    callback_data=f"{CALLBACK_PREFIX}:{ACTION_CANCEL}:0:0",
                )
            ],
        ]
    )


def _format_size_mb(size_bytes: int) -> str:
    return f"{size_bytes / 1024 / 1024:.1f}"


def _short_reason(err: BaseException) -> str:
    msg = str(err).strip().splitlines()[0] if str(err).strip() else err.__class__.__name__
    # Strip yt-dlp's "ERROR: [extractor] " prefix if present.
    for prefix in ("ERROR: ", "error: "):
        if msg.startswith(prefix):
            msg = msg[len(prefix) :]
    if msg.startswith("[") and "]" in msg:
        msg = msg.split("]", 1)[1].lstrip()
    return msg[:200] or "неизвестная ошибка"


def _format_choice_message(info: MediaInfo) -> str:
    title = html.escape(info.title or "Без названия")
    lines = [f"✨ <b>{title}</b>"]

    meta_parts: list[str] = []
    if info.uploader:
        meta_parts.append(f"👤 {html.escape(info.uploader)}")
    if info.duration:
        meta_parts.append(f"⏱ {format_duration(info.duration)}")
    if info.extractor:
        meta_parts.append(f"📺 {html.escape(info.extractor)}")
    if meta_parts:
        lines.append(" · ".join(meta_parts))

    lines.append("")
    lines.append("Выбери формат:")
    return "\n".join(lines)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return
    settings = get_settings(context)
    if not settings.is_user_allowed(_user_id(update)):
        await message.reply_text("🚫 У тебя нет доступа к этому боту.")
        return

    text = message.text or message.caption or ""
    url = extract_first_url(text)
    if not url:
        return

    placeholder = await message.reply_text("🔍 <b>Ищу видео…</b>", parse_mode="HTML")

    try:
        info = await fetch_info(url)
    except UnsupportedURLError:
        await placeholder.edit_text(
            "❌ <b>Эта ссылка не поддерживается.</b>\n\n"
            "Загляни в /menu — там есть список поддерживаемых платформ.",
            parse_mode="HTML",
        )
        return
    except DownloadError as err:
        logger.warning("fetch_info failed for %s: %s", url, err)
        await placeholder.edit_text(
            "❌ <b>Не удалось получить инфо о видео.</b>\n"
            f"<i>{html.escape(_short_reason(err))}</i>",
            parse_mode="HTML",
        )
        return

    if info.is_live:
        await placeholder.edit_text(
            "📡 <b>Прямые трансляции скачивать нельзя.</b>\nПришли ссылку, когда стрим закончится.",
            parse_mode="HTML",
        )
        return

    cache = get_cache(context)
    token = cache.put(url)
    keyboard = _build_keyboard(token)
    body = _format_choice_message(info)

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
            f"{info.title}\n\nВыбери формат:",
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
        await query.edit_message_text("🚫 У тебя нет доступа к этому боту.")
        return

    parts = query.data.split(":")
    if len(parts) < 2 or parts[0] != CALLBACK_PREFIX:
        return
    action = parts[1]

    if action == ACTION_CANCEL:
        await query.edit_message_text("✖ <b>Отменено.</b>", parse_mode="HTML")
        return

    if action not in {ACTION_VIDEO, ACTION_AUDIO} or len(parts) < 4:
        return

    quality = parts[2]
    token = parts[3]
    cache = get_cache(context)
    url = cache.pop(token)
    if url is None:
        await query.edit_message_text(
            "⌛ <b>Срок действия ссылки истёк</b> — пришли её ещё раз.",
            parse_mode="HTML",
        )
        return

    kind = MediaKind.VIDEO if action == ACTION_VIDEO else MediaKind.AUDIO
    chat_id = query.message.chat_id if query.message else None
    if chat_id is None:
        return

    if kind is MediaKind.VIDEO:
        max_height = SD_HEIGHT if quality == QUALITY_SD else settings.max_video_height
        quality_label = (
            f"SD {SD_HEIGHT}p" if quality == QUALITY_SD else f"HD {settings.max_video_height}p"
        )
        status_text = f"📥 <b>Скачиваю видео…</b>\n<i>Качество: {quality_label}</i>"
        chat_action = ChatAction.UPLOAD_VIDEO
    else:
        max_height = settings.max_video_height
        status_text = "🎵 <b>Готовлю MP3…</b>\n<i>192 kbps</i>"
        chat_action = ChatAction.UPLOAD_VOICE

    await query.edit_message_text(status_text, parse_mode="HTML")
    with contextlib.suppress(TelegramError):
        await context.bot.send_chat_action(chat_id=chat_id, action=chat_action)

    try:
        result = await download(
            url,
            kind=kind,
            max_filesize_bytes=settings.max_file_size_bytes,
            max_height=max_height,
            cookiefile=settings.cookies_file,
        )
    except UnsupportedURLError:
        await query.edit_message_text("❌ <b>Ссылка не поддерживается.</b>", parse_mode="HTML")
        return
    except LiveStreamError:
        await query.edit_message_text(
            "📡 <b>Прямые трансляции скачивать нельзя.</b>", parse_mode="HTML"
        )
        return
    except FileTooLargeError as err:
        await query.edit_message_text(
            f"⚠️ <b>Файл слишком большой:</b> {err.size_mb:.1f} МБ "
            f"(лимит {err.limit_mb:.0f} МБ).\n"
            "Попробуй вариант <i>«🎵 Аудио (MP3)»</i> или ссылку покороче.",
            parse_mode="HTML",
        )
        return
    except DownloadError as err:
        logger.warning("download failed for %s: %s", url, err)
        await query.edit_message_text(
            f"❌ <b>Ошибка при скачивании.</b>\n<i>{html.escape(_short_reason(err))}</i>",
            parse_mode="HTML",
        )
        return

    try:
        with contextlib.suppress(TelegramError):
            await query.edit_message_text("📤 <b>Отправляю файл…</b>", parse_mode="HTML")
        await _send_result(context, chat_id=chat_id, result=result)
        size_mb = _format_size_mb(result.path.stat().st_size)
        kind_label = "🎬 Видео" if kind is MediaKind.VIDEO else "🎵 MP3"
        title = html.escape(result.title[:200])
        with contextlib.suppress(TelegramError):
            await query.edit_message_text(
                f"✅ <b>Готово!</b>\n\n<b>{title}</b>\n{kind_label} · 📦 {size_mb} МБ",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
    except TelegramError:
        logger.exception("failed to send media")
        await query.edit_message_text("❌ <b>Не удалось отправить файл.</b>", parse_mode="HTML")
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
