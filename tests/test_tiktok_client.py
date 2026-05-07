from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from tiktok_autopost.client import (
    DEFAULT_CHUNK_SIZE,
    MAX_CHUNK_SIZE,
    MIN_CHUNK_SIZE,
    TikTokAPIError,
    TikTokClient,
    plan_upload,
)


def test_plan_upload_single_chunk_for_small_files() -> None:
    chunk_size, count = plan_upload(1024, requested_chunk_size=None)
    assert chunk_size == 1024
    assert count == 1


def test_plan_upload_uses_default_for_large_files() -> None:
    size = MAX_CHUNK_SIZE * 3 + 7  # forces multi-chunk
    chunk_size, count = plan_upload(size, requested_chunk_size=None)
    assert chunk_size == DEFAULT_CHUNK_SIZE
    assert count == (size + DEFAULT_CHUNK_SIZE - 1) // DEFAULT_CHUNK_SIZE


def test_plan_upload_rejects_out_of_range_chunk_sizes() -> None:
    big_video = MAX_CHUNK_SIZE * 2
    with pytest.raises(ValueError):
        plan_upload(big_video, requested_chunk_size=MIN_CHUNK_SIZE - 1)
    with pytest.raises(ValueError):
        plan_upload(big_video, requested_chunk_size=MAX_CHUNK_SIZE + 1)


def test_plan_upload_rejects_zero_size() -> None:
    with pytest.raises(ValueError):
        plan_upload(0, requested_chunk_size=None)


def _make_client(handler: httpx.MockTransport) -> TikTokClient:
    http = httpx.AsyncClient(transport=handler)
    return TikTokClient(access_token="at", client=http)


async def test_init_direct_post_sends_expected_payload(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"\x00" * 1234)

    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "data": {
                    "publish_id": "pub-123",
                    "upload_url": "https://upload.example.com/abc",
                },
                "error": {"code": "ok", "message": ""},
            },
        )

    client = _make_client(httpx.MockTransport(handler))
    try:
        result = await client.init_direct_post(
            video,
            title="Hello",
            privacy_level="SELF_ONLY",
        )
    finally:
        await client.aclose()

    assert result == {
        "publish_id": "pub-123",
        "upload_url": "https://upload.example.com/abc",
    }
    assert captured["url"] == "https://open.tiktokapis.com/v2/post/publish/video/init/"
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["authorization"] == "Bearer at"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["post_info"] == {
        "title": "Hello",
        "privacy_level": "SELF_ONLY",
        "disable_duet": False,
        "disable_comment": False,
        "disable_stitch": False,
    }
    assert body["source_info"] == {
        "source": "FILE_UPLOAD",
        "video_size": 1234,
        "chunk_size": 1234,
        "total_chunk_count": 1,
    }


async def test_init_inbox_omits_post_info(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"\x00" * 256)
    captured_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content.decode()))
        return httpx.Response(
            200,
            json={
                "data": {"publish_id": "p", "upload_url": "u"},
                "error": {"code": "ok", "message": ""},
            },
        )

    client = _make_client(httpx.MockTransport(handler))
    try:
        await client.init_inbox(video)
    finally:
        await client.aclose()

    assert "post_info" not in captured_body
    assert captured_body["source_info"] == {
        "source": "FILE_UPLOAD",
        "video_size": 256,
        "chunk_size": 256,
        "total_chunk_count": 1,
    }


async def test_unwrap_raises_on_error_envelope(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {},
                "error": {
                    "code": "invalid_param",
                    "message": "title too long",
                },
            },
        )

    client = _make_client(httpx.MockTransport(handler))
    try:
        with pytest.raises(TikTokAPIError) as excinfo:
            await client.fetch_status("pub-123")
    finally:
        await client.aclose()
    assert excinfo.value.code == "invalid_param"
    assert "title too long" in str(excinfo.value)


async def test_upload_video_sends_expected_chunks(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    payload = b"abcdef" * 1024  # 6144 bytes
    video.write_bytes(payload)

    received: list[tuple[str, int, bytes]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        received.append(
            (
                request.headers["content-range"],
                int(request.headers["content-length"]),
                request.content,
            )
        )
        return httpx.Response(200)

    chunk_size = 2048
    client = _make_client(httpx.MockTransport(handler))
    try:
        await client.upload_video(
            "https://upload.example.com/abc",
            video,
            chunk_size=chunk_size,
        )
    finally:
        await client.aclose()

    assert len(received) == 3
    assert received[0][0] == "bytes 0-2047/6144"
    assert received[0][1] == 2048
    assert received[1][0] == "bytes 2048-4095/6144"
    assert received[2][0] == "bytes 4096-6143/6144"
    assert b"".join(c for _, _, c in received) == payload


async def test_upload_video_rejects_empty_files(tmp_path: Path) -> None:
    video = tmp_path / "empty.mp4"
    video.touch()

    client = _make_client(httpx.MockTransport(lambda r: httpx.Response(200)))
    try:
        with pytest.raises(ValueError):
            await client.upload_video("https://example.com/u", video, chunk_size=1024)
    finally:
        await client.aclose()


async def test_post_video_happy_path(tmp_path: Path) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"\x00" * 4096)

    state = {"status_calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/v2/post/publish/video/init/"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "publish_id": "pub-xyz",
                        "upload_url": "https://upload.example.com/u",
                    },
                    "error": {"code": "ok", "message": ""},
                },
            )
        if url.startswith("https://upload.example.com"):
            assert request.method == "PUT"
            return httpx.Response(200)
        if url.endswith("/v2/post/publish/status/fetch/"):
            state["status_calls"] += 1
            status = "PROCESSING_DOWNLOAD" if state["status_calls"] < 2 else "PUBLISH_COMPLETE"
            return httpx.Response(
                200,
                json={
                    "data": {"status": status, "publicly_available_post_id": ["1234567890"]},
                    "error": {"code": "ok", "message": ""},
                },
            )
        raise AssertionError(f"unexpected request: {url}")

    client = _make_client(httpx.MockTransport(handler))
    try:
        result = await client.post_video(
            video,
            title="Promo",
            privacy_level="SELF_ONLY",
        )
    finally:
        await client.aclose()

    assert result["status"] == "PUBLISH_COMPLETE"
    assert state["status_calls"] >= 2


async def test_wait_for_completion_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {"status": "PROCESSING_DOWNLOAD"},
                "error": {"code": "ok", "message": ""},
            },
        )

    client = _make_client(httpx.MockTransport(handler))

    async def fake_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("tiktok_autopost.client.asyncio.sleep", fake_sleep)
    try:
        with pytest.raises(TikTokAPIError):
            await client.wait_for_completion("pub", poll_interval=0.0, timeout=0.0)
    finally:
        await client.aclose()
