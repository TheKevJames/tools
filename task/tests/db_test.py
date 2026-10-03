import contextlib
import datetime
import os
import pathlib
import sqlite3
import string
import tempfile
from collections.abc import Generator

import hypothesis
import pytest
from hypothesis import strategies as st

from task import db
from task import query
from task import schema

NAME = st.text(string.ascii_letters + string.digits, min_size=1, max_size=8)
SEGMENT = (
    st.text(
        st.characters(categories=['L', 'N', 'P', 'S'], exclude_characters='/')
        | st.just(' '),
        min_size=1,
        max_size=8,
    )
    .map(lambda x: x.strip().lower())
    .filter(lambda x: x and x.isprintable() and '/' not in x)
)
SUMMARY = st.text(
    st.characters(exclude_categories=['Cs'], exclude_characters='\n'),
    min_size=1,
    max_size=30,
).filter(str.strip)
DESCRIPTION = st.text(
    string.ascii_letters + string.digits + string.punctuation + ' \n',
    max_size=80,
).map(lambda x: x.strip() or None)
OWNER = st.none() | st.from_regex(schema.OWNER_RE, fullmatch=True)
LINK = st.none() | st.builds(
    lambda repo, path, line: (
        f'https://github.com/TheKevJames/{repo}/blob/HEAD/{path}#L{line}'
    ),
    NAME,
    NAME,
    st.integers(min_value=1),
)
INTERVAL = st.builds(
    lambda count, unit: f'{count}{unit}',
    st.integers(1, 99),
    st.sampled_from('dwm'),
)


def details(
    dates: st.SearchStrategy[datetime.date],
) -> st.SearchStrategy[schema.Details | None]:
    return st.none() | st.builds(
        lambda next_, interval, shift: schema.Details.model_validate(
            {
                'next': next_,
                'interval': interval and {'raw': interval},
                'shift': shift,
            }
        ),
        dates,
        st.none() | INTERVAL,
        st.booleans(),
    )


TASK = st.builds(
    schema.Task,
    summary=SUMMARY,
    details=details(st.dates()),
    tag=st.lists(SEGMENT, min_size=1, max_size=3).map('/'.join),
    description=DESCRIPTION,
    owner=OWNER,
    link=LINK,
    priority=st.none() | st.sampled_from(schema.Priority),
    size=st.none() | st.sampled_from(schema.Size),
)

# Small alphabets, so that filters often match. Tag segments include ones
# sorting either side of `/`, and summaries non-ASCII case.
TODAY = datetime.date.today()
QUERY_TAG = st.lists(
    st.sampled_from(['a', 'a!', 'é', schema.TRIAGE]), min_size=1, max_size=3
).map('/'.join)
QUERY_TASK = st.builds(
    schema.Task,
    summary=st.text('aAbÉé ', min_size=1, max_size=3).filter(str.strip),
    details=details(
        st.dates(TODAY - datetime.timedelta(3), TODAY + datetime.timedelta(5))
    ),
    tag=QUERY_TAG,
    owner=st.sampled_from([None, 'a', 'A', 'b']),
    link=st.sampled_from([None, 'a', 'A/b']),
    priority=st.none() | st.sampled_from(schema.Priority),
    size=st.none() | st.sampled_from(schema.Size),
)
FILTER = st.builds(
    lambda target, op, data: f'{target}{op}{data}',
    st.sampled_from(query.Target),
    st.sampled_from(['=', '!=', '~', '!~']),
    st.sampled_from(['', 'high', 'small'])
    | QUERY_TAG
    | st.text('aAbÉé/! ', max_size=4),
)


@contextlib.contextmanager
def task_folder() -> Generator[pathlib.Path]:
    with tempfile.TemporaryDirectory() as folder:
        os.environ['TASK_FOLDER'] = folder
        yield pathlib.Path(folder)


def store(tasks: list[schema.Task]) -> None:
    with db.write() as conn:
        for task in tasks:
            db.insert(conn, task)


@hypothesis.settings(max_examples=200, deadline=None)
@hypothesis.given(st.lists(TASK, max_size=12))
def test_save_load_roundtrip(tasks: list[schema.Task]) -> None:
    with task_folder():
        store(tasks)
        with db.connect() as conn:
            loaded = db.select(conn, ' ORDER BY id')

    assert loaded == tasks


def reference_match(filter_: query.Filter, task: schema.Task) -> bool:
    if filter_.target == query.Target.tag:
        names = task.tag_names
        paths = ['/'.join(names[:i]) for i in range(2, len(names) + 1)]
        candidates = names + paths
    else:
        value = {
            query.Target.summary: task.summary,
            query.Target.owner: task.owner,
            query.Target.link: task.link,
            query.Target.priority: task.priority,
            query.Target.size: task.size,
        }[filter_.target]
        candidates = [(value or '').lower()]

    if filter_.contains:
        matched = any(filter_.data in x for x in candidates)
    else:
        matched = filter_.data in candidates
    return matched is not filter_.negate


def reference_key(
    order: query.SortOrder, task: schema.Task
) -> tuple[object, ...]:
    if order == query.SortOrder.due:
        next_ = task.details.next_ if task.details else datetime.date.min
        return (task.details is not None, next_, task.ident)
    if order == query.SortOrder.tag:
        return (task.tag != schema.TRIAGE, task.tag_names, task.ident)
    return (task.ident,)


@hypothesis.settings(max_examples=300, deadline=None)
@hypothesis.given(
    tasks=st.lists(QUERY_TASK, max_size=10),
    filters=st.lists(FILTER, max_size=2),
    days=st.integers(-1, 4),
    limit=st.integers(-1, 4),
    order=st.sampled_from(query.SortOrder),
    scheduled=st.booleans(),
)
@hypothesis.example(  # a path match must be anchored at the root
    tasks=[schema.Task(summary='a', details=None, tag='a/b/a')],
    filters=['tag=b/a'],
    days=-1,
    limit=-1,
    order=query.SortOrder.ident,
    scheduled=False,
)
def test_query_matches_reference(  # pylint: disable=too-many-arguments
    tasks: list[schema.Task],
    filters: list[str],
    days: int,
    limit: int,
    order: query.SortOrder,
    scheduled: bool,
) -> None:
    filter_ = ','.join(filters)
    clauses = query.compile_(filter_, days, limit, order, scheduled=scheduled)
    with task_folder():
        store(tasks)
        with db.connect() as conn:
            selected = [t.ident for t in db.select(conn, *clauses)]

    target = TODAY + datetime.timedelta(days=days)
    expected = [
        t
        for t in tasks
        if all(reference_match(f, t) for f in query.Filter.parse(filter_))
        and (days < 0 or not t.details or t.details.next_ <= target)
        and (t.details or not scheduled)
    ]
    expected.sort(key=lambda t: reference_key(order, t))
    if limit >= 0:
        expected = expected[:limit]
    assert selected == [t.ident for t in expected]


@pytest.mark.parametrize(
    'assignment',
    [
        "summary = ''",
        "summary = 'a' || char(10) || 'b'",
        "tag = 'Triage'",
        "next = '2026-02-30'",
        "next = '2026-01-01', interval = '0d'",
        "next = '2026-01-01', interval = '1y'",
        "next = '2026-01-01', interval = '1x1d'",
        'shift = 1',
        "owner = 'a b'",
        "link = 'a b'",
        "priority = 'urgent'",
        "size = 'huge'",
    ],
)
def test_constraints_refuse_bad_data(assignment: str) -> None:
    with task_folder():
        store([schema.Task(summary='a', details=None, tag=schema.TRIAGE)])
        with db.connect() as conn, pytest.raises(sqlite3.IntegrityError):
            conn.execute(f'UPDATE task SET {assignment}')
