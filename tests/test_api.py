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

from cortexwatcher.api.main import app
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

