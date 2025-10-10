"""Конфігурація сервісу через pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Загальні налаштування для всіх компонентів."""

    tg_bot_token: str = Field(..., alias="TG_BOT_TOKEN")
    allowed_chat_ids: List[int] = Field(default_factory=list, alias="ALLOWED_CHAT_IDS")
    database_url: str = Field(..., alias="DATABASE_URL")
    redis_url: str = Field(..., alias="REDIS_URL")
    clickhouse_url: str | None = Field(None, alias="CLICKHOUSE_URL")
    clickhouse_enabled: bool = Field(False, alias="CLICKHOUSE")
    ingest_max_file_mb: int = Field(50, alias="INGEST_MAX_FILE_MB")
    alert_min_level: int = Field(5, alias="ALERT_MIN_LEVEL")
    anomaly_window_min: int = Field(5, alias="ANOMALY_WINDOW_MIN")
    api_auth_token: str = Field(..., alias="API_AUTH_TOKEN")
    rules_path: str = Field("src/cortexwatcher/rules/sample_rules.yaml", alias="RULES_PATH")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    @field_validator("allowed_chat_ids", mode="before")
    @classmethod
    def _parse_chat_ids(cls, value: List[int] | str | None) -> List[int]:
        return cls._parse_allowed_chat_ids(value)

    @model_validator(mode="after")
    def _normalize(self) -> "Settings":
        self.allowed_chat_ids = self._parse_allowed_chat_ids(self.allowed_chat_ids)
        return self

    @staticmethod
    def _parse_allowed_chat_ids(raw: List[int] | str | None) -> List[int]:
        """Перетворення списку chat_id з рядка."""

        if raw is None:
            return []
        if isinstance(raw, list):
            return [int(item) for item in raw]
        parts = [part.strip() for part in str(raw).split(",") if part.strip()]
        result: List[int] = []
        for part in parts:
            try:
                result.append(int(part))
            except ValueError:
                continue
        return result


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Повертає кешований екземпляр налаштувань."""

    return Settings()


__all__ = ["Settings", "get_settings"]
