import datetime
import json
import pathlib
import sqlite3
import sysconfig

import pytest
from typer import testing

from task import cli
from task import db
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


def schedule() -> tuple[object, ...]:
    [task] = listed()
    return task['next'], task['interval'], task['shift']


def editor(folder: pathlib.Path, script: str) -> str:
    path = folder / 'editor'
    path.write_text(f'#!/bin/sh\n{script}\n')
    path.chmod(0o755)
    return str(path)


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
def test_add_reports_the_new_ref() -> None:
    run('namespace', 'add', 'b')
    assert run('add', 'a') == 'added task 1: a\n'
    assert run('add', 'b', '-n', 'b') == 'added task b:1: b\n'


@pytest.mark.parametrize(
    'args',
    [
        ('add', 'c', '-n', 'b', '--tag', 'build'),
        ('1', 'set', '--priority', 'high', '--description-append', 'y'),
        ('1', 'set', '-n', 'b'),
        ('1', 'unset', 'shift', 'description'),
        ('1', 'describe'),
        ('1', 'delay', '2'),
        ('1', 'done'),
        ('2', 'done'),
    ],
)
def test_writes_report_the_resulting_task(
    folder: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    args: tuple[str, ...],
) -> None:
    monkeypatch.setenv('EDITOR', editor(folder, 'echo " mine" >> "$1"'))
    run('namespace', 'add', 'b')
    recurring = ('--next', '2026-03-01', '--interval', '1d', '--shift')
    run('add', 'a', *recurring, '--description', 'x')
    run('add', 'b')

    reported = json.loads(run(*args, '--json'))
    print(f'{args} reported {reported}')
    if reported is None:
        assert refused(args[0]) == f'task {args[0]} not found'
        return
    [ref] = refs([reported])
    assert json.loads(run(ref, '--json')) == reported


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
    script = f'echo mine > "$1"\n"{task}" 1 set --description-append theirs'
    monkeypatch.setenv('EDITOR', editor(folder, script))

    assert (
        refused('1', 'describe')
        == "task 1's description changed while editing"
    )
    assert listed()[0]['description'] == 'x\n\ntheirs'


@pytest.mark.usefixtures('folder')
def test_monthly_recurrence_clamps_to_month_end() -> None:
    run('add', 'a', '--next', '2026-01-31', '--interval', '1m')
    assert run('1', 'done') == (
        'completed recurring task 1, next occurrence: 2026-02-28\n'
    )
    assert run('1', 'done') == (
        'completed recurring task 1, next occurrence: 2026-03-28\n'
    )


@pytest.mark.usefixtures('folder')
def test_invalid_filters_are_refused() -> None:
    assert refused('list', '-f', 'bogus=1') == (
        "invalid target: 'bogus'"
        ' (use summary, namespace, tag, owner, link, priority, size, next)'
    )
    assert refused('due', '-f', 'tag=a,summary') == (
        "invalid filter: 'summary' (use eg. tag=a, tag!=a, tag~a, tag!~a)"
    )
    assert refused('list', '-f', 'next~2026') == (
        'next only supports exact matches'
        ' (use eg. next=2026-01-31, next!=2026-01-31, next=)'
    )
    assert refused('list', '-f', 'next=2026-1-31') == (
        "invalid date: '2026-1-31' (use eg. 2026-01-31)"
    )


@pytest.mark.usefixtures('folder')
def test_filter_by_next() -> None:
    run('add', 'unscheduled')
    run('add', 'a', '--next', '2026-01-31')
    run('add', 'b', '--next', '2026-02-01')

    def summaries(filter_: str) -> list[object]:
        return [t['summary'] for t in listed(filter_)]

    assert summaries('next=') == ['unscheduled']
    assert summaries('next!=') == ['a', 'b']
    assert summaries('next=2026-01-31') == ['a']
    assert summaries('next=20260131') == ['a']
    assert summaries('next!=2026-01-31') == ['unscheduled', 'b']


@pytest.mark.usefixtures('folder')
def test_fixed_schedules_cannot_be_delayed() -> None:
    run('add', 'a', '--next', '2026-01-01', '--interval', '1w')
    assert refused('1', 'delay', '3') == (
        'periodic tasks with shift=false cannot be delayed'
    )


def test_describe_saves_the_edit(
    folder: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run('add', 'a', '--description', 'x')
    monkeypatch.setenv('EDITOR', editor(folder, 'echo " mine" >> "$1"'))

    run('1', 'describe')
    assert listed()[0]['description'] == 'x mine'


@pytest.mark.usefixtures('folder')
def test_delay_reschedules_from_today() -> None:
    run('add', 'a')
    run('add', 'b', '--next', '2026-03-01', '--interval', '1d', '--shift')

    assert run('1', 'delay', '2') == (
        'delayed task 1, next occurrence: 2026-01-17\n'
    )
    assert run('2', 'delay', '0') == (
        'delayed task 2, next occurrence: 2026-01-15\n'
    )


@pytest.mark.usefixtures('folder')
def test_done_advances_fixed_schedules_past_today() -> None:
    run('add', 'a', '--next', '2026-01-01', '--interval', '1w')
    assert run('1', 'done') == (
        'completed recurring task 1, next occurrence: 2026-01-22\n'
    )


@pytest.mark.usefixtures('folder')
def test_unset_clears_the_schedule() -> None:
    run('add', 'a', '--next', '2026-02-01', '--interval', '1d', '--shift')
    run('1', 'unset', 'shift')
    assert schedule() == ('2026-02-01', '1d', False)
    run('1', 'unset', 'interval')
    assert schedule() == ('2026-02-01', None, False)
    run('1', 'set', '--interval', '1d', '--shift')
    run('1', 'unset', 'next')
    assert schedule() == (None, None, False)
    run('1', 'unset', 'interval', 'shift')
    assert schedule() == (None, None, False)


@pytest.mark.usefixtures('folder')
def test_namespaces_are_managed() -> None:
    run('namespace', 'add', 'B')
    assert refused('namespace', 'add', 'b') == 'namespace b already exists'
    run('add', 'a')
    assert run('namespace', 'list') == 'b\ndefault\n'

    run('namespace', 'delete', 'b')
    assert run('namespace', 'list') == 'default\n'


@pytest.mark.usefixtures('folder')
def test_unknown_task_command_shows_the_task() -> None:
    run('add', 'a')
    assert json.loads(run('1', '--json'))['summary'] == 'a'


@pytest.mark.usefixtures('folder')
def test_list_renders_tasks() -> None:
    run('namespace', 'add', 'b')
    run('add', 'a', '--next', '2026-01-16')
    run('add', 'b', '-n', 'b', '--tag', 'build', '--description', 'd')
    run('b:1', 'set', '--priority', 'high', '--owner', 'bot')
    run('b:1', 'set', '--next', '2026-01-20', '--interval', '1w')
    run('add', 'c', '--next', '2026-02-01', '--interval', '2d', '--shift')

    assert run('list') == (
        'triage\t1: a\n'
        '\tDue: 2026-01-16\n'
        'triage\t2: c\n'
        '\tDue: 2026-02-01, repeats every 2 days after completion\n'
        'b > build\tb:1: b + !high @bot\n'
        '\tDue: 2026-01-20, repeats weekly since last deadline\n'
    )


def test_show_renders_details(folder: pathlib.Path) -> None:
    run('namespace', 'add', 'b')
    run('add', 'fix it', '-n', 'b', '--tag', 'build', '--owner', 'bot')
    run('b:1', 'set', '--link', 'x', '--priority', 'high', '--size', 'small')
    run('b:1', 'set', '--next', '2026-01-16', '--interval', '2w', '--shift')
    run('b:1', 'set', '--description', 'notes')
    conn = sqlite3.connect(folder / 'b' / db.DATABASE, isolation_level=None)
    conn.execute(
        'UPDATE task SET created = ?, updated = ?',
        ('2026-01-12T17:00:00Z', '2026-01-15T16:00:00Z'),
    )
    conn.close()

    assert run('b:1') == (
        'Summary:     fix it\n'
        'ID:          b:1\n'
        'Tag:         b > build\n'
        'Owner:       bot\n'
        'Link:        x\n'
        'Priority:    high\n'
        'Size:        small\n'
        'Due:         2026-01-16 (1 day)\n'
        'Recurrence:  every 2 weeks after completion\n'
        'Created:     2026-01-12 12:00 (3 days ago)\n'
        'Updated:     2026-01-15 11:00 (1 hour ago)\n'
        '---\n'
        'notes\n'
    )


@pytest.mark.parametrize(
    ('next_', 'status'),
    [
        ('2026-01-14', 'overdue'),
        ('2026-01-15', 'due today'),
        ('2026-01-17', '2 days'),
    ],
)
@pytest.mark.usefixtures('folder')
def test_show_renders_due_status(next_: str, status: str) -> None:
    run('add', 'a', '--next', next_)
    assert f'\nDue:      {next_} ({status})\n' in run('show', '1')


@pytest.mark.parametrize(
    ('args', 'message'),
    [
        (('add', ' '), "invalid summary: ' '"),
        (('1', 'set', '--summary', 'a\nb'), "invalid summary: 'a\\nb'"),
        (('add', 'a', '--owner', 'a b'), "invalid owner: 'a b'"),
        (('add', 'a', '--link', 'a b'), "invalid link: 'a b'"),
        (('add', 'a', '--interval', '1y'), "invalid interval: '1y'"),
        (('show', 'B:1'), "invalid task id: 'B:1'"),
        (
            ('1', 'set', '-n', 'default', '--owner', 'bot'),
            '--namespace and --owner are exclusive',
        ),
        (
            ('1', 'set', '--description', 'x', '--description-append', 'y'),
            '--description and --description-append are exclusive',
        ),
    ],
)
@pytest.mark.usefixtures('folder')
def test_invalid_input_is_refused(args: tuple[str, ...], message: str) -> None:
    run('add', 'a')
    assert refused(*args) == message
    assert listed()[0]['summary'] == 'a'
