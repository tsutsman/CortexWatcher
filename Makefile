PYTHON=python3
POETRY?=

.PHONY: setup lint format typecheck test run migrate seed down clean pre-commit

setup:
$(PYTHON) -m pip install --upgrade pip
$(PYTHON) -m pip install -e .[dev]

lint:
ruff check src tests

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
mypy src
ruff check src tests
ruff format --check src tests

pre-commit:
pre-commit run --all-files

test:
pytest

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

