"""Обробники повідомлень бота."""
from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Document, Message

from cortexwatcher.bot.security import RateLimiter, is_chat_allowed
from cortexwatcher.bot.validation import AttachmentValidationError, validate_document
from cortexwatcher.logging import logger
from cortexwatcher.parsers import detect_format, parse_gelf, parse_json_lines, parse_syslog, parse_wazuh_alert
from cortexwatcher.workers.tasks import enqueue_ingest

router = Router()
limiter = RateLimiter()


@router.message(Command("start"))
async def start_command(message: Message) -> None:
    """Вітальне повідомлення."""

    if not _authorize(message):
        return
    await message.answer(
        "Привіт! Я CortexWatcher. Надішліть лог або файл, і я додам його до аналітики.",
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    """Опис можливостей."""

    if not _authorize(message):
        return
    await message.answer(
        "Надішліть текст логів чи файл (.log/.json/.ndjson/.gz/.zip). Команда /status покаже метрики.",
    )


@router.message(Command("status"))
async def status_command(message: Message) -> None:
    """Повертає просту статистику (тимчасово)."""

    if not _authorize(message):
        return
    metrics = enqueue_ingest("status", payload={"chat_id": message.chat.id}, immediate=True)
    await message.answer(f"Подій за хвилину: {metrics.get('events_per_min', 0)}\nАлертів: {metrics.get('alerts', 0)}")


@router.message()
async def handle_message(message: Message) -> None:
    """Основна логіка обробки повідомлень."""

    if not _authorize(message):
        return
    if message.document:
        await _handle_document(message, message.document)
        return
    if message.text:
        await _handle_text(message, message.text)


async def _handle_document(message: Message, document: Document) -> None:
    """Скачує документ та передає в чергу."""

    if document.file_size and document.file_size > 20 * 1024 * 1024:
        await message.reply("Файл завеликий. Максимум 20 МБ.")
        return
    file = await message.bot.download(document)
    content = await asyncio.to_thread(file.read)
    try:
        await validate_document(document, content)
    except AttachmentValidationError as error:
        logger.warning(
            "Документ не пройшов перевірку",
            chat_id=message.chat.id,
            message_id=message.message_id,
            reason=error.user_message,
        )
        await message.reply(error.user_message)
        return
    summary = await _summarize(content.decode(errors="ignore"))
    await message.reply(summary, parse_mode=ParseMode.MARKDOWN)
    enqueue_ingest(
        source="telegram",
        payload={
            "chat_id": message.chat.id,
            "message_id": message.message_id,
            "filename": document.file_name,
            "content": content.decode(errors="ignore"),
        },
    )


async def _handle_text(message: Message, text: str) -> None:
    summary = await _summarize(text)
    await message.reply(summary, parse_mode=ParseMode.MARKDOWN)
    enqueue_ingest(
        source="telegram",
        payload={
            "chat_id": message.chat.id,
            "message_id": message.message_id,
            "content": text,
        },
    )


async def _summarize(content: str) -> str:
    """Повертає коротку характеристику логів."""

    return await asyncio.to_thread(_summarize_sync, content)


def _summarize_sync(content: str) -> str:
    fmt = detect_format(content)
    parsed: list[dict[str, Any]]
    if fmt == "syslog":
        parsed = parse_syslog(content)
    elif fmt == "json_lines":
        parsed = parse_json_lines(content)
    elif fmt == "gelf":
        parsed = parse_gelf(content)
    elif fmt == "wazuh":
        parsed = parse_wazuh_alert(content)
    else:
        parsed = []
    apps = Counter(item.get("app") for item in parsed if item.get("app"))
    severities = Counter(item.get("severity") for item in parsed if item.get("severity"))
    top_apps = ", ".join(f"{app}: {count}" for app, count in apps.most_common(3)) or "немає"
    top_sev = ", ".join(f"{sev}: {count}" for sev, count in severities.most_common(3)) or "немає"
    return (
        f"📄 Рядків: {len(content.splitlines())}\n"
        f"Формат: {fmt}\n"
        f"Нормалізованих подій: {len(parsed)}\n"
        f"Топ застосунків: {top_apps}\n"
        f"Топ рівнів: {top_sev}"
    )


def _authorize(message: Message) -> bool:
    chat_id = message.chat.id
    if not is_chat_allowed(chat_id):
        logger.warning("Відхилено повідомлення з недозволеного чату", chat_id=chat_id)
        return False
    if not limiter.allowed(chat_id):
        asyncio.create_task(message.reply("Перевищено ліміт запитів. Спробуйте пізніше."))
        return False
    return True


__all__ = ["router"]
