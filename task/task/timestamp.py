"""Timestamps: stored as UTC ISO 8601, rendered locally with an age."""

import datetime

FORMAT = '%Y-%m-%dT%H:%M:%SZ'
AGE_UNITS = (
    ('year', 52 * 7 * 86400),
    ('week', 7 * 86400),
    ('day', 86400),
    ('hour', 3600),
    ('minute', 60),
)


def serialize(value: datetime.datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(datetime.UTC).strftime(FORMAT)


def age(value: datetime.datetime) -> tuple[int, str] | None:
    """Time since `value` in its largest whole unit; None if under one."""
    seconds = (datetime.datetime.now(datetime.UTC) - value).total_seconds()
    for unit, length in AGE_UNITS:
        if seconds >= length:
            return int(seconds // length), unit
    return None


def render_age(value: datetime.datetime) -> str:
    """`3 hours ago`."""
    match age(value):
        case None:
            return 'just now'
        case 1, unit:
            return f'1 {unit} ago'
        case count, unit:
            return f'{count} {unit}s ago'


def render_short_age(value: datetime.datetime) -> str:
    """`~3h`."""
    match age(value):
        case None:
            return '~now'
        case count, unit:
            return f'~{count}{unit[0]}'


def render(value: datetime.datetime) -> str:
    local = value.astimezone().strftime('%Y-%m-%d %H:%M')
    return f'{local} ({render_age(value)})'
