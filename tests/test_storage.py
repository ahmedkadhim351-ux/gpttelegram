"""Tests for the in-memory storage."""

from __future__ import annotations

from bot.storage import MemoryStorage


def test_default_session_uses_configured_models() -> None:
    storage = MemoryStorage(default_chat_model="gpt-4o-mini", default_image_model="dall-e-3")
    session = storage.get(42)
    assert session.chat_model == "gpt-4o-mini"
    assert session.image_model == "dall-e-3"
    assert session.history == []


def test_history_trim_keeps_last_n_messages() -> None:
    storage = MemoryStorage(default_chat_model="gpt-4o-mini", default_image_model="dall-e-3")
    session = storage.get(1)
    for i in range(10):
        session.add("user", f"msg {i}")
    session.trim(3)
    assert len(session.history) == 3
    assert [m.content for m in session.history] == ["msg 7", "msg 8", "msg 9"]


def test_reset_clears_history_for_user() -> None:
    storage = MemoryStorage(default_chat_model="gpt-4o-mini", default_image_model="dall-e-3")
    session = storage.get(1)
    session.add("user", "hi")
    session.add("assistant", "hello")
    storage.reset(1)
    assert storage.get(1).history == []


def test_set_chat_model_updates_session() -> None:
    storage = MemoryStorage(default_chat_model="gpt-4o-mini", default_image_model="dall-e-3")
    storage.set_chat_model(7, "gpt-4o")
    assert storage.get(7).chat_model == "gpt-4o"


def test_sessions_are_isolated_between_users() -> None:
    storage = MemoryStorage(default_chat_model="gpt-4o-mini", default_image_model="dall-e-3")
    storage.get(1).add("user", "alice")
    storage.get(2).add("user", "bob")
    assert [m.content for m in storage.get(1).history] == ["alice"]
    assert [m.content for m in storage.get(2).history] == ["bob"]
