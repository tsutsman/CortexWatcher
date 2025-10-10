"""Створення асинхронного підключення до БД."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from cortexwatcher.config import get_settings
from cortexwatcher.db.models import Base

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False, future=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_models() -> None:
    """Ініціалізує таблиці без Alembic (для розробки)."""

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


__all__ = ["engine", "async_session_maker", "init_models"]
