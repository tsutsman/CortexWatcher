"""Автовизначення формату логів."""
from __future__ import annotations

import json
import re
from typing import Iterable

SYSLOG_HINT = re.compile(r"<\d+>[A-Z][a-z]{2} +\d{1,2} \d{2}:\d{2}:\d{2}")
GELF_HINT_KEYS = {"short_message", "full_message", "_id"}
WAZUH_HINT_KEYS = {"rule", "agent", "decoder"}


def detect_format(sample: str | Iterable[str]) -> str:
    """Повертає рядок формату: syslog/json_lines/gelf/wazuh/unknown."""

    if isinstance(sample, str):
        text = sample.strip()
        first_line = text.splitlines()[0] if text else ""
    else:
        lines = list(sample)
        first_line = next((line.strip() for line in lines if line.strip()), "")
        text = "\n".join(lines)

    if not first_line:
        return "unknown"

    if first_line.startswith("{") or first_line.endswith("}"):
        try:
            parsed = json.loads(first_line)
            if isinstance(parsed, dict):
                if any(key in parsed for key in WAZUH_HINT_KEYS):
                    return "wazuh"
                if any(key in parsed for key in GELF_HINT_KEYS):
                    return "gelf"
            return "json_lines"
        except json.JSONDecodeError:
            pass

    if SYSLOG_HINT.search(first_line):
        return "syslog"

    if first_line.count(" ") >= 2 and first_line.split(" ")[1].isdigit():
        return "syslog"

    if text.count("\n") > 0 and all(line.strip().startswith("{") for line in text.splitlines() if line.strip()):
        return "json_lines"

    return "unknown"


__all__ = ["detect_format"]
