"""Tests for configuration loading and validation."""

from __future__ import annotations

import pytest

from bot.config import Settings


def test_settings_load_minimal_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tg-token")
    monkeypatch.setenv("OPENAI_API_KEY", "oai-key")
    monkeypatch.delenv("ALLOWED_USER_IDS", raising=False)
    monkeypatch.chdir("/tmp")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.telegram_bot_token == "tg-token"
    assert settings.openai_api_key == "oai-key"
    assert settings.default_model == "gpt-4o-mini"
    assert settings.default_image_model == "dall-e-3"
    assert settings.allowed_user_ids == []


def test_allowed_user_ids_parse_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tg")
    monkeypatch.setenv("OPENAI_API_KEY", "oai")
    monkeypatch.setenv("ALLOWED_USER_IDS", "1, 2,3")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.allowed_user_ids == [1, 2, 3]


def test_invalid_default_model_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tg")
    monkeypatch.setenv("OPENAI_API_KEY", "oai")
    monkeypatch.setenv("DEFAULT_MODEL", "made-up-model")
    with pytest.raises(ValueError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_invalid_default_image_model_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tg")
    monkeypatch.setenv("OPENAI_API_KEY", "oai")
    monkeypatch.setenv("DEFAULT_IMAGE_MODEL", "midjourney")
    with pytest.raises(ValueError):
        Settings(_env_file=None)  # type: ignore[call-arg]
