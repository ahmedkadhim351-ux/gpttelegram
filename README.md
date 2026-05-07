# gpt-telegram-bot

Telegram-бот на базе OpenAI GPT по типу [@GPT4Telegrambot](https://t.me/GPT4Telegrambot).

## Возможности

- Чат с моделью OpenAI (`gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `gpt-3.5-turbo`) и историей диалога
- Генерация изображений через DALL-E (`dall-e-3`, `dall-e-2`) — команда `/image`
- Расшифровка голосовых, аудио и кружочков через Whisper
- Переключение модели чата и модели картинок прямо из чата (inline-кнопки)
- Команда `/reset` — очистить историю
- Опциональный allow-list пользователей через `ALLOWED_USER_IDS`

## Команды

| Команда         | Что делает                              |
|-----------------|------------------------------------------|
| `/start`        | Приветствие и список команд              |
| `/help`         | Справка                                  |
| `/reset`        | Сброс истории диалога                    |
| `/model`        | Выбор модели чата                        |
| `/image_model`  | Выбор модели для картинок                |
| `/image <текст>`| Сгенерировать картинку по описанию       |

Любой обычный текст — это сообщение в чат с GPT. Голосовое/аудио/кружочек —
бот сам распознает и ответит.

## Быстрый старт

Понадобится Python 3.10+.

```bash
git clone https://github.com/<your-username>/gpt-telegram-bot.git
cd gpt-telegram-bot

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# заполните TELEGRAM_BOT_TOKEN и OPENAI_API_KEY в .env

python -m bot
```

## Переменные окружения

См. [.env.example](.env.example). Ключевые:

- `TELEGRAM_BOT_TOKEN` — токен от [@BotFather](https://t.me/BotFather) (обязательно)
- `OPENAI_API_KEY` — ключ OpenAI (обязательно)
- `OPENAI_BASE_URL` — необязательно, для прокси или совместимых API
- `ALLOWED_USER_IDS` — список ID через запятую; пусто = доступ всем
- `DEFAULT_MODEL` — модель чата по умолчанию (по умолчанию `gpt-4o-mini`)
- `DEFAULT_IMAGE_MODEL` — модель картинок (`dall-e-3` по умолчанию)
- `WHISPER_MODEL` — модель распознавания (`whisper-1`)
- `HISTORY_LIMIT` — сколько последних сообщений хранить в истории (по умолчанию 20)
- `SYSTEM_PROMPT` — системный промпт, который отправляется в начале каждого диалога

## Запуск в Docker

```bash
docker build -t gpt-telegram-bot .
docker run --rm --env-file .env gpt-telegram-bot
```

## Разработка

```bash
ruff check .
ruff format --check .
pytest
```

## Лицензия

[MIT](LICENSE)
