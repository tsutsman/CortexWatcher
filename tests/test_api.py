"""Інтеграційні тести FastAPI."""
from __future__ import annotations

import os

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


def test_status_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyRedis:
        url: str

        @classmethod
        def from_url(cls, url: str, **_: object) -> "DummyRedis":
            instance = cls()
            instance.url = url
            return instance

        async def ping(self) -> bool:
            return True

        async def llen(self, key: str) -> int:
            assert key == "rq:queue:ingest"
            return 3

        async def hgetall(self, key: str) -> dict[str, str]:
            assert key == "cortexwatcher:metrics"
            return {"events": "5", "alerts": "2"}

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
    assert body["components"]["metrics"]["values"]["events"] == 5
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

