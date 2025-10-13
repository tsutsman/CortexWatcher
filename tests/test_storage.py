"""Тести для реалізацій сховищ."""

from __future__ import annotations

import importlib
import os
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, AsyncIterator, Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles


@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(element: JSONB, compiler, **_: object) -> str:  # type: ignore[override]
    """Дає змогу використовувати JSONB у sqlite під час тестів."""

    return "JSON"

# Гарантуємо наявність базових налаштувань до імпорту модулів конфігурації
os.environ.setdefault("TG_BOT_TOKEN", "test")
os.environ.setdefault("ALLOWED_CHAT_IDS", "1")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("API_AUTH_TOKEN", "token")
os.environ.setdefault("CLICKHOUSE", "0")
os.environ.setdefault("RULES_PATH", "src/cortexwatcher/rules/sample_rules.yaml")


if TYPE_CHECKING:
    from cortexwatcher.storage.postgres import PostgresStorage


@pytest.fixture(scope="module")
def _database_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Створює окремий sqlite-файл та віддає URL під нього."""

    db_dir = tmp_path_factory.mktemp("storage-db")
    db_path = db_dir / "test.db"
    url = f"sqlite+aiosqlite:///{db_path}"
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        yield url
    finally:
        if previous is not None:
            os.environ["DATABASE_URL"] = previous
        else:
            os.environ.pop("DATABASE_URL", None)


@pytest.fixture(scope="module")
async def postgres_storage(_database_url: str) -> AsyncIterator["PostgresStorage"]:
    """Ініціалізує PostgresStorage поверх sqlite для тестів."""

    from cortexwatcher.config import get_settings

    get_settings.cache_clear()
    session_module = importlib.import_module("cortexwatcher.db.session")
    importlib.reload(session_module)
    db_module = importlib.import_module("cortexwatcher.db")
    importlib.reload(db_module)
    storage_module = importlib.import_module("cortexwatcher.storage.postgres")
    importlib.reload(storage_module)

    from cortexwatcher.db.session import init_models
    from cortexwatcher.db.session import engine
    from cortexwatcher.storage.postgres import PostgresStorage

    await init_models()
    async with engine.begin() as conn:  # type: ignore[attr-defined]
        tables = await conn.run_sync(
            lambda sync_conn: sync_conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        )
        assert {name for name, in tables} >= {
            "logs_raw",
            "logs_normalized",
            "alerts",
            "anomalies",
        }
    storage = PostgresStorage()
    try:
        yield storage
    finally:
        # Немає додаткових ресурсів для закриття, але очищаємо кеш налаштувань
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_postgres_storage_persists_and_filters(postgres_storage: "PostgresStorage") -> None:
    from cortexwatcher.db.models import Alert, LogNormalized, LogRaw

    now = datetime.now(timezone.utc)
    raw = LogRaw(
        source="api",
        received_at=now,
        payload_raw="{}",
        format="json",
        hash="hash-1",
    )
    await postgres_storage.store_raw_batch([raw])
    assert raw.id is not None

    normalized = LogNormalized(
        raw_id=raw.id,
        ts=now,
        host="web",
        app="frontend",
        severity="error",
        msg="Failed to load",
        meta_json={"ip": "127.0.0.1"},
        correlation_key="web-frontend",
    )
    await postgres_storage.store_normalized_batch([normalized])

    later = now + timedelta(minutes=5)
    extra = LogNormalized(
        raw_id=raw.id,
        ts=later,
        host="web",
        app="frontend",
        severity="error",
        msg="Recovered",
        meta_json={"ip": "127.0.0.1"},
        correlation_key="web-frontend",
    )
    await postgres_storage.attach_normalized_to_raw(raw, [extra])

    logs = await postgres_storage.list_logs(host="web", severity="error", limit=5)
    assert [item.msg for item in logs] == ["Recovered", "Failed to load"]
    assert all(item.raw_id == raw.id for item in logs)

    alert = Alert(
        created_at=now,
        rule_id="rule-1",
        level=2,
        title="Test alert",
        description="Example",
        tags=["demo"],
        evidence_json={"foo": "bar"},
    )
    stored_alert = await postgres_storage.store_alert(alert)
    alerts = await postgres_storage.list_alerts()
    assert alerts
    assert alerts[0].id == stored_alert.id


@pytest.mark.asyncio
async def test_postgres_storage_handles_anomalies(postgres_storage: "PostgresStorage") -> None:
    from cortexwatcher.db.models import Anomaly

    now = datetime.now(timezone.utc)
    anomaly = Anomaly(
        created_at=now,
        signal="events_total",
        score=3.14,
        window=15,
        details_json={"value": 42},
    )
    stored = await postgres_storage.store_anomaly(anomaly)
    anomalies = await postgres_storage.list_anomalies()
    assert anomalies
    assert anomalies[0].id == stored.id
    assert anomalies[0].signal == "events_total"


@pytest.mark.asyncio
async def test_clickhouse_storage_in_memory_behaviour() -> None:
    from cortexwatcher.db.models import Alert, LogNormalized, LogRaw
    from cortexwatcher.storage.clickhouse import ClickHouseStorage

    storage = ClickHouseStorage("http://localhost")
    now = datetime.now(timezone.utc)

    raw = LogRaw(
        source="telegram",
        received_at=now,
        payload_raw="{}",
        format="json",
        hash="hash-raw",
    )
    await storage.store_raw_batch([raw])

    record = LogNormalized(
        raw_id=raw.id or 1,
        ts=now,
        host="edge",
        app="collector",
        severity="info",
        msg="Heartbeat",
        meta_json={},
        correlation_key="edge-collector",
    )
    await storage.store_normalized_batch([record])
    logs = await storage.list_logs(text="Heart")
    assert len(logs) == 1
    assert logs[0].msg == "Heartbeat"

    alert = Alert(
        created_at=now,
        rule_id=None,
        level=1,
        title="Info",
        description="Heartbeat",
        tags=[],
        evidence_json={},
    )
    await storage.store_alert(alert)
    alerts = await storage.list_alerts()
    assert alerts
    assert alerts[0].title == "Info"

    anomalies = await storage.list_anomalies()
    assert anomalies == []

