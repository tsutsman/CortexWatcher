"""Загальні фікстури та допоміжні хелпери для pytest."""
from __future__ import annotations

import asyncio
import inspect
import sys
from collections.abc import Awaitable
from pathlib import Path
from typing import Any

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Реєструє ini-опцію asyncio_mode для сумісності з pytest-asyncio."""

    parser.addini(
        "asyncio_mode",
        "Режим роботи кастомного asyncio-плагіна (для сумісності з pytest-asyncio)",
        default="auto",
    )

# Додаємо src до sys.path, щоб імпортувати cortexwatcher без інсталяції пакета
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if SRC.exists():
    sys.path.insert(0, str(SRC))


class _LoopManager:
    """Керує окремим asyncio-loop для тесту або фікстури."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._policy = asyncio.get_event_loop_policy()

    def run(self, awaitable: Awaitable[Any]) -> Any:
        """Виконує корутину всередині контрольованого циклу подій."""

        self._policy.set_event_loop(self._loop)
        try:
            return self._loop.run_until_complete(awaitable)
        finally:
            self._policy.set_event_loop(None)

    def close(self) -> None:
        """Акуратно зупиняє цикл, завершаючи асинхронні генератори."""

        self._policy.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
        finally:
            self._policy.set_event_loop(None)
            self._loop.close()


def pytest_configure(config: pytest.Config) -> None:
    """Реєструє кастомну мітку asyncio, щоб уникнути попереджень pytest."""

    config.addinivalue_line(
        "markers",
        "asyncio: запускати тест або фікстуру в циклі подій asyncio без pytest-asyncio",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool:
    """Дозволяє виконувати async def тести без додаткових плагінів."""

    if inspect.iscoroutinefunction(pyfuncitem.obj):
        manager = _LoopManager()
        try:
            testargs = {
                name: pyfuncitem.funcargs[name]
                for name in pyfuncitem._fixtureinfo.argnames
            }
            manager.run(pyfuncitem.obj(**testargs))
        finally:
            manager.close()
        return True
    return False


@pytest.hookimpl(tryfirst=True)
def pytest_fixture_setup(
    fixturedef: pytest.FixtureDef[Any], request: pytest.FixtureRequest
) -> Any:
    """Запускає асинхронні фікстури у власному циклі подій."""

    func = fixturedef.func
    if inspect.isasyncgenfunction(func):
        manager = _LoopManager()
        kwargs = {name: request.getfixturevalue(name) for name in (fixturedef.argnames or ())}
        async_gen = func(**kwargs)
        cache_key = fixturedef.cache_key(request)
        try:
            value = manager.run(async_gen.__anext__())
        except StopAsyncIteration as exc:  # pragma: no cover - захист від неправильного використання
            manager.close()
            raise RuntimeError("Асинхронна фікстура повинна містити хоча б один yield") from exc
        except BaseException as exc:  # pragma: no cover - передаємо помилку далі
            fixturedef.cached_result = (None, cache_key, (exc, exc.__traceback__))
            manager.close()
            raise
        else:
            fixturedef.cached_result = (value, cache_key, None)

        def finalizer() -> None:
            try:
                manager.run(async_gen.__anext__())
            except StopAsyncIteration:
                pass
            else:  # pragma: no cover - не очікується більше одного yield
                raise RuntimeError("Асинхронна фікстура може повертати лише одне значення")
            finally:
                manager.close()

        request.addfinalizer(finalizer)
        return value

    if inspect.iscoroutinefunction(func):
        manager = _LoopManager()
        kwargs = {name: request.getfixturevalue(name) for name in (fixturedef.argnames or ())}
        cache_key = fixturedef.cache_key(request)
        try:
            result = manager.run(func(**kwargs))
        except BaseException as exc:  # pragma: no cover - передаємо помилку далі
            fixturedef.cached_result = (None, cache_key, (exc, exc.__traceback__))
            manager.close()
            raise
        else:
            fixturedef.cached_result = (result, cache_key, None)
            return result
        finally:
            manager.close()

    return None
