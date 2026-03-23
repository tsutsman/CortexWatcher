"""Фабрика сховищ логів."""
from __future__ import annotations

from cortexwatcher.storage.base import LogStorage
from cortexwatcher.storage.postgres import PostgresStorage


def get_storage() -> LogStorage:
    """Повертає сховище залежно від конфігурації.

    ClickHouse тимчасово вимкнено через нестабільну in-memory реалізацію.
    Використовується тільки PostgreSQL.
    """
    return PostgresStorage()


__all__ = ["get_storage"]
