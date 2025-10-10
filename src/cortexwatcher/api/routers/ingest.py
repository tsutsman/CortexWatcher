"""Ендпоінти прийому логів."""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from cortexwatcher.analyzer.correlate import build_correlation_key
from cortexwatcher.config import get_settings
from cortexwatcher.db.models import LogNormalized, LogRaw
from cortexwatcher.parsers import detect_format, parse_gelf, parse_json_lines, parse_syslog, parse_wazuh_alert
from cortexwatcher.storage.base import LogStorage

router = APIRouter()


class IngestPayload(BaseModel):
    items: List[Any] | None = Field(default=None, description="Список JSON обʼєктів")
    content: str | None = Field(default=None, description="Сирий текст або NDJSON")


async def get_storage_from_app(request: Request) -> LogStorage:
    storage = getattr(request.app.state, "storage", None)
    if storage is None:
        raise HTTPException(status_code=500, detail="Storage не ініціалізовано")
    return storage


def _check_token(request: Request) -> None:
    settings = get_settings()
    token = request.headers.get("X-API-Token")
    if token != settings.api_auth_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недійсний токен")


@router.post("/ingest/{source}")
async def ingest_logs(
    source: str,
    payload: IngestPayload,
    request: Request,
    storage: LogStorage = Depends(get_storage_from_app),
) -> dict[str, Any]:
    _check_token(request)
    content = payload.content or ""
    if payload.items:
        content += "\n".join([_ensure_string(item) for item in payload.items])
    if not content.strip():
        raise HTTPException(status_code=400, detail="Порожнє повідомлення")

    fmt = detect_format(content)
    parsed = _parse_by_format(fmt, content)

    received_at = datetime.utcnow()
    raw = LogRaw(
        source=source,
        received_at=received_at,
        payload_raw=content,
        format=fmt,
        hash=hashlib.sha256(content.encode()).hexdigest(),
    )
    normalized = [
        LogNormalized(
            raw_id=0,
            ts=item.get("timestamp") or received_at,
            host=item.get("host"),
            app=item.get("app"),
            severity=item.get("severity"),
            msg=str(item.get("message") or item.get("msg") or ""),
            meta_json=item,
            correlation_key=build_correlation_key(item),
        )
        for item in parsed
    ]

    await storage.store_raw_batch([raw])
    raw_id = getattr(raw, "id", None)
    for item in normalized:
        item.raw_id = raw_id or 0
    await storage.store_normalized_batch(normalized)
    return {"stored": len(normalized), "format": fmt}


def _ensure_string(item: Any) -> str:
    if isinstance(item, str):
        return item
    return json_dumps(item)


def json_dumps(item: Any) -> str:
    import json

    return json.dumps(item, ensure_ascii=False)


def _parse_by_format(fmt: str, content: str) -> list[dict[str, Any]]:
    if fmt == "syslog":
        return parse_syslog(content)
    if fmt == "json_lines":
        return parse_json_lines(content)
    if fmt == "gelf":
        return parse_gelf(content)
    if fmt == "wazuh":
        return parse_wazuh_alert(content)
    return []


__all__ = ["router"]
