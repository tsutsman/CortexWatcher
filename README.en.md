# CortexWatcher

CortexWatcher is a Telegram bot and platform for streaming collection, normalization, and analytics of logs from various sources. The solution targets security and SRE teams that need to quickly process events from Telegram groups, Wazuh, Graylog, and syslog while receiving structured alerts and metrics in one place.

## Features
- Receive logs from Telegram (text and files, including .gz/.zip) and HTTP APIs (GELF, Wazuh, JSON/NDJSON).
- Normalize data and store it in PostgreSQL (or ClickHouse when the profile is enabled).
- Detection rules and signature-based alerts defined via YAML files.
- Anomaly detection powered by rolling metrics (z-score, median).
- Integration with Redis + RQ for asynchronous jobs.
- FastAPI web interface with filters for logs, alerts, and service status.
- Prometheus metrics (`/metrics`) for the API and analyzer.
- Structured JSON logging.

## Quick start (docker-compose)
1. Copy `.env.example` to `.env` and fill in the required variables:
   ```bash
   cp .env.example .env
   ```
2. Start the infrastructure:
   ```bash
   docker compose up --build
   ```
3. After startup:
   - FastAPI is available at `http://localhost:8080` (docs at `/docs`).
   - Prometheus metrics: `http://localhost:8080/metrics`.
   - The Telegram bot listens for commands in whitelisted groups.

## Local development
- Python 3.11 (we recommend using `pyenv` or `asdf`).
- Install dependencies and tooling as described in `Makefile setup`.
- Run `make format` before committing.
- Run tests with `make test`.

## Environment variables
Key configuration parameters:
- `TG_BOT_TOKEN` — Telegram bot token.
- `ALLOWED_CHAT_IDS` — comma-separated list of permitted chat IDs.
- `DATABASE_URL` — PostgreSQL connection URL.
- `REDIS_URL` — Redis URL for the RQ queue.
- `CLICKHOUSE_URL` — optional ClickHouse connection.
- `INGEST_MAX_FILE_MB` — maximum size of an input file.
- `ALERT_MIN_LEVEL` — minimum alert severity level.
- `ANOMALY_WINDOW_MIN` — anomaly window size (in minutes).
- `API_AUTH_TOKEN` — token for secured API endpoints.

## Typical workflows
1. **Monitoring Telegram groups:** the bot reads messages from whitelisted groups, automatically extracts files, and pushes them to the normalization queue.
2. **Parsing syslog/JSON/GELF:** the API accepts log batches, stores them in raw and normalized form, and exposes filters at `/logs`.
3. **Wazuh integration:** a dedicated `/ingest/wazuh` endpoint receives JSON alerts, creates records in the `alerts` table, and sends notifications to Telegram.
4. **Alert review:** filter recent notifications and their context via `/alerts`.

## Limitations and security
- Secrets must be supplied only via `.env` or environment variables.
- Telegram chat IDs are whitelisted; basic rate limits are applied.
- File size checks and protections against zip bombs are in place.
- The anomaly mechanisms are basic and do not replace full SIEM solutions.

## Starter tasks (Tickets)
- [ ] Import Telegram attachments → ingestor → normalization → storage.
- [ ] Implement three detection rules (SSH brute-force, NGINX 5xx burst, Wazuh high-level).
- [ ] Publish alerts to Telegram with throttling.
- [ ] `/status` should return key counters from Redis/DB.
- [ ] Document docker-compose and local development setup.
