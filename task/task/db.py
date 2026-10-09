"""
The task store: a SQLite database plus one `<id>.txt` file per description.

Descriptions live beside the database as plain files so they can be edited by
hand; a file's existence is the only record that a task has one. Writers
change them while holding the write lock but before committing, so a failed
commit can strand an orphan, which the next write removes. Ids are never
reused, so an orphan cannot attach itself to a different task.

Tasks are never deleted: completing one stamps `done`, which hides it from
listings. `created` and `updated` belong to the store, never to callers: every
write which changes a task's row or description bumps `updated`. Editing a
description file by hand does not.
"""

import contextlib
import os
import pathlib
import re
import sqlite3
from collections.abc import Generator

from . import schema
from . import timestamp

BUSY_TIMEOUT = 30.0
DESCRIPTION_RE = re.compile(r'(\d+)\.txt')
WRITABLE = (
    'id',
    'summary',
    'tag',
    'next',
    'interval',
    'shift',
    'owner',
    'link',
    'priority',
    'size',
    'done',
)
COLUMNS = (*WRITABLE, 'created', 'updated')
NOW = f"strftime('{timestamp.FORMAT}', 'now')"

# Applied in order; PRAGMA user_version counts how many have run. Never edit
# one that has shipped: append another.
MIGRATIONS = (
    """
    CREATE TABLE task (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        summary TEXT NOT NULL
            CHECK (trim(summary) != '' AND instr(summary, char(10)) = 0),
        tag TEXT NOT NULL CHECK (tag != '' AND tag = lower(tag)),
        next TEXT CHECK (date(next) IS next),
        interval TEXT CHECK (
            interval GLOB '[1-9]*[dwm]'
            AND substr(interval, 1, length(interval) - 1) NOT GLOB '*[^0-9]*'
        ),
        shift INTEGER NOT NULL DEFAULT 0 CHECK (shift IN (0, 1)),
        owner TEXT CHECK (
            owner != '' AND owner NOT GLOB '*[^A-Za-z0-9_.-]*'
        ),
        link TEXT CHECK (
            link != '' AND link NOT GLOB ('*[ ' || char(9, 10, 13) || ']*')
        ),
        priority TEXT CHECK (priority IN ('low', 'medium', 'high')),
        size TEXT CHECK (size IN ('small', 'medium', 'large')),
        CHECK (next IS NOT NULL OR (interval IS NULL AND shift = 0))
    ) STRICT
    """,
    # Adding required columns which default to the current time needs a
    # rebuild. The AUTOINCREMENT high-water mark moves to the new table first,
    # since dropping the old one discards it and ids must never be reused.
    """
    CREATE TABLE task_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        summary TEXT NOT NULL
            CHECK (trim(summary) != '' AND instr(summary, char(10)) = 0),
        tag TEXT NOT NULL CHECK (tag != '' AND tag = lower(tag)),
        next TEXT CHECK (date(next) IS next),
        interval TEXT CHECK (
            interval GLOB '[1-9]*[dwm]'
            AND substr(interval, 1, length(interval) - 1) NOT GLOB '*[^0-9]*'
        ),
        shift INTEGER NOT NULL DEFAULT 0 CHECK (shift IN (0, 1)),
        owner TEXT CHECK (
            owner != '' AND owner NOT GLOB '*[^A-Za-z0-9_.-]*'
        ),
        link TEXT CHECK (
            link != '' AND link NOT GLOB ('*[ ' || char(9, 10, 13) || ']*')
        ),
        priority TEXT CHECK (priority IN ('low', 'medium', 'high')),
        size TEXT CHECK (size IN ('small', 'medium', 'large')),
        done TEXT CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', done) IS done),
        created TEXT NOT NULL
            DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', created) IS created),
        updated TEXT NOT NULL
            DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', updated) IS updated),
        CHECK (next IS NOT NULL OR (interval IS NULL AND shift = 0)),
        CHECK (done IS NULL OR interval IS NULL),
        CHECK (updated >= created)
    ) STRICT
    """,
    """
    INSERT INTO task_new (
        id, summary, tag, next, interval, shift, owner, link, priority, size
    )
    SELECT id, summary, tag, next, interval, shift, owner, link, priority, size
    FROM task
    """,
    "DELETE FROM sqlite_sequence WHERE name = 'task_new'",
    "UPDATE sqlite_sequence SET name = 'task_new' WHERE name = 'task'",
    'DROP TABLE task',
    'ALTER TABLE task_new RENAME TO task',
)


def folder() -> pathlib.Path:
    return pathlib.Path(os.environ['TASK_FOLDER'])


@contextlib.contextmanager
def connect() -> Generator[sqlite3.Connection]:
    """A connection outside any transaction: each statement stands alone."""
    conn = sqlite3.connect(
        folder() / 'tasks.db', timeout=BUSY_TIMEOUT, isolation_level=None
    )
    try:
        conn.create_function('fold', 1, str.lower, deterministic=True)
        # A rollback journal keeps the database a single self-contained file
        # between commits, which is what Syncthing backs up. WAL would not.
        conn.execute('PRAGMA journal_mode = DELETE')
        _migrate(conn)
        yield conn
    finally:
        conn.close()


@contextlib.contextmanager
def write() -> Generator[sqlite3.Connection]:
    """A connection holding the write lock, committed if the block succeeds."""
    with connect() as conn, _transaction(conn):
        yield conn
        _remove_orphans(conn)


@contextlib.contextmanager
def _transaction(conn: sqlite3.Connection) -> Generator[None]:
    # IMMEDIATE takes the write lock up front, so read-check-write sequences
    # (eg. claiming a task) cannot interleave with another writer.
    conn.execute('BEGIN IMMEDIATE')
    try:
        yield
    except BaseException:
        conn.execute('ROLLBACK')
        raise
    conn.execute('COMMIT')


def _version(conn: sqlite3.Connection) -> int:
    version: int = conn.execute('PRAGMA user_version').fetchone()[0]
    if version > len(MIGRATIONS):
        raise schema.TaskError(
            f'database is at version {version}, newer than this task CLI'
        )
    return version


def _migrate(conn: sqlite3.Connection) -> None:
    if _version(conn) == len(MIGRATIONS):
        return
    with _transaction(conn):
        for migration in MIGRATIONS[_version(conn) :]:
            conn.execute(migration)
        conn.execute(f'PRAGMA user_version = {len(MIGRATIONS)}')


def select(
    conn: sqlite3.Connection,
    clauses: str = '',
    params: dict[str, object] | None = None,
) -> list[schema.Task]:
    rows = conn.execute(
        f'SELECT {", ".join(COLUMNS)} FROM task{clauses}', params or {}
    )
    return [_to_task(row) for row in rows]


def get(conn: sqlite3.Connection, ident: int) -> schema.Task:
    tasks = select(conn, ' WHERE id = :id', {'id': ident})
    if not tasks:
        raise schema.TaskError(f'task {ident} not found')
    return tasks[0]


def get_open(conn: sqlite3.Connection, ident: int) -> schema.Task:
    """A task which may still change: done tasks are only ever reopened."""
    task = get(conn, ident)
    if task.done:
        raise schema.TaskError(f'task {ident} is done')
    return task


def insert(conn: sqlite3.Connection, task: schema.Task) -> None:
    """Store a new task, assigning its id unless it already has one."""
    names = ', '.join(WRITABLE)
    values = ', '.join(f':{column}' for column in WRITABLE)
    task.ident, task.created, task.updated = conn.execute(
        f'INSERT INTO task ({names}) VALUES ({values})'
        ' RETURNING id, created, updated',
        _to_row(task),
    ).fetchone()
    _write_description(task)


def update(conn: sqlite3.Connection, task: schema.Task) -> None:
    """Store a changed task, bumping `updated` unless nothing changed."""
    assert task.ident is not None, 'task id has not been assigned'
    fields = [column for column in WRITABLE if column != 'id']
    assignments = ', '.join(f'{column} = :{column}' for column in fields)
    # SET expressions all see the row as it was before this statement.
    old = ', '.join(fields)
    new = ', '.join(f':{column}' for column in fields)
    (task.updated,) = conn.execute(
        f'UPDATE task SET {assignments}, updated = CASE'
        f' WHEN :described OR ({old}) IS NOT ({new}) THEN {NOW}'
        ' ELSE updated END WHERE id = :id RETURNING updated',
        _to_row(task)
        | {'described': _read_description(task.ident) != task.description},
    ).fetchone()
    _write_description(task)


def _to_row(task: schema.Task) -> dict[str, object]:
    details = task.details
    interval = details.interval if details else None
    return {
        'id': task.ident,
        'summary': task.summary,
        'tag': task.tag,
        'next': details.next_.isoformat() if details else None,
        'interval': interval.raw if interval else None,
        'shift': int(bool(details and details.shift)),
        'owner': task.owner,
        'link': task.link,
        'priority': task.priority,
        'size': task.size,
        'done': timestamp.serialize(task.done),
    }


def _to_task(row: tuple[object, ...]) -> schema.Task:
    fields = dict(zip(COLUMNS, row, strict=True))
    ident = fields.pop('id')
    assert isinstance(ident, int)
    next_ = fields.pop('next')
    interval = fields.pop('interval')
    shift = fields.pop('shift')
    details = None
    if next_ is not None:
        details = schema.Details.model_validate(
            {
                'next': next_,
                'interval': None if interval is None else {'raw': interval},
                'shift': bool(shift),
            }
        )
    return schema.Task.model_validate(
        fields
        | {
            'ident': ident,
            'details': details,
            'description': _read_description(ident),
        }
    )


def _description_path(ident: int) -> pathlib.Path:
    return folder() / f'{ident}.txt'


def _read_description(ident: int) -> str | None:
    try:
        text = _description_path(ident).read_text(encoding='utf-8')
    except FileNotFoundError:
        return None
    return text.strip() or None


def _write_description(task: schema.Task) -> None:
    assert task.ident is not None, 'task id has not been assigned'
    if _read_description(task.ident) == task.description:
        return

    path = _description_path(task.ident)
    if task.description is None:
        path.unlink(missing_ok=True)
        return

    tmp = path.with_name(f'.{path.name}.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        f.write(task.description)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def _remove_orphans(conn: sqlite3.Connection) -> None:
    idents = {row[0] for row in conn.execute('SELECT id FROM task')}
    for path in folder().iterdir():
        match = DESCRIPTION_RE.fullmatch(path.name)
        if match and int(match.group(1)) not in idents:
            path.unlink(missing_ok=True)
