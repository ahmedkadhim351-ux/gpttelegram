# Telegram Media Downloader Bot

Telegram-бот, который качает видео и аудио по ссылке: YouTube, TikTok, Instagram,
X (Twitter), Reddit, Facebook, VK, SoundCloud и ещё [более 1500 сайтов][sites].
Под капотом — [`yt-dlp`](https://github.com/yt-dlp/yt-dlp), без платных API.

## Возможности

- Кидаешь в чат любую ссылку — бот отвечает превью и кнопками «Видео» / «Аудио (MP3)».
- Видео отдаётся как `mp4` (с поддержкой стриминга в TG).
- Аудио конвертируется в `mp3 192 kbps` через ffmpeg.
- Уважает 50‑мегабайтный лимит Telegram: если файл больше — присылает понятную ошибку.
- Опциональный allow‑list пользователей через `ALLOWED_USER_IDS`.
- Поддержка cookies‑файла для приватных/возрастных видео.
- Запускается одной командой в Docker.

## Команды

| Команда   | Что делает                              |
|-----------|------------------------------------------|
| `/start`  | Приветствие и краткий мануал             |
| `/help`   | То же, что `/start`                      |
| `/about`  | Поддерживаемые сайты и ограничения       |

Любое сообщение со ссылкой запускает скачивание.

## Быстрый старт

Нужен Python 3.10+ и установленный `ffmpeg`.

```bash
git clone https://github.com/ahmedkadhim351-ux/gpttelegram.git
cd gpttelegram

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# заполни TELEGRAM_BOT_TOKEN

python -m bot
```

## Запуск в Docker

```bash
docker build -t media-telegram-bot .
docker run --rm --env-file .env media-telegram-bot
```

`ffmpeg` уже зашит в образ.

## Переменные окружения

Полный список — в [`.env.example`](.env.example).

| Переменная          | Назначение                                                          |
|---------------------|---------------------------------------------------------------------|
| `TELEGRAM_BOT_TOKEN`| Токен от [@BotFather](https://t.me/BotFather). Обязательно.         |
| `ALLOWED_USER_IDS`  | Через запятую — кому разрешён доступ. Пусто = всем.                 |
| `MAX_FILE_SIZE_MB`  | Потолок размера итогового файла. По умолчанию 50.                   |
| `MAX_VIDEO_HEIGHT`  | Максимальная высота видео в пикселях. По умолчанию 720.             |
| `COOKIES_FILE`      | Путь к Netscape‑cookies для входа на платформах с авторизацией.     |
| `LOG_LEVEL`         | `DEBUG` / `INFO` / `WARNING` / `ERROR`. По умолчанию `INFO`.        |

## Разработка

```bash
ruff check .
ruff format --check .
pytest
```

Структура проекта:

```
bot/
├── app.py            # фабрика Application и точка входа
├── config.py         # загрузка настроек из env
├── handlers/         # /start, /help, обработчик ссылок и колбэков
├── services/
│   ├── cache.py      # короткоживущий стор для callback_data
│   └── downloader.py # async-обёртка над yt-dlp
└── utils/url.py      # извлечение URL из текста сообщения
```

## Ограничения

- Telegram пускает ботов заливать файлы до 50 МБ. Для роликов больше — нужен
  self‑hosted [Bot API server](https://github.com/tdlib/telegram-bot-api).
- Прямые трансляции и плейлисты осознанно не поддерживаются.
- yt‑dlp периодически ломается на отдельных сайтах — обновляй версию.

## Лицензия

[MIT](LICENSE)

[sites]: https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md
