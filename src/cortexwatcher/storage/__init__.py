"""Фабрика сховищ логів."""
from __future__ import annotations

from cortexwatcher.config import get_settings
from cortexwatcher.storage.base import LogStorage
from cortexwatcher.storage.clickhouse import ClickHouseStorage
from cortexwatcher.storage.postgres import PostgresStorage


def get_storage() -> LogStorage:
    """Повертає сховище залежно від конфігурації."""

    settings = get_settings()
    if settings.clickhouse_enabled and settings.clickhouse_url:
        return ClickHouseStorage(settings.clickhouse_url)
    return PostgresStorage()


__all__ = ["get_storage"]
