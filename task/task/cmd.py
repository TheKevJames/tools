import datetime
import functools
import itertools
from collections.abc import Iterable
from collections.abc import Iterator

from .schema import Filter
from .schema import SortOrder
from .schema import Task


def filter_max_ahead(task: Task, days: int) -> bool:
    if days >= 0 and task.details:
        target = datetime.date.today() + datetime.timedelta(days=days)
        if task.details.next_ > target:
            return False

    return True


def sort(tasks: Iterable[Task], order: SortOrder) -> Iterator[Task]:
    if order == SortOrder.due:
        tasks = list(tasks)
        lhs = (t for t in tasks if t.details is None)
        rhs: Iterable[Task] = (t for t in tasks if t.details is not None)
        rhs = sorted(
            rhs, key=lambda t: t.details.next_,  # type: ignore[union-attr]
        )
        tasks = itertools.chain(lhs, rhs)
    elif order == SortOrder.ident:
        tasks = sorted(tasks, key=lambda t: t.link)
    elif order == SortOrder.tag:
        tasks = sorted(tasks, key=lambda t: t.tag)

    yield from tasks


def load(
        tasks: Iterable[Task],
        filter_: str = '',
        days: int = -1,
        limit: int = -1,
        order: SortOrder = SortOrder.ident,
) -> Iterator[Task]:
    tasks = functools.reduce(Filter.apply, Filter.parse(filter_), tasks)
    tasks = (x for x in tasks if filter_max_ahead(x, days))
    if limit >= 0:
        tasks = itertools.islice(tasks, limit)

    yield from sort(tasks, order)


def load_with_next(
        tasks: Iterable[Task],
        filter_: str = '',
        days: int = -1,
        limit: int = -1,
        order: SortOrder = SortOrder.ident,
) -> Iterator[Task]:
    tasks = load(tasks, filter_, days, -1)
    tasks = (x for x in tasks if x.details)
    if limit >= 0:
        tasks = itertools.islice(tasks, limit)

    yield from sort(tasks, order)
