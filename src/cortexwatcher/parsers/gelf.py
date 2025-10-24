"""Парсер GELF (Graylog Extended Log Format)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, List, TypedDict


class GelfRecord(TypedDict, total=False):
    timestamp: datetime | None
    host: str | None
    app: str | None
    severity: str | None
    message: str | None
    full_message: str | None
    data: dict


LEVELS = {
    0: "emerg",
    1: "alert",
    2: "crit",
    3: "err",
    4: "warning",
    5: "notice",
    6: "info",
    7: "debug",
}


def parse_gelf(payload: str | Dict[str, object]) -> List[GelfRecord]:
    """Парсить GELF JSON або рядок."""

    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return []
    else:
        data = payload

    if isinstance(data, dict) and "_id" in data:
        return [_convert_entry(data)]
    if isinstance(data, list):
        return [_convert_entry(item) for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [_convert_entry(data)]
    return []


def _ensure_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _convert_entry(entry: Dict[str, object]) -> GelfRecord:
    timestamp = entry.get("timestamp")
    ts: datetime | None
    if isinstance(timestamp, (float, int)):
        ts = datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
    elif isinstance(timestamp, str):
        try:
            from dateutil import parser as date_parser

            ts = date_parser.parse(timestamp)
        except (ValueError, TypeError):
            ts = None
        else:
            ts = _ensure_utc(ts)
    elif isinstance(timestamp, datetime):
        ts = _ensure_utc(timestamp)
    else:
        ts = None
    level = entry.get("level")
    severity = LEVELS.get(int(level)) if isinstance(level, (int, float)) else None
    record: GelfRecord = {
        "timestamp": ts,
        "host": entry.get("host") or entry.get("_host"),
        "app": entry.get("facility") or entry.get("_app"),
        "severity": severity,
        "message": entry.get("short_message") or entry.get("message"),
        "full_message": entry.get("full_message"),
        "data": entry,
    }
    return record


__all__ = ["parse_gelf", "GelfRecord"]
