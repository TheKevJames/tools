import datetime

import pytest

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
