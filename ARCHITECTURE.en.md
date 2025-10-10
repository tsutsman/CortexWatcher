# CortexWatcher Architecture

## Overview
CortexWatcher consists of four primary services:
- **bot** — aiogram-based Telegram bot that receives messages and pushes them to the queue.
- **api** — FastAPI application for HTTP integrations, querying logs, alerts, and metrics.
- **ingestor worker** — handles the RQ queue: parsing, normalization, and persistence.
- **analyzer worker** — evaluates rules and anomalies, producing alerts.

```
Telegram groups → bot → Redis (RQ) → ingestor → storage (Postgres/ClickHouse)
                                               ↘
                                                analyzer → alerts → Telegram / API
```

## Data and storage
- **PostgreSQL** — primary database for the `logs_raw`, `logs_normalized`, `alerts`, and `anomalies` tables.
- **ClickHouse** (optional) — high-throughput storage for `logs_*`; controlled via the `CLICKHOUSE` variable.
- **Redis** — broker and cache for short-lived metrics (`/status`).

### SQLAlchemy ORM
Files:
- `src/cortexwatcher/db/models.py` — model definitions.
- `src/cortexwatcher/db/session.py` — asynchronous engine and session creation.
- `src/cortexwatcher/storage/postgres.py` — storage interface implementation.

## Parsers
The `src/cortexwatcher/parsers/` package contains modules for multiple log formats. The `detect.py` module automatically identifies the format.

## Analytics
- `analyzer/rules_engine.py` — loads YAML rules, applies regex/glob filters.
- `analyzer/anomalies.py` — calculates rolling metrics (z-score, median).
- `analyzer/correlate.py` — builds the `correlation_key`.
- `analyzer/notifier.py` — sends alerts to Telegram and stores records in the database.

## API
FastAPI application with routers:
- `/ingest/{source}` — accepts log batches.
- `/logs`, `/alerts`, `/anomalies` — filtering endpoints.
- `/healthz` — health check endpoint.
- `/metrics` — Prometheus metrics.

## Queues
RQ orchestrates asynchronous tasks:
- `workers/tasks.py` contains parsing and analysis jobs.
- `workers/ingestor.py` launches the RQ worker.

## Migrations
Alembic configuration lives in `src/cortexwatcher/db/migrations`. The base script initializes the tables.

## Metrics
- The API exposes `/metrics` via `prometheus_client`.
- The analyzer updates event counters in Redis.
