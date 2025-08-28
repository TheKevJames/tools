import os
import subprocess
from typing import Annotated

import typer

from . import command
from . import files
from . import schema


app = typer.Typer()

Ago = Annotated[int, typer.Option('-a', '--ago')]
Days = Annotated[int, typer.Option('-d', '--days')]
Filter = Annotated[str, typer.Option('-f', '--filter', help='foo=bar,baz!=bq')]
Limit = Annotated[int, typer.Option('-l', '--limit')]
Sort = Annotated[schema.SortOrder, typer.Option('-s', '--sort')]


@app.command('add')
def add(idx: int, task: str) -> None:
    conf = files.Settings()
    tasks = list(command.load(files.load()))

    # TODO: allow adding details
    details = None
    link = schema.Link(fname=conf.fnames[idx], ftitle='x', lineno=-1)
    added = schema.Task(
        summary=task, details=details, link=link, tag=['## Triage'],
    )
    tasks.append(added)
    files.save(tasks)


@app.command('delay')
def delay(task: str, days: Days) -> None:
    tasks = list(command.load(files.load()))
    item = next((x for x in tasks if str(x.link) == task), None)
    assert item, f'task {task} not found!'

    delayed = item.postpone(days)
    assert delayed.details, 'delayed task has no details'
    print(f'delayed task, next occurrence: {delayed.details.next_}')

    tasks.pop(tasks.index(item))
    tasks.append(delayed)
    files.save(tasks)


@app.command('done')
def done(task: str, ago: Ago = 0) -> None:
    tasks = list(command.load(files.load()))
    item = next((x for x in tasks if str(x.link) == task), None)
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
    # TODO: column-aligned printing
    for task in command.load_with_next(files.load(), filter_, 0, limit, sort):
        print(task)


# TODO: allow editing a task ID? eg. open with cursor on correct line
# TODO: instead of indices, should use ftitle[0].lower()
@app.command('edit')
def edit(idx: int) -> None:
    conf = files.Settings()
    subprocess.run(
        [os.environ.get('EDITOR', 'vim'), conf.fnames[idx]],
        check=True,
    )


@app.command('filters')
def filters() -> None:
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
    for task in command.load(files.load(), filter_, days, limit, sort):
        print(task)


@app.command('rewrite')
def rewrite() -> None:
    files.save(command.load(files.load()))


# TODO(feat): split to get/set
@app.command('settings')
def settings() -> None:
    conf = files.Settings()
    for i, fname in enumerate(conf.fnames):
        print(f'{i}\t{fname}')


@app.command('soon')
def soon(
        days: Days = 3,
        filter_: Filter = '',
        limit: Limit = -1,
        sort: Sort = schema.SortOrder.due,
) -> None:
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
    filt = f'{filter_},tag=triage'
    for task in command.load(files.load(), filt, days, limit, sort):
        print(task)


def cli() -> None:
    app()
