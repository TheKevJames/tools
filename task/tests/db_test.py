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
TIMESTAMP = st.datetimes(
    datetime.datetime(2000, 1, 1),
    datetime.datetime(2099, 12, 31),
    timezones=st.just(datetime.UTC),
).map(lambda x: x.replace(microsecond=0))
EPOCH = '2000-01-01T00:00:00Z'


def consistent(task: schema.Task) -> bool:
    """Recurring tasks advance rather than being done."""
    return not (task.done and task.details and task.details.interval)


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
    done=st.none() | TIMESTAMP,
).filter(consistent)

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
    done=st.none() | TIMESTAMP,
).filter(consistent)
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
    if order == query.SortOrder.created:
        assert task.created
        return (task.created, task.ident)
    if order == query.SortOrder.updated:
        assert task.updated
        return (-task.updated.timestamp(), task.ident)
    return (task.ident,)


@hypothesis.settings(max_examples=300, deadline=None)
@hypothesis.given(
    tasks=st.lists(QUERY_TASK, max_size=10),
    filters=st.lists(FILTER, max_size=2),
    days=st.integers(-1, 4),
    limit=st.integers(-1, 4),
    order=st.sampled_from(query.SortOrder),
    scheduled=st.booleans(),
    done=st.booleans(),
)
@hypothesis.example(  # a path match must be anchored at the root
    tasks=[schema.Task(summary='a', details=None, tag='a/b/a')],
    filters=['tag=b/a'],
    days=-1,
    limit=-1,
    order=query.SortOrder.ident,
    scheduled=False,
    done=False,
)
def test_query_matches_reference(  # pylint: disable=too-many-arguments
    tasks: list[schema.Task],
    filters: list[str],
    days: int,
    limit: int,
    order: query.SortOrder,
    scheduled: bool,
    done: bool,
) -> None:
    filter_ = ','.join(filters)
    clauses = query.compile_(
        filter_, days, limit, order, scheduled=scheduled, done=done
    )
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
        and (t.done is not None) == done
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
        "done = '2026-01-01'",
        "created = '2026-01-01 00:00:00'",
        f"updated = '{EPOCH}'",
        "next = '2026-01-01', interval = '1d', done = updated",
    ],
)
def test_constraints_refuse_bad_data(assignment: str) -> None:
    with task_folder():
        store([schema.Task(summary='a', details=None, tag=schema.TRIAGE)])
        with db.connect() as conn, pytest.raises(sqlite3.IntegrityError):
            conn.execute(f'UPDATE task SET {assignment}')


CONTENT = (
    'summary',
    'details',
    'tag',
    'description',
    'owner',
    'link',
    'priority',
    'size',
    'done',
)


def content(task: schema.Task) -> dict[str, object]:
    return {
        k: v
        for k, v in task.to_json().items()
        if k not in {'created', 'updated'}
    }


@hypothesis.settings(max_examples=200, deadline=None)
@hypothesis.given(TASK, TASK, st.sets(st.sampled_from(CONTENT)))
def test_updated_bumps_only_on_change(
    old: schema.Task, other: schema.Task, fields: set[str]
) -> None:
    with task_folder():
        store([old])
        ident = old.ident
        assert ident is not None
        new = old.model_copy(update={f: getattr(other, f) for f in fields})
        hypothesis.assume(consistent(new))
        with db.write() as conn:
            conn.execute(
                'UPDATE task SET created = :t, updated = :t', {'t': EPOCH}
            )
            before = db.get(conn, ident)
            db.update(conn, new)
            after = db.get(conn, ident)

    assert content(after) == content(new)
    assert after.created == before.created
    bumped = after.updated != before.updated
    assert bumped == (content(after) != content(before))
    assert new.updated == after.updated


@pytest.mark.parametrize('deleted', [[3], [1, 2, 3]])
def test_migration_keeps_tasks_and_never_reuses_ids(
    deleted: list[int],
) -> None:
    with task_folder() as folder:
        conn = sqlite3.connect(folder / 'tasks.db', isolation_level=None)
        conn.execute(db.MIGRATIONS[0])
        conn.execute('PRAGMA user_version = 1')
        conn.executemany(
            "INSERT INTO task (summary, tag, owner) VALUES (?, 'a', ?)",
            [('x', 'bot'), ('y', None), ('z', None)],
        )
        conn.executemany(
            'DELETE FROM task WHERE id = ?', [(i,) for i in deleted]
        )
        conn.close()

        added = schema.Task(summary='new', details=None, tag='a')
        with db.write() as conn:
            kept = db.select(conn, ' ORDER BY id')
            db.insert(conn, added)

    assert [(t.ident, t.summary, t.owner) for t in kept] == [
        (i, s, o)
        for i, s, o in ((1, 'x', 'bot'), (2, 'y', None))
        if i not in deleted
    ]
    assert all(t.created == t.updated and not t.done for t in kept)
    assert added.ident == 4
