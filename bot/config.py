"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _parse_user_ids(raw: str) -> frozenset[int]:
    if not raw:
        return frozenset()
    out: set[int] = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            out.add(int(chunk))
        except ValueError as e:
            raise ValueError(f"Invalid user id in ALLOWED_USER_IDS: {chunk!r}") from e
    return frozenset(out)


def _parse_int(name: str, raw: str | None, default: int, *, minimum: int = 1) -> int:
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as e:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from e
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


@dataclass(frozen=True)
class Settings:
    """Bot configuration."""

    telegram_bot_token: str
    allowed_user_ids: frozenset[int] = field(default_factory=frozenset)
    max_file_size_mb: int = 50
    max_video_height: int = 720
    cookies_file: str | None = None
    log_level: str = "INFO"

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def is_user_filter_enabled(self) -> bool:
        return len(self.allowed_user_ids) > 0

    def is_user_allowed(self, user_id: int | None) -> bool:
        if not self.is_user_filter_enabled:
            return True
        if user_id is None:
            return False
        return user_id in self.allowed_user_ids

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = dict(os.environ if env is None else env)

        token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN is required. Get one from @BotFather and put it in .env"
            )

        allowed = _parse_user_ids(env.get("ALLOWED_USER_IDS", ""))
        max_file_size_mb = _parse_int(
            "MAX_FILE_SIZE_MB", env.get("MAX_FILE_SIZE_MB"), default=50, minimum=1
        )
        max_video_height = _parse_int(
            "MAX_VIDEO_HEIGHT", env.get("MAX_VIDEO_HEIGHT"), default=720, minimum=144
        )

        cookies_file = (env.get("COOKIES_FILE") or "").strip() or None
        if cookies_file and not os.path.exists(cookies_file):
            raise RuntimeError(f"COOKIES_FILE points to a missing path: {cookies_file}")

        log_level = (env.get("LOG_LEVEL") or "INFO").strip().upper()

        return cls(
            telegram_bot_token=token,
            allowed_user_ids=allowed,
            max_file_size_mb=max_file_size_mb,
            max_video_height=max_video_height,
            cookies_file=cookies_file,
            log_level=log_level,
        )
