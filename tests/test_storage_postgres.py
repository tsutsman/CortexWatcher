"""Тести для PostgresStorage із використанням SQLite."""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("TG_BOT_TOKEN", "test")
os.environ.setdefault("ALLOWED_CHAT_IDS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("API_AUTH_TOKEN", "token")
os.environ.setdefault("RULES_PATH", "src/cortexwatcher/rules/sample_rules.yaml")

from cortexwatcher.db.models import Alert, Anomaly, Base, LogNormalized, LogRaw
from cortexwatcher.storage import postgres as postgres_module
from cortexwatcher.storage.postgres import PostgresStorage


@pytest.fixture()
async def storage(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> PostgresStorage:
    """Готує ізольоване in-memory сховище для кожного тесту."""

    db_path = tmp_path_factory.mktemp("pg") / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(postgres_module, "async_session_maker", session_factory)
    yield PostgresStorage()
    await engine.dispose()


@pytest.mark.asyncio()
async def test_postgres_storage_persists_logs_and_filters(storage: PostgresStorage) -> None:
    now = datetime.utcnow()
    raw_first = LogRaw(
        source="api",
        received_at=now,
        payload_raw="{}",
        format="json_lines",
        hash="hash-1",
    )
    raw_second = LogRaw(
        source="bot",
        received_at=now + timedelta(seconds=1),
        payload_raw="{}",
        format="json_lines",
        hash="hash-2",
    )
    await storage.store_raw_batch([raw_first, raw_second])

    normalized_first = LogNormalized(
        raw_id=raw_first.id or 0,
        ts=now - timedelta(minutes=1),
        host="web",
        app="api",
        severity="info",
        msg="service ready",
        meta_json={"field": "value"},
        correlation_key="web|api|info",
    )
    normalized_second = LogNormalized(
        raw_id=raw_second.id or 0,
        ts=now,
        host="db",
        app="postgres",
        severity="error",
        msg="disk full",
        meta_json={"field": "other"},
        correlation_key="db|postgres|error",
    )
    await storage.store_normalized_batch([normalized_first, normalized_second])

    only_web = await storage.list_logs(host="web")
    assert len(only_web) == 1
    assert only_web[0].msg == "service ready"

    only_error = await storage.list_logs(severity="error")
    assert len(only_error) == 1
    assert only_error[0].host == "db"

    recent = await storage.list_logs(start=now - timedelta(minutes=2), end=now - timedelta(seconds=30))
    assert len(recent) == 1
    assert recent[0].correlation_key == "web|api|info"

    search = await storage.list_logs(text="disk")
    assert len(search) == 1
    assert search[0].app == "postgres"

    additional_raw = LogRaw(
        source="api",
        received_at=now,
        payload_raw="{}",
        format="json_lines",
        hash="hash-3",
    )
    await storage.store_raw_batch([additional_raw])
    attached = LogNormalized(
        raw_id=0,
        ts=now,
        host="web",
        app="api",
        severity="warning",
        msg="attached",
        meta_json={},
        correlation_key="web|api|warning",
    )
    await storage.attach_normalized_to_raw(additional_raw, [attached])
    attached_logs = await storage.list_logs(text="attached")
    assert attached_logs
    assert attached_logs[0].raw_id == additional_raw.id


@pytest.mark.asyncio()
async def test_postgres_storage_alerts_and_anomalies(storage: PostgresStorage) -> None:
    now = datetime.utcnow()
    alert = Alert(
        created_at=now,
        rule_id="rule-1",
        level=7,
        title="Подія",
        description="Спрацьовування правила",
        tags=["critical"],
        evidence_json={"key": "value"},
    )
    saved_alert = await storage.store_alert(alert)
    assert saved_alert.id is not None

    alerts = await storage.list_alerts()
    assert len(alerts) == 1
    assert alerts[0].title == "Подія"

    anomaly = Anomaly(
        created_at=now,
        signal="web|api|info",
        score=3.2,
        window=5,
        details_json={"log_id": 1},
    )
    saved_anomaly = await storage.store_anomaly(anomaly)
    assert saved_anomaly.id is not None

    anomalies = await storage.list_anomalies()
    assert len(anomalies) == 1
    assert anomalies[0].score == pytest.approx(3.2)
