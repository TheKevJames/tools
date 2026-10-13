import datetime
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
    result = run(folder, 'list', '--json', '-f', filter_)
    assert result.returncode == 0, result.stderr
    tasks: list[dict[str, object]] = json.loads(result.stdout)
    return tasks


def refs(tasks: list[dict[str, object]]) -> list[str]:
    return [
        str(t['id'])
        if t['namespace'] == 'default'
        else f'{t["namespace"]}:{t["id"]}'
        for t in tasks
    ]


def test_concurrent_writers_lose_nothing(tmp_path: pathlib.Path) -> None:
    assert run(tmp_path, 'namespace', 'add', 'b').returncode == 0
    procs = [
        task(tmp_path, 'add', '-n', ('default', 'b')[i % 2], f'task {i}')
        for i in range(WRITERS)
    ]
    assert all(p.wait() == 0 for p in procs)

    tasks = listed(tmp_path)
    assert sorted(str(t['summary']) for t in tasks) == sorted(
        f'task {i}' for i in range(WRITERS)
    )
    assert len(set(refs(tasks))) == WRITERS


def test_concurrent_moves_lose_nothing(tmp_path: pathlib.Path) -> None:
    assert run(tmp_path, 'namespace', 'add', 'b').returncode == 0
    for i in range(WRITERS):
        namespace = ('default', 'b')[i % 2]
        assert run(tmp_path, 'add', '-n', namespace, str(i)).returncode == 0
    # Moves both ways at once, so each takes both namespaces' locks.
    added = listed(tmp_path)
    procs = [
        task(tmp_path, ref, 'set', '-n', 'b' if ref.isdigit() else 'default')
        for ref in refs(added)
    ]
    assert all(p.wait() == 0 for p in procs)

    tasks = listed(tmp_path)
    assert sorted(int(str(t['summary'])) for t in tasks) == list(
        range(WRITERS)
    )
    assert all(
        t['namespace'] == ('b', 'default')[int(str(t['summary'])) % 2]
        for t in tasks
    )


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
    assert run(tmp_path, 'namespace', 'add', 'Bakery').returncode == 0
    for bad in ('bakery/build', '-build', ''):
        refused = run(tmp_path, '1', 'set', '--tag', bad)
        assert refused.returncode == 1
        assert 'invalid tag' in refused.stderr
    moved = run(tmp_path, '1', 'set', '-n', 'Bakery ', '--tag', 'Build')
    assert moved.stdout == 'moved to bakery:1\n'

    claimable = 'namespace=bakery,tag=build,owner='
    assert refs(listed(tmp_path, claimable)) == ['bakery:1']
    assert refs(listed(tmp_path, f'link={link}')) == ['bakery:1']

    assert run(tmp_path, 'bakery:1', 'set', '--owner', 'build').returncode == 0
    assert not listed(tmp_path, claimable)
    for args in (('--owner', 'triage'), ('-n', 'default')):
        refused = run(tmp_path, 'bakery:1', 'set', *args)
        assert refused.returncode == 1
        assert 'owned by build' in refused.stderr

    for note in ('a', 'b'):
        appended = run(
            tmp_path, 'bakery:1', 'set', '--description-append', note
        )
        assert appended.returncode == 0
    assert run(tmp_path, 'bakery:1', 'unset', 'owner').returncode == 0
    [released] = listed(tmp_path, claimable)
    assert released['description'] == 'a\n\nb'

    # Moving back keeps the tag, and ids are never reused.
    assert run(tmp_path, 'bakery:1', 'set', '-n', 'default').returncode == 0
    assert refs(listed(tmp_path, 'tag=build')) == ['3']
    assert (tmp_path / 'default' / '3.txt').read_text() == 'a\n\nb'
    assert not (tmp_path / 'bakery' / '1.txt').exists()


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
    folder = tmp_path / 'default'
    assert (folder / '1.txt').read_text() == 'x'

    (folder / '1.txt').write_text('\nedited by hand\n')
    assert listed(tmp_path)[0]['description'] == 'edited by hand'

    assert run(tmp_path, '1', 'unset', 'description').returncode == 0
    assert not (folder / '1.txt').exists()
    assert run(tmp_path, '2', 'done').returncode == 0
    assert not (folder / '2.txt').exists()

    (folder / '9.txt').write_text('orphan')
    assert run(tmp_path, 'add', 'c').returncode == 0
    assert not (folder / '9.txt').exists()
    assert [t['id'] for t in listed(tmp_path)] == [1, 3]  # ids never reused


def test_done_deletes_one_off_tasks(tmp_path: pathlib.Path) -> None:
    assert run(tmp_path, 'add', 'a').returncode == 0
    assert run(tmp_path, 'add', 'b').returncode == 0
    recurring = ('--next', '2000-01-01', '--interval', '1d', '--shift')
    assert run(tmp_path, 'add', 'c', *recurring).returncode == 0

    refused = run(tmp_path, '1', 'done', '--ago', '2')
    assert refused.returncode == 1
    assert '--ago only applies to recurring tasks' in refused.stderr
    assert run(tmp_path, '1', 'done').stdout == 'deleted task 1: a\n'
    assert [t['id'] for t in listed(tmp_path)] == [2, 3]
    for args in ((), ('done',), ('set', '--summary', 'x')):
        result = run(tmp_path, '1', *args)
        assert result.returncode == 1
        assert 'task 1 not found' in result.stderr

    # Done yesterday, so due again a day after that.
    assert run(tmp_path, '3', 'done', '--ago', '1').returncode == 0
    assert listed(tmp_path)[1]['next'] == datetime.date.today().isoformat()


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
