"""Thin wrapper around the OpenAI Python SDK.

Centralises retries, timeouts, and turns the SDK responses into simple values
the handlers can use directly.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from io import BytesIO
from pathlib import Path

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from bot.storage import Message

log = logging.getLogger(__name__)

_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (TimeoutError, ConnectionError)


class OpenAIService:
    """High-level wrapper that handlers actually call."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str | None,
        default_chat_model: str,
        whisper_model: str,
        default_image_model: str,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=60.0)
        self._default_chat_model = default_chat_model
        self._whisper_model = whisper_model
        self._default_image_model = default_image_model

    async def chat(
        self,
        *,
        messages: Iterable[Message],
        model: str | None = None,
    ) -> str:
        """Send a chat completion request and return the assistant text."""

        payload: list[ChatCompletionMessageParam] = [
            {"role": m.role, "content": m.content} for m in messages
        ]
        chosen_model = model or self._default_chat_model

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
            reraise=True,
        ):
            with attempt:
                response = await self._client.chat.completions.create(
                    model=chosen_model,
                    messages=payload,
                )
        content = response.choices[0].message.content or ""
        return content.strip()

    async def transcribe(self, audio_path: Path) -> str:
        """Transcribe a voice file to text using Whisper."""

        with audio_path.open("rb") as fh:
            result = await self._client.audio.transcriptions.create(
                model=self._whisper_model,
                file=fh,
            )
        return (result.text or "").strip()

    async def generate_image(
        self,
        *,
        prompt: str,
        model: str | None = None,
        size: str = "1024x1024",
    ) -> str:
        """Generate an image and return its URL."""

        chosen_model = model or self._default_image_model
        response = await self._client.images.generate(
            model=chosen_model,
            prompt=prompt,
            n=1,
            size=size,
        )
        url = response.data[0].url
        if not url:
            raise RuntimeError("OpenAI returned no image URL")
        return url

    async def fetch_image_bytes(self, url: str) -> BytesIO:
        """Download a generated image into memory for direct upload to Telegram."""

        # The OpenAI SDK ships httpx; we use it via the underlying client to
        # keep dependency surface small.
        client = self._client._client  # type: ignore[attr-defined]
        response = await client.get(url)
        response.raise_for_status()
        buf = BytesIO(response.content)
        buf.seek(0)
        return buf
