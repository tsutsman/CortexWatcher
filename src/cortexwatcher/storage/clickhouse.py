"""Легка реалізація для ClickHouse (in-memory заглушка)."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from cortexwatcher.db.models import Alert, Anomaly, LogNormalized, LogRaw
from cortexwatcher.storage.base import LogStorage


class ClickHouseStorage(LogStorage):
    """Проста in-memory реалізація, що імітує ClickHouse."""

    def __init__(self, url: str) -> None:
        self.url = url
        self._raw: list[LogRaw] = []
        self._normalized: list[LogNormalized] = []
        self._alerts: list[Alert] = []
        self._anomalies: list[Anomaly] = []

    async def store_raw_batch(self, records: Sequence[LogRaw]) -> None:
        for record in records:
            record.id = len(self._raw) + 1  # type: ignore[assignment]
            self._raw.append(record)

    async def store_normalized_batch(self, records: Sequence[LogNormalized]) -> None:
        for record in records:
            record.id = len(self._normalized) + 1  # type: ignore[assignment]
            self._normalized.append(record)

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
        result = list(self._normalized)
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
        return list(sorted(result, key=lambda x: x.ts, reverse=True))[:limit]

    async def store_alert(self, alert: Alert) -> Alert:
        alert.id = len(self._alerts) + 1  # type: ignore[assignment]
        self._alerts.append(alert)
        return alert

    async def list_alerts(self, limit: int = 100) -> list[Alert]:
        return list(self._alerts)[-limit:][::-1]

    async def store_anomaly(self, anomaly: Anomaly) -> Anomaly:
        anomaly.id = len(self._anomalies) + 1  # type: ignore[assignment]
        self._anomalies.append(anomaly)
        return anomaly

    async def list_anomalies(self, limit: int = 100) -> list[Anomaly]:
        return list(self._anomalies)[-limit:][::-1]

    async def attach_normalized_to_raw(self, raw: LogRaw, normalized: Iterable[LogNormalized]) -> None:
        for item in normalized:
            item.raw_id = raw.id
            await self.store_normalized_batch([item])


__all__ = ["ClickHouseStorage"]
