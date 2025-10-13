"""Парсери логів."""

from .detect import detect_format
from .gelf import parse_gelf
from .json_lines import parse_json_lines
from .suricata import parse_suricata
from .syslog import parse_syslog
from .wazuh import parse_wazuh_alert

__all__ = [
    "detect_format",
    "parse_gelf",
    "parse_json_lines",
    "parse_suricata",
    "parse_syslog",
    "parse_wazuh_alert",
]
