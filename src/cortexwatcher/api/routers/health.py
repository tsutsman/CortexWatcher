"""Health-check ендпоінти."""
from __future__ import annotations

import inspect
import time
from collections.abc import Iterable
from typing import Any

import httpx
from fastapi import APIRouter, Request
from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from cortexwatcher.config import Settings, get_settings
from cortexwatcher.db.session import async_session_maker

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/status")
async def status(request: Request) -> dict[str, Any]:
    """Повертає зведення про стан основних компонентів."""

    settings = get_settings()
    storage = getattr(request.app.state, "storage", None)

    database_state = await _check_database()
    redis_state, queue_state, metrics_state = await _check_redis(settings)
    clickhouse_state = await _check_clickhouse(settings)
    storage_state = _build_storage_state(storage, settings)

    components = {
        "database": database_state,
        "redis": redis_state,
        "queue": queue_state,
        "metrics": metrics_state,
        "clickhouse": clickhouse_state,
        "storage": storage_state,
    }
    overall = _overall_status(components.values())
    return {"status": overall, "components": components}


async def _check_database() -> dict[str, Any]:
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok"}
    except SQLAlchemyError as exc:  # pragma: no cover - захист від непередбачених помилок
        return {"status": "error", "detail": str(exc)}


async def _check_redis(settings: Settings) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    client = AsyncRedis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    redis_state: dict[str, Any]
    queue_state: dict[str, Any]
    metrics_state: dict[str, Any]
    try:
        await client.ping()
        redis_state = {"status": "ok"}
    except RedisError as exc:
        detail = str(exc)
        redis_state = {"status": "error", "detail": detail}
        queue_state = {"status": "error", "detail": "Redis недоступний"}
        metrics_state = {"status": "error", "values": {}}
        await _close_redis(client)
        return redis_state, queue_state, metrics_state

    try:
        backlog = await client.llen("rq:queue:ingest")
        queue_state = {"status": "ok", "backlog": backlog}
    except RedisError as exc:  # pragma: no cover - залежить від середовища
        queue_state = {"status": "degraded", "detail": str(exc)}

    try:
        metrics_raw = await client.hgetall("cortexwatcher:metrics")
        metrics_values = _decode_metrics(metrics_raw)
        metrics_values["events_rate_1m"] = await _calculate_rate(
            client, "cortexwatcher:metrics:events_window", 60
        )
        metrics_values["alerts_rate_1m"] = await _calculate_rate(
            client, "cortexwatcher:metrics:alerts_window", 60
        )
        metrics_state = {
            "status": "ok",
            "values": metrics_values,
        }
    except RedisError as exc:  # pragma: no cover - залежить від середовища
        metrics_state = {"status": "degraded", "detail": str(exc), "values": {}}

    await _close_redis(client)
    return redis_state, queue_state, metrics_state


async def _check_clickhouse(settings: Settings) -> dict[str, Any]:
    if not settings.clickhouse_enabled or not settings.clickhouse_url:
        return {"status": "disabled"}

    url = settings.clickhouse_url.rstrip("/") + "/ping"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(url)
    except httpx.HTTPError as exc:
        return {"status": "error", "url": url, "detail": str(exc)}

    if response.status_code == httpx.codes.OK:
        return {"status": "ok", "url": url}
    return {"status": "degraded", "url": url, "detail": f"HTTP {response.status_code}"}


def _build_storage_state(storage: Any, settings: Settings) -> dict[str, Any]:
    if storage is None:
        return {"status": "degraded", "detail": "Сховище не ініціалізовано"}

    backend = type(storage).__name__
    state: dict[str, Any] = {"status": "ok", "backend": backend}
    if backend.lower().startswith("clickhouse"):
        state["url"] = settings.clickhouse_url
        if not settings.clickhouse_enabled:
            state["status"] = "degraded"
            state["detail"] = "ClickHouse вимкнено в конфігурації"
    return state


def _overall_status(components: Iterable[dict[str, Any]]) -> str:
    status = "ok"
    for component in components:
        current = component.get("status", "unknown")
        if current == "disabled":
            continue
        if current == "error":
            return "error"
        if current not in {"ok", "disabled"}:
            status = "degraded"
    return status


async def _close_redis(client: AsyncRedis) -> None:
    try:
        result = client.close()
        if inspect.isawaitable(result):
            await result
    finally:
        wait_closed = getattr(client, "wait_closed", None)
        if callable(wait_closed):  # pragma: no cover - залежить від версії redis
            maybe_coro = wait_closed()
            if inspect.isawaitable(maybe_coro):
                await maybe_coro


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _decode_metrics(metrics_raw: dict[str, Any]) -> dict[str, Any]:
    numeric_keys = {
        "events_total",
        "alerts_total",
        "avg_ingest_latency_ms",
        "max_ingest_latency_ms",
        "last_batch_size",
    }
    decoded: dict[str, Any] = {}
    for key, value in metrics_raw.items():
        if key in numeric_keys:
            decoded[key] = _safe_int(value)
        else:
            decoded[key] = value
    for key in numeric_keys:
        decoded.setdefault(key, 0)
    return decoded


async def _calculate_rate(client: AsyncRedis, key: str, window_seconds: int) -> int:
    now = time.time()
    cutoff = now - window_seconds
    try:
        await client.zremrangebyscore(key, 0, cutoff)
        members = await client.zrange(key, 0, -1)
    except RedisError:  # pragma: no cover - залежить від середовища
        return 0

    total = 0
    for member in members:
        try:
            _, count, _ = member.split(":")
            total += int(count)
        except (ValueError, TypeError):  # pragma: no cover - захист від пошкоджених даних
            continue
    return total


__all__ = ["router"]
