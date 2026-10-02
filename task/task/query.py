"""Selecting and ordering tasks: filters and sort orders."""

import enum
import re
from collections.abc import Iterable
from collections.abc import Iterator
from typing import Self
from typing import assert_never

import pydantic

from . import schema


class Target(enum.StrEnum):
    summary = 'summary'
    tag = 'tag'
    owner = 'owner'
    link = 'link'
    priority = 'priority'
    size = 'size'


class Filter(pydantic.BaseModel, extra='forbid'):
    data: str
    negate: bool
    contains: bool
    target: Target

    @classmethod
    def parse(cls, raw: str) -> Iterator[Self]:
        for filter_ in raw.split(','):
            if not filter_.strip():
                continue

            match = re.match(
                r'(?P<target>[^!=~]+)(?P<op>!?[=~])(?P<data>.*)', filter_
            )
            assert match, f'{filter_} is not a valid filter'
            op = match.group('op')

            yield cls(
                data=match.group('data').lower(),
                negate=op.startswith('!'),
                contains=op.endswith('~'),
                target=Target(match.group('target')),
            )

    def match(self, value: str) -> bool:
        if self.contains:
            return self.data in value
        return self.data == value

    def func(self, task: schema.Task) -> bool:  # pylint: disable=inconsistent-return-statements
        if self.target == Target.summary:
            return self.match(task.summary.lower()) is not self.negate
        if self.target == Target.tag:
            # Any single heading or any full path from the root matches, so
            # `tag=build` and `tag=bakery/build` both select Bakery > build.
            names = [x.lower() for x in task.tag_names]
            paths = ['/'.join(names[:i]) for i in range(2, len(names) + 1)]
            matched = any(self.match(x) for x in names + paths)
            return matched is not self.negate
        if self.target == Target.owner:
            # An empty value selects unowned (claimable) tasks: `owner=`.
            return self.match((task.owner or '').lower()) is not self.negate
        if self.target == Target.link:
            return self.match((task.link or '').lower()) is not self.negate
        if self.target == Target.priority:
            return self.match(task.priority or '') is not self.negate
        if self.target == Target.size:
            return self.match(task.size or '') is not self.negate

        assert_never(self.target)

    @staticmethod
    def apply(
        tasks: Iterable[schema.Task], self: 'Filter'
    ) -> Iterator[schema.Task]:
        # TODO(refactor): weird af call signature
        yield from (x for x in tasks if self.func(x))


class SortOrder(enum.StrEnum):
    ident = 'id'
    due = 'due'
    tag = 'tag'
