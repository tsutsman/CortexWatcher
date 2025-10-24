"""Парсер для syslog (RFC3164/5424)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterable, List, TypedDict

from dateutil import parser as date_parser


class SyslogRecord(TypedDict, total=False):
    timestamp: datetime
    host: str
    app: str
    pid: str | None
    severity: str | None
    message: str


RFC3164_REGEX = re.compile(
    r"^(?:(?:<(?P<pri>\d+)>)?)(?P<ts>[A-Z][a-z]{2} +\d{1,2} \d{2}:\d{2}:\d{2}) (?P<host>\S+) (?P<tag>[\w\-/]+)(?:\[(?P<pid>\d+)\])?: (?P<msg>.*)$"
)
RFC5424_REGEX = re.compile(
    r"^(?:<(?P<pri>\d+)>)?(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})) (?P<host>\S+) (?P<app>\S+) (?P<pid>\S+) (?P<msgid>\S+) (?P<structured>-|\[.*\]) (?P<msg>.*)$"
)

SEVERITY_MAP = {
    0: "emerg",
    1: "alert",
    2: "crit",
    3: "err",
    4: "warning",
    5: "notice",
    6: "info",
    7: "debug",
}


def _ensure_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def parse_syslog(lines: str | Iterable[str]) -> List[SyslogRecord]:
    """Парсить syslog у список словників."""

    if isinstance(lines, str):
        items = lines.splitlines()
    else:
        items = list(lines)
    records: List[SyslogRecord] = []
    for raw in items:
        raw = raw.strip()
        if not raw:
            continue
        match = RFC5424_REGEX.match(raw)
        if match:
            pri = match.group("pri")
            severity = SEVERITY_MAP.get(int(pri) % 8) if pri else None
            ts = _ensure_utc(date_parser.parse(match.group("ts")))
            record: SyslogRecord = {
                "timestamp": ts,
                "host": match.group("host"),
                "app": match.group("app"),
                "pid": match.group("pid") if match.group("pid") != "-" else None,
                "severity": severity,
                "message": match.group("msg"),
            }
            records.append(record)
            continue
        match = RFC3164_REGEX.match(raw)
        if match:
            pri = match.group("pri")
            severity = SEVERITY_MAP.get(int(pri) % 8) if pri else None
            now = datetime.now(timezone.utc)
            ts = date_parser.parse(match.group("ts"), default=now)
            ts = _ensure_utc(ts).replace(year=now.year)
            record = {
                "timestamp": ts,
                "host": match.group("host"),
                "app": match.group("tag"),
                "pid": match.group("pid"),
                "severity": severity,
                "message": match.group("msg"),
            }
            records.append(record)
    return records


__all__ = ["parse_syslog", "SyslogRecord"]
