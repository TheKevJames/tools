import datetime
import functools
import itertools
from collections.abc import Iterable
from collections.abc import Iterator

from . import schema


def _next_date(task: schema.Task) -> datetime.date:
    assert task.details is not None, '_next_date requires tasks with details'
    return task.details.next_


def filter_max_ahead(task: schema.Task, days: int) -> bool:
    if days >= 0 and task.details:
        target = datetime.date.today() + datetime.timedelta(days=days)
        if task.details.next_ > target:
            return False

    return True


def sort(
    tasks: Iterable[schema.Task], order: schema.SortOrder
) -> Iterator[schema.Task]:
    if order == schema.SortOrder.due:
        tasks = list(tasks)
        lhs = (t for t in tasks if t.details is None)
        rhs: Iterable[schema.Task] = (
            t for t in tasks if t.details is not None
        )
        rhs = sorted(rhs, key=_next_date)
        tasks = itertools.chain(lhs, rhs)
    elif order == schema.SortOrder.ident:
        tasks = sorted(tasks, key=lambda t: t.ident or 0)
    elif order == schema.SortOrder.tag:
        tasks = sorted(tasks, key=lambda t: t.tag)

    yield from tasks


def load(
    tasks: Iterable[schema.Task],
    filter_: str = '',
    days: int = -1,
    limit: int = -1,
    order: schema.SortOrder = schema.SortOrder.ident,
) -> Iterator[schema.Task]:
    tasks = functools.reduce(
        schema.Filter.apply, schema.Filter.parse(filter_), tasks
    )
    tasks = (x for x in tasks if filter_max_ahead(x, days))
    if limit >= 0:
        tasks = itertools.islice(tasks, limit)

    yield from sort(tasks, order)


def load_with_next(
    tasks: Iterable[schema.Task],
    filter_: str = '',
    days: int = -1,
    limit: int = -1,
    order: schema.SortOrder = schema.SortOrder.ident,
) -> Iterator[schema.Task]:
    tasks = load(tasks, filter_, days, -1)
    tasks = (x for x in tasks if x.details)
    if limit >= 0:
        tasks = itertools.islice(tasks, limit)

    yield from sort(tasks, order)
