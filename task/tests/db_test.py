import contextlib
import datetime
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
TAG = st.from_regex(r'[a-z0-9][a-z0-9_.-]{0,7}', fullmatch=True)
NAMESPACES = (schema.DEFAULT, 'b', 'c.d')
NAMESPACE = st.sampled_from(NAMESPACES)
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
EPOCH = '2000-01-01T00:00:00Z'


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
    namespace=NAMESPACE,
    tag=TAG,
    description=DESCRIPTION,
    owner=OWNER,
    link=LINK,
    priority=st.none() | st.sampled_from(schema.Priority),
    size=st.none() | st.sampled_from(schema.Size),
)

# Small alphabets, so that filters often match, and summaries non-ASCII case.
QUERY_NAME = st.sampled_from(['a', 'a-b', 'b', schema.TRIAGE, schema.DEFAULT])


def query_task(today: datetime.date) -> st.SearchStrategy[schema.Task]:
    return st.builds(
        schema.Task,
        summary=st.text('aAbÉé ', min_size=1, max_size=3).filter(str.strip),
        details=details(
            st.dates(
                today - datetime.timedelta(3), today + datetime.timedelta(5)
            )
        ),
        namespace=st.sampled_from([schema.DEFAULT, 'a', 'b']),
        tag=QUERY_NAME,
        owner=st.sampled_from([None, 'a', 'A', 'b']),
        link=st.sampled_from([None, 'a', 'A/b']),
        priority=st.none() | st.sampled_from(schema.Priority),
        size=st.none() | st.sampled_from(schema.Size),
    )


FILTER_VALUE = (
    st.sampled_from(['', 'high', 'small'])
    | QUERY_NAME
    | st.text('aAbÉé-! ', max_size=4)
)
# (field, operator, value): `list -f` syntax, joined only when queried.
FILTER = st.tuples(
    st.sampled_from(
        ['summary', 'namespace', 'tag', 'owner', 'link', 'priority', 'size']
    ),
    st.sampled_from(['=', '!=', '~', '!~']),
    FILTER_VALUE | FILTER_VALUE.map(str.upper),
)


@contextlib.contextmanager
def task_folder() -> Generator[pathlib.Path]:
    """An empty store per hypothesis example, which fixtures cannot give."""
    with (
        tempfile.TemporaryDirectory() as folder,
        pytest.MonkeyPatch.context() as monkeypatch,
    ):
        monkeypatch.setenv('TASK_FOLDER', folder)
        yield pathlib.Path(folder)


def store(tasks: list[schema.Task]) -> None:
    namespaces = {task.namespace for task in tasks}
    for namespace in namespaces - {schema.DEFAULT}:
        db.add_namespace(namespace)
    with db.write(schema.DEFAULT, *namespaces) as conn:
        for task in tasks:
            db.insert(conn, task)


def location(task: schema.Task) -> tuple[str, int | None]:
    return task.namespace, task.ident


@hypothesis.settings(max_examples=200, deadline=None)
@hypothesis.given(st.lists(TASK, max_size=12))
def test_save_load_roundtrip(tasks: list[schema.Task]) -> None:
    with task_folder():
        store(tasks)
        with db.connect() as conn:
            loaded = db.select(conn, ' ORDER BY namespace, id')

    assert loaded == sorted(tasks, key=location)


def reference_match(filter_: tuple[str, str, str], task: schema.Task) -> bool:
    field, op, value = filter_
    candidate = str(getattr(task, field) or '').lower()
    if op.endswith('~'):
        matched = value.lower() in candidate
    else:
        matched = value.lower() == candidate
    return matched != op.startswith('!')


def reference_key(
    order: query.SortOrder, task: schema.Task
) -> tuple[object, ...]:
    if order == query.SortOrder.tag:
        return (
            task.namespace != schema.DEFAULT,
            task.namespace,
            task.tag != schema.TRIAGE,
            task.tag,
            task.ident,
        )
    if order == query.SortOrder.due:
        next_ = task.details.next_ if task.details else datetime.date.min
        key: tuple[object, ...] = (task.details is not None, next_)
    elif order == query.SortOrder.created:
        assert task.created
        key = (task.created,)
    elif order == query.SortOrder.updated:
        assert task.updated
        key = (-task.updated.timestamp(),)
    else:
        key = ()
    return (*key, task.ident, task.namespace)


# The clock stays stopped across examples, which is what they need.
@hypothesis.settings(
    max_examples=300,
    deadline=None,
    suppress_health_check=[hypothesis.HealthCheck.function_scoped_fixture],
)
@hypothesis.given(
    data=st.data(),
    filters=st.lists(FILTER, max_size=2),
    days=st.integers(-1, 4),
    limit=st.integers(-1, 4),
    order=st.sampled_from(query.SortOrder),
    scheduled=st.booleans(),
)
def test_query_matches_reference(  # pylint: disable=too-many-arguments
    today: datetime.date,
    data: st.DataObject,
    filters: list[tuple[str, str, str]],
    days: int,
    limit: int,
    order: query.SortOrder,
    scheduled: bool,
) -> None:
    tasks = data.draw(st.lists(query_task(today), max_size=10))
    filter_ = ','.join(''.join(f) for f in filters)
    clauses = query.compile_(filter_, days, limit, order, scheduled=scheduled)
    with task_folder():
        store(tasks)
        with db.connect() as conn:
            selected = [location(t) for t in db.select(conn, *clauses)]

    target = today + datetime.timedelta(days=days)
    expected = [
        t
        for t in tasks
        if all(reference_match(f, t) for f in filters)
        and (days < 0 or not t.details or t.details.next_ <= target)
        and (t.details or not scheduled)
    ]
    expected.sort(key=lambda t: reference_key(order, t))
    if limit >= 0:
        expected = expected[:limit]
    assert selected == [location(t) for t in expected]


@pytest.mark.parametrize(
    'assignment',
    [
        "summary = ''",
        "summary = 'a' || char(10) || 'b'",
        "tag = 'Triage'",
        "tag = 'a/b'",
        "tag = '-a'",
        "next = '2026-02-30'",
        "next = '2026-01-01', interval = '0d'",
        "next = '2026-01-01', interval = '1y'",
        "next = '2026-01-01', interval = '1x1d'",
        'shift = 1',
        "owner = 'a b'",
        "link = 'a b'",
        "priority = 'urgent'",
        "size = 'huge'",
        "created = '2026-01-01 00:00:00'",
        f"updated = '{EPOCH}'",
    ],
)
@pytest.mark.usefixtures('folder')
def test_constraints_refuse_bad_data(assignment: str) -> None:
    store([schema.Task(summary='a', details=None, tag=schema.TRIAGE)])
    with db.connect() as conn, pytest.raises(sqlite3.IntegrityError):
        conn.conn.execute(
            f'UPDATE {conn.table(schema.DEFAULT)} SET {assignment}'
        )


CONTENT = (
    'summary',
    'details',
    'tag',
    'description',
    'owner',
    'link',
    'priority',
    'size',
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
        new = old.model_copy(update={f: getattr(other, f) for f in fields})
        with db.write(old.namespace) as conn:
            conn.conn.execute(
                f'UPDATE {conn.table(old.namespace)}'
                ' SET created = :t, updated = :t',
                {'t': EPOCH},
            )
            before = db.get(conn, old.ref)
            db.update(conn, new)
            after = db.get(conn, old.ref)

    assert content(after) == content(new)
    assert after.created == before.created
    bumped = after.updated != before.updated
    assert bumped == (content(after) != content(before))
    assert new.updated == after.updated


@hypothesis.settings(max_examples=100, deadline=None)
@hypothesis.given(st.lists(TASK, min_size=1, max_size=8), st.data())
def test_move_gives_a_new_id_and_keeps_the_rest(
    tasks: list[schema.Task], data: st.DataObject
) -> None:
    with task_folder() as folder:
        store(tasks)
        source = data.draw(st.sampled_from(tasks)).ref
        target = data.draw(NAMESPACE.filter(lambda n: n != source.namespace))
        if target not in db.namespaces():
            db.add_namespace(target)
        with db.write(source.namespace, target) as conn:
            conn.conn.execute(
                f'UPDATE {conn.table(source.namespace)}'
                ' SET created = :t, updated = :t WHERE id = :id',
                {'t': EPOCH, 'id': source.ident},
            )
            before = db.get(conn, source)
            moved = before.model_copy()
            moved.namespace = target
            db.move(conn, moved, source)
        with db.connect() as conn:
            after = db.select(conn, ' ORDER BY namespace, id')

        [found] = [t for t in after if t.ref == moved.ref]
        assert not (folder / source.namespace / f'{source.ident}.txt').exists()
        described = folder / target / f'{moved.ident}.txt'
        assert described.exists() == (before.description is not None)

    others = sorted((t for t in tasks if t.ref != source), key=location)
    assert [t for t in after if t.ref != moved.ref] == others
    unplaced = {'id', 'namespace', 'updated'}
    assert {k: v for k, v in found.to_json().items() if k not in unplaced} == {
        k: v for k, v in before.to_json().items() if k not in unplaced
    }
    assert found == moved
    assert before.updated
    assert found.updated
    assert found.updated > before.updated


def operate(
    conn: db.Store, operation: tuple[str, str, int]
) -> schema.Ref | None:
    """Apply `operation`, returning the ref it created, if any."""
    kind, namespace, pick = operation
    live = db.select(conn)
    if kind == 'add' or not live:
        task = schema.Task(
            summary='a', details=None, tag='a', namespace=namespace
        )
        db.insert(conn, task)
        return task.ref
    task = live[pick % len(live)]
    if kind == 'done':
        db.delete(conn, task.ref)
        return None
    if task.namespace == namespace:
        return None
    source = task.ref
    task.namespace = namespace
    db.move(conn, task, source)
    return task.ref


@hypothesis.settings(max_examples=50, deadline=None)
@hypothesis.given(
    st.lists(
        st.tuples(
            st.sampled_from(['add', 'done', 'move']),
            NAMESPACE,
            st.integers(min_value=0),
        ),
        max_size=12,
    )
)
def test_ids_are_never_reused(operations: list[tuple[str, str, int]]) -> None:
    seen: set[schema.Ref] = set()
    with task_folder():
        for namespace in NAMESPACES[1:]:
            db.add_namespace(namespace)
        for operation in operations:
            with db.write(*NAMESPACES) as conn:
                ref = operate(conn, operation)
            assert ref not in seen
            if ref:
                seen.add(ref)


def test_unwritable_namespace_is_readable_only(folder: pathlib.Path) -> None:
    store([schema.Task(summary='a', details=None, tag='a', namespace='b')])
    directory = folder / 'b'
    tasks_db = directory / db.DATABASE
    directory.chmod(0o555)
    tasks_db.chmod(0o444)
    try:
        with db.connect() as conn:
            [task] = db.select(conn)
        with (
            db.write('b') as conn,
            pytest.raises(sqlite3.OperationalError, match='readonly'),
        ):
            db.update(conn, task)
        directory.chmod(0o755)
        tasks_db.chmod(0o644)
        with db.write('b') as conn:
            conn.conn.execute('PRAGMA user_version = 1')
        directory.chmod(0o555)
        tasks_db.chmod(0o444)
        with (
            pytest.raises(schema.TaskError, match='^namespace b: '),
            db.connect(),
        ):
            pass
    finally:
        directory.chmod(0o755)
        tasks_db.chmod(0o644)


def test_only_empty_namespaces_may_be_deleted(folder: pathlib.Path) -> None:
    store([schema.Task(summary='a', details=None, tag='a', namespace='b')])
    for namespace, error in (
        (schema.DEFAULT, 'cannot be deleted'),
        ('b', 'not empty'),
        ('c', 'no such namespace'),
    ):
        with pytest.raises(schema.TaskError, match=error):
            db.delete_namespace(namespace)

    with db.write('b') as conn:
        db.delete(conn, schema.Ref('b', 1))
    (folder / 'b' / '9.txt').write_text('orphan')
    (folder / 'b' / '.9.txt.tmp').write_text('half written')
    db.delete_namespace('b')
    assert not (folder / 'b').exists()

    db.add_namespace('c')
    (folder / 'c' / 'unexpected').write_text('')
    with pytest.raises(schema.TaskError, match='^namespace c: '):
        db.delete_namespace('c')
    assert db.namespaces() == [schema.DEFAULT]


def test_writers_touch_only_their_namespaces(folder: pathlib.Path) -> None:
    db.add_namespace('b')
    # eg. a sandbox granting only `b`: not even `default` may be created.
    folder.chmod(0o555)
    try:
        with db.write('b') as conn:
            db.insert(
                conn,
                schema.Task(summary='a', details=None, tag='a', namespace='b'),
            )
    finally:
        folder.chmod(0o755)
    assert db.namespaces() == ['b']
