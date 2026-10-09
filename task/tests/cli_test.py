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


def listed(
    folder: pathlib.Path, filter_: str = '', *, done: bool = False
) -> list[dict[str, object]]:
    flags = ['--done'] if done else []
    result = run(folder, 'list', '--json', '-f', filter_, *flags)
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
    assert released['tag'] == 'bakery/build'


def test_due(tmp_path: pathlib.Path) -> None:
    assert run(tmp_path, 'add', 'unscheduled').returncode == 0
    assert (
        run(tmp_path, 'add', 'later', '--next', '2999-01-01').returncode == 0
    )
    assert run(tmp_path, 'add', 'old', '--next', '2000-01-01').returncode == 0
    assert run(tmp_path, 'add', 'soon', '--next', '2000-01-02').returncode == 0

    result = run(tmp_path, 'due', '--json')
    assert result.returncode == 0, result.stderr
    assert [t['summary'] for t in json.loads(result.stdout)] == ['old', 'soon']
    assert len(listed(tmp_path)) == 4


def test_priority_and_size(tmp_path: pathlib.Path) -> None:
    assert run(tmp_path, 'add', 'a', '--priority', 'high').returncode == 0
    assert run(tmp_path, 'add', 'b', '--size', 'large').returncode == 0
    assert run(tmp_path, '2', 'set', '--priority', 'low').returncode == 0
    assert run(tmp_path, '1', 'set', '--priority', 'urgent').returncode == 2

    assert [t['id'] for t in listed(tmp_path, 'priority=high')] == [1]
    assert [t['id'] for t in listed(tmp_path, 'size=large')] == [2]
    assert [t['id'] for t in listed(tmp_path, 'size=')] == [1]

    assert run(tmp_path, '1', 'unset', 'priority').returncode == 0
    assert [t['id'] for t in listed(tmp_path, 'priority=')] == [1]


def test_descriptions_are_text_files(tmp_path: pathlib.Path) -> None:
    assert run(tmp_path, 'add', 'a', '--description', ' x\n ').returncode == 0
    assert run(tmp_path, 'add', 'b', '--description', 'y').returncode == 0
    assert (tmp_path / '1.txt').read_text() == 'x'

    (tmp_path / '1.txt').write_text('\nedited by hand\n')
    assert listed(tmp_path)[0]['description'] == 'edited by hand'

    assert run(tmp_path, '1', 'unset', 'description').returncode == 0
    assert not (tmp_path / '1.txt').exists()
    assert run(tmp_path, '2', 'done').returncode == 0
    assert (tmp_path / '2.txt').read_text() == 'y'

    (tmp_path / '9.txt').write_text('orphan')
    assert run(tmp_path, 'add', 'c').returncode == 0
    assert not (tmp_path / '9.txt').exists()
    assert [t['id'] for t in listed(tmp_path)] == [1, 3]  # ids never reused


def test_done_hides_until_reopened(tmp_path: pathlib.Path) -> None:
    assert run(tmp_path, 'add', 'a').returncode == 0
    assert run(tmp_path, 'add', 'b').returncode == 0
    assert run(tmp_path, '1', 'done', '--ago', '2').returncode == 0

    assert [t['id'] for t in listed(tmp_path)] == [2]
    [done] = listed(tmp_path, done=True)
    assert done['id'] == 1
    assert str(done['done']) < str(done['updated'])
    assert 'Done:' in run(tmp_path, '1').stdout

    for args in (
        ('done',),
        ('set', '--summary', 'x'),
        ('delay', '1'),
        ('unset', 'owner'),
        ('describe',),
    ):
        result = run(tmp_path, '1', *args)
        assert result.returncode == 1
        assert 'task 1 is done' in result.stderr

    refused = run(tmp_path, '2', 'reopen')
    assert refused.returncode == 1
    assert 'task 2 is not done' in refused.stderr
    assert run(tmp_path, '1', 'reopen').returncode == 0
    assert [t['id'] for t in listed(tmp_path)] == [1, 2]
    assert not listed(tmp_path, done=True)


def test_describe_refuses_concurrent_change(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run(tmp_path, 'add', 'a', '--description', 'x').returncode == 0
    # An "editor" which saves its buffer while a bot appends a note.
    editor = tmp_path / 'editor'
    editor.write_text(
        '#!/bin/sh\n'
        'echo mine > "$1"\n'
        f'"{sys.executable}" -c "from task.cli import cli; cli()"'
        ' 1 set --description-append theirs\n'
    )
    editor.chmod(0o755)
    monkeypatch.setenv('EDITOR', str(editor))

    result = run(tmp_path, '1', 'describe')

    assert result.returncode == 1
    assert 'changed while editing' in result.stderr
    assert listed(tmp_path)[0]['description'] == 'x\n\ntheirs'
