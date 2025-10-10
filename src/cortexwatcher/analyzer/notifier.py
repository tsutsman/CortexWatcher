"""Надсилання алертів у Telegram."""
from __future__ import annotations

from aiogram import Bot

from cortexwatcher.config import get_settings
from cortexwatcher.db.models import Alert
from cortexwatcher.logging import logger
from cortexwatcher.storage.base import LogStorage


class AlertNotifier:
    """Відправляє алерти у whitelisted чати."""

    def __init__(self, storage: LogStorage, bot: Bot | None = None) -> None:
        self.storage = storage
        settings = get_settings()
        self.chat_ids = settings.allowed_chat_ids
        self.bot = bot

    async def persist_and_notify(self, alert: Alert, thread_id: int | None = None) -> Alert:
        """Зберігає алерт і за потреби відправляє у Telegram."""

        saved = await self.storage.store_alert(alert)
        if self.bot and self.chat_ids:
            message = self._format_message(saved)
            for chat_id in self.chat_ids:
                try:
                    await self.bot.send_message(chat_id=chat_id, text=message, message_thread_id=thread_id)
                except Exception as exc:  # noqa: BLE001
                    logger.error("Не вдалося відправити алерт", error=str(exc), chat_id=chat_id)
        return saved

    def _format_message(self, alert: Alert) -> str:
        tags = ", ".join(alert.tags or [])
        return (
            f"⚠️ *{alert.title}*\n"
            f"Рівень: {alert.level}\n"
            f"Опис: {alert.description}\n"
            f"Теги: {tags if tags else 'немає'}"
        )


__all__ = ["AlertNotifier"]
