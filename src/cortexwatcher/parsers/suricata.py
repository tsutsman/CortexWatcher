"""Парсер логів Suricata EVE JSON."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from cortexwatcher.parsers.json_lines import coerce_timestamp


def _build_message(event: dict[str, Any]) -> str:
    alert = event.get("alert") or {}
    signature = alert.get("signature")
    category = alert.get("category")
    event_type = event.get("event_type")
    if signature:
        parts = [signature]
        if category:
            parts.append(f"[{category}]")
        return " ".join(parts)
    if event.get("http"):
        http = event["http"]
        method = http.get("http_method")
        uri = http.get("url") or http.get("hostname")
        if method or uri:
            return " ".join(str(part) for part in (method, uri) if part)
    if event_type:
        return str(event_type)
    return event.get("message") or ""


def parse_suricata(content: str) -> list[dict[str, Any]]:
    """Парсить NDJSON із Suricata, повертаючи нормалізовані події."""

    events: list[dict[str, Any]] = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue

        timestamp = coerce_timestamp(payload.get("timestamp") or payload.get("event_timestamp"))
        host = payload.get("host") or payload.get("src_ip") or payload.get("dest_ip")
        event_type = payload.get("event_type")
        severity: str | None = None
        alert = payload.get("alert") or {}
        if "severity" in alert:
            severity = str(alert["severity"])
        elif "priority" in alert:
            severity = str(alert["priority"])

        event_record: dict[str, Any] = {
            "timestamp": timestamp or datetime.now(timezone.utc),
            "host": host,
            "app": f"suricata{(':' + event_type) if event_type else ''}",
            "severity": severity,
            "message": _build_message(payload),
            "raw": payload,
        }
        if "src_ip" in payload:
            event_record.setdefault("src_ip", payload["src_ip"])
        if "dest_ip" in payload:
            event_record.setdefault("dest_ip", payload["dest_ip"])
        events.append(event_record)
    return events


__all__ = ["parse_suricata"]
