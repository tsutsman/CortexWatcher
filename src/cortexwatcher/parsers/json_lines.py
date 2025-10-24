"""Парсер JSON lines."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterable, List, TypedDict


class JsonLineRecord(TypedDict, total=False):
    timestamp: datetime | None
    host: str | None
    app: str | None
    severity: str | None
    message: str | None
    data: dict


def parse_json_lines(lines: str | Iterable[str]) -> List[JsonLineRecord]:
    """Парсить JSON lines у список словників."""

    if isinstance(lines, str):
        items = lines.splitlines()
    else:
        items = list(lines)
    records: List[JsonLineRecord] = []
    for raw in items:
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        record: JsonLineRecord = {
            "timestamp": coerce_timestamp(payload.get("timestamp") or payload.get("ts")),
            "host": payload.get("host"),
            "app": payload.get("app"),
            "severity": payload.get("severity"),
            "message": payload.get("message") or payload.get("msg"),
            "data": payload,
        }
        records.append(record)
    return records


def _ensure_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def coerce_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str):
        try:
            from dateutil import parser as date_parser

            parsed = date_parser.parse(value)
        except (ValueError, TypeError):
            return None
        return _ensure_utc(parsed)
    if isinstance(value, datetime):
        return _ensure_utc(value)
    return None


__all__ = ["parse_json_lines", "JsonLineRecord", "coerce_timestamp"]
