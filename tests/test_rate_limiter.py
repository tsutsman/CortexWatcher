import itertools

import pytest
from pytest import MonkeyPatch

from cortexwatcher.bot.security import RateLimiter


@pytest.mark.parametrize("limit", [1, 3])
def test_rate_limiter_blocks_when_exceeding_limit(
    monkeypatch: MonkeyPatch, limit: int,
) -> None:
    limiter = RateLimiter(limit=limit, window_seconds=60)
    call_times = itertools.count(start=0, step=1)

    monkeypatch.setattr(
        "cortexwatcher.bot.security.time.time",
        lambda: next(call_times),
    )

    chat_id = 123
    for _ in range(limit):
        assert limiter.allowed(chat_id)
    assert not limiter.allowed(chat_id)


def test_rate_limiter_expires_events_after_window(monkeypatch: MonkeyPatch) -> None:
    limiter = RateLimiter(limit=2, window_seconds=10)
    times = iter([0, 5, 15])

    monkeypatch.setattr(
        "cortexwatcher.bot.security.time.time",
        lambda: next(times),
    )

    chat_id = 999
    assert limiter.allowed(chat_id)
    assert limiter.allowed(chat_id)
    assert limiter.allowed(chat_id)


def test_rate_limiter_isolated_queues_per_chat(monkeypatch: MonkeyPatch) -> None:
    limiter = RateLimiter(limit=2, window_seconds=10)
    times = iter([0, 1, 2, 3])

    monkeypatch.setattr(
        "cortexwatcher.bot.security.time.time",
        lambda: next(times),
    )

    chat_a = 1
    chat_b = 2

    assert limiter.allowed(chat_a)
    assert limiter.allowed(chat_a)
    assert not limiter.allowed(chat_a)
    assert limiter.allowed(chat_b)
