# Архітектура CortexWatcher

## Огляд
CortexWatcher складається з чотирьох основних сервісів:
- **bot** — телеграм-бот на aiogram, що приймає повідомлення та передає їх у чергу.
- **api** — FastAPI застосунок для HTTP інтеграцій, запитів до логів, алертів, метрик.
- **ingestor worker** — обробка черги RQ: парсинг, нормалізація, запис у сховище.
- **analyzer worker** — оцінка правил та аномалій, формування алертів.

```
Telegram групи → bot → Redis (RQ) → ingestor → storage (Postgres/ClickHouse)
                                               ↘
                                                analyzer → alerts → Telegram / API
```

## Дані та сховище
- **PostgreSQL** — основна БД для таблиць `logs_raw`, `logs_normalized`, `alerts`, `anomalies`.
- **ClickHouse** (опційно) — для високонавантаженого зберігання `logs_*`. Вибір керується змінною `CLICKHOUSE`.
- **Redis** — брокер і кеш для коротких метрик (`/status`).

### SQLAlchemy ORM
Файли:
- `src/cortexwatcher/db/models.py` — визначення моделей.
- `src/cortexwatcher/db/session.py` — створення асинхронного engine та сесій.
- `src/cortexwatcher/storage/postgres.py` — реалізація інтерфейсу збереження.

## Парсери
У каталозі `src/cortexwatcher/parsers/` реалізовано модулі для різних форматів логів. Модуль `detect.py` автоматично визначає формат.

## Аналітика
- `analyzer/rules_engine.py` — завантаження правил із YAML, застосування regex/glob та фільтрів.
- `analyzer/anomalies.py` — обчислення ковзних метрик (з-score, медіана).
- `analyzer/correlate.py` — створення correlation_key.
- `analyzer/notifier.py` — відправка алертів у Telegram та створення записів у БД.

## API
FastAPI застосунок із роутерами:
- `/ingest/{source}` — прийом пакетів логів.
- `/logs`, `/alerts`, `/anomalies` — фільтри.
- `/healthz` — перевірка стану.
- `/metrics` — Prometheus метрики.

## Черги
RQ використовується для обробки асинхронних задач:
- `workers/tasks.py` містить задачі для парсингу та аналізу.
- `workers/ingestor.py` запускає воркера RQ.

## Міграції
Алембік конфігурація знаходиться в `src/cortexwatcher/db/migrations`. Базовий скрипт ініціалізує таблиці.

## Метрики
- API експонує `/metrics` за допомогою `prometheus_client`.
- Analyzer оновлює лічильники подій у Redis.

