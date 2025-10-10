"""Тести парсерів."""
from __future__ import annotations

from datetime import datetime

from cortexwatcher.parsers import detect_format, parse_gelf, parse_json_lines, parse_syslog, parse_wazuh_alert


def test_detect_syslog() -> None:
    sample = "<34>Oct 11 22:14:15 mymachine su: 'su root' failed for lonvick"
    assert detect_format(sample) == "syslog"


def test_parse_syslog() -> None:
    sample = "<34>Oct 11 22:14:15 mymachine su: 'su root' failed"
    result = parse_syslog(sample)
    assert result[0]["app"] == "su"


def test_parse_json_lines() -> None:
    sample = '{"host": "web", "app": "nginx", "message": "ok", "timestamp": "2024-01-01T00:00:00Z"}'
    result = parse_json_lines(sample)
    assert result[0]["app"] == "nginx"
    assert isinstance(result[0]["timestamp"], datetime)


def test_parse_gelf() -> None:
    sample = '{"short_message": "Hello", "timestamp": 1700000000, "host": "api", "level": 6}'
    result = parse_gelf(sample)
    assert result[0]["severity"] == "info"


def test_parse_wazuh() -> None:
    sample = '{"rule": {"id": "123", "level": 10}, "agent": {"name": "sensor"}, "timestamp": "2024-01-01T00:00:00Z"}'
    result = parse_wazuh_alert(sample)
    assert result[0]["rule_id"] == "123"

