"""Tests for ``bot.utils.url``."""

from __future__ import annotations

import pytest

from bot.utils.url import extract_first_url


@pytest.mark.parametrize(
    "text, expected",
    [
        ("https://youtu.be/dQw4w9WgXcQ", "https://youtu.be/dQw4w9WgXcQ"),
        ("Check this out https://youtu.be/dQw4w9WgXcQ!", "https://youtu.be/dQw4w9WgXcQ"),
        ("link: (https://example.com/video).", "https://example.com/video"),
        (
            "https://www.tiktok.com/@user/video/12345?lang=en",
            "https://www.tiktok.com/@user/video/12345?lang=en",
        ),
        (
            "first https://a.com/x then https://b.com/y",
            "https://a.com/x",
        ),
        ("HTTPS://Example.COM/Foo", "HTTPS://Example.COM/Foo"),
    ],
)
def test_extract_first_url_returns_url(text: str, expected: str) -> None:
    assert extract_first_url(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        None,
        "no link here",
        "ftp://example.com/file",
        "javascript:alert(1)",
        "https://",
    ],
)
def test_extract_first_url_returns_none(text: str | None) -> None:
    assert extract_first_url(text) is None
