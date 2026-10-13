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


@pytest.mark.usefixtures('folder')
def test_tags_are_normalized() -> None:
    run('add', 'a', '--tag', ' Build ')
    for bad in ('bakery/build', '-build', ''):
        assert refused('1', 'set', '--tag', bad) == f'invalid tag: {bad!r}'
    assert listed()[0]['tag'] == 'build'


@pytest.mark.usefixtures('folder')
def test_set_namespace_moves_the_task() -> None:
    run('add', 'a')
    assert refused('1', 'set', '-n', 'bakery') == 'no such namespace: bakery'
    run('namespace', 'add', 'Bakery')

    assert run('1', 'set', '-n', 'Bakery ') == 'moved to bakery:1\n'
    assert run('bakery:1', 'set', '-n', 'bakery') == ''
    assert refs(listed()) == ['bakery:1']


@pytest.mark.usefixtures('folder')
def test_claims_are_exclusive_until_released() -> None:
    run('namespace', 'add', 'b')
    run('add', 'a')
    run('1', 'set', '--owner', 'build')
    run('1', 'set', '--owner', 'build')

    owned = 'task 1 is owned by build'
    assert refused('1', 'set', '--owner', 'triage') == owned
    assert refused('1', 'set', '-n', 'b') == f'{owned}: release it first'
    assert listed('owner=build')

    run('1', 'unset', 'owner')
    assert listed('owner=')
    run('1', 'set', '--owner', 'triage')
    run('1', 'set', '--owner', 'bot', '--force')
    assert listed()[0]['owner'] == 'bot'


@pytest.mark.usefixtures('folder')
def test_description_append_adds_paragraphs() -> None:
    run('add', 'a')
    for note in ('a', ' ', 'b\n'):
        run('1', 'set', '--description-append', note)
    assert listed()[0]['description'] == 'a\n\nb'


@pytest.mark.usefixtures('folder')
def test_due() -> None:
    run('add', 'unscheduled')
    run('add', 'later', '--next', '2999-01-01')
    run('add', 'old', '--next', '2000-01-01')
    run('add', 'soon', '--next', '2000-01-02')

    due = json.loads(run('due', '--json'))
    assert [t['summary'] for t in due] == ['old', 'soon']


@pytest.mark.usefixtures('folder')
def test_metadata_flags() -> None:
    run('add', 'a', '--priority', 'high', '--size', 'large', '--link', 'x')
    run('1', 'set', '--priority', 'low')
    assert invoke('1', 'set', '--priority', 'urgent').exit_code == 2
    run('1', 'unset', 'size')

    [task] = listed()
    assert (task['priority'], task['size'], task['link']) == ('low', None, 'x')


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


@pytest.mark.usefixtures('folder')
def test_monthly_recurrence_clamps_to_month_end() -> None:
    run('add', 'a', '--next', '2026-01-31', '--interval', '1m')
    assert run('1', 'done') == (
        'completed recurring task, next occurrence: 2026-02-28\n'
    )
    assert run('1', 'done') == (
        'completed recurring task, next occurrence: 2026-03-28\n'
    )


@pytest.mark.usefixtures('folder')
def test_invalid_filters_are_refused() -> None:
    assert refused('list', '-f', 'bogus=1') == (
        "invalid target: 'bogus'"
        ' (use summary, namespace, tag, owner, link, priority, size)'
    )
    assert refused('due', '-f', 'tag=a,summary') == (
        "invalid filter: 'summary' (use eg. tag=a, tag!=a, tag~a, tag!~a)"
    )
