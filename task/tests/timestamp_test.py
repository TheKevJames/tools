import datetime

import hypothesis
import pytest
from hypothesis import strategies as st

from task import timestamp


@pytest.mark.parametrize(
    ('ago', 'rendered'),
    [
        (datetime.timedelta(hours=-1), 'just now'),
        (datetime.timedelta(seconds=59), 'just now'),
        (datetime.timedelta(minutes=1), '1 minute ago'),
        (datetime.timedelta(hours=2, minutes=59), '2 hours ago'),
        (datetime.timedelta(days=13), '1 week ago'),
        (datetime.timedelta(weeks=52), '1 year ago'),
        (datetime.timedelta(weeks=200), '3 years ago'),
    ],
)
def test_age_is_rendered_in_its_largest_unit(
    now: datetime.datetime, ago: datetime.timedelta, rendered: str
) -> None:
    assert timestamp.render_age(now - ago) == rendered


@hypothesis.given(
    st.datetimes(
        datetime.datetime(2000, 1, 1),
        datetime.datetime(9000, 1, 1),
        timezones=st.timezones(),
    )
)
def test_serialize_is_utc_iso_8601(value: datetime.datetime) -> None:
    serialized = timestamp.serialize(value)
    assert serialized
    assert serialized.endswith('Z')
    # Not compared with ==, which is never true across zones for times in
    # a repeated hour.
    parsed = datetime.datetime.fromisoformat(serialized)
    assert parsed.timestamp() == value.replace(microsecond=0).timestamp()
