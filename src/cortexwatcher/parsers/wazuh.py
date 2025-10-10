"""Парсер Wazuh alert JSON."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List, TypedDict


class WazuhRecord(TypedDict, total=False):
    rule_id: str | None
    level: int | None
    agent: str | None
    timestamp: datetime | None
    srcip: str | None
    dstip: str | None
    full: dict


def parse_wazuh_alert(payload: str | Dict[str, object]) -> List[WazuhRecord]:
    """Парсить alert від Wazuh."""

    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return []
    else:
        data = payload

    if isinstance(data, dict):
        return [_convert(data)]
    if isinstance(data, list):
        return [_convert(item) for item in data if isinstance(item, dict)]
    return []


def _convert(entry: Dict[str, object]) -> WazuhRecord:
    rule = entry.get("rule") if isinstance(entry.get("rule"), dict) else {}
    agent = entry.get("agent") if isinstance(entry.get("agent"), dict) else {}
    timestamp_raw = entry.get("timestamp")
    ts: datetime | None
    if isinstance(timestamp_raw, str):
        try:
            from dateutil import parser as date_parser

            ts = date_parser.parse(timestamp_raw)
        except (ValueError, TypeError):
            ts = None
    else:
        ts = None
    record: WazuhRecord = {
        "rule_id": str(rule.get("id")) if rule else None,
        "level": int(rule.get("level")) if rule and rule.get("level") is not None else None,
        "agent": agent.get("name") if agent else None,
        "timestamp": ts,
        "srcip": entry.get("srcip"),
        "dstip": entry.get("dstip"),
        "full": entry,
    }
    return record


__all__ = ["parse_wazuh_alert", "WazuhRecord"]
