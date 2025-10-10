"""Ендпоінт Prometheus."""
from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

router = APIRouter()

REQUESTS_TOTAL = Counter("cortexwatcher_requests_total", "Кількість HTTP запитів", ["endpoint"])


def track_request(endpoint: str) -> None:
    REQUESTS_TOTAL.labels(endpoint=endpoint).inc()


@router.get("/metrics")
async def metrics() -> Response:
    track_request("metrics")
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


__all__ = ["router", "REQUESTS_TOTAL", "track_request"]
