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
    Enable `task <id> <cmd>` by rewriting a task-led invocation.

    A leading task id (the subject) is moved to sit behind the command so
    ordinary Typer parsing applies. A bare task id means `show`.
    """

    def parse_args(self, ctx: _click.Context, args: list[str]) -> list[str]:
        if args and schema.REF_RE.fullmatch(args[0]):
            if len(args) == 1:
                args = ['show', args[0]]
            else:
                ident, cmd, *rest = args
                if cmd in self.commands:
                    args = [cmd, ident, *rest]
                else:
                    args = ['show', ident, cmd, *rest]
        return super().parse_args(ctx, args)


app = typer.Typer(cls=SubjectGroup, add_completion=False, no_args_is_help=True)
namespace_app = typer.Typer(no_args_is_help=True)
app.add_typer(namespace_app, name='namespace', help='Manage namespaces.')


@app.callback()
def main() -> None:
    """Simple personal task manager, shared by humans and bots."""


Ago = Annotated[int, typer.Option('-a', '--ago')]
Days = Annotated[int, typer.Option('-d', '--days')]
Filter = Annotated[
    str,
    typer.Option('-f', '--filter', help='namespace=foo,tag=bar,summary!~bq'),
]
Limit = Annotated[int, typer.Option('-l', '--limit')]
Sort = Annotated[query.SortOrder, typer.Option('-s', '--sort')]
AsJson = Annotated[bool, typer.Option('--json', help='Machine-readable.')]

Ref = Annotated[
    schema.Ref,
    typer.Argument(
        metavar='ID', parser=schema.Ref.parse, help='[namespace:]id'
    ),
]
NamespaceName = Annotated[str, typer.Argument(metavar='NAMESPACE')]

# Shared detail flags: `add` and `set` funnel these into Task.update, keeping a
# single source of truth for task modifications.
Summary = Annotated[str | None, typer.Option('--summary')]
AddNamespace = Annotated[str, typer.Option('-n', '--namespace')]
MoveNamespace = Annotated[
    str | None,
    typer.Option(
        '-n', '--namespace', help='Move the task here; it gets a new id.'
    ),
]
Tag = Annotated[str | None, typer.Option('--tag', help='Section, eg. build')]
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
    clauses = query.compile_(filter_, days, limit, sort)
    with db.connect() as store:
        tasks = db.select(store, *clauses)
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
    with db.connect() as store:
        tasks = db.select(store, *clauses)
    print_tasks(tasks, as_json)


@app.command('add')
def add(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    summary: str,
    namespace: AddNamespace = schema.DEFAULT,
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
    task = schema.Task(
        summary=summary,
        details=None,
        namespace=schema.normalize_name('namespace', namespace),
        tag=schema.TRIAGE,
    )
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
    with db.write(task.namespace) as store:
        db.insert(store, task)


@app.command('show', rich_help_panel=SUBJECT_PANEL)
def show(ref: Ref, as_json: AsJson = False) -> None:
    """Show a task's full details and status."""
    with db.connect() as store:
        task = db.get(store, ref)
    if as_json:
        print(json.dumps(task.to_json(), indent=2))
        return
    print(task.render_detail())


@app.command('done', rich_help_panel=SUBJECT_PANEL)
def done(ref: Ref, ago: Ago = 0) -> None:
    """Complete a task: delete it, or advance it if it recurs."""
    with db.write(ref.namespace) as store:
        task = db.get(store, ref)
        completed = task.complete(ago)
        if completed is None:
            db.delete(store, ref)
        else:
            db.update(store, completed)

    if completed is None:
        print(f'deleted task {ref}: {task.summary}')
        return
    assert completed.details, 'completed recurring task has no details'
    print(
        f'completed recurring task, next occurrence: {completed.details.next_}'
    )


@app.command('delay', rich_help_panel=SUBJECT_PANEL)
def delay(ref: Ref, days: int) -> None:
    """Postpone a task by the given number of days."""
    with db.write(ref.namespace) as store:
        delayed = db.get(store, ref).postpone(days)
        db.update(store, delayed)

    assert delayed.details, 'delayed task has no details'
    print(f'delayed task, next occurrence: {delayed.details.next_}')


@app.command('set', rich_help_panel=SUBJECT_PANEL)
def set_(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    ref: Ref,
    summary: Summary = None,
    namespace: MoveNamespace = None,
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
    """Edit a task's summary, namespace, section, metadata, or schedule."""
    target = ref.namespace
    if namespace is not None:
        target = schema.normalize_name('namespace', namespace)
    with db.write(ref.namespace, target) as store:
        task = db.get(store, ref)
        task.update(
            summary=summary,
            namespace=namespace,
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
        if task.namespace == ref.namespace:
            db.update(store, task)
        else:
            db.move(store, task, ref)

    if task.namespace != ref.namespace:
        print(f'moved to {task.ref}')


@app.command('describe', rich_help_panel=SUBJECT_PANEL)
def describe(ref: Ref) -> None:
    """Edit a task's description in $EDITOR."""
    with db.connect() as store:
        original = db.get(store, ref).description

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

    with db.write(ref.namespace) as store:
        task = db.get(store, ref)
        if task.description != original:
            raise schema.TaskError(
                f"task {ref}'s description changed while editing"
            )
        task.update(description=edited)
        db.update(store, task)


@app.command('unset', rich_help_panel=SUBJECT_PANEL)
def unset(ref: Ref, fields: list[schema.ClearableField]) -> None:
    """Clear fields from a task; `unset <id> owner` releases a claim."""
    with db.write(ref.namespace) as store:
        task = db.get(store, ref)
        task.clear(fields)
        db.update(store, task)


@namespace_app.command('list')
def namespace_list() -> None:
    """List namespaces."""
    for namespace in db.namespaces():
        print(namespace)


@namespace_app.command('add')
def namespace_add(namespace: NamespaceName) -> None:
    """Add a namespace."""
    db.add_namespace(schema.normalize_name('namespace', namespace))


@namespace_app.command('delete')
def namespace_delete(namespace: NamespaceName) -> None:
    """Delete an empty namespace."""
    db.delete_namespace(schema.normalize_name('namespace', namespace))


def cli() -> None:
    try:
        app()
    except schema.TaskError as e:
        print(f'error: {e}', file=sys.stderr)
        sys.exit(1)
