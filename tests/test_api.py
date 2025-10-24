"""Інтеграційні тести FastAPI."""
from __future__ import annotations

import os
import time

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("TG_BOT_TOKEN", "test")
os.environ.setdefault("ALLOWED_CHAT_IDS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("API_AUTH_TOKEN", "token")
os.environ.setdefault("CLICKHOUSE", "1")
os.environ.setdefault("CLICKHOUSE_URL", "http://localhost")
os.environ.setdefault("RULES_PATH", "src/cortexwatcher/rules/sample_rules.yaml")

from redis.exceptions import RedisError

from cortexwatcher.api.main import app
from cortexwatcher.api.routers import health
from cortexwatcher.storage.clickhouse import ClickHouseStorage


@pytest.fixture(autouse=True)
def setup_storage() -> None:
    app.state.storage = ClickHouseStorage("http://localhost")


def test_ingest_and_query() -> None:
    client = TestClient(app)
    payload = {
        "content": "{\"host\": \"web\", \"app\": \"nginx\", \"message\": \"error\"}"
    }
    response = client.post("/ingest/test", json=payload, headers={"X-API-Token": "token"})
    assert response.status_code == 200
    data = response.json()
    assert data["format"] == "json_lines"

    logs = client.get("/logs")
    assert logs.status_code == 200
    body = logs.json()
    assert isinstance(body, list)
    assert body

    naive_filter = client.get("/logs", params={"start": "1970-01-01T00:00:00"})
    assert naive_filter.status_code == 200
    assert naive_filter.json()


def test_status_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyRedis:
        url: str

        @classmethod
        def from_url(cls, url: str, **_: object) -> "DummyRedis":
            instance = cls()
            instance.url = url
            instance._metrics = {
                "events_total": "5",
                "alerts_total": "2",
                "avg_ingest_latency_ms": "12",
                "max_ingest_latency_ms": "42",
                "last_batch_size": "2",
                "last_event_ts": "2024-01-01T00:00:00+00:00",
                "last_alert_ts": "2024-01-01T00:01:00+00:00",
            }
            instance._zsets: dict[str, list[tuple[str, float]]] = {
                "cortexwatcher:metrics:events_window": [("1000:5:deadbeef", time.time())],
                "cortexwatcher:metrics:alerts_window": [("2000:2:feedface", time.time())],
            }
            return instance

        async def ping(self) -> bool:
            return True

        async def llen(self, key: str) -> int:
            assert key == "rq:queue:ingest"
            return 3

        async def hgetall(self, key: str) -> dict[str, str]:
            assert key == "cortexwatcher:metrics"
            return self._metrics

        async def zremrangebyscore(self, key: str, _min: float, max_score: float) -> int:
            items = self._zsets.get(key, [])
            retained = [(member, score) for member, score in items if score > max_score]
            removed = len(items) - len(retained)
            self._zsets[key] = retained
            return removed

        async def zrange(self, key: str, start: int, end: int) -> list[str]:
            assert start == 0 and end == -1
            return [member for member, _ in self._zsets.get(key, [])]

        async def expire(self, key: str, ttl: int) -> bool:
            assert key in self._zsets
            assert ttl > 0
            return True

        def close(self) -> None:
            pass

    class DummyResponse:
        status_code = 200
        text = "Ok."

    class DummyAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:  # noqa: D401 - простий стаб
            pass

        async def __aenter__(self) -> "DummyAsyncClient":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        async def get(self, url: str) -> DummyResponse:
            assert url.endswith("/ping")
            return DummyResponse()

    monkeypatch.setattr(health, "AsyncRedis", DummyRedis)
    monkeypatch.setattr(health.httpx, "AsyncClient", DummyAsyncClient)

    client = TestClient(app)
    response = client.get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["components"]["redis"]["status"] == "ok"
    assert body["components"]["queue"]["backlog"] == 3
    metrics = body["components"]["metrics"]["values"]
    assert metrics["events_total"] == 5
    assert metrics["alerts_total"] == 2
    assert metrics["events_rate_1m"] == 5
    assert metrics["alerts_rate_1m"] == 2
    assert body["components"]["clickhouse"]["status"] == "ok"


def test_status_endpoint_handles_redis_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingRedis:
        @classmethod
        def from_url(cls, *_: object, **__: object) -> "FailingRedis":
            return cls()

        async def ping(self) -> bool:
            raise RedisError("connection error")

        def close(self) -> None:
            pass

    class DummyResponse:
        status_code = 200
        text = "Ok."

    class DummyAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "DummyAsyncClient":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        async def get(self, url: str) -> DummyResponse:
            assert url.endswith("/ping")
            return DummyResponse()

    monkeypatch.setattr(health, "AsyncRedis", FailingRedis)
    monkeypatch.setattr(health.httpx, "AsyncClient", DummyAsyncClient)

    client = TestClient(app)
    response = client.get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "error"
    assert body["components"]["redis"]["status"] == "error"
    assert body["components"]["queue"]["status"] == "error"
    assert body["components"]["metrics"]["status"] == "error"

