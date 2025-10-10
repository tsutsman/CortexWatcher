"""Точка входу телеграм-бота."""
from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from cortexwatcher.bot.commands import setup_commands
from cortexwatcher.bot.handlers import router
from cortexwatcher.config import get_settings
from cortexwatcher.logging import configure_logging


async def main() -> None:
    """Запускає бота."""

    configure_logging()
    settings = get_settings()
    bot = Bot(token=settings.tg_bot_token, parse_mode=ParseMode.MARKDOWN)
    dp = Dispatcher()
    dp.include_router(router)
    await setup_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
