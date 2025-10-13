"""Тести для воркерів ingest та analyzer."""
from __future__ import annotations

import os
from datetime import datetime
from types import SimpleNamespace
from typing import Iterable, Sequence

import pytest

os.environ.setdefault("TG_BOT_TOKEN", "test")
os.environ.setdefault("ALLOWED_CHAT_IDS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("API_AUTH_TOKEN", "token")
os.environ.setdefault("RULES_PATH", "src/cortexwatcher/rules/sample_rules.yaml")

from cortexwatcher.db.models import Alert, Anomaly, LogNormalized, LogRaw
from cortexwatcher.storage.base import LogStorage
from cortexwatcher.workers import tasks


class InMemoryStorage(LogStorage):
    """Проста in-memory реалізація для тестів воркерів."""

    def __init__(self) -> None:
        self.raw_records: list[LogRaw] = []
        self.normalized_records: list[LogNormalized] = []
        self.alerts: list[Alert] = []
        self.anomalies: list[Anomaly] = []

    async def store_raw_batch(self, records: Sequence[LogRaw]) -> None:
        for record in records:
            if getattr(record, "id", None) is None:
                record.id = len(self.raw_records) + 1  # type: ignore[assignment]
            self.raw_records.append(record)

    async def store_normalized_batch(self, records: Sequence[LogNormalized]) -> None:
        for record in records:
            if getattr(record, "id", None) is None:
                record.id = len(self.normalized_records) + 1  # type: ignore[assignment]
            self.normalized_records.append(record)

    async def list_logs(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        host: str | None = None,
        app: str | None = None,
        severity: str | None = None,
        text: str | None = None,
        limit: int = 100,
    ) -> list[LogNormalized]:
        result = list(self.normalized_records)
        if start is not None:
            result = [item for item in result if item.ts >= start]
        if end is not None:
            result = [item for item in result if item.ts <= end]
        if host is not None:
            result = [item for item in result if item.host == host]
        if app is not None:
            result = [item for item in result if item.app == app]
        if severity is not None:
            result = [item for item in result if item.severity == severity]
        if text is not None:
            result = [item for item in result if text.lower() in item.msg.lower()]
        return list(sorted(result, key=lambda log: log.ts, reverse=True))[:limit]

    async def store_alert(self, alert: Alert) -> Alert:
        alert.id = len(self.alerts) + 1  # type: ignore[assignment]
        self.alerts.append(alert)
        return alert

    async def list_alerts(self, limit: int = 100) -> list[Alert]:
        return list(self.alerts)[-limit:][::-1]

    async def store_anomaly(self, anomaly: Anomaly) -> Anomaly:
        anomaly.id = len(self.anomalies) + 1  # type: ignore[assignment]
        self.anomalies.append(anomaly)
        return anomaly

    async def list_anomalies(self, limit: int = 100) -> list[Anomaly]:
        return list(self.anomalies)[-limit:][::-1]

    async def attach_normalized_to_raw(self, raw: LogRaw, normalized: Iterable[LogNormalized]) -> None:
        for item in normalized:
            item.raw_id = raw.id
            await self.store_normalized_batch([item])


@pytest.mark.asyncio()
async def test_process_ingest_creates_records(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = InMemoryStorage()
    monkeypatch.setattr(tasks, "get_storage", lambda: storage)
    metrics_calls: list[tuple[int, list[float]]] = []
    monkeypatch.setattr(
        tasks,
        "_bump_metrics",
        lambda count, latencies: metrics_calls.append((count, list(latencies))),
    )

    result = await tasks._process_ingest(
        "api",
        {"content": '{"host": "web", "app": "svc", "message": "hello"}'},
    )

    assert result == {"stored": 1, "format": "json_lines"}
    assert len(storage.raw_records) == 1
    assert len(storage.normalized_records) == 1
    assert storage.normalized_records[0].raw_id == storage.raw_records[0].id
    assert metrics_calls and metrics_calls[0][0] == 1
    assert metrics_calls[0][1] == [0.0]


@pytest.mark.asyncio()
async def test_process_ingest_handles_empty_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = InMemoryStorage()
    monkeypatch.setattr(tasks, "get_storage", lambda: storage)
    monkeypatch.setattr(tasks, "_bump_metrics", lambda *_: (_ for _ in ()).throw(RuntimeError("не має викликатись")))

    result = await tasks._process_ingest("api", {"content": "   "})

    assert result == {"stored": 0, "format": "unknown"}
    assert not storage.raw_records
    assert not storage.normalized_records


@pytest.mark.asyncio()
async def test_evaluate_log_creates_alert_and_anomaly(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = InMemoryStorage()

    class DummyEngine:
        def match(self, record: dict[str, object]) -> list[SimpleNamespace]:
            return [
                SimpleNamespace(
                    id="rule-42",
                    severity=7,
                    title="Алерт",
                    description="Опис",
                    tags=["security"],
                )
            ]

    class DummyNotifier:
        def __init__(self) -> None:
            self.alerts: list[Alert] = []

        async def persist_and_notify(self, alert: Alert, thread_id: int | None = None) -> Alert:
            saved = await storage.store_alert(alert)
            self.alerts.append(saved)
            return saved

    class DummyDetector:
        window_minutes = 5

        def update(
            self,
            host: str | None,
            app: str | None,
            severity: str | None,
            timestamp: datetime,
        ) -> tuple[bool, float]:
            return True, 3.7

    monkeypatch.setattr(tasks, "_bump_alert_metrics", lambda: None)

    log = LogNormalized(
        raw_id=1,
        ts=datetime.utcnow(),
        host="web",
        app="svc",
        severity="error",
        msg="problem",
        meta_json={"srcip": "1.1.1.1"},
        correlation_key="web|svc|error",
    )
    log.id = 10  # type: ignore[assignment]

    await tasks._evaluate_log(storage, DummyEngine(), DummyNotifier(), DummyDetector(), log)

    assert len(storage.alerts) == 1
    saved_alert = storage.alerts[0]
    assert saved_alert.rule_id == "rule-42"
    assert saved_alert.evidence_json["log_id"] == log.id

    assert len(storage.anomalies) == 1
    saved_anomaly = storage.anomalies[0]
    assert saved_anomaly.signal == "web|svc|error"
    assert saved_anomaly.score == pytest.approx(3.7)
