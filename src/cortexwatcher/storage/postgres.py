"""Реалізація сховища на PostgreSQL."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from cortexwatcher.db import async_session_maker
from cortexwatcher.db.models import Alert, Anomaly, LogNormalized, LogRaw
from cortexwatcher.storage.base import LogStorage


class PostgresStorage(LogStorage):
    """Збереження логів у PostgreSQL."""

    def _session(self) -> AsyncSession:
        return async_session_maker()

    async def store_raw_batch(self, records: Sequence[LogRaw]) -> None:
        async with self._session() as session:
            session.add_all(records)
            await session.commit()

    async def store_normalized_batch(self, records: Sequence[LogNormalized]) -> None:
        async with self._session() as session:
            session.add_all(records)
            await session.commit()

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
        stmt: Select[tuple[LogNormalized]] = select(LogNormalized).order_by(LogNormalized.ts.desc()).limit(limit)
        if start is not None:
            stmt = stmt.where(LogNormalized.ts >= start)
        if end is not None:
            stmt = stmt.where(LogNormalized.ts <= end)
        if host is not None:
            stmt = stmt.where(LogNormalized.host == host)
        if app is not None:
            stmt = stmt.where(LogNormalized.app == app)
        if severity is not None:
            stmt = stmt.where(LogNormalized.severity == severity)
        if text is not None:
            stmt = stmt.where(LogNormalized.msg.ilike(f"%{text}%"))

        async with self._session() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def store_alert(self, alert: Alert) -> Alert:
        async with self._session() as session:
            session.add(alert)
            await session.flush()
            await session.commit()
            await session.refresh(alert)
            return alert

    async def list_alerts(self, limit: int = 100) -> list[Alert]:
        stmt: Select[tuple[Alert]] = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
        async with self._session() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def store_anomaly(self, anomaly: Anomaly) -> Anomaly:
        async with self._session() as session:
            session.add(anomaly)
            await session.flush()
            await session.commit()
            await session.refresh(anomaly)
            return anomaly

    async def list_anomalies(self, limit: int = 100) -> list[Anomaly]:
        stmt: Select[tuple[Anomaly]] = select(Anomaly).order_by(Anomaly.created_at.desc()).limit(limit)
        async with self._session() as session:
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def attach_normalized_to_raw(self, raw: LogRaw, normalized: Iterable[LogNormalized]) -> None:
        async with self._session() as session:
            db_raw = await session.get(LogRaw, raw.id)
            if db_raw is None:
                return
            for item in normalized:
                item.raw_id = raw.id
                session.add(item)
            await session.commit()


__all__ = ["PostgresStorage"]
