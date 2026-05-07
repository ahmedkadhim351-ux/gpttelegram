"""Tests for ``bot.config``."""

from __future__ import annotations

import pytest

from bot.config import Settings


def test_from_env_requires_token() -> None:
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        Settings.from_env({})


def test_from_env_parses_minimal() -> None:
    settings = Settings.from_env({"TELEGRAM_BOT_TOKEN": "abc:123"})
    assert settings.telegram_bot_token == "abc:123"
    assert settings.allowed_user_ids == frozenset()
    assert settings.is_user_allowed(0) is True
    assert settings.is_user_allowed(None) is True
    assert settings.max_file_size_mb == 50
    assert settings.max_file_size_bytes == 50 * 1024 * 1024
    assert settings.max_video_height == 720
    assert settings.cookies_file is None


def test_from_env_parses_allowed_user_ids() -> None:
    settings = Settings.from_env({"TELEGRAM_BOT_TOKEN": "abc:123", "ALLOWED_USER_IDS": "1, 2,3"})
    assert settings.allowed_user_ids == frozenset({1, 2, 3})
    assert settings.is_user_allowed(1) is True
    assert settings.is_user_allowed(99) is False
    assert settings.is_user_allowed(None) is False


def test_from_env_invalid_user_id() -> None:
    with pytest.raises(ValueError, match="Invalid user id"):
        Settings.from_env({"TELEGRAM_BOT_TOKEN": "abc", "ALLOWED_USER_IDS": "1,bad"})


def test_from_env_invalid_int() -> None:
    with pytest.raises(ValueError, match="MAX_FILE_SIZE_MB"):
        Settings.from_env({"TELEGRAM_BOT_TOKEN": "abc", "MAX_FILE_SIZE_MB": "huge"})


def test_from_env_minimum_enforced() -> None:
    with pytest.raises(ValueError, match=">="):
        Settings.from_env({"TELEGRAM_BOT_TOKEN": "abc", "MAX_VIDEO_HEIGHT": "10"})


def test_from_env_missing_cookies_file(tmp_path) -> None:
    with pytest.raises(RuntimeError, match="COOKIES_FILE"):
        Settings.from_env(
            {
                "TELEGRAM_BOT_TOKEN": "abc",
                "COOKIES_FILE": str(tmp_path / "missing.txt"),
            }
        )


def test_from_env_existing_cookies_file(tmp_path) -> None:
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# cookies\n")
    settings = Settings.from_env({"TELEGRAM_BOT_TOKEN": "abc", "COOKIES_FILE": str(cookies)})
    assert settings.cookies_file == str(cookies)
