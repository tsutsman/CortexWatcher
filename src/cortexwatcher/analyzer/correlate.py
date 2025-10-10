"""Побудова ключа кореляції."""
from __future__ import annotations

from typing import Dict


def build_correlation_key(record: Dict[str, object]) -> str:
    """Формує ключ із srcip, dstip та app."""

    src = str(record.get("srcip") or record.get("source_ip") or "*")
    dst = str(record.get("dstip") or record.get("destination_ip") or "*")
    app = str(record.get("app") or record.get("program") or "*")
    return f"{src}|{dst}|{app}"


__all__ = ["build_correlation_key"]
