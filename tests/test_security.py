"""Тести для безпекових утиліт бота."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from cortexwatcher.bot.security import RateLimiter, is_chat_allowed


@pytest.fixture(autouse=True)
def reset_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """Скидає час між тестами, щоби лімітер працював детерміновано."""

    # За замовчуванням використовуємо монотонний час, який збільшується на кожен виклик.
    counter = {"value": 0.0}

    def fake_time() -> float:
        counter["value"] += 1.0
        return counter["value"]

    monkeypatch.setattr("cortexwatcher.bot.security.time", SimpleNamespace(time=fake_time))


def test_rate_limiter_blocks_after_reaching_limit() -> None:
    limiter = RateLimiter(limit=2, window_seconds=5)

    assert limiter.allowed(chat_id=1) is True
    assert limiter.allowed(chat_id=1) is True
    assert limiter.allowed(chat_id=1) is False


def test_rate_limiter_frees_slots_after_window(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = RateLimiter(limit=2, window_seconds=3)
    call_times = iter([0.0, 1.0, 2.0, 5.1])

    monkeypatch.setattr(
        "cortexwatcher.bot.security.time.time",
        lambda: next(call_times),
    )

    assert limiter.allowed(chat_id=42) is True
    assert limiter.allowed(chat_id=42) is True
    assert limiter.allowed(chat_id=42) is False
    assert limiter.allowed(chat_id=42) is True


def test_is_chat_allowed_uses_whitelist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "cortexwatcher.bot.security.get_settings",
        lambda: SimpleNamespace(allowed_chat_ids=[10, 20]),
    )

    assert is_chat_allowed(10) is True
    assert is_chat_allowed(30) is False
