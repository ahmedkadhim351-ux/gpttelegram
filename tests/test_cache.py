"""Tests for ``bot.services.cache``."""

from __future__ import annotations

import pytest

from bot.services.cache import TokenCache


def test_put_and_pop_round_trip() -> None:
    cache = TokenCache()
    token = cache.put("https://example.com/video")
    assert isinstance(token, str)
    assert len(token) >= 6

    assert cache.pop(token) == "https://example.com/video"
    assert cache.pop(token) is None


def test_peek_does_not_remove() -> None:
    cache = TokenCache()
    token = cache.put("hello")
    assert cache.peek(token) == "hello"
    assert cache.peek(token) == "hello"
    assert cache.pop(token) == "hello"


def test_unknown_token_returns_none() -> None:
    cache = TokenCache()
    assert cache.pop("nope") is None
    assert cache.peek("nope") is None


def test_eviction_drops_oldest() -> None:
    cache = TokenCache(max_size=3)
    tokens = [cache.put(str(i)) for i in range(3)]
    # Access the second token so it's most-recently-used
    assert cache.peek(tokens[1]) == "1"
    overflow = cache.put("3")

    assert cache.pop(tokens[0]) is None  # oldest evicted
    assert cache.pop(tokens[1]) == "1"
    assert cache.pop(tokens[2]) == "2"
    assert cache.pop(overflow) == "3"


def test_invalid_constructor_args() -> None:
    with pytest.raises(ValueError):
        TokenCache(max_size=0)
    with pytest.raises(ValueError):
        TokenCache(token_bytes=2)


def test_tokens_are_unique() -> None:
    cache = TokenCache()
    seen = {cache.put(f"v{i}") for i in range(50)}
    assert len(seen) == 50
