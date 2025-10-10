"""Ендпоінти запитів."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from cortexwatcher.storage.base import LogStorage

router = APIRouter()


async def get_storage_from_app(request: Request) -> LogStorage:
    storage = getattr(request.app.state, "storage", None)
    if storage is None:
        raise HTTPException(status_code=500, detail="Storage не ініціалізовано")
    return storage


@router.get("/logs")
async def list_logs(
    request: Request,
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    host: str | None = Query(default=None),
    app: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    text: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    storage: LogStorage = Depends(get_storage_from_app),
) -> list[dict[str, Any]]:
    items = await storage.list_logs(start=start, end=end, host=host, app=app, severity=severity, text=text, limit=limit)
    return [
        {
            "id": item.id,
            "ts": item.ts,
            "host": item.host,
            "app": item.app,
            "severity": item.severity,
            "msg": item.msg,
            "meta": item.meta_json,
            "correlation_key": item.correlation_key,
        }
        for item in items
    ]


@router.get("/alerts")
async def list_alerts(
    storage: LogStorage = Depends(get_storage_from_app),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    alerts = await storage.list_alerts(limit=limit)
    return [
        {
            "id": alert.id,
            "created_at": alert.created_at,
            "rule_id": alert.rule_id,
            "level": alert.level,
            "title": alert.title,
            "description": alert.description,
            "tags": alert.tags,
            "evidence": alert.evidence_json,
        }
        for alert in alerts
    ]


@router.get("/anomalies")
async def list_anomalies(
    storage: LogStorage = Depends(get_storage_from_app),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    anomalies = await storage.list_anomalies(limit=limit)
    return [
        {
            "id": anomaly.id,
            "created_at": anomaly.created_at,
            "signal": anomaly.signal,
            "score": anomaly.score,
            "window": anomaly.window,
            "details": anomaly.details_json,
        }
        for anomaly in anomalies
    ]


__all__ = ["router"]
