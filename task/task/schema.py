import dataclasses
import datetime
import enum
import re
from collections.abc import Iterable
from collections.abc import Iterator
from typing import Self
from typing import assert_never

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
    ident: int | None = None
    tag: list[str]
    description: str | None = None

    @classmethod
    def parse(
        cls, raw: str, tag: list[str], description: str | None = None
    ) -> Self:
        ident: int | None = None
        match = re.match(r'\[(\d+)\] (.*)', raw)
        if match:
            ident = int(match.group(1))
            raw = match.group(2)

        details: Details | None
        groups = re.findall(r'(.*) {(.*)}', raw)
        if groups:
            raw, raw_details = groups[0]
            details = Details.parse(raw_details)
        else:
            details = None

        return cls(
            description=description,
            details=details,
            ident=ident,
            summary=raw,
            tag=tag,
        )

    @property
    def raw(self) -> str:
        assert self.ident is not None, 'task id has not been assigned'
        result = f'[{self.ident}] {self.summary}'
        if self.details:
            result += f' {{{self.details.raw}}}'
        return result

    def __str__(self) -> str:
        result = ''
        result += ' > '.join(x.split(maxsplit=1)[1] for x in self.tag)
        result += f'\t{self.ident}: {self.summary}'
        if self.description:
            result += ' +'
        if self.details:
            result += f'\n\t{self.details}'
        return result

    def complete(self, ago: int) -> Self | None:
        if self.details and self.details.interval:
            new_task = self.model_copy()
            assert new_task.details

            if self.details.shift:
                new_task.details.next_ = self.details.interval.apply(
                    datetime.date.today() - datetime.timedelta(days=ago)
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
                    'periodic tasks with shift=false cannot be delayed'
                )
        else:
            assert False, 'impossible task state'

        new_task.details.next_ = datetime.date.today() + datetime.timedelta(
            days=days
        )
        return new_task

    def update(
        self,
        *,
        summary: str | None = None,
        tag: str | None = None,
        next_: str | None = None,
        interval: str | None = None,
        shift: bool | None = None,
        description: str | None = None,
    ) -> None:
        if summary is not None:
            self.summary = summary
        if tag is not None:
            self.tag = [f'## {tag}']
        if description is not None:
            self.description = description.strip() or None

        if next_ is not None or interval is not None or shift is not None:
            if self.details is None:
                seed = next_ or datetime.date.today().isoformat()
                self.details = Details.model_validate({'next': seed})
            if next_ is not None:
                self.details.next_ = datetime.date.fromisoformat(next_)
            if interval is not None:
                self.details.interval = Interval(raw=interval)
            if shift is not None:
                self.details.shift = shift

    def clear(self, fields: Iterable['ClearableField']) -> None:
        for field in fields:
            if field is ClearableField.next:
                self.details = None
            elif field is ClearableField.description:
                self.description = None
            elif self.details is None:
                continue
            elif field is ClearableField.interval:
                self.details.interval = None
            elif field is ClearableField.shift:
                self.details.shift = False

    def render_detail(self) -> str:
        rows = [
            ('Summary', self.summary),
            ('ID', str(self.ident)),
            ('Tag', ' > '.join(x.split(maxsplit=1)[1] for x in self.tag)),
        ]
        if self.details:
            rows.append(('Due', self._render_due()))
            if self.details.interval:
                anchor = (
                    'after completion'
                    if self.details.shift
                    else 'since last deadline'
                )
                rows.append(
                    ('Recurrence', f'{self.details.interval} {anchor}')
                )

        width = max(len(label) for label, _ in rows)
        header = '\n'.join(
            f'{label + ":":<{width + 2}} {value}' for label, value in rows
        )
        if self.description:
            return f'{header}\n---\n{self.description}'
        return header

    def _render_due(self) -> str:
        assert self.details, 'due row requires details'
        diff = (self.details.next_ - datetime.date.today()).days
        if diff > 0:
            status = f'{diff} {"day" if diff == 1 else "days"}'
        elif diff == 0:
            status = 'due today'
        else:
            status = 'overdue'
        return f'{self.details.next_} ({status})'


class Target(enum.StrEnum):
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
                r'(?P<target>[^!=~]+)(?P<op>!?[=~])(?P<data>.*)', filter_
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


class SortOrder(enum.StrEnum):
    ident = 'id'
    due = 'due'
    tag = 'tag'


class ClearableField(enum.StrEnum):
    description = 'description'
    interval = 'interval'
    next = 'next'
    shift = 'shift'


class Preset(enum.StrEnum):
    due = 'due'
    ready = 'ready'
    highpri = 'highpri'
    triage = 'triage'
    all = 'all'


@dataclasses.dataclass(frozen=True)
class PresetConfig:
    days: int
    filter: str
    sort: SortOrder
    due_only: bool


PRESETS = {
    Preset.due: PresetConfig(0, '', SortOrder.due, True),
    Preset.ready: PresetConfig(0, '', SortOrder.tag, False),
    Preset.highpri: PresetConfig(-1, 'tag=highpri', SortOrder.due, False),
    Preset.triage: PresetConfig(-1, 'tag=triage', SortOrder.tag, False),
    Preset.all: PresetConfig(-1, '', SortOrder.tag, False),
}
