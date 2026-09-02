import datetime
import enum
import re
from collections.abc import Iterable
from collections.abc import Iterator
from typing import assert_never
from typing import Self

import pydantic


class Interval(pydantic.BaseModel, extra='forbid'):
    raw: str

    @pydantic.field_validator('raw')
    @classmethod
    def validate_raw(cls, value: str) -> str:
        # TODO(refactor): use an enum
        assert value[-1] in {'d', 'w', 'm'}, f'{value} is not supported'
        _ = int(value[:-1])
        return value

    @property
    def value(self) -> int:
        return int(self.raw[:-1])

    def __str__(self) -> str:
        if self.raw.endswith('d'):
            if self.value == 1:
                return 'daily'
            return f'every {self.value} days'

        if self.raw.endswith('w'):
            if self.value == 1:
                return 'weekly'
            return f'every {self.value} weeks'

        if self.raw.endswith('m'):
            if self.value == 1:
                return 'monthly'
            return f'every {self.value} months'

        assert False, f'invalid interval {self.raw}'

    def apply(self, value: datetime.date) -> datetime.date:
        if self.raw.endswith('d'):
            days = self.value
            return value + datetime.timedelta(days=days)

        if self.raw.endswith('w'):
            days = self.value * 7
            return value + datetime.timedelta(days=days)

        if self.raw.endswith('m'):
            months = self.value
            tyear, tmonth = divmod(value.month - 1 + months, 12)
            return value.replace(year=value.year + tyear, month=tmonth + 1)

        assert False, f'invalid interval {self.raw}'


class Details(pydantic.BaseModel, extra='forbid'):
    interval: Interval | None = None
    next_: datetime.date = pydantic.Field(..., alias='next')
    shift: bool = False

    @property
    def raw(self) -> str:
        result = f'next: {self.next_}'
        if self.interval:
            result += f', interval: {self.interval.raw}'
        if self.shift:
            result += ', shift: true'
        return result

    @classmethod
    def parse(cls, raw: str) -> Self:
        fields: dict[str, str | dict[str, str]] = {}
        for x in raw.split(', '):
            k, v = x.split(': ')
            if k == 'interval':
                fields['interval'] = {'raw': v}
            else:
                fields[k] = v
        return cls.model_validate(fields)

    def __str__(self) -> str:
        result = f'Due: {self.next_}'

        if self.interval:
            result += f', repeats {self.interval}'
            if self.shift:
                result += ' after completion'
            else:
                result += ' since last deadline'

        return result


class Task(pydantic.BaseModel, extra='forbid'):
    summary: str
    details: Details | None
    ident: int
    tag: list[str]

    @classmethod
    def parse(cls, raw: str, tag: list[str], ident: int) -> Self:
        details: Details | None
        groups = re.findall(r'(.*) {(.*)}', raw)
        if groups:
            raw, raw_details = groups[0]
            details = Details.parse(raw_details)
        else:
            details = None

        return cls(details=details, ident=ident, summary=raw, tag=tag)

    @property
    def raw(self) -> str:
        result = self.summary
        if self.details:
            result += f' {{{self.details.raw}}}'
        return result

    def __str__(self) -> str:
        result = ''
        result += ' > '.join(x.split(maxsplit=1)[1] for x in self.tag)
        result += f'\t{self.ident}: {self.summary}'
        if self.details:
            result += f'\n\t{self.details}'
        return result

    def complete(self, ago: int) -> Self | None:
        if self.details and self.details.interval:
            new_task = self.model_copy()
            assert new_task.details

            if self.details.shift:
                new_task.details.next_ = self.details.interval.apply(
                    datetime.date.today() - datetime.timedelta(days=ago),
                )
            else:
                next_ = self.details.interval.apply(self.details.next_)
                while next_ <= datetime.date.today():
                    next_ = self.details.interval.apply(next_)
                new_task.details.next_ = next_
            return new_task
        return None

    def postpone(self, days: int) -> Self:
        new_task = self.model_copy()
        if not new_task.details:
            details = {'next': datetime.date.today()}
            new_task.details = Details.model_validate(details)
        elif self.details:
            if self.details.interval and not self.details.shift:
                raise AssertionError(
                    'periodic tasks with shift=false cannot be delayed',
                )
        else:
            assert False, 'impossible task state'

        new_task.details.next_ = (
            datetime.date.today()
            + datetime.timedelta(days=days)
        )
        return new_task


class Target(str, enum.Enum):
    summary = 'summary'
    tag = 'tag'


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
                r'(?P<target>[^!=~]+)(?P<op>!?[=~])(?P<data>.*)', filter_,
            )
            assert match, f'{filter_} is not a valid filter'
            op = match.group('op')

            yield cls(
                data=match.group('data'),
                negate=op.startswith('!'),
                contains=op.endswith('~'),
                target=Target(match.group('target')),
            )

    def match(self, value: str) -> bool:
        if self.contains:
            return self.data in value
        return self.data == value

    def func(self, task: Task) -> bool:  # pylint: disable=inconsistent-return-statements
        if self.target == Target.summary:
            return self.match(task.summary.lower()) is not self.negate
        if self.target == Target.tag:
            matched = any(
                self.match(t.split(maxsplit=1)[1].lower()) for t in task.tag
            )
            return matched is not self.negate

        assert_never(self.target)

    @staticmethod
    def apply(tasks: Iterable[Task], self: 'Filter') -> Iterator[Task]:
        # TODO(refactor): weird af call signature
        yield from (x for x in tasks if self.func(x))


class SortOrder(str, enum.Enum):
    ident = 'id'
    due = 'due'
    tag = 'tag'
