"""Settings loaded from environment variables / .env.

We keep the model permissive (``extra="ignore"``) because the same .env file is
shared with the main Telegram bot and contains keys this module does not need.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TikTokSettings(BaseSettings):
    """Configuration for the TikTok auto-post client.

    All fields are read from environment variables prefixed with ``TIKTOK_``
    (e.g. ``TIKTOK_CLIENT_KEY``). A local ``.env`` file is loaded if present.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TIKTOK_",
        extra="ignore",
        case_sensitive=False,
    )

    client_key: str = Field(
        ...,
        description="App client key from https://developers.tiktok.com app settings.",
    )
    client_secret: str = Field(
        ...,
        description="App client secret from https://developers.tiktok.com app settings.",
    )
    redirect_uri: str = Field(
        ...,
        description="OAuth redirect URI registered for the TikTok app.",
    )

    access_token: str | None = Field(
        default=None,
        description="Cached OAuth access token (filled after the first auth flow).",
    )
    refresh_token: str | None = Field(
        default=None,
        description="Cached OAuth refresh token (used to obtain new access tokens).",
    )

    api_base: str = Field(
        default="https://open.tiktokapis.com",
        description="Base URL of the TikTok Open API.",
    )
    auth_base: str = Field(
        default="https://www.tiktok.com",
        description="Base URL hosting the OAuth authorization page.",
    )
