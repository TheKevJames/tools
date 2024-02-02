from typing import Annotated

import typer

from . import cmd
from . import files
from . import schema


app = typer.Typer()

Ago = Annotated[int, typer.Option('-a', '--ago')]
Days = Annotated[int, typer.Option('-d', '--days')]
Filter = Annotated[str, typer.Option('-f', '--filter', help='foo=bar,baz!=bq')]
Limit = Annotated[int, typer.Option('-l', '--limit')]


@app.command('delay')
def delay(task: str, days: Days) -> None:
    tasks = list(cmd.load(files.load(), '', -1, -1))
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
    tasks = list(cmd.load(files.load(), '', -1, -1))
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
def due(filter_: Filter = '', limit: Limit = -1) -> None:
    for task in cmd.load_with_next(files.load(), filter_, 0, limit):
        print(task)


@app.command('edit')
def edit(idx: int) -> None:
    conf = files.Settings()
    # TODO(feat): open in subprocess
    print(f'$EDITOR {conf.fnames[idx]}')


@app.command('filters')
def filters() -> None:
    print('Filters:')
    for target in schema.Target:
        print(f'* {target.value}')


@app.command('highpri')
def highpri(filter_: Filter = '', days: Days = -1, limit: Limit = -1) -> None:
    for task in cmd.load(files.load(), f'{filter_},tag=highpri', days, limit):
        print(task)


@app.command('list')
def list_(filter_: Filter = '', days: Days = 7, limit: Limit = -1) -> None:
    for task in cmd.load(files.load(), filter_, days, limit):
        print(task)


@app.command('rewrite')
def rewrite() -> None:
    tasks = cmd.load(files.load(), '', -1, -1)
    files.save(tasks)


# TODO(feat): split to get/set
@app.command('settings')
def settings() -> None:
    conf = files.Settings()
    for i, fname in enumerate(conf.fnames):
        print(f'{i}\t{fname}')


@app.command('soon')
def soon(filter_: Filter = '', days: Days = 3, limit: Limit = -1) -> None:
    for task in cmd.load_with_next(files.load(), filter_, days, limit):
        print(task)


@app.command('triage')
def triage(filter_: Filter = '', days: Days = -1, limit: Limit = -1) -> None:
    for task in cmd.load(files.load(), f'{filter_},tag=triage', days, limit):
        print(task)


def cli() -> None:
    app()
