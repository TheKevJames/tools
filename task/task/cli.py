import json
import os
import pathlib
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from typing import Annotated

import typer
from typer import _click
from typer import core

from . import db
from . import query
from . import schema


class SubjectGroup(core.TyperGroup):
    """
    Enable `task <id> <cmd>` by rewriting an integer-led invocation.

    A leading integer is the task id (the subject); it is moved to sit behind
    the command so ordinary Typer parsing applies. A bare integer means `show`.
    With no command at all, default to `list`; leading global flags likewise
    route to `list`.
    """

    def parse_args(self, ctx: _click.Context, args: list[str]) -> list[str]:
        if not args:
            args = ['list']
        elif args[0].lstrip('-').isdigit():
            if len(args) == 1:
                args = ['show', args[0]]
            else:
                ident, cmd, *rest = args
                if cmd in self.commands:
                    args = [cmd, ident, *rest]
                else:
                    args = ['show', ident, cmd, *rest]
        elif args[0] not in self.commands and args[0] != '--help':
            args = ['list', *args]
        return super().parse_args(ctx, args)


app = typer.Typer(
    cls=SubjectGroup, add_completion=False, no_args_is_help=False
)


@app.callback()
def main() -> None:
    """Simple personal task manager, shared by humans and bots."""


Ago = Annotated[int, typer.Option('-a', '--ago')]
Days = Annotated[int, typer.Option('-d', '--days')]
Filter = Annotated[
    str, typer.Option('-f', '--filter', help='tag=bar,summary!~bq')
]
Limit = Annotated[int, typer.Option('-l', '--limit')]
Sort = Annotated[query.SortOrder, typer.Option('-s', '--sort')]
AsJson = Annotated[bool, typer.Option('--json', help='Machine-readable.')]

# Shared detail flags: `add` and `set` funnel these into Task.update, keeping a
# single source of truth for task modifications.
Summary = Annotated[str | None, typer.Option('--summary')]
Tag = Annotated[
    str | None, typer.Option('--tag', help='Section path, eg. bakery/build')
]
Next = Annotated[str | None, typer.Option('--next')]
Interval = Annotated[str | None, typer.Option('--interval')]
Shift = Annotated[bool | None, typer.Option('--shift/--no-shift')]
Description = Annotated[str | None, typer.Option('--description')]
DescriptionAppend = Annotated[str | None, typer.Option('--description-append')]
Owner = Annotated[
    str | None,
    typer.Option(
        '--owner', help='Claim the task; fails if someone else owns it.'
    ),
]
Link = Annotated[str | None, typer.Option('--link')]
PriorityOpt = Annotated[schema.Priority | None, typer.Option('--priority')]
SizeOpt = Annotated[schema.Size | None, typer.Option('--size')]
Force = Annotated[
    bool, typer.Option('--force', help='Take ownership from another owner.')
]


# Per-task commands are invoked as `task <id> <cmd>`; group them under their
# own help panel so they don't read as bare top-level commands.
SUBJECT_PANEL = 'Task commands (use as: task <id> <cmd>)'


def print_tasks(tasks: Iterable[schema.Task], as_json: bool) -> None:
    if as_json:
        print(json.dumps([t.to_json() for t in tasks], indent=2))
        return
    for task in tasks:
        print(task)


@app.command('list')
def list_(
    days: Days = -1,
    filter_: Filter = '',
    limit: Limit = -1,
    sort: Sort = query.SortOrder.tag,
    as_json: AsJson = False,
) -> None:
    """List all tasks."""
    with db.connect() as conn:
        tasks = db.select(conn, *query.compile_(filter_, days, limit, sort))
    print_tasks(tasks, as_json)


@app.command('due')
def due(
    days: Days = 0,
    filter_: Filter = '',
    limit: Limit = -1,
    sort: Sort = query.SortOrder.due,
    as_json: AsJson = False,
) -> None:
    """List scheduled tasks due within the given number of days."""
    clauses = query.compile_(filter_, days, limit, sort, scheduled=True)
    with db.connect() as conn:
        tasks = db.select(conn, *clauses)
    print_tasks(tasks, as_json)


@app.command('add')
def add(
    summary: str,
    tag: Tag = None,
    next_: Next = None,
    interval: Interval = None,
    shift: Shift = None,
    description: Description = None,
    owner: Owner = None,
    link: Link = None,
    priority: PriorityOpt = None,
    size: SizeOpt = None,
) -> None:
    """Add a new task, optionally with schedule details."""
    task = schema.Task(summary=summary, details=None, tag=schema.TRIAGE)
    task.update(
        tag=tag,
        next_=next_,
        interval=interval,
        shift=shift,
        description=description,
        owner=owner,
        link=link,
        priority=priority,
        size=size,
    )
    with db.write() as conn:
        db.insert(conn, task)


@app.command('show', rich_help_panel=SUBJECT_PANEL)
def show(ident: int, as_json: AsJson = False) -> None:
    """Show a task's full details and status."""
    with db.connect() as conn:
        task = db.get(conn, ident)
    if as_json:
        print(json.dumps(task.to_json(), indent=2))
        return
    print(task.render_detail())


@app.command('done', rich_help_panel=SUBJECT_PANEL)
def done(ident: int, ago: Ago = 0) -> None:
    """Mark a task as completed, optionally some days ago."""
    with db.write() as conn:
        completed = db.get(conn, ident).complete(ago)
        if not completed:
            db.delete(conn, ident)
        else:
            db.update(conn, completed)

    if not completed:
        print('completed task')
        return
    assert completed.details, 'completed recurring task has no details'
    print(
        f'completed recurring task, next occurrence: {completed.details.next_}'
    )


@app.command('delay', rich_help_panel=SUBJECT_PANEL)
def delay(ident: int, days: int) -> None:
    """Postpone a task by the given number of days."""
    with db.write() as conn:
        delayed = db.get(conn, ident).postpone(days)
        db.update(conn, delayed)

    assert delayed.details, 'delayed task has no details'
    print(f'delayed task, next occurrence: {delayed.details.next_}')


@app.command('set', rich_help_panel=SUBJECT_PANEL)
def set_(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    ident: int,
    summary: Summary = None,
    tag: Tag = None,
    next_: Next = None,
    interval: Interval = None,
    shift: Shift = None,
    description: Description = None,
    description_append: DescriptionAppend = None,
    owner: Owner = None,
    link: Link = None,
    priority: PriorityOpt = None,
    size: SizeOpt = None,
    force: Force = False,
) -> None:
    """Edit a task's summary, section, metadata, or schedule."""
    with db.write() as conn:
        task = db.get(conn, ident)
        task.update(
            summary=summary,
            tag=tag,
            next_=next_,
            interval=interval,
            shift=shift,
            description=description,
            description_append=description_append,
            owner=owner,
            link=link,
            priority=priority,
            size=size,
            force=force,
        )
        db.update(conn, task)


@app.command('describe', rich_help_panel=SUBJECT_PANEL)
def describe(ident: int) -> None:
    """Edit a task's description in $EDITOR."""
    with db.connect() as conn:
        original = db.get(conn, ident).description

    # The editor runs without the write lock, so other writers carry on; the
    # result is only saved if nobody else changed the description meanwhile.
    with tempfile.NamedTemporaryFile(
        'w', suffix='.txt', delete=False, encoding='utf-8'
    ) as f:
        f.write(original or '')
        path = pathlib.Path(f.name)
    try:
        subprocess.run([os.environ.get('EDITOR', 'vim'), path], check=True)
        edited = path.read_text(encoding='utf-8')
    finally:
        path.unlink()

    with db.write() as conn:
        task = db.get(conn, ident)
        if task.description != original:
            raise schema.TaskError(
                f"task {ident}'s description changed while editing"
            )
        task.update(description=edited)
        db.update(conn, task)


@app.command('unset', rich_help_panel=SUBJECT_PANEL)
def unset(ident: int, fields: list[schema.ClearableField]) -> None:
    """Clear fields from a task; `unset <id> owner` releases a claim."""
    with db.write() as conn:
        task = db.get(conn, ident)
        task.clear(fields)
        db.update(conn, task)


def cli() -> None:
    try:
        app()
    except schema.TaskError as e:
        print(f'error: {e}', file=sys.stderr)
        sys.exit(1)
