"""Custom aiogram filters."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message


class AllowedUserFilter(Filter):
    """Restricts handlers to a known list of Telegram user IDs.

    If the configured allow-list is empty, every user passes.
    """

    def __init__(self, allowed_ids: Sequence[int]) -> None:
        self._allowed = set(allowed_ids)

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        if not self._allowed:
            return True
        user = event.from_user
        return user is not None and user.id in self._allowed
