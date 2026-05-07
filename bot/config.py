"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

CHAT_MODELS: tuple[str, ...] = (
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
)

IMAGE_MODELS: tuple[str, ...] = ("dall-e-3", "dall-e-2")


class Settings(BaseSettings):
    """Settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    telegram_bot_token: str = Field(..., description="Telegram bot token from @BotFather")
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_base_url: str | None = Field(default=None, description="Custom OpenAI base URL")

    # ``NoDecode`` keeps pydantic-settings from trying to JSON-parse the value;
    # we accept a comma-separated string from the env file and convert it below.
    allowed_user_ids: Annotated[list[int], NoDecode] = Field(
        default_factory=list,
        description="If non-empty, only these Telegram user IDs may use the bot.",
    )

    default_model: str = Field(default="gpt-4o-mini")
    default_image_model: str = Field(default="dall-e-3")
    whisper_model: str = Field(default="whisper-1")

    history_limit: int = Field(default=20, ge=2, le=200)

    system_prompt: str = Field(
        default=(
            "You are a helpful AI assistant integrated into a Telegram bot. "
            "Be concise, friendly, and helpful. Use Markdown formatting when appropriate."
        )
    )

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def _split_ids(cls, value: object) -> object:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [int(part) for part in value.split(",") if part.strip()]
        return value

    @field_validator("default_model")
    @classmethod
    def _validate_default_model(cls, value: str) -> str:
        if value not in CHAT_MODELS:
            raise ValueError(f"default_model must be one of {CHAT_MODELS}, got {value!r}")
        return value

    @field_validator("default_image_model")
    @classmethod
    def _validate_default_image_model(cls, value: str) -> str:
        if value not in IMAGE_MODELS:
            raise ValueError(f"default_image_model must be one of {IMAGE_MODELS}, got {value!r}")
        return value


@lru_cache
def get_settings() -> Settings:
    """Return cached :class:`Settings` instance."""

    return Settings()  # type: ignore[call-arg]
