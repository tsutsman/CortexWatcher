"""ORM-моделі для таблиць з логами."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовий клас моделей."""

    type_annotation_map = {dict[str, Any]: JSONB}


class LogRaw(Base):
    """Сирі логи у первинному вигляді."""

    __tablename__ = "logs_raw"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    received_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    payload_raw: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(String(32), nullable=False)
    hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    normalized: Mapped[list["LogNormalized"]] = relationship(back_populates="raw")


class LogNormalized(Base):
    """Нормалізовані логи для пошуку."""

    __tablename__ = "logs_normalized"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    raw_id: Mapped[int] = mapped_column(ForeignKey("logs_raw.id", ondelete="CASCADE"), nullable=False)
    ts: Mapped[datetime] = mapped_column(nullable=False, index=True)
    host: Mapped[str | None] = mapped_column(String(255), index=True)
    app: Mapped[str | None] = mapped_column(String(255), index=True)
    severity: Mapped[str | None] = mapped_column(String(32), index=True)
    msg: Mapped[str] = mapped_column(Text, nullable=False)
    meta_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    correlation_key: Mapped[str | None] = mapped_column(String(255), index=True)

    raw: Mapped[LogRaw] = relationship(back_populates="normalized")

    __table_args__ = (
        Index("ix_logs_normalized_ts_host_app", "ts", "host", "app"),
    )


class Alert(Base):
    """Алерти, сформовані правилами чи аномаліями."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    rule_id: Mapped[str | None] = mapped_column(String(64), index=True)
    level: Mapped[int] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class Anomaly(Base):
    """Аномалії, що перевищили поріг."""

    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    signal: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[float] = mapped_column(nullable=False)
    window: Mapped[int] = mapped_column(nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


__all__ = ["Base", "LogRaw", "LogNormalized", "Alert", "Anomaly"]
