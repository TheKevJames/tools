import os
import subprocess
from typing import Annotated

import typer

from . import command
from . import files
from . import schema


app = typer.Typer(add_completion=False)

Ago = Annotated[int, typer.Option('-a', '--ago')]
Days = Annotated[int, typer.Option('-d', '--days')]
Filter = Annotated[
    str, typer.Option(
        '-f', '--filter', help='tag=bar,summary!~bq',
    ),
]
Limit = Annotated[int, typer.Option('-l', '--limit')]
Sort = Annotated[schema.SortOrder, typer.Option('-s', '--sort')]


@app.command('add')
def add(task: str) -> None:
    """Add a new task to the task file."""
    tasks = list(command.load(files.load()))

    # TODO: allow adding details
    details = None
    added = schema.Task(
        summary=task, details=details, ident=-1, tag=['## Triage'],
    )
    tasks.append(added)
    files.save(tasks)


@app.command('delay')
def delay(task: str, days: Days) -> None:
    """Postpone a task by the given number of days."""
    tasks = list(command.load(files.load()))
    item = next((x for x in tasks if str(x.ident) == task), None)
    assert item, f'task {task} not found!'

    delayed = item.postpone(days)
    assert delayed.details, 'delayed task has no details'
    print(f'delayed task, next occurrence: {delayed.details.next_}')

    tasks.pop(tasks.index(item))
    tasks.append(delayed)
    files.save(tasks)


@app.command('done')
def done(task: str, ago: Ago = 0) -> None:
    """Mark a task as completed, optionally some days ago."""
    tasks = list(command.load(files.load()))
    item = next((x for x in tasks if str(x.ident) == task), None)
    assert item, f'task {task} not found!'

    completed = item.complete(ago)
    if not completed:
        print('completed task')
        tasks.pop(tasks.index(item))
        files.save(tasks)
        return

    assert completed.details, 'completed recurring task has no details'
    print(
        'completed recurring task, next occurrence: '
        f'{completed.details.next_}',
    )
    tasks.pop(tasks.index(item))
    tasks.append(completed)
    files.save(tasks)


@app.command('due')
def due(
        filter_: Filter = '',
        limit: Limit = -1,
        sort: Sort = schema.SortOrder.due,
) -> None:
    """List tasks that are currently due."""
    # TODO: column-aligned printing
    for task in command.load_with_next(files.load(), filter_, 0, limit, sort):
        print(task)


# TODO: allow editing a task ID? eg. open with cursor on correct line
@app.command('edit')
def edit() -> None:
    """Open the task file in $EDITOR."""
    subprocess.run(
        [os.environ.get('EDITOR', 'vim'), files.TASK_FILE],
        check=True,
    )


@app.command('filters')
def filters() -> None:
    """Show the available filter targets."""
    print('Filters:')
    for target in schema.Target:
        print(f'* {target.value}')


@app.command('highpri')
def highpri(
        days: Days = -1,
        filter_: Filter = '',
        limit: Limit = -1,
        sort: Sort = schema.SortOrder.due,
) -> None:
    """List high-priority tasks."""
    filt = f'{filter_},tag=highpri'
    for task in command.load(files.load(), filt, days, limit, sort):
        print(task)


@app.command('list')
def list_(
        days: Days = 7,
        filter_: Filter = '',
        limit: Limit = -1,
        sort: Sort = schema.SortOrder.ident,
) -> None:
    """List tasks, by default those due within the next week."""
    for task in command.load(files.load(), filter_, days, limit, sort):
        print(task)


@app.command('rewrite')
def rewrite() -> None:
    """Reformat and rewrite the task files in place."""
    files.save(command.load(files.load()))


@app.command('soon')
def soon(
        days: Days = 3,
        filter_: Filter = '',
        limit: Limit = -1,
        sort: Sort = schema.SortOrder.due,
) -> None:
    """List tasks due soon, by default within three days."""
    for task in command.load_with_next(
            files.load(), filter_, days, limit, sort,
    ):
        print(task)


@app.command('triage')
def triage(
        days: Days = -1,
        filter_: Filter = '',
        limit: Limit = -1,
        sort: Sort = schema.SortOrder.ident,
) -> None:
    """List tasks tagged for triage."""
    filt = f'{filter_},tag=triage'
    for task in command.load(files.load(), filt, days, limit, sort):
        print(task)


def cli() -> None:
    app()
