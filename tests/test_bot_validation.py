"""Тести перевірок вкладень бота."""
from __future__ import annotations

import asyncio
import gzip
from io import BytesIO
from types import SimpleNamespace
from zipfile import ZipFile

import pytest

from cortexwatcher.bot.validation import ALLOWED_EXTENSIONS, AttachmentValidationError, validate_document


def _fake_document(**kwargs):
    defaults = {"file_name": "sample.log", "mime_type": "text/plain", "file_size": 1024}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_validate_document_allows_known_text():
    document = _fake_document()
    asyncio.run(validate_document(document, b"line1\nline2"))


def test_validate_document_rejects_unknown_extension():
    document = _fake_document(file_name="payload.exe", mime_type="application/octet-stream")
    with pytest.raises(AttachmentValidationError) as error:
        asyncio.run(validate_document(document, b"binary"))
    assert "Непідтримуваний тип файлу" in error.value.user_message


def test_validate_document_rejects_zip_with_traversal(monkeypatch):
    document = _fake_document(file_name="archive.zip", mime_type="application/zip")
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("../etc/passwd", "root")
    buffer.seek(0)
    with pytest.raises(AttachmentValidationError) as error:
        asyncio.run(validate_document(document, buffer.read()))
    assert "небезпечні шляхи" in error.value.user_message


def test_validate_document_rejects_large_gzip(monkeypatch):
    document = _fake_document(file_name="payload.gz", mime_type="application/gzip")
    monkeypatch.setattr("cortexwatcher.bot.validation.MAX_UNCOMPRESSED_BYTES", 100)
    payload = b"A" * 128
    buffer = BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb") as archive:
        archive.write(payload)
    with pytest.raises(AttachmentValidationError) as error:
        asyncio.run(validate_document(document, buffer.getvalue()))
    assert "перевищує допустимі" in error.value.user_message


def test_allowed_extensions_contains_expected():
    assert {".log", ".json", ".ndjson", ".gz", ".zip"}.issubset(ALLOWED_EXTENSIONS)

