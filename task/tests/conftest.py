import datetime
import pathlib
import zoneinfo
from collections.abc import Generator

import pytest
import time_machine

# Not UTC, so that rendering local times is exercised.
NOW = datetime.datetime(
    2026, 1, 15, 12, tzinfo=zoneinfo.ZoneInfo('America/Toronto')
)


@pytest.fixture(scope='function')
def folder(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> pathlib.Path:
    """An empty task store, used by in-process and subprocess invocations."""
    monkeypatch.setenv('TASK_FOLDER', str(tmp_path))
    return tmp_path


@pytest.fixture(scope='function', name='now')
def fixture_now() -> Generator[datetime.datetime]:
    """
    Stop the clock. SQLite's own clock, which stamps `created` and `updated`,
    keeps running.
    """
    with time_machine.travel(NOW, tick=False):
        yield NOW


@pytest.fixture(scope='function')
def today(now: datetime.datetime) -> datetime.date:
    return now.date()
