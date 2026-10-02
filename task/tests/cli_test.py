import json
import os
import pathlib
import subprocess
import sys

import pytest

WRITERS = 8


def task(folder: pathlib.Path, *args: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, '-c', 'from task.cli import cli; cli()', *args],
        env=os.environ | {'TASK_FOLDER': str(folder)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def run(folder: pathlib.Path, *args: str) -> subprocess.CompletedProcess[str]:
    proc = task(folder, *args)
    stdout, stderr = proc.communicate()
    return subprocess.CompletedProcess(args, proc.returncode, stdout, stderr)


def listed(folder: pathlib.Path, filter_: str = '') -> list[dict[str, object]]:
    result = run(folder, 'list', '-pall', '--json', '-f', filter_)
    assert result.returncode == 0, result.stderr
    tasks: list[dict[str, object]] = json.loads(result.stdout)
    return tasks


def test_concurrent_writers_lose_nothing(tmp_path: pathlib.Path) -> None:
    procs = [task(tmp_path, 'add', f'task {i}') for i in range(WRITERS)]
    assert all(p.wait() == 0 for p in procs)

    tasks = listed(tmp_path)
    assert sorted(str(t['summary']) for t in tasks) == sorted(
        f'task {i}' for i in range(WRITERS)
    )
    assert len({t['id'] for t in tasks}) == WRITERS


def test_concurrent_claims_have_one_winner(tmp_path: pathlib.Path) -> None:
    assert run(tmp_path, 'add', 'contested').returncode == 0

    procs = [
        task(tmp_path, '1', 'set', '--owner', f'bot{i}')
        for i in range(WRITERS)
    ]
    winners = [i for i, p in enumerate(procs) if p.wait() == 0]

    assert len(winners) == 1
    assert listed(tmp_path)[0]['owner'] == f'bot{winners[0]}'


def test_claim_lifecycle(tmp_path: pathlib.Path) -> None:
    link = 'https://github.com/TheKevJames/tools/issues/1'
    assert run(tmp_path, 'add', 'fix it', '--link', link).returncode == 0
    assert run(tmp_path, 'add', 'unrelated').returncode == 0
    assert run(tmp_path, '1', 'set', '--tag', 'Bakery/build').returncode == 0

    claimable = 'tag=bakery/build,owner='
    assert [t['id'] for t in listed(tmp_path, claimable)] == [1]
    assert [t['id'] for t in listed(tmp_path, f'link={link}')] == [1]

    assert run(tmp_path, '1', 'set', '--owner', 'build').returncode == 0
    assert not listed(tmp_path, claimable)
    stolen = run(tmp_path, '1', 'set', '--owner', 'triage')
    assert stolen.returncode == 1
    assert 'owned by build' in stolen.stderr

    assert (
        run(tmp_path, '1', 'set', '--description-append', 'a').returncode == 0
    )
    assert (
        run(tmp_path, '1', 'set', '--description-append', 'b').returncode == 0
    )
    assert run(tmp_path, '1', 'unset', 'owner').returncode == 0
    [released] = listed(tmp_path, claimable)
    assert released['description'] == 'a\n\nb'
    assert released['tag'] == 'Bakery/build'


@pytest.mark.parametrize(
    'conflict',
    [
        "index (Kevin's conflicted copy 2026-10-02).md",
        'index.sync-conflict-20261002-101010-ABCDEFG.md',
    ],
)
def test_refuses_sync_conflicts(tmp_path: pathlib.Path, conflict: str) -> None:
    (tmp_path / conflict).touch()

    result = run(tmp_path, 'list')

    assert result.returncode == 1
    assert conflict in result.stderr
