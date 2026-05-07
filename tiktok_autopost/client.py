"""Client for TikTok's Content Posting API.

The package implements the official ``init -> upload -> status`` flow:

1. ``POST /v2/post/publish/video/init/`` (or ``.../inbox/video/init/``) with
   metadata and ``source_info`` describing the upload — the response carries a
   ``publish_id`` and an ``upload_url``.
2. ``PUT`` chunks of the video to ``upload_url`` with ``Content-Range``
   headers.
3. Poll ``POST /v2/post/publish/status/fetch/`` until the post is complete
   (or fails).

Reference: https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Literal

import httpx

logger = logging.getLogger(__name__)

PrivacyLevel = Literal[
    "PUBLIC_TO_EVERYONE",
    "MUTUAL_FOLLOW_FRIENDS",
    "FOLLOWER_OF_CREATOR",
    "SELF_ONLY",
]

# Per the TikTok upload spec:
#   * single-chunk uploads must use chunk_size == video_size,
#   * multi-chunk uploads must use 5 MiB <= chunk_size <= 64 MiB,
#   * total_chunk_count = ceil(video_size / chunk_size).
MIN_CHUNK_SIZE = 5 * 1024 * 1024
MAX_CHUNK_SIZE = 64 * 1024 * 1024
DEFAULT_CHUNK_SIZE = 10 * 1024 * 1024


class TikTokAPIError(RuntimeError):
    """Raised when the TikTok API returns an error envelope."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.payload = payload or {}


class TikTokClient:
    """Async client for the TikTok Content Posting API.

    The client takes an OAuth access token. Use :class:`TikTokAuth` to obtain
    one. Pass an ``httpx.AsyncClient`` to share connection pooling, otherwise
    one is created and closed automatically when the context manager exits.
    """

    def __init__(
        self,
        access_token: str,
        *,
        api_base: str = "https://open.tiktokapis.com",
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.access_token = access_token
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self) -> TikTokClient:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

    async def query_creator_info(self) -> dict[str, Any]:
        """Return creator-level constraints (allowed privacy levels, etc.).

        TikTok requires this to be called before showing a publishing UI to
        the creator — the response tells you which privacy levels are
        available, whether duet/stitch/comments are allowed and so on.
        """
        response = await self._client.post(
            f"{self.api_base}/v2/post/publish/creator_info/query/",
            headers=self._headers,
        )
        return self._unwrap(response)

    async def init_direct_post(
        self,
        video_path: Path,
        *,
        title: str,
        privacy_level: PrivacyLevel = "SELF_ONLY",
        disable_duet: bool = False,
        disable_comment: bool = False,
        disable_stitch: bool = False,
        chunk_size: int | None = None,
    ) -> dict[str, Any]:
        """Initialise a *direct* post (the video is published immediately)."""
        return await self._init(
            "/v2/post/publish/video/init/",
            video_path=video_path,
            payload={
                "post_info": {
                    "title": title,
                    "privacy_level": privacy_level,
                    "disable_duet": disable_duet,
                    "disable_comment": disable_comment,
                    "disable_stitch": disable_stitch,
                }
            },
            chunk_size=chunk_size,
        )

    async def init_inbox(
        self,
        video_path: Path,
        *,
        chunk_size: int | None = None,
    ) -> dict[str, Any]:
        """Initialise an *inbox* upload (a draft the creator finishes in-app)."""
        return await self._init(
            "/v2/post/publish/inbox/video/init/",
            video_path=video_path,
            payload={},
            chunk_size=chunk_size,
        )

    async def upload_video(
        self,
        upload_url: str,
        video_path: Path,
        chunk_size: int,
    ) -> None:
        """``PUT`` the video bytes to TikTok's upload URL."""
        size = video_path.stat().st_size  # noqa: ASYNC240 - local stat is non-blocking enough
        if size == 0:
            raise ValueError(f"Video file is empty: {video_path}")

        with video_path.open("rb") as fh:
            offset = 0
            while offset < size:
                end = min(offset + chunk_size, size) - 1
                chunk = fh.read(end - offset + 1)
                response = await self._client.put(
                    upload_url,
                    content=chunk,
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Length": str(len(chunk)),
                        "Content-Range": f"bytes {offset}-{end}/{size}",
                    },
                )
                response.raise_for_status()
                offset = end + 1
                logger.debug(
                    "Uploaded chunk to TikTok: bytes=%s-%s size=%s status=%s",
                    offset - len(chunk),
                    end,
                    size,
                    response.status_code,
                )

    async def fetch_status(self, publish_id: str) -> dict[str, Any]:
        response = await self._client.post(
            f"{self.api_base}/v2/post/publish/status/fetch/",
            headers=self._headers,
            json={"publish_id": publish_id},
        )
        return self._unwrap(response)

    async def wait_for_completion(
        self,
        publish_id: str,
        *,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
    ) -> dict[str, Any]:
        """Poll :meth:`fetch_status` until the publish completes or fails."""
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        last_status: str | None = None
        while True:
            data = await self.fetch_status(publish_id)
            last_status = data.get("status")
            if last_status in {"PUBLISH_COMPLETE", "FAILED"}:
                return data
            if loop.time() >= deadline:
                raise TikTokAPIError(
                    f"Timed out waiting for publish_id={publish_id}; last status={last_status}",
                    payload=data,
                )
            await asyncio.sleep(poll_interval)

    async def post_video(
        self,
        video_path: Path,
        *,
        title: str,
        privacy_level: PrivacyLevel = "SELF_ONLY",
        chunk_size: int | None = None,
        wait: bool = True,
    ) -> dict[str, Any]:
        """High-level helper: ``init`` + ``upload`` + (optional) ``wait``."""
        init = await self.init_direct_post(
            video_path,
            title=title,
            privacy_level=privacy_level,
            chunk_size=chunk_size,
        )
        publish_id = init["publish_id"]
        upload_url = init["upload_url"]
        actual_chunk_size, _ = plan_upload(video_path.stat().st_size, chunk_size)  # noqa: ASYNC240
        await self.upload_video(upload_url, video_path, actual_chunk_size)
        if wait:
            return await self.wait_for_completion(publish_id)
        return init

    async def _init(
        self,
        path: str,
        *,
        video_path: Path,
        payload: dict[str, Any],
        chunk_size: int | None,
    ) -> dict[str, Any]:
        size = video_path.stat().st_size  # noqa: ASYNC240
        if size == 0:
            raise ValueError(f"Video file is empty: {video_path}")
        actual_chunk_size, total_chunk_count = plan_upload(size, chunk_size)
        body = {
            **payload,
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": actual_chunk_size,
                "total_chunk_count": total_chunk_count,
            },
        }
        response = await self._client.post(
            f"{self.api_base}{path}",
            headers=self._headers,
            json=body,
        )
        return self._unwrap(response)

    @staticmethod
    def _unwrap(response: httpx.Response) -> dict[str, Any]:
        """Validate the standard ``{data, error}`` envelope and return ``data``."""
        try:
            payload = response.json()
        except ValueError:
            response.raise_for_status()
            raise

        error = payload.get("error") or {}
        code = error.get("code")
        # The API returns code="ok" on success; everything else is an error.
        if code and code != "ok":
            raise TikTokAPIError(
                error.get("message") or f"TikTok API error: {code}",
                code=code,
                payload=payload,
            )
        if not response.is_success:
            response.raise_for_status()
        return payload.get("data", {}) or {}


def plan_upload(video_size: int, requested_chunk_size: int | None) -> tuple[int, int]:
    """Decide ``(chunk_size, total_chunk_count)`` for the init request.

    For files <= 64 MiB the spec mandates ``chunk_size == video_size`` and
    ``total_chunk_count == 1``. For larger files the chunk size must lie in
    ``[5 MiB, 64 MiB]``.
    """
    if video_size <= 0:
        raise ValueError("video_size must be positive")
    if video_size <= MAX_CHUNK_SIZE:
        return video_size, 1
    chunk_size = requested_chunk_size or DEFAULT_CHUNK_SIZE
    if chunk_size < MIN_CHUNK_SIZE or chunk_size > MAX_CHUNK_SIZE:
        raise ValueError(
            f"chunk_size must be between {MIN_CHUNK_SIZE} and {MAX_CHUNK_SIZE} bytes "
            f"(got {chunk_size})"
        )
    total_chunk_count = (video_size + chunk_size - 1) // chunk_size
    return chunk_size, total_chunk_count
