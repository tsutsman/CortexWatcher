"""FastAPI застосунок."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from cortexwatcher.api.routers import health, ingest, metrics, query
from cortexwatcher.config import get_settings
from cortexwatcher.logging import configure_logging
from cortexwatcher.storage import get_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ініціалізує стан застосунку під час життєвого циклу."""

    settings = get_settings()
    app.state.settings = settings
    app.state.storage = get_storage()
    try:
        yield
    finally:
        storage = getattr(app.state, "storage", None)
        close = getattr(storage, "close", None)
        if callable(close):
            close()


configure_logging()
app = FastAPI(title="CortexWatcher API", version="0.1.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(ingest.router)
app.include_router(query.router)


__all__ = ["app"]
