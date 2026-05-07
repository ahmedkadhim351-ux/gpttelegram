"""Main menu screens (welcome, supported sites, help, limits)."""

from __future__ import annotations

import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from ..config import Settings

logger = logging.getLogger(__name__)

CALLBACK_PREFIX = "menu"
SECTION_MAIN = "main"
SECTION_SITES = "sites"
SECTION_HELP = "help"
SECTION_LIMITS = "limits"

SUPPORTED_SITES_URL = "https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md"


def welcome_html(name: str | None) -> str:
    safe_name = html.escape(name) if name else "друг"
    return (
        f"👋 <b>Привет, {safe_name}!</b>\n\n"
        "🎬 Я качаю <b>видео и музыку</b> с YouTube, TikTok, Instagram, "
        "X (Twitter), Reddit, Facebook, VK, SoundCloud — и ещё <b>1500+ сайтов</b>.\n\n"
        "<b>Как пользоваться:</b>\n"
        "▫️ Пришли ссылку\n"
        "▫️ Жми <code>🎬 Видео HD</code>, <code>📱 Видео SD</code> или <code>🎵 MP3</code>\n"
        "▫️ Получи файл прямо в чат\n\n"
        "<i>Telegram пускает заливать файлы до 50 МБ — для тяжёлых роликов выбирай аудио.</i>"
    )


SITES_HTML = (
    "📚 <b>Поддерживаемые платформы</b>\n\n"
    "🎥 YouTube · YouTube Shorts\n"
    "📱 TikTok\n"
    "📸 Instagram (Reels, Posts, IGTV)\n"
    "🐦 X / Twitter\n"
    "💬 Reddit\n"
    "📘 Facebook\n"
    "🎵 SoundCloud · Bandcamp\n"
    "🎬 VK · Одноклассники\n"
    "📺 Twitch (clips, VODs)\n"
    "📡 Vimeo · Dailymotion · Rutube\n\n"
    f'<i>… и ещё 1500+ — </i><a href="{SUPPORTED_SITES_URL}">полный список</a>.'
)


HELP_HTML = (
    "ℹ️ <b>Как пользоваться</b>\n\n"
    "1. Скопируй ссылку на видео.\n"
    "2. Кинь её в этот чат.\n"
    "3. Дождись превью с метаданными.\n"
    "4. Жми <code>🎬 Видео HD</code>, <code>📱 Видео SD</code> или <code>🎵 Аудио (MP3)</code>.\n"
    "5. Бот пришлёт файл прямо в чат.\n\n"
    "Если ролик длинный — лучше выбирай <b>MP3</b>: он почти всегда влезает в лимит Telegram.\n\n"
    "Команды: /start · /menu · /help"
)


def limits_html(settings: Settings) -> str:
    return (
        "⚙️ <b>Лимиты</b>\n\n"
        f"• <b>Размер файла</b>: до {settings.max_file_size_mb} МБ "
        "<i>(ограничение Telegram)</i>.\n"
        f"• <b>Видео HD</b>: до {settings.max_video_height}p.\n"
        "• <b>Видео SD</b>: до 360p.\n"
        "• <b>Аудио</b>: MP3 192 kbps.\n"
        "• <b>Прямые трансляции</b> и <b>плейлисты</b> не качаем.\n"
        "• <b>Приватный/возрастной</b> контент — только с настроенным cookies‑файлом."
    )


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "📚 Платформы",
                    callback_data=f"{CALLBACK_PREFIX}:{SECTION_SITES}",
                ),
                InlineKeyboardButton(
                    "ℹ️ Помощь",
                    callback_data=f"{CALLBACK_PREFIX}:{SECTION_HELP}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⚙️ Лимиты",
                    callback_data=f"{CALLBACK_PREFIX}:{SECTION_LIMITS}",
                ),
            ],
        ]
    )


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "← Главное меню",
                    callback_data=f"{CALLBACK_PREFIX}:{SECTION_MAIN}",
                ),
            ]
        ]
    )


def render_section(
    section: str, *, name: str | None, settings: Settings
) -> tuple[str, InlineKeyboardMarkup] | None:
    if section == SECTION_MAIN:
        return welcome_html(name), main_menu_keyboard()
    if section == SECTION_SITES:
        return SITES_HTML, back_keyboard()
    if section == SECTION_HELP:
        return HELP_HTML, back_keyboard()
    if section == SECTION_LIMITS:
        return limits_html(settings), back_keyboard()
    return None


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    settings = context.application.bot_data.get("settings")
    if not isinstance(settings, Settings):
        raise RuntimeError("Settings missing from application bot_data")
    return settings


async def on_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.data is None:
        return
    await query.answer()

    parts = query.data.split(":", 1)
    if len(parts) != 2 or parts[0] != CALLBACK_PREFIX:
        return
    section = parts[1]

    user = query.from_user
    name = user.first_name if user is not None else None
    rendered = render_section(section, name=name, settings=_settings(context))
    if rendered is None:
        return
    text, keyboard = rendered

    try:
        await query.edit_message_text(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=keyboard,
        )
    except BadRequest as err:
        # "Message is not modified" happens if user re-clicks same section
        if "not modified" not in str(err).lower():
            logger.debug("menu edit failed: %s", err)
