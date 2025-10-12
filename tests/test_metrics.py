"""Тести оновлених метрик ingest/alerts."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

os.environ.setdefault("TG_BOT_TOKEN", "test")
os.environ.setdefault("ALLOWED_CHAT_IDS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("API_AUTH_TOKEN", "token")

from cortexwatcher.workers import tasks


class DummyPipeline:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []
        self.executed = False

    def hincrby(self, *args: object, **kwargs: object) -> "DummyPipeline":
        self.calls.append(("hincrby", args, kwargs))
        return self

    def hset(self, *args: object, **kwargs: object) -> "DummyPipeline":
        self.calls.append(("hset", args, kwargs))
        return self

    def zadd(self, *args: object, **kwargs: object) -> "DummyPipeline":
        self.calls.append(("zadd", args, kwargs))
        return self

    def zremrangebyscore(self, *args: object, **kwargs: object) -> "DummyPipeline":
        self.calls.append(("zremrangebyscore", args, kwargs))
        return self

    def expire(self, *args: object, **kwargs: object) -> "DummyPipeline":
        self.calls.append(("expire", args, kwargs))
        return self

    def execute(self) -> list[object]:
        self.executed = True
        return []


class DummyRedis:
    def __init__(self) -> None:
        self.pipeline_instance = DummyPipeline()

    def pipeline(self) -> DummyPipeline:
        return self.pipeline_instance


def test_calculate_latencies_handles_timezones() -> None:
    received_at = datetime.now(timezone.utc)
    logs = [
        SimpleNamespace(ts=received_at - timedelta(seconds=1)),
        SimpleNamespace(ts=(received_at - timedelta(seconds=2)).astimezone(timezone.utc)),
        SimpleNamespace(ts="invalid"),
    ]

    latencies = tasks._calculate_latencies(logs, received_at.replace(tzinfo=None))

    assert len(latencies) == 2
    assert all(value >= 0 for value in latencies)


def test_bump_metrics_uses_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyRedis()
    monkeypatch.setattr(tasks, "redis_conn", dummy)

    tasks._bump_metrics(3, [10.0, 20.0, 30.0])

    pipeline = dummy.pipeline_instance
    assert pipeline.executed is True
    commands = [name for name, _, _ in pipeline.calls]
    assert commands.count("hincrby") == 1
    assert commands.count("hset") == 1
    assert "zadd" in commands
    assert "expire" in commands


def test_bump_alert_metrics_updates_totals(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyRedis()
    monkeypatch.setattr(tasks, "redis_conn", dummy)

    tasks._bump_alert_metrics()

    pipeline = dummy.pipeline_instance
    assert pipeline.executed is True
    commands = [name for name, _, _ in pipeline.calls]
    assert commands.count("hincrby") == 1
    assert commands.count("hset") == 1
    assert "zadd" in commands
