import datetime

import hypothesis
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
