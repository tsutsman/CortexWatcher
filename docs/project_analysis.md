# Аналітика стану CortexWatcher

## 1. Продукт і ключові сценарії
- CortexWatcher позиціоновано як телеграм-бот і платформу для потокового збору логів із Telegram, HTTP API (GELF, Wazuh, JSON/NDJSON), їх нормалізації та побудови алертів для SOC/SRE команд.【F:README.md†L5-L15】
- Поточні сценарії включають моніторинг Telegram-груп, прийом syslog/JSON/GELF через API, інтеграцію з Wazuh та перегляд алертів через REST, що задає основний фокус на швидкому зборі та аналізі інцидентів.【F:README.md†L49-L53】
- Базові обмеження описують whitelist чатів, контроль розміру файлів, зберігання секретів лише у середовищі та застереження, що наявні механізми аномалій не замінюють повноцінні SIEM-рішення — це визначає зону подальшого розвитку.【F:README.md†L55-L59】

## 2. Архітектура та компоненти
### 2.1 Високорівневий огляд
- Система складається з Telegram-бота, FastAPI застосунку, воркера ingestor і воркера analyzer, які взаємодіють через Redis RQ та зберігають дані у PostgreSQL/ClickHouse.【F:ARCHITECTURE.md†L6-L16】
- Основне сховище — PostgreSQL для таблиць логів, алертів та аномалій; ClickHouse використовується опційно, а Redis виступає брокером та кешем метрик, що потрібно враховувати під час вибору середовищ.【F:ARCHITECTURE.md†L18-L22】

### 2.2 Конфігурація та залежності
- Конфігурація централізована через `Settings`, що вимагає токени бота, список дозволених чатів, URL БД/Redis/ClickHouse, пороги алертів та шлях до YAML правил.【F:src/cortexwatcher/config.py†L11-L53】
- Фабрика сховищ автоматично обирає ClickHouse або PostgreSQL залежно від прапорця `CLICKHOUSE`, що дає просту точку для розширення зберігання.【F:src/cortexwatcher/storage/__init__.py†L10-L16】
- У `pyproject.toml` зафіксовано стек із FastAPI, aiogram, SQLAlchemy, RQ, Prometheus client та dev-залежностями (pytest, ruff, mypy), що визначає вимоги до інфраструктури CI/CD.【F:pyproject.toml†L5-L42】

### 2.3 API шар
- Головний застосунок FastAPI підключає роутери для health, metrics, ingest та query й на старті зберігає налаштування та інстанс сховища у `app.state`.【F:src/cortexwatcher/api/main.py†L6-L24】
- `/ingest/{source}` приймає пакети логів, перевіряє токен, визначає формат (syslog/json_lines/gelf/wazuh), нормалізує записи та зберігає сирі й нормалізовані дані, формуючи correlation key для подальшої аналітики.【F:src/cortexwatcher/api/routers/ingest.py†L39-L107】
- `/logs`, `/alerts` та `/anomalies` надають фільтрований доступ до нормалізованих подій, алертів і аномалій, повертаючи обмежені списки з ключовими полями для UI або інтеграцій.【F:src/cortexwatcher/api/routers/query.py†L21-L86】
- `/status` агрерує стан БД, Redis-черги, кешу метрик, ClickHouse та бекенда зберігання, що є основою для сторінки моніторингу/health-check; `/metrics` експонує Prometheus-лічильник запитів.【F:src/cortexwatcher/api/routers/health.py†L26-L134】【F:src/cortexwatcher/api/routers/metrics.py†L9-L20】

### 2.4 Обробка логів, аналітика та нотифікації
- ORM моделі описують сирі та нормалізовані логи, алерти й аномалії, з індексами по `ts`, `host`, `app`, `severity` та JSONB-полями для метаданих.【F:src/cortexwatcher/db/models.py†L18-L80】
- Базовий інтерфейс `LogStorage` регламентує операції для запису/читання логів, алертів і аномалій, а реалізація `PostgresStorage` формує SQLAlchemy-запити з фільтрами, тоді як `ClickHouseStorage` наразі є in-memory заглушкою, що не масштабується у продакшні.【F:src/cortexwatcher/storage/base.py†L11-L53】【F:src/cortexwatcher/storage/postgres.py†L15-L95】【F:src/cortexwatcher/storage/clickhouse.py†L11-L75】
- Воркери RQ обробляють інжест: нормалізують події, оновлюють метрики у Redis, а цикл analyzer застосовує YAML-правила, зберігає алерти, відправляє їх через `AlertNotifier` та фіксує аномалії за допомогою ковзного вікна `AnomalyDetector`.【F:src/cortexwatcher/workers/tasks.py†L26-L188】【F:src/cortexwatcher/analyzer/rules_engine.py†L13-L89】【F:src/cortexwatcher/analyzer/anomalies.py†L10-L56】【F:src/cortexwatcher/analyzer/notifier.py†L8-L36】
- Telegram-бот виконує whitelist/ratelimit перевірки, приймає текст/файли, формує коротку статистику та кладе події у чергу або одразу повертає метрики `/status`, що забезпечує польовий збір даних без API інтеграцій.【F:src/cortexwatcher/bot/handlers.py†L22-L137】【F:src/cortexwatcher/bot/security.py†L11-L34】

## 3. Якість коду та тестування
- Наявні тести охоплюють інжест і REST запити, включно з обробкою `/status`, забезпечуючи базову перевірку API та health-логіки.【F:tests/test_api.py†L1-L144】
- Окремі тести валідують парсери форматів та rules engine, однак сховища, воркери та телеграм-бот залишаються без автоматичного покриття, що створює ризик регресій у критичних пайплайнах інжесту.【F:tests/test_parsers.py†L1-L36】【F:tests/test_rules_engine.py†L1-L24】
- Makefile містить цілі для lint (ruff), format (black+ruff), typecheck (mypy) та pytest, але немає обовʼязкового контролю покриття чи безпекових сканувань у стандартних командах.【F:Makefile†L4-L48】

## 4. Процеси розробки та експлуатація
- `README` надає базовий гайд із запуску через docker-compose та локальної розробки з Python 3.11, проте не описує детально CI/CD або середовища staging/production.【F:README.md†L17-L35】
- У `pyproject.toml` задано строгі налаштування mypy та coverage, але автоматичний запуск цих інструментів залежить від ручних команд, тож варто впровадити їх у pipeline.【F:pyproject.toml†L34-L72】
- Redis-черга та воркери запускаються окремими процесами (`workers/ingestor.py` та `tasks.py`), що вимагає оркестрації та моніторингу для продуктивного середовища.【F:src/cortexwatcher/workers/ingestor.py†L10-L15】【F:src/cortexwatcher/workers/tasks.py†L21-L188】

## 5. Ключові ризики та технічний борг
- Реалізація ClickHouse наразі in-memory, тому при увімкненні прапорця `CLICKHOUSE` дані не зберігатимуться персистентно, що критично для високонавантажених сценаріїв.【F:src/cortexwatcher/storage/clickhouse.py†L11-L75】
- Analyzer працює як нескінченний цикл з простим набором правил та базовим z-score; відсутні механізми backpressure, обмеження памʼяті та збереження стану ковзного вікна, що може призвести до втрати подій при великих потоках.【F:src/cortexwatcher/workers/tasks.py†L119-L177】【F:src/cortexwatcher/analyzer/anomalies.py†L16-L56】
- Бот синхронно завантажує файли та кладе їх у чергу без перевірки типів вкладень/архівів, покладаючись лише на обмеження розміру, що залишає потенційні вектори для zip-bomb/шкідливих даних.【F:src/cortexwatcher/bot/handlers.py†L67-L98】
- Відсутні автоматичні перевірки безпеки залежностей і секретів у репозиторії, попри вимоги до роботи з чутливими логами.【F:Makefile†L4-L48】

## 6. Дорожня карта розвитку
### Етап 0 — стабілізація та технічний борг
1. **Реалізувати повноцінний драйвер ClickHouse** або інтегрувати офіційну бібліотеку, забезпечивши персистентність та тестування запитів, оскільки нинішня заглушка не підходить для продакшн-навантажень.【F:src/cortexwatcher/storage/clickhouse.py†L11-L75】
2. **Посилити пайплайн analyzer**: додати збереження стану оброблених логів, обмеження черги та метрики для затримок, щоб уникнути пропуску подій у циклі `run_analyzer_loop`.【F:src/cortexwatcher/workers/tasks.py†L119-L177】
3. **Розширити автотести** покриттям сховищ (PostgreSQL/ClickHouse), воркерів і RateLimiter, використовуючи наявну інфраструктуру pytest, аби знизити ризик регресій у найкритичніших частинах пайплайна.【F:tests/test_api.py†L1-L144】【F:tests/test_parsers.py†L1-L36】
4. **Впровадити обовʼязковий lint/typecheck/test у CI** і додати контроль покриття та сканування залежностей у Makefile/pipeline, що відповідає вимогам до безпеки платформи.【F:Makefile†L4-L48】【F:pyproject.toml†L34-L72】

### Етап 1 — розширення збору та обробки даних
1. **Додати валідацію вкладень і типів файлів у боті** (MIME, перевірка архівів, quarantine), щоби закрити ризики зловмисних payload-ів, а також асинхронну обробку великих файлів.【F:src/cortexwatcher/bot/handlers.py†L67-L98】
2. **Розширити парсери/ingest** підтримкою додаткових форматів (наприклад, Zeek, Suricata), використовуючи існуючий механізм `detect_format` і `_parse_by_format`, щоб покрити більше джерел без зміни API.【F:src/cortexwatcher/api/routers/ingest.py†L53-L107】
3. **Запровадити редактор правил та їх валідацію** перед завантаженням у `RuleEngine`, включно з тестами на конфлікти/синтаксис, щоб спростити оновлення YAML без перезапуску сервісу.【F:src/cortexwatcher/analyzer/rules_engine.py†L34-L89】
4. **Нормалізувати схему зберігання**: додати індекси/пошук (PG Trigram/GIN) і DTO версіонування для API `/logs`, підготувавши основу для зовнішніх інтеграцій та оптимізації запитів.【F:src/cortexwatcher/db/models.py†L33-L52】【F:src/cortexwatcher/api/routers/query.py†L21-L46】

### Етап 2 — спостережність та UX
1. **Розширити `/status` і метрики** додатковими показниками (latency ingestion, розмір черг, rate алертів) та побудувати Grafana-дашборди для SOC/SRE команд на базі Prometheus-лічильників.【F:src/cortexwatcher/api/routers/health.py†L26-L134】【F:src/cortexwatcher/api/routers/metrics.py†L9-L20】
2. **Створити веб-UI або інтеграцію з Grafana/Streamlit** для перегляду логів, алертів і аномалій, спираючись на існуючі REST-ендпоінти `/logs`, `/alerts`, `/anomalies` та `/status`.【F:src/cortexwatcher/api/routers/query.py†L21-L86】【F:src/cortexwatcher/api/routers/health.py†L26-L47】
3. **Додати багатоканальні нотифікації** (Slack, email) у `AlertNotifier` з можливістю ack/auto-close, розширивши наявну логіку Telegram-розсилки, щоби збільшити застосовність для команд без Telegram.【F:src/cortexwatcher/analyzer/notifier.py†L8-L36】
4. **Документувати оперативні плейбуки та процес оновлення правил** (підписи, контроль версій), використавши існуючий README як базу та доповнивши інформацією про релізний цикл і управління секретами.【F:README.md†L17-L47】

### Етап 3 — інтелектуальна аналітика
1. **Покращити аномалії**: додати адаптивні пороги, підтримку сезонності та збереження історії сигналів у БД, розширивши можливості `AnomalyDetector` і моделі `Anomaly` для складніших сценаріїв SOC.【F:src/cortexwatcher/analyzer/anomalies.py†L16-L56】【F:src/cortexwatcher/db/models.py†L70-L80】
2. **Побудувати систему пріоритизації алертів** з урахуванням контексту (частота, критичність сервісу, джерело), розширивши структуру `Alert` та відповіді `/alerts` додатковими полями ризику.【F:src/cortexwatcher/db/models.py†L55-L68】【F:src/cortexwatcher/api/routers/query.py†L49-L67】
3. **Автоматизувати enrichment** логів (GeoIP, дані про користувачів/сервіси) у пайплайні ingestor, використовуючи перетворення перед збереженням у `LogNormalized`, що підвищить якість аналітики без ручної обробки.【F:src/cortexwatcher/api/routers/ingest.py†L64-L83】【F:src/cortexwatcher/workers/tasks.py†L61-L80】

Ця аналітика та дорожня карта задають пріоритети для переходу CortexWatcher від MVP до готового до промислового використання рішення з підсиленими можливостями, якістю та спостережністю.
