"""Tiny in-memory cache to ferry URLs through callback_data.

Telegram limits ``callback_data`` to 64 bytes, which is too small for many media
URLs. We stash URLs server-side keyed by a short token and only put the token in
the keyboard.
"""

from __future__ import annotations

import secrets
from collections import OrderedDict


class TokenCache:
    """Bounded LRU-ish mapping of short tokens to arbitrary string values."""

    def __init__(self, *, max_size: int = 1024, token_bytes: int = 6) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        if token_bytes < 4:
            raise ValueError("token_bytes must be >= 4")
        self._store: OrderedDict[str, str] = OrderedDict()
        self._max_size = max_size
        self._token_bytes = token_bytes

    def put(self, value: str) -> str:
        token = secrets.token_urlsafe(self._token_bytes)
        # Avoid colliding with an existing token
        while token in self._store:
            token = secrets.token_urlsafe(self._token_bytes)
        self._store[token] = value
        self._store.move_to_end(token)
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)
        return token

    def pop(self, token: str) -> str | None:
        return self._store.pop(token, None)

    def peek(self, token: str) -> str | None:
        value = self._store.get(token)
        if value is not None:
            self._store.move_to_end(token)
        return value

    def __len__(self) -> int:
        return len(self._store)
