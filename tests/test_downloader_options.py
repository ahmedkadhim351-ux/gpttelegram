"""Unit tests for the pure helpers in ``bot.services.downloader``."""

from __future__ import annotations

import pytest

from bot.services.downloader import (
    FileTooLargeError,
    MediaKind,
    build_ydl_options,
    format_duration,
)


def test_video_options_include_height_constraint() -> None:
    opts = build_ydl_options(
        output_template="/tmp/%(id)s.%(ext)s",
        kind=MediaKind.VIDEO,
        max_height=480,
    )
    assert opts["noplaylist"] is True
    assert opts["merge_output_format"] == "mp4"
    assert "height<=480" in opts["format"]
    # Audio postprocessor should NOT be in the video pipeline
    assert all(p["key"] != "FFmpegExtractAudio" for p in opts.get("postprocessors", []))


def test_audio_options_use_mp3_postprocessor() -> None:
    opts = build_ydl_options(
        output_template="/tmp/%(id)s.%(ext)s",
        kind=MediaKind.AUDIO,
    )
    assert opts["format"] == "bestaudio/best"
    assert any(
        p["key"] == "FFmpegExtractAudio" and p["preferredcodec"] == "mp3"
        for p in opts.get("postprocessors", [])
    )


def test_max_filesize_propagates() -> None:
    opts = build_ydl_options(
        output_template="/tmp/%(id)s.%(ext)s",
        kind=MediaKind.VIDEO,
        max_filesize_bytes=10 * 1024 * 1024,
    )
    assert opts["max_filesize"] == 10 * 1024 * 1024


def test_max_filesize_omitted_when_zero() -> None:
    opts = build_ydl_options(
        output_template="/tmp/%(id)s.%(ext)s",
        kind=MediaKind.VIDEO,
        max_filesize_bytes=0,
    )
    assert "max_filesize" not in opts


def test_cookiefile_propagates() -> None:
    opts = build_ydl_options(
        output_template="/tmp/%(id)s.%(ext)s",
        kind=MediaKind.AUDIO,
        cookiefile="/tmp/cookies.txt",
    )
    assert opts["cookiefile"] == "/tmp/cookies.txt"


def test_unknown_kind_rejected() -> None:
    with pytest.raises(ValueError):
        build_ydl_options(
            output_template="/tmp/%(id)s.%(ext)s",
            kind="other",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (None, "—"),
        (-1, "—"),
        (0, "0:00"),
        (5, "0:05"),
        (65, "1:05"),
        (3600, "1:00:00"),
        (3661, "1:01:01"),
    ],
)
def test_format_duration(seconds: int | None, expected: str) -> None:
    assert format_duration(seconds) == expected


def test_file_too_large_error_carries_metadata() -> None:
    err = FileTooLargeError(size_bytes=100 * 1024 * 1024, limit_bytes=50 * 1024 * 1024)
    assert err.size_mb == pytest.approx(100.0)
    assert err.limit_mb == pytest.approx(50.0)
    assert "exceeds" in str(err)
