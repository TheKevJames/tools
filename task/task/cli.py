import json
import os
import pathlib
import subprocess
import sys
import tempfile
from typing import Annotated

import typer
from typer import _click
from typer import core

from . import command
from . import files
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
file_app = typer.Typer(
    add_completion=False, help='Operate on the whole task file.'
)
app.add_typer(file_app, name='file')


@app.callback()
def main(ctx: typer.Context) -> None:
    """Simple personal task manager, shared by humans and bots."""
    ctx.with_resource(files.locked())


Ago = Annotated[int, typer.Option('-a', '--ago')]
Days = Annotated[int | None, typer.Option('-d', '--days')]
Filter = Annotated[
    str | None, typer.Option('-f', '--filter', help='tag=bar,summary!~bq')
]
Limit = Annotated[int | None, typer.Option('-l', '--limit')]
Preset = Annotated[query.Preset, typer.Option('-p', '--preset')]
Sort = Annotated[query.SortOrder | None, typer.Option('-s', '--sort')]
AsJson = Annotated[bool, typer.Option('--json', help='Machine-readable.')]

# Shared detail flags: `add` and `set` funnel these into Task.update, keeping a
# single source of truth for task modifications.
Summary = Annotated[str | None, typer.Option('--summary')]
Tag = Annotated[
    str | None, typer.Option('--tag', help='Section path, eg. Bakery/build')
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


def require(tasks: list[schema.Task], ident: int) -> schema.Task:
    item = next((x for x in tasks if x.ident == ident), None)
    assert item, f'task {ident} not found!'
    return item


@app.command('list')
def list_(
    preset: Preset = query.Preset.due,
    days: Days = None,
    filter_: Filter = None,
    limit: Limit = None,
    sort: Sort = None,
    as_json: AsJson = False,
) -> None:
    """List tasks using a preset view; explicit flags override the preset."""
    cfg = query.PRESETS[preset]
    filt = ','.join(x for x in (filter_ or '', cfg.filter) if x)
    reader = command.load_with_next if cfg.due_only else command.load
    tasks = reader(
        files.load(),
        filt,
        cfg.days if days is None else days,
        -1 if limit is None else limit,
        cfg.sort if sort is None else sort,
    )
    if as_json:
        print(json.dumps([t.to_json() for t in tasks], indent=2))
        return
    for task in tasks:
        print(task)


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
    tasks = list(command.load(files.load()))
    task = schema.Task(summary=summary, details=None, tag=['## Triage'])
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
    tasks.append(task)
    files.save(tasks)


@app.command('show', rich_help_panel=SUBJECT_PANEL)
def show(ident: int, as_json: AsJson = False) -> None:
    """Show a task's full details and status."""
    task = require(list(command.load(files.load())), ident)
    if as_json:
        print(json.dumps(task.to_json(), indent=2))
        return
    print(task.render_detail())


@app.command('done', rich_help_panel=SUBJECT_PANEL)
def done(ident: int, ago: Ago = 0) -> None:
    """Mark a task as completed, optionally some days ago."""
    tasks = list(command.load(files.load()))
    item = require(tasks, ident)

    completed = item.complete(ago)
    if not completed:
        print('completed task')
        tasks.pop(tasks.index(item))
        files.save(tasks)
        return

    assert completed.details, 'completed recurring task has no details'
    print(
        f'completed recurring task, next occurrence: {completed.details.next_}'
    )
    tasks.pop(tasks.index(item))
    tasks.append(completed)
    files.save(tasks)


@app.command('delay', rich_help_panel=SUBJECT_PANEL)
def delay(ident: int, days: int) -> None:
    """Postpone a task by the given number of days."""
    tasks = list(command.load(files.load()))
    item = require(tasks, ident)

    delayed = item.postpone(days)
    assert delayed.details, 'delayed task has no details'
    print(f'delayed task, next occurrence: {delayed.details.next_}')

    tasks.pop(tasks.index(item))
    tasks.append(delayed)
    files.save(tasks)


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
    tasks = list(command.load(files.load()))
    require(tasks, ident).update(
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
    files.save(tasks)


@app.command('describe', rich_help_panel=SUBJECT_PANEL)
def describe(ident: int) -> None:
    """Edit a task's description in $EDITOR."""
    tasks = list(command.load(files.load()))
    item = require(tasks, ident)

    with tempfile.NamedTemporaryFile(
        'w', suffix='.md', delete=False, encoding='utf-8'
    ) as f:
        f.write(item.description or '')
        path = pathlib.Path(f.name)

    subprocess.run([os.environ.get('EDITOR', 'vim'), path], check=True)
    item.update(description=path.read_text(encoding='utf-8'))
    path.unlink()

    files.save(tasks)


@app.command('unset', rich_help_panel=SUBJECT_PANEL)
def unset(ident: int, fields: list[schema.ClearableField]) -> None:
    """Clear fields from a task; `unset <id> owner` releases a claim."""
    tasks = list(command.load(files.load()))
    require(tasks, ident).clear(fields)
    files.save(tasks)


@file_app.command('edit')
def file_edit() -> None:
    """Open the task file in $EDITOR."""
    subprocess.run(
        [os.environ.get('EDITOR', 'vim'), files.index_file()], check=True
    )


@file_app.command('rewrite')
def file_rewrite() -> None:
    """Reformat and rewrite the task file in place."""
    files.save(command.load(files.load()))


def cli() -> None:
    try:
        app()
    except schema.TaskError as e:
        print(f'error: {e}', file=sys.stderr)
        sys.exit(1)
