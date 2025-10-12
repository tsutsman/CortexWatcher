"""Задачі RQ та аналітика."""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from statistics import mean
from time import time
from typing import Any, Iterable
from uuid import uuid4

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue

from cortexwatcher.analyzer import AlertNotifier, AnomalyDetector, RuleEngine, build_correlation_key
from cortexwatcher.config import get_settings
from cortexwatcher.db.models import Alert, Anomaly, LogNormalized, LogRaw
from cortexwatcher.parsers import detect_format, parse_gelf, parse_json_lines, parse_syslog, parse_wazuh_alert
from cortexwatcher.storage import get_storage
from cortexwatcher.storage.base import LogStorage

settings = get_settings()
redis_conn = Redis.from_url(settings.redis_url)
queue = Queue("ingest", connection=redis_conn)


def enqueue_ingest(source: str, payload: dict[str, Any], immediate: bool = False) -> Any:
    """Додає задачу у чергу або виконує негайно."""

    if immediate:
        if source == "status":
            return _status_snapshot()
        return asyncio.run(_process_ingest(source, payload))
    job = queue.enqueue(process_ingest_job, source, payload)
    return {"job_id": job.id}


def process_ingest_job(source: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Виконується воркером RQ."""

    return asyncio.run(_process_ingest(source, payload))


async def _process_ingest(source: str, payload: dict[str, Any]) -> dict[str, Any]:
    storage = get_storage()
    content = payload.get("content") or ""
    if isinstance(payload.get("items"), list):
        content += "\n".join(json.dumps(item, ensure_ascii=False) for item in payload["items"])
    if not content.strip():
        return {"stored": 0, "format": "unknown"}

    fmt = detect_format(content)
    parsed = _parse(fmt, content)
    received_at = datetime.utcnow()
    raw = LogRaw(
        source=source,
        received_at=received_at,
        payload_raw=content,
        format=fmt,
        hash=_hash(content),
    )
    normalized = [
        LogNormalized(
            raw_id=0,
            ts=item.get("timestamp") or received_at,
            host=item.get("host"),
            app=item.get("app"),
            severity=item.get("severity"),
            msg=str(item.get("message") or item.get("msg") or ""),
            meta_json=item,
            correlation_key=build_correlation_key(item),
        )
        for item in parsed
    ]
    await storage.store_raw_batch([raw])
    raw_id = getattr(raw, "id", None)
    for item in normalized:
        item.raw_id = raw_id or 0
    await storage.store_normalized_batch(normalized)
    _bump_metrics(len(normalized), _calculate_latencies(normalized, received_at))
    return {"stored": len(normalized), "format": fmt}


def _hash(content: str) -> str:
    import hashlib

    return hashlib.sha256(content.encode()).hexdigest()


def _parse(fmt: str, content: str) -> list[dict[str, Any]]:
    if fmt == "syslog":
        return parse_syslog(content)
    if fmt == "json_lines":
        return parse_json_lines(content)
    if fmt == "gelf":
        return parse_gelf(content)
    if fmt == "wazuh":
        return parse_wazuh_alert(content)
    return []


def _calculate_latencies(logs: Iterable[LogNormalized], received_at: datetime) -> list[float]:
    latencies: list[float] = []
    for log in logs:
        ts = getattr(log, "ts", None)
        if not isinstance(ts, datetime):
            continue
        normalized_ts = ts
        if ts.tzinfo is not None:
            normalized_ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
        latency_ms = (received_at - normalized_ts).total_seconds() * 1000
        if latency_ms >= 0:
            latencies.append(latency_ms)
    return latencies


def _bump_metrics(count: int, latencies: Iterable[float]) -> None:
    if count <= 0:
        return

    latencies_list = list(latencies)
    avg_latency = int(mean(latencies_list)) if latencies_list else 0
    max_latency = int(max(latencies_list)) if latencies_list else 0
    now_iso = datetime.now(timezone.utc).isoformat()
    timestamp = time()
    member_id = f"{int(timestamp * 1000)}:{count}:{uuid4().hex}"
    try:
        pipe = redis_conn.pipeline()
        pipe.hincrby("cortexwatcher:metrics", "events_total", count)
        pipe.hset(
            "cortexwatcher:metrics",
            mapping={
                "last_event_ts": now_iso,
                "last_batch_size": count,
                "avg_ingest_latency_ms": avg_latency,
                "max_ingest_latency_ms": max_latency,
            },
        )
        pipe.zadd("cortexwatcher:metrics:events_window", {member_id: timestamp})
        pipe.zremrangebyscore("cortexwatcher:metrics:events_window", 0, timestamp - 600)
        pipe.expire("cortexwatcher:metrics:events_window", 3600)
        pipe.execute()
    except RedisError:
        pass


def _bump_alert_metrics() -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    timestamp = time()
    member_id = f"{int(timestamp * 1000)}:1:{uuid4().hex}"
    try:
        pipe = redis_conn.pipeline()
        pipe.hincrby("cortexwatcher:metrics", "alerts_total", 1)
        pipe.hset("cortexwatcher:metrics", mapping={"last_alert_ts": now_iso})
        pipe.zadd("cortexwatcher:metrics:alerts_window", {member_id: timestamp})
        pipe.zremrangebyscore("cortexwatcher:metrics:alerts_window", 0, timestamp - 600)
        pipe.expire("cortexwatcher:metrics:alerts_window", 3600)
        pipe.execute()
    except RedisError:
        pass


def _status_snapshot() -> dict[str, Any]:
    try:
        metrics = redis_conn.hgetall("cortexwatcher:metrics")
    except RedisError:
        metrics = {}
    return {
        "events_total": int(metrics.get(b"events_total", 0)) if metrics else 0,
        "alerts_total": int(metrics.get(b"alerts_total", 0)) if metrics else 0,
        "avg_ingest_latency_ms": int(metrics.get(b"avg_ingest_latency_ms", 0)) if metrics else 0,
        "max_ingest_latency_ms": int(metrics.get(b"max_ingest_latency_ms", 0)) if metrics else 0,
    }


async def run_analyzer_loop() -> None:
    storage = get_storage()
    engine = RuleEngine(settings.rules_path)
    notifier = AlertNotifier(storage)
    detector = AnomalyDetector(window_minutes=settings.anomaly_window_min)
    processed: set[int] = set()
    while True:
        logs = await storage.list_logs(limit=200)
        for log in logs:
            if log.id in processed:
                continue
            processed.add(log.id)
            await _evaluate_log(storage, engine, notifier, detector, log)
        await asyncio.sleep(10)


async def _evaluate_log(
    storage: LogStorage,
    engine: RuleEngine,
    notifier: AlertNotifier,
    detector: AnomalyDetector,
    log: LogNormalized,
) -> None:
    record = {
        "msg": log.msg,
        "host": log.host,
        "app": log.app,
        "severity": log.severity,
        "srcip": log.meta_json.get("srcip") if isinstance(log.meta_json, dict) else None,
        "dstip": log.meta_json.get("dstip") if isinstance(log.meta_json, dict) else None,
    }
    matches = engine.match(record)
    for rule in matches:
        if rule.severity < settings.alert_min_level:
            continue
        alert = Alert(
            created_at=datetime.utcnow(),
            rule_id=rule.id,
            level=rule.severity,
            title=rule.title,
            description=rule.description,
            tags=list(rule.tags),
            evidence_json={"log_id": log.id, "msg": log.msg},
        )
        await notifier.persist_and_notify(alert)
        _bump_alert_metrics()
    anomaly, score = detector.update(log.host, log.app, log.severity, log.ts)
    if anomaly:
        anomaly_obj = Anomaly(
            created_at=datetime.utcnow(),
            signal=f"{log.host}|{log.app}|{log.severity}",
            score=score,
            window=detector.window_minutes,
            details_json={"log_id": log.id},
        )
        await storage.store_anomaly(anomaly_obj)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "analyzer":
        asyncio.run(run_analyzer_loop())
    else:
        from rq import Worker

        with queue.connection:
            worker = Worker([queue])
            worker.work()


if __name__ == "__main__":
    main()
