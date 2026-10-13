import datetime
import json
import pathlib
import sysconfig

import pytest
from typer import testing

from task import cli
from task import schema

RUNNER = testing.CliRunner()
pytestmark = pytest.mark.usefixtures('today')


def invoke(*args: str) -> testing.Result:
    return RUNNER.invoke(cli.app, args, catch_exceptions=False)


def run(*args: str) -> str:
    """The output of a successful invocation."""
    result = invoke(*args)
    assert result.exit_code == 0, result.output
    return result.stdout


def refused(*args: str) -> str:
    """The message `task.cli.cli` reports for a refused invocation."""
    with pytest.raises(schema.TaskError) as excinfo:
        invoke(*args)
    return str(excinfo.value)


def listed(filter_: str = '') -> list[dict[str, object]]:
    tasks: list[dict[str, object]] = json.loads(
        run('list', '--json', '-f', filter_)
    )
    return tasks


def refs(tasks: list[dict[str, object]]) -> list[str]:
    return [
        str(t['id'])
        if t['namespace'] == 'default'
        else f'{t["namespace"]}:{t["id"]}'
        for t in tasks
    ]


def test_claim_lifecycle(folder: pathlib.Path) -> None:
    link = 'https://github.com/TheKevJames/tools/issues/1'
    run('add', 'fix it', '--link', link)
    run('add', 'unrelated')
    run('namespace', 'add', 'Bakery')
    for bad in ('bakery/build', '-build', ''):
        assert 'invalid tag' in refused('1', 'set', '--tag', bad)
    moved = run('1', 'set', '-n', 'Bakery ', '--tag', 'Build')
    assert moved == 'moved to bakery:1\n'

    claimable = 'namespace=bakery,tag=build,owner='
    assert refs(listed(claimable)) == ['bakery:1']
    assert refs(listed(f'link={link}')) == ['bakery:1']

    run('bakery:1', 'set', '--owner', 'build')
    assert not listed(claimable)
    for args in (('--owner', 'triage'), ('-n', 'default')):
        assert 'owned by build' in refused('bakery:1', 'set', *args)

    for note in ('a', 'b'):
        run('bakery:1', 'set', '--description-append', note)
    run('bakery:1', 'unset', 'owner')
    [released] = listed(claimable)
    assert released['description'] == 'a\n\nb'

    # Moving back keeps the tag, and ids are never reused.
    run('bakery:1', 'set', '-n', 'default')
    assert refs(listed('tag=build')) == ['3']
    assert (folder / 'default' / '3.txt').read_text() == 'a\n\nb'
    assert not (folder / 'bakery' / '1.txt').exists()


@pytest.mark.usefixtures('folder')
def test_due() -> None:
    run('add', 'unscheduled')
    run('add', 'later', '--next', '2999-01-01')
    run('add', 'old', '--next', '2000-01-01')
    run('add', 'soon', '--next', '2000-01-02')

    due = json.loads(run('due', '--json'))
    assert [t['summary'] for t in due] == ['old', 'soon']
    assert len(listed()) == 4


@pytest.mark.usefixtures('folder')
def test_priority_and_size() -> None:
    run('add', 'a', '--priority', 'high')
    run('add', 'b', '--size', 'large')
    run('2', 'set', '--priority', 'low')
    assert invoke('1', 'set', '--priority', 'urgent').exit_code == 2

    assert [t['id'] for t in listed('priority=high')] == [1]
    assert [t['id'] for t in listed('size=large')] == [2]
    assert [t['id'] for t in listed('size=')] == [1]

    run('1', 'unset', 'priority')
    assert [t['id'] for t in listed('priority=')] == [1]


def test_descriptions_are_text_files(folder: pathlib.Path) -> None:
    run('add', 'a', '--description', ' x\n ')
    run('add', 'b', '--description', 'y')
    default = folder / 'default'
    assert (default / '1.txt').read_text() == 'x'

    (default / '1.txt').write_text('\nedited by hand\n')
    assert listed()[0]['description'] == 'edited by hand'

    run('1', 'unset', 'description')
    assert not (default / '1.txt').exists()
    run('2', 'done')
    assert not (default / '2.txt').exists()

    (default / '9.txt').write_text('orphan')
    run('add', 'c')
    assert not (default / '9.txt').exists()
    assert [t['id'] for t in listed()] == [1, 3]  # ids never reused


@pytest.mark.usefixtures('folder')
def test_done_deletes_one_off_tasks(today: datetime.date) -> None:
    run('add', 'a')
    run('add', 'b')
    recurring = ('--next', '2000-01-01', '--interval', '1d', '--shift')
    run('add', 'c', *recurring)

    message = refused('1', 'done', '--ago', '2')
    assert message == '--ago only applies to recurring tasks'
    assert run('1', 'done') == 'deleted task 1: a\n'
    assert [t['id'] for t in listed()] == [2, 3]
    for args in ((), ('done',), ('set', '--summary', 'x')):
        assert refused('1', *args) == 'task 1 not found'

    # Done yesterday, so due again a day after that.
    run('3', 'done', '--ago', '1')
    assert listed()[1]['next'] == today.isoformat()


def test_describe_refuses_concurrent_change(
    folder: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run('add', 'a', '--description', 'x')
    # An "editor" which saves its buffer while a bot appends a note.
    task = pathlib.Path(sysconfig.get_path('scripts')) / 'task'
    editor = folder / 'editor'
    editor.write_text(
        '#!/bin/sh\n'
        'echo mine > "$1"\n'
        f'"{task}" 1 set --description-append theirs\n'
    )
    editor.chmod(0o755)
    monkeypatch.setenv('EDITOR', str(editor))

    assert (
        refused('1', 'describe')
        == "task 1's description changed while editing"
    )
    assert listed()[0]['description'] == 'x\n\ntheirs'
