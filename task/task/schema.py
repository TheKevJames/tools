import datetime
import enum
import re
from collections.abc import Iterable
from typing import Self
from typing import TypeVar

import pydantic

from . import timestamp

OWNER_RE = re.compile(r'[A-Za-z0-9_.-]+')
LINK_RE = re.compile(r'\S+')
INTERVAL_RE = re.compile(r'[1-9][0-9]*[dwm]')
TRIAGE = 'triage'


class TaskError(Exception):
    """A user-facing failure, reported without a traceback."""


def check_owner(value: str) -> str:
    if not OWNER_RE.fullmatch(value):
        raise TaskError(f'invalid owner: {value!r}')
    return value


def check_link(value: str) -> str:
    if not LINK_RE.fullmatch(value):
        raise TaskError(f'invalid link: {value!r}')
    return value


class Priority(enum.StrEnum):
    low = 'low'
    medium = 'medium'
    high = 'high'


class Size(enum.StrEnum):
    small = 'small'
    medium = 'medium'
    large = 'large'


E = TypeVar('E', bound=enum.StrEnum)


def parse_enum(kind: type[E], value: str) -> E:
    try:
        return kind(value)
    except ValueError:
        choices = ', '.join(kind)
        raise TaskError(
            f'invalid {kind.__name__.lower()}: {value!r} (use {choices})'
        ) from None


def normalize_tag(path: str) -> str:
    """`Foo/ bar` -> `foo/bar`."""
    names = [name.strip().lower() for name in path.split('/')]
    # Control characters are refused so that sorting may join segments with
    # one: see query.ORDER_BY.
    if not all(name and name.isprintable() for name in names):
        raise TaskError(f'invalid tag: {path!r}')
    return '/'.join(names)


class Interval(pydantic.BaseModel, extra='forbid'):
    raw: str

    @pydantic.field_validator('raw')
    @classmethod
    def validate_raw(cls, value: str) -> str:
        # TODO(refactor): use an enum
        if not INTERVAL_RE.fullmatch(value):
            raise TaskError(f'invalid interval: {value!r}')
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

    def __str__(self) -> str:
        result = f'Due: {self.next_}'

        if self.interval:
            result += f', repeats {self.interval}'
            if self.shift:
                result += ' after completion'
            else:
                result += ' since last deadline'

        return result


class Task(pydantic.BaseModel, extra='forbid', validate_assignment=True):
    # pylint: disable=too-many-instance-attributes
    summary: str
    details: Details | None
    ident: int | None = None
    tag: str
    description: str | None = None
    owner: str | None = None
    link: str | None = None
    priority: Priority | None = None
    size: Size | None = None
    done: pydantic.AwareDatetime | None = None
    # Assigned by the store: see db.
    created: pydantic.AwareDatetime | None = None
    updated: pydantic.AwareDatetime | None = None

    @pydantic.field_validator('summary')
    @classmethod
    def validate_summary(cls, value: str) -> str:
        if not value.strip() or '\n' in value:
            raise TaskError(f'invalid summary: {value!r}')
        return value

    @pydantic.field_validator('tag')
    @classmethod
    def validate_tag(cls, value: str) -> str:
        if normalize_tag(value) != value:
            raise TaskError(f'tag is not normalized: {value!r}')
        return value

    @pydantic.field_validator('description')
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is not None and value != value.strip():
            raise TaskError('description is not stripped')
        return value or None

    @pydantic.field_validator('owner')
    @classmethod
    def validate_owner(cls, value: str | None) -> str | None:
        return None if value is None else check_owner(value)

    @pydantic.field_validator('link')
    @classmethod
    def validate_link(cls, value: str | None) -> str | None:
        return None if value is None else check_link(value)

    @property
    def tag_names(self) -> list[str]:
        return self.tag.split('/')

    def __str__(self) -> str:
        result = ''
        result += ' > '.join(self.tag_names)
        result += f'\t{self.ident}: {self.summary}'
        if self.description:
            result += ' +'
        if self.priority:
            result += f' !{self.priority}'
        if self.owner:
            result += f' @{self.owner}'
        if self.updated:
            result += f' {timestamp.render_short_age(self.updated)}'
        if self.details:
            result += f'\n\t{self.details}'
        return result

    def complete(self, ago: int) -> Self:
        """Mark done, or advance to the next occurrence if recurring."""
        new_task = self.model_copy()
        if self.details and self.details.interval:
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
        else:
            now = datetime.datetime.now(datetime.UTC).replace(microsecond=0)
            new_task.done = now - datetime.timedelta(days=ago)
        return new_task

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

    def update(  # pylint: disable=too-many-arguments
        self,
        *,
        summary: str | None = None,
        tag: str | None = None,
        next_: str | None = None,
        interval: str | None = None,
        shift: bool | None = None,
        description: str | None = None,
        description_append: str | None = None,
        owner: str | None = None,
        link: str | None = None,
        priority: str | None = None,
        size: str | None = None,
        force: bool = False,
    ) -> None:
        if description is not None and description_append is not None:
            raise TaskError(
                '--description and --description-append are exclusive'
            )
        if summary is not None:
            self.summary = summary
        if tag is not None:
            self.tag = normalize_tag(tag)
        if description is not None:
            self.description = description.strip() or None
        if description_append is not None:
            self._append_description(description_append)
        self._set_metadata(owner, link, priority, size, force=force)
        if next_ is not None or interval is not None or shift is not None:
            self._schedule(next_, interval, shift)

    def _set_metadata(
        self,
        owner: str | None,
        link: str | None,
        priority: str | None,
        size: str | None,
        *,
        force: bool,
    ) -> None:
        if owner is not None:
            self._claim(owner, force=force)
        if link is not None:
            self.link = check_link(link)
        if priority is not None:
            self.priority = parse_enum(Priority, priority)
        if size is not None:
            self.size = parse_enum(Size, size)

    def _schedule(
        self, next_: str | None, interval: str | None, shift: bool | None
    ) -> None:
        if self.details is None:
            seed = next_ or datetime.date.today().isoformat()
            self.details = Details.model_validate({'next': seed})
        if next_ is not None:
            self.details.next_ = datetime.date.fromisoformat(next_)
        if interval is not None:
            self.details.interval = Interval(raw=interval)
        if shift is not None:
            self.details.shift = shift

    def _append_description(self, text: str) -> None:
        addition = text.strip()
        if not addition:
            return
        if self.description:
            self.description = f'{self.description}\n\n{addition}'
        else:
            self.description = addition

    def _claim(self, owner: str, *, force: bool) -> None:
        """Compare-and-set: only an unowned task may change hands."""
        check_owner(owner)
        if self.owner not in {None, owner} and not force:
            raise TaskError(f'task {self.ident} is owned by {self.owner}')
        self.owner = owner

    def clear(self, fields: Iterable['ClearableField']) -> None:
        for field in fields:
            if field is ClearableField.next:
                self.details = None
            elif field in OPTIONAL_FIELDS:
                setattr(self, field.value, None)
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
            ('Tag', ' > '.join(self.tag_names)),
        ]
        if self.owner:
            rows.append(('Owner', self.owner))
        if self.link:
            rows.append(('Link', self.link))
        if self.priority:
            rows.append(('Priority', self.priority))
        if self.size:
            rows.append(('Size', self.size))
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
        rows.extend(
            (label, timestamp.render(value))
            for label, value in (
                ('Created', self.created),
                ('Updated', self.updated),
                ('Done', self.done),
            )
            if value
        )

        width = max(len(label) for label, _ in rows)
        header = '\n'.join(
            f'{label + ":":<{width + 2}} {value}' for label, value in rows
        )
        if self.description:
            return f'{header}\n---\n{self.description}'
        return header

    def to_json(self) -> dict[str, object]:
        interval = self.details.interval if self.details else None
        return {
            'id': self.ident,
            'summary': self.summary,
            'tag': self.tag,
            'owner': self.owner,
            'link': self.link,
            'priority': self.priority,
            'size': self.size,
            'description': self.description,
            'next': self.details.next_.isoformat() if self.details else None,
            'interval': interval.raw if interval else None,
            'shift': bool(self.details and self.details.shift),
            'created': timestamp.serialize(self.created),
            'updated': timestamp.serialize(self.updated),
            'done': timestamp.serialize(self.done),
        }

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


class ClearableField(enum.StrEnum):
    description = 'description'
    interval = 'interval'
    link = 'link'
    next = 'next'
    owner = 'owner'
    priority = 'priority'
    shift = 'shift'
    size = 'size'


# Task attributes that `unset` clears to None, named as in ClearableField.
OPTIONAL_FIELDS = frozenset(
    {
        ClearableField.description,
        ClearableField.link,
        ClearableField.owner,
        ClearableField.priority,
        ClearableField.size,
    }
)
