"""Виявлення аномалій на основі ковзного вікна."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Deque, Dict, List, Tuple


@dataclass
class WindowStat:
    timestamp: datetime
    value: int


class AnomalyDetector:
    """Обчислює z-score для сигналів (host+app+severity)."""

    def __init__(self, window_minutes: int, threshold: float = 3.0) -> None:
        self.window_minutes = window_minutes
        self.threshold = threshold
        self.history: Dict[str, Deque[WindowStat]] = defaultdict(deque)

    def _key(self, host: str | None, app: str | None, severity: str | None) -> str:
        return "|".join(filter(None, [host or "*", app or "*", severity or "*"]))

    def update(self, host: str | None, app: str | None, severity: str | None, timestamp: datetime) -> Tuple[bool, float]:
        key = self._key(host, app, severity)
        bucket_ts = timestamp.replace(second=0, microsecond=0)
        series = self.history[key]
        if series and series[-1].timestamp == bucket_ts:
            series[-1].value += 1
        else:
            series.append(WindowStat(timestamp=bucket_ts, value=1))
        self._trim(series, bucket_ts)
        values = [stat.value for stat in series]
        if len(values) < 3:
            return False, 0.0
        mean = sum(values) / len(values)
        variance = sum((val - mean) ** 2 for val in values) / len(values)
        std = variance ** 0.5
        if std == 0:
            return False, 0.0
        current = series[-1].value
        z_score = (current - mean) / std
        return z_score >= self.threshold, z_score

    def _trim(self, series: Deque[WindowStat], current_ts: datetime) -> None:
        limit = current_ts - timedelta(minutes=self.window_minutes)
        while series and series[0].timestamp < limit:
            series.popleft()

    def snapshot(self) -> Dict[str, List[WindowStat]]:
        """Повертає копію статистик."""

        return {key: list(stats) for key, stats in self.history.items()}


__all__ = ["AnomalyDetector", "WindowStat"]
