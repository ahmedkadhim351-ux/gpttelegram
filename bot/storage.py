"""In-memory per-user state.

The bot intentionally keeps state in memory only — it is reset on restart.
This keeps the deployment story trivial (no database) while still feeling
conversational. Persistence can be added later by swapping :class:`MemoryStorage`
for a database-backed implementation.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["system", "user", "assistant"]


@dataclass(slots=True)
class Message:
    role: Role
    content: str


@dataclass(slots=True)
class UserSession:
    """State held for a single Telegram user."""

    chat_model: str
    image_model: str
    history: list[Message] = field(default_factory=list)

    def add(self, role: Role, content: str) -> None:
        self.history.append(Message(role=role, content=content))

    def trim(self, max_messages: int) -> None:
        if len(self.history) > max_messages:
            del self.history[: len(self.history) - max_messages]

    def reset(self) -> None:
        self.history.clear()


class MemoryStorage:
    """Thread/async-safe enough for a single-process bot."""

    def __init__(self, *, default_chat_model: str, default_image_model: str) -> None:
        self._default_chat_model = default_chat_model
        self._default_image_model = default_image_model
        self._sessions: dict[int, UserSession] = defaultdict(self._new_session)

    def _new_session(self) -> UserSession:
        return UserSession(
            chat_model=self._default_chat_model,
            image_model=self._default_image_model,
        )

    def get(self, user_id: int) -> UserSession:
        return self._sessions[user_id]

    def reset(self, user_id: int) -> None:
        self._sessions[user_id].reset()

    def set_chat_model(self, user_id: int, model: str) -> None:
        self._sessions[user_id].chat_model = model

    def set_image_model(self, user_id: int, model: str) -> None:
        self._sessions[user_id].image_model = model

    def all_user_ids(self) -> Iterable[int]:
        return list(self._sessions.keys())
