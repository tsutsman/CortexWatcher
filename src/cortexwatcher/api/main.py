"""FastAPI застосунок."""
from __future__ import annotations

from fastapi import FastAPI

from cortexwatcher.api.routers import health, ingest, metrics, query
from cortexwatcher.config import get_settings
from cortexwatcher.logging import configure_logging
from cortexwatcher.storage import get_storage

configure_logging()
app = FastAPI(title="CortexWatcher API", version="0.1.0")

app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(ingest.router)
app.include_router(query.router)


@app.on_event("startup")
async def startup_event() -> None:
    settings = get_settings()
    app.state.settings = settings
    app.state.storage = get_storage()


__all__ = ["app"]
