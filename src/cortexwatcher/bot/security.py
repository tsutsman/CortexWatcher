"""Перевірки безпеки для бота."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict

from cortexwatcher.config import get_settings


class RateLimiter:
    """Простий ліміт на кількість викликів за хвилину."""

    def __init__(self, limit: int = 30, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window = window_seconds
        self.calls: Dict[int, Deque[float]] = defaultdict(deque)

    def allowed(self, chat_id: int) -> bool:
        now = time.time()
        q = self.calls[chat_id]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


def is_chat_allowed(chat_id: int) -> bool:
    """Перевіряє whitelist чатів."""

    settings = get_settings()
    return chat_id in settings.allowed_chat_ids


__all__ = ["RateLimiter", "is_chat_allowed"]
