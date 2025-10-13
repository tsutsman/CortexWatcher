"""Тести для ClickHouseStorage (in-memory реалізація)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from cortexwatcher.db.models import Alert, Anomaly, LogNormalized, LogRaw
from cortexwatcher.storage.clickhouse import ClickHouseStorage


@pytest.mark.asyncio()
async def test_clickhouse_storage_filters_and_sorting() -> None:
    storage = ClickHouseStorage("http://localhost")
    now = datetime.utcnow()
    raw_first = LogRaw(
        source="api",
        received_at=now,
        payload_raw="{}",
        format="json_lines",
        hash="h1",
    )
    raw_second = LogRaw(
        source="api",
        received_at=now,
        payload_raw="{}",
        format="json_lines",
        hash="h2",
    )
    await storage.store_raw_batch([raw_first, raw_second])

    first = LogNormalized(
        raw_id=raw_first.id or 0,
        ts=now - timedelta(minutes=5),
        host="web",
        app="frontend",
        severity="info",
        msg="all good",
        meta_json={},
        correlation_key="web|frontend|info",
    )
    second = LogNormalized(
        raw_id=raw_second.id or 0,
        ts=now,
        host="web",
        app="frontend",
        severity="error",
        msg="failure detected",
        meta_json={},
        correlation_key="web|frontend|error",
    )
    await storage.store_normalized_batch([first, second])

    latest = await storage.list_logs(host="web", severity="error")
    assert len(latest) == 1
    assert latest[0].msg == "failure detected"

    by_text = await storage.list_logs(text="good")
    assert len(by_text) == 1
    assert by_text[0].severity == "info"

    window = await storage.list_logs(start=now - timedelta(minutes=10), end=now - timedelta(minutes=1))
    assert len(window) == 1
    assert window[0].msg == "all good"


@pytest.mark.asyncio()
async def test_clickhouse_storage_alerts_anomalies_and_attachment() -> None:
    storage = ClickHouseStorage("http://localhost")
    now = datetime.utcnow()
    alert = Alert(
        created_at=now,
        rule_id="r1",
        level=6,
        title="Інцидент",
        description="Проблема",
        tags=["p1"],
        evidence_json={"detail": 1},
    )
    saved_alert = await storage.store_alert(alert)
    assert saved_alert.id == 1
    alerts = await storage.list_alerts()
    assert alerts
    assert alerts[0].title == "Інцидент"

    anomaly = Anomaly(
        created_at=now,
        signal="web|frontend|error",
        score=4.5,
        window=5,
        details_json={"log": 1},
    )
    saved_anomaly = await storage.store_anomaly(anomaly)
    assert saved_anomaly.id == 1
    anomalies = await storage.list_anomalies()
    assert anomalies
    assert anomalies[0].score == pytest.approx(4.5)

    raw = LogRaw(
        source="api",
        received_at=now,
        payload_raw="{}",
        format="json_lines",
        hash="h3",
    )
    await storage.store_raw_batch([raw])
    attached = LogNormalized(
        raw_id=0,
        ts=now,
        host="db",
        app="postgres",
        severity="warning",
        msg="attached",
        meta_json={},
        correlation_key="db|postgres|warning",
    )
    await storage.attach_normalized_to_raw(raw, [attached])
    stored = await storage.list_logs(host="db")
    assert len(stored) == 1
    assert stored[0].raw_id == raw.id
