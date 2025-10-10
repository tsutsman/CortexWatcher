"""Інтерфейс сховища логів."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterable, Sequence

from cortexwatcher.db.models import Alert, Anomaly, LogNormalized, LogRaw


class LogStorage(ABC):
    """Абстрактний клас для різних реалізацій сховищ."""

    @abstractmethod
    async def store_raw_batch(self, records: Sequence[LogRaw]) -> None:
        """Зберігає пакет сирих логів."""

    @abstractmethod
    async def store_normalized_batch(self, records: Sequence[LogNormalized]) -> None:
        """Зберігає пакет нормалізованих логів."""

    @abstractmethod
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
        """Повертає список логів із фільтрами."""

    @abstractmethod
    async def store_alert(self, alert: Alert) -> Alert:
        """Зберігає алерт та повертає його з id."""

    @abstractmethod
    async def list_alerts(self, limit: int = 100) -> list[Alert]:
        """Повертає останні алерти."""

    @abstractmethod
    async def store_anomaly(self, anomaly: Anomaly) -> Anomaly:
        """Зберігає аномалію."""

    @abstractmethod
    async def list_anomalies(self, limit: int = 100) -> list[Anomaly]:
        """Повертає останні аномалії."""

    @abstractmethod
    async def attach_normalized_to_raw(self, raw: LogRaw, normalized: Iterable[LogNormalized]) -> None:
        """Створює звʼязок між сирими та нормалізованими записами."""
