import pathlib

import pytest


@pytest.fixture(scope='function')
def folder(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> pathlib.Path:
    """An empty task store, used by in-process and subprocess invocations."""
    monkeypatch.setenv('TASK_FOLDER', str(tmp_path))
    return tmp_path
