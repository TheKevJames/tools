import datetime
import functools
import itertools
from collections.abc import Iterable
from collections.abc import Iterator

from .schema import Filter
from .schema import Task


def filter_max_ahead(task: Task, days: int) -> bool:
    if days >= 0 and task.details:
        target = datetime.date.today() + datetime.timedelta(days=days)
        if task.details.next_ > target:
            return False

    return True


def load(
    tasks: Iterable[Task], filter_: str, days: int, limit: int,
) -> Iterator[Task]:
    tasks = functools.reduce(Filter.apply, Filter.parse(filter_), tasks)
    tasks = (x for x in tasks if filter_max_ahead(x, days))
    if limit >= 0:
        tasks = itertools.islice(tasks, limit)

    yield from tasks


def load_with_next(
    tasks: Iterable[Task], filter_: str, days: int, limit: int,
) -> Iterator[Task]:
    tasks = load(tasks, filter_, days, -1)
    tasks = (x for x in tasks if x.details)
    if limit >= 0:
        tasks = itertools.islice(tasks, limit)

    yield from tasks
