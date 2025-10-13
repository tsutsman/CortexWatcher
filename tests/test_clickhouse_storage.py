"""Тести для in-memory ClickHouseStorage."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("TG_BOT_TOKEN", "test")
os.environ.setdefault("ALLOWED_CHAT_IDS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("API_AUTH_TOKEN", "token")
os.environ.setdefault("CLICKHOUSE", "1")
os.environ.setdefault("CLICKHOUSE_URL", "http://localhost")

from cortexwatcher.db.models import Alert, Anomaly, LogNormalized, LogRaw
from cortexwatcher.storage.clickhouse import ClickHouseStorage


@pytest.mark.asyncio
async def test_clickhouse_storage_filters_and_limits_logs() -> None:
    storage = ClickHouseStorage("http://localhost")
    now = datetime.now(timezone.utc)
    raw = LogRaw(
        source="telegram",
        received_at=now,
        payload_raw="{}",
        format="json_lines",
        hash="raw-1",
    )
    await storage.store_raw_batch([raw])

    records = [
        LogNormalized(
            raw_id=raw.id or 1,
            ts=now - timedelta(minutes=5),
            host="web-1",
            app="api",
            severity="error",
            msg="First error",
            meta_json={"line": 10},
            correlation_key="key-1",
        ),
        LogNormalized(
            raw_id=raw.id or 1,
            ts=now - timedelta(minutes=1),
            host="web-2",
            app="worker",
            severity="info",
            msg="Heartbeat ok",
            meta_json={"line": 20},
            correlation_key="key-2",
        ),
    ]
    await storage.store_normalized_batch(records)

    latest = await storage.list_logs(limit=1)
    assert len(latest) == 1
    assert latest[0].host == "web-2"

    filtered = await storage.list_logs(host="web-1", severity="error")
    assert len(filtered) == 1
    assert filtered[0].msg == "First error"

    search = await storage.list_logs(text="heart")
    assert len(search) == 1
    assert search[0].app == "worker"


@pytest.mark.asyncio
async def test_clickhouse_storage_attach_normalized_to_raw() -> None:
    storage = ClickHouseStorage("http://localhost")
    now = datetime.now(timezone.utc)
    raw = LogRaw(
        source="telegram",
        received_at=now,
        payload_raw="{}",
        format="json_lines",
        hash="raw-attach",
    )
    await storage.store_raw_batch([raw])

    normalized = [
        LogNormalized(
            raw_id=0,
            ts=now,
            host="edge",
            app="proxy",
            severity="warning",
            msg="Latency high",
            meta_json={},
            correlation_key=None,
        ),
        LogNormalized(
            raw_id=0,
            ts=now + timedelta(minutes=1),
            host="edge",
            app="proxy",
            severity="warning",
            msg="Latency recovered",
            meta_json={},
            correlation_key=None,
        ),
    ]

    await storage.attach_normalized_to_raw(raw, normalized)
    logs = await storage.list_logs(host="edge")
    assert {item.msg for item in logs} == {"Latency high", "Latency recovered"}
    assert all(item.raw_id == raw.id for item in logs)


@pytest.mark.asyncio
async def test_clickhouse_storage_persists_alerts_and_anomalies() -> None:
    storage = ClickHouseStorage("http://localhost")
    now = datetime.now(timezone.utc)

    stored_alert = await storage.store_alert(
        Alert(
            created_at=now,
            rule_id="rule-1",
            level=5,
            title="Test alert",
            description="Something happened",
            tags=["infra"],
            evidence_json={"key": "value"},
        )
    )
    assert stored_alert.id == 1

    stored_anomaly = await storage.store_anomaly(
        Anomaly(
            created_at=now,
            signal="errors",
            score=3.14,
            window=5,
            details_json={"p95": 700},
        )
    )
    assert stored_anomaly.id == 1

    alerts = await storage.list_alerts()
    anomalies = await storage.list_anomalies()

    assert len(alerts) == 1
    assert alerts[0].title == "Test alert"

    assert len(anomalies) == 1
    assert anomalies[0].signal == "errors"
