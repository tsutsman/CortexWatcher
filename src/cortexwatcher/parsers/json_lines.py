"""Парсер JSON lines."""
from __future__ import annotations

import json
from datetime import datetime
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
            "timestamp": _extract_timestamp(payload),
            "host": payload.get("host"),
            "app": payload.get("app"),
            "severity": payload.get("severity"),
            "message": payload.get("message") or payload.get("msg"),
            "data": payload,
        }
        records.append(record)
    return records


def _extract_timestamp(payload: dict) -> datetime | None:
    value = payload.get("timestamp") or payload.get("ts")
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(float(value))
    if isinstance(value, str):
        try:
            from dateutil import parser as date_parser

            return date_parser.parse(value)
        except (ValueError, TypeError):
            return None
    return None


__all__ = ["parse_json_lines", "JsonLineRecord"]
