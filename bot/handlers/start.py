"""``/start``, ``/help`` and ``/about`` commands."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

WELCOME = (
    "Привет! Я качаю видео и аудио из соцсетей.\n\n"
    "Просто пришли мне ссылку — на YouTube, TikTok, Instagram, X (Twitter), "
    "Reddit, Facebook, VK, SoundCloud и ещё пару сотен сайтов — и выбери, "
    "что прислать обратно: видео или MP3.\n\n"
    "Команды:\n"
    "/help — это сообщение\n"
    "/about — список поддерживаемых сайтов и ограничения"
)

ABOUT = (
    "Под капотом — yt-dlp, поэтому работает почти везде, где есть видео.\n"
    "Полный список платформ: https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md\n\n"
    "Ограничения:\n"
    "• Telegram пускает боты заливать файлы до 50 МБ. Если ролик больше — "
    "попробуй вариант «Аудио (MP3)» или ссылку покороче.\n"
    "• Прямые трансляции и плейлисты не поддерживаются.\n"
    "• Контент 18+, приватные видео и страницы за логином качаются только "
    "при настроенном файле cookies."
)


async def cmd_start(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is not None:
        await message.reply_text(WELCOME, disable_web_page_preview=True)


async def cmd_help(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is not None:
        await message.reply_text(WELCOME, disable_web_page_preview=True)


async def cmd_about(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is not None:
        await message.reply_text(ABOUT, disable_web_page_preview=True)
