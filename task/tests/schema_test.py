import datetime

import hypothesis
import pytest
import time_machine
from hypothesis import strategies as st

from task import schema

INTERVAL = st.builds(
    lambda count, unit: schema.Interval(raw=f'{count}{unit}'),
    st.integers(1, 99),
    st.sampled_from('dwm'),
)


def month_end(date: datetime.date) -> datetime.date:
    following = date.replace(day=28) + datetime.timedelta(days=4)
    return following.replace(day=1) - datetime.timedelta(days=1)


# Far enough from date.max that any INTERVAL stays representable; month ends
# are where adding months goes wrong.
ANY_DATE = st.dates(max_value=datetime.date(9000, 1, 1))
DATE = ANY_DATE | ANY_DATE.map(month_end)


@hypothesis.given(INTERVAL, DATE)
def test_interval_moves_forward(
    interval: schema.Interval, date: datetime.date
) -> None:
    assert interval.apply(date) > date


@hypothesis.given(
    INTERVAL,
    st.dates(datetime.date(2000, 1, 1), datetime.date(2100, 1, 1)),
    st.integers(-1000, 1000),
)
def test_completing_a_fixed_schedule_moves_past_today(
    interval: schema.Interval, today: datetime.date, offset: int
) -> None:
    next_ = today + datetime.timedelta(days=offset)
    task = schema.Task(
        summary='a',
        tag='a',
        details=schema.Details.model_validate(
            {'next': next_, 'interval': interval}
        ),
    )
    noon = datetime.datetime.combine(
        today, datetime.time(12), tzinfo=datetime.UTC
    )
    with time_machine.travel(noon, tick=False):
        completed = task.complete(0)

    assert completed
    assert completed.details
    assert completed.details.next_ > max(today, next_)


@hypothesis.given(
    st.from_regex(r'[a-z0-9][a-z0-9_.-]{0,10}', fullmatch=True),
    st.integers(min_value=0),
)
def test_ref_roundtrips(namespace: str, ident: int) -> None:
    ref = schema.Ref(namespace, ident)
    assert schema.Ref.parse(str(ref)) == ref


@hypothesis.given(st.text() | st.text(' \tAZaz09_.-'))
def test_normalize_name_is_idempotent(value: str) -> None:
    try:
        name = schema.normalize_name('tag', value)
    except schema.TaskError:
        return
    assert schema.normalize_name('tag', name) == name


@pytest.mark.parametrize(
    ('raw', 'rendered'),
    [
        ('1d', 'daily'),
        ('3d', 'every 3 days'),
        ('1w', 'weekly'),
        ('2w', 'every 2 weeks'),
        ('1m', 'monthly'),
        ('12m', 'every 12 months'),
    ],
)
def test_interval_renders(raw: str, rendered: str) -> None:
    assert str(schema.Interval(raw=raw)) == rendered
