"""Інструменти для перевірки вкладень від Telegram."""
from __future__ import annotations

import asyncio
import gzip
import mimetypes
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable
from zipfile import BadZipFile, ZipFile

from aiogram.types import Document

ALLOWED_MIME_TYPES: set[str] = {
    "text/plain",
    "application/json",
    "application/x-ndjson",
    "application/gzip",
    "application/x-gzip",
    "application/zip",
}
ALLOWED_EXTENSIONS: set[str] = {".log", ".txt", ".json", ".ndjson", ".gz", ".zip"}
MAX_ARCHIVE_MEMBERS = 200
MAX_UNCOMPRESSED_BYTES = 32 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200


@dataclass(slots=True)
class AttachmentValidationError(Exception):
    """Помилка перевірки вкладення."""

    user_message: str

    def __post_init__(self) -> None:
        self.args = (self.user_message,)


async def validate_document(document: Document, content: bytes) -> None:
    """Асинхронно перевіряє тип файлу та архіви."""

    await asyncio.to_thread(_validate_document_sync, document, content)


def _validate_document_sync(document: Document, content: bytes) -> None:
    mime = (document.mime_type or "").lower()
    extension = _normalize_extension(document.file_name)
    guessed, _ = mimetypes.guess_type(document.file_name or "")
    guessed_mime = (guessed or "").lower()

    if extension and extension not in ALLOWED_EXTENSIONS:
        raise AttachmentValidationError("Непідтримуваний тип файлу. Дозволені: log, txt, json, ndjson, gz, zip.")
    if mime and mime not in ALLOWED_MIME_TYPES:
        raise AttachmentValidationError("Небезпечний MIME-тип. Відправте текстовий або архівований лог.")
    if guessed_mime and guessed_mime not in ALLOWED_MIME_TYPES:
        raise AttachmentValidationError("Розширення не відповідає очікуваному формату логів.")

    if extension in {".zip"} or mime == "application/zip" or guessed_mime == "application/zip":
        _validate_zip_archive(content)
    elif extension in {".gz"} or mime in {"application/gzip", "application/x-gzip"}:
        _validate_gzip_archive(content)


def _normalize_extension(filename: str | None) -> str:
    if not filename:
        return ""
    return Path(filename).suffix.lower()


def _validate_zip_archive(content: bytes) -> None:
    try:
        with ZipFile(BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise AttachmentValidationError("Архів містить занадто багато файлів. Стисніть дані краще.")
            _reject_unsafe_paths(info.filename for info in members)
            total_uncompressed = 0
            for info in members:
                if info.is_dir():
                    continue
                total_uncompressed += info.file_size
                compression_ratio = info.file_size / max(info.compress_size, 1)
                if compression_ratio > MAX_COMPRESSION_RATIO:
                    raise AttachmentValidationError("Запідозрено zip-bomb через надмірне стиснення.")
            if total_uncompressed > MAX_UNCOMPRESSED_BYTES:
                raise AttachmentValidationError("Розмір розпакованих файлів перевищує безпечний поріг (32 МБ).")
    except BadZipFile as error:  # pragma: no cover - очікуваний шлях для пошкоджених архівів
        raise AttachmentValidationError("Архів пошкоджено або має невідомий формат.") from error


def _reject_unsafe_paths(paths: Iterable[str]) -> None:
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_absolute() or ".." in path.parts:
            raise AttachmentValidationError("Архів містить небезпечні шляхи. Видаліть .. або абсолютні шляхи.")


def _validate_gzip_archive(content: bytes) -> None:
    try:
        with gzip.GzipFile(fileobj=BytesIO(content)) as archive:
            read_bytes = archive.read(MAX_UNCOMPRESSED_BYTES + 1)
    except OSError as error:  # pragma: no cover - помилки стиснення
        raise AttachmentValidationError("Неможливо прочитати gzip-файл. Перевірте архів.") from error
    if len(read_bytes) > MAX_UNCOMPRESSED_BYTES:
        raise AttachmentValidationError("Розмір розпакованого gzip перевищує допустимі 32 МБ.")


__all__ = ["AttachmentValidationError", "validate_document"]
