"""Налаштування структурованого логування через loguru."""
from __future__ import annotations

import json
import sys
from typing import Any, Dict

from loguru import logger


class JsonFormatter:
    """Простий JSON-форматер для loguru."""

    def __call__(self, message: "loguru.Message") -> str:  # type: ignore[name-defined]
        record = message.record
        payload: Dict[str, Any] = {
            "time": record["time"].strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record["level"].name,
            "message": record["message"],
            "module": record["module"],
            "function": record["function"],
            "line": record["line"],
        }
        if record.get("extra"):
            payload.update(record["extra"])
        return json.dumps(payload, ensure_ascii=False) + "\n"


def configure_logging() -> None:
    """Ініціалізує логер із JSON-форматом."""

    logger.remove()
    logger.add(sys.stdout, level="INFO", serialize=False, format=JsonFormatter())


__all__ = ["configure_logging", "logger"]
