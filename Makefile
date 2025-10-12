PYTHON=python3
POETRY?=
TYPECHECK_PATHS=src/cortexwatcher/api/main.py \
src/cortexwatcher/api/routers/health.py \
src/cortexwatcher/api/routers/metrics.py
COVERAGE_THRESHOLD?=52
PIP_AUDIT_IGNORES?=GHSA-4xh5-x5gv-qwph

.PHONY: setup lint format format-check typecheck test test-coverage security-check ci run migrate seed down clean pre-commit

setup:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .[dev]

lint:
	ruff check src tests --select E,F --ignore E501

format:
	black src tests
	ruff check src tests --fix
	ruff format src tests
	ruff format tests

format-check:
	black --check src tests
	ruff check src tests
	ruff format --check src tests

typecheck:
	mypy $(TYPECHECK_PATHS)

pre-commit:
	pre-commit run --all-files

test:
	pytest

test-coverage:
	pytest --cov=src --cov-report=term-missing --cov-report=xml --cov-fail-under=$(COVERAGE_THRESHOLD)

security-check:
	pip-audit --ignore-vuln $(PIP_AUDIT_IGNORES)

ci: lint typecheck test-coverage security-check

run:
	uvicorn cortexwatcher.api.main:app --reload --host 0.0.0.0 --port 8080

migrate:
	alembic -c src/cortexwatcher/db/migrations/alembic.ini upgrade head

seed:
	$(PYTHON) -m cortexwatcher.db.migrations.seed

down:
	docker compose down -v

clean:
	rm -rf .mypy_cache .pytest_cache build dist

