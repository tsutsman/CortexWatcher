"""Опис команд бота."""
from __future__ import annotations

from aiogram import Bot
from aiogram.types import BotCommand


async def setup_commands(bot: Bot) -> None:
    """Реєструє стандартні команди."""

    commands = [
        BotCommand(command="start", description="Розпочати роботу з CortexWatcher"),
        BotCommand(command="help", description="Допомога та список можливостей"),
        BotCommand(command="status", description="Поточні метрики"),
        BotCommand(command="subscribe", description="Керування підписками на алерти"),
        BotCommand(command="groups", description="Керування whitelist груп"),
    ]
    await bot.set_my_commands(commands)


__all__ = ["setup_commands"]
