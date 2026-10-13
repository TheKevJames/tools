"""
The task store: one directory per namespace under $TASK_FOLDER, each holding
a SQLite database plus one `<id>.txt` file per description.

Namespaces are directories so that access to each may be granted separately:
eg. a sandbox which reads every namespace but writes only its own, so a writer
touches only the namespaces it writes. A namespace is a directory with a valid
name holding a database; `default` is created by the first write to it, the
rest by `add_namespace`. Ids are unique only within a namespace, so a task's
address is its `schema.Ref`, and moving a task to another namespace gives it a
new id there.

Descriptions live beside each database as plain files so they can be edited
by hand; a file's existence is the only record that a task has one. Writers
change them while holding the write lock but before committing, so a failed
commit can strand an orphan, which the next write to its namespace removes.
Ids are never reused, so an orphan cannot attach itself to a different task.

Completing a one-off task deletes it, with its description; recurring tasks
advance instead. `created` and `updated` belong to the store, never to
callers: every write which changes a task's row or description bumps
`updated`. Editing a description file by hand does not.
"""

import contextlib
import dataclasses
import os
import pathlib
import re
import sqlite3
from collections.abc import Generator
from collections.abc import Iterable

from . import migrations
from . import schema
from . import timestamp

BUSY_TIMEOUT = 30.0
DATABASE = 'tasks.db'
DESCRIPTION_RE = re.compile(r'(\d+)\.txt')
DESCRIPTION_TMP_RE = re.compile(r'\.\d+\.txt\.tmp')
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
)
COLUMNS = (*WRITABLE, 'created', 'updated')
# The `tasks` view, over every namespace a Store sees, adds the namespace.
VIEW_COLUMNS = ('namespace', *COLUMNS)
NOW = f"strftime('{timestamp.FORMAT}', 'now')"


@dataclasses.dataclass(frozen=True)
class Store:
    """A connection to some namespaces, which its `tasks` view unites."""

    conn: sqlite3.Connection
    # Namespace -> the name its database is attached as.
    schemas: dict[str, str]

    def table(self, namespace: str) -> str:
        return f'{self.schemas[namespace]}.task'


def folder() -> pathlib.Path:
    return pathlib.Path(os.environ['TASK_FOLDER'])


def namespaces() -> list[str]:
    return sorted(
        path.name
        for path in folder().iterdir()
        if schema.NAME_RE.fullmatch(path.name) and _exists(path.name)
    )


def add_namespace(namespace: str) -> None:
    if _exists(namespace):
        raise schema.TaskError(f'namespace {namespace} already exists')
    _create(namespace)


def delete_namespace(namespace: str) -> None:
    """Delete an empty namespace; its orphans and temporary files go too."""
    if namespace == schema.DEFAULT:
        raise schema.TaskError(f'namespace {schema.DEFAULT} cannot be deleted')
    with write(namespace) as store:
        query = f'SELECT 1 FROM {store.table(namespace)} LIMIT 1'
        if store.conn.execute(query).fetchone():
            raise schema.TaskError(f'namespace {namespace} is not empty')

    path = _directory(namespace)
    (path / DATABASE).unlink()
    for file in path.iterdir():
        if DESCRIPTION_TMP_RE.fullmatch(file.name):
            file.unlink(missing_ok=True)
    try:
        path.rmdir()
    except OSError as e:
        raise schema.TaskError(f'namespace {namespace}: {e}') from e


@contextlib.contextmanager
def connect() -> Generator[Store]:
    """Every namespace, outside any transaction: statements stand alone."""
    with _store(None, namespaces()) as store:
        yield store


@contextlib.contextmanager
def write(namespace: str, *others: str) -> Generator[Store]:
    """Namespaces under their write locks, committed if the block succeeds."""
    names = {namespace, *others}
    for name in names:
        if _exists(name):
            continue
        if name != schema.DEFAULT:
            raise schema.TaskError(f'no such namespace: {name}')
        _create(name)

    # BEGIN IMMEDIATE locks every attached database, in the order attached,
    # so taking namespaces in sorted order keeps two writers from deadlocking.
    # Attached databases commit atomically only if `main` is a file.
    main, *attached = sorted(names)
    with _store(main, attached) as store, _transaction(store.conn):
        yield store
        for name in store.schemas:
            _remove_orphans(store, name)


def _directory(namespace: str) -> pathlib.Path:
    return folder() / namespace


def _exists(namespace: str) -> bool:
    return (_directory(namespace) / DATABASE).is_file()


def _create(namespace: str) -> None:
    _directory(namespace).mkdir(exist_ok=True)
    _open(namespace).close()


def _connect(database: str | pathlib.Path) -> sqlite3.Connection:
    conn = sqlite3.connect(
        database, timeout=BUSY_TIMEOUT, isolation_level=None
    )
    conn.create_function('fold', 1, str.lower, deterministic=True)
    return conn


def _open(namespace: str) -> sqlite3.Connection:
    """A connection to one namespace's database, migrated."""
    conn = _connect(_directory(namespace) / DATABASE)
    try:
        # A rollback journal keeps the database a single self-contained file
        # between commits, which is what Syncthing backs up. WAL would not.
        conn.execute('PRAGMA journal_mode = DELETE')
        _migrate(conn)
    except (sqlite3.DatabaseError, schema.TaskError) as e:
        conn.close()
        raise schema.TaskError(f'namespace {namespace}: {e}') from e
    return conn


@contextlib.contextmanager
def _store(main: str | None, attached: Iterable[str]) -> Generator[Store]:
    """`main` (or an in-memory database) with the rest attached."""
    schemas: dict[str, str] = {}
    if main is None:
        conn = _connect(':memory:')
    else:
        conn = _open(main)
        schemas[main] = 'main'
    try:
        for i, name in enumerate(attached):
            _open(name).close()
            schemas[name] = f'ns{i}'
            conn.execute(
                f'ATTACH DATABASE ? AS {schemas[name]}',
                (str(_directory(name) / DATABASE),),
            )
        _create_view(conn, schemas)
        yield Store(conn, schemas)
    finally:
        conn.close()


def _create_view(conn: sqlite3.Connection, schemas: dict[str, str]) -> None:
    columns = ', '.join(COLUMNS)
    # Namespace names are checked by schema.NAME_RE, so are safe to inline.
    selects = [
        f"SELECT '{name}' AS namespace, {columns} FROM {alias}.task"
        for name, alias in schemas.items()
    ] or [f'SELECT {", ".join(f"NULL AS {c}" for c in VIEW_COLUMNS)} LIMIT 0']
    conn.execute(f'CREATE TEMP VIEW tasks AS {" UNION ALL ".join(selects)}')


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
    if version > len(migrations.MIGRATIONS):
        raise schema.TaskError(
            f'database is at version {version}, newer than this task CLI'
        )
    return version


def _migrate(conn: sqlite3.Connection) -> None:
    if _version(conn) == len(migrations.MIGRATIONS):
        return
    with _transaction(conn):
        for migration in migrations.MIGRATIONS[_version(conn) :]:
            conn.execute(migration)
        conn.execute(f'PRAGMA user_version = {len(migrations.MIGRATIONS)}')


def select(
    store: Store, clauses: str = '', params: dict[str, object] | None = None
) -> list[schema.Task]:
    rows = store.conn.execute(
        f'SELECT {", ".join(VIEW_COLUMNS)} FROM tasks{clauses}', params or {}
    )
    return [_to_task(row) for row in rows]


def get(store: Store, ref: schema.Ref) -> schema.Task:
    tasks = select(
        store,
        ' WHERE namespace = :namespace AND id = :id',
        {'namespace': ref.namespace, 'id': ref.ident},
    )
    if not tasks:
        raise schema.TaskError(f'task {ref} not found')
    return tasks[0]


def insert(store: Store, task: schema.Task) -> None:
    """Store a new task, assigning its id unless it already has one."""
    names = ', '.join(WRITABLE)
    values = ', '.join(f':{column}' for column in WRITABLE)
    task.ident, task.created, task.updated = store.conn.execute(
        f'INSERT INTO {store.table(task.namespace)} ({names})'
        f' VALUES ({values}) RETURNING id, created, updated',
        _to_row(task),
    ).fetchone()
    _write_description(task)


def update(store: Store, task: schema.Task) -> None:
    """Store a changed task, bumping `updated` unless nothing changed."""
    fields = [column for column in WRITABLE if column != 'id']
    assignments = ', '.join(f'{column} = :{column}' for column in fields)
    # SET expressions all see the row as it was before this statement.
    old = ', '.join(fields)
    new = ', '.join(f':{column}' for column in fields)
    (task.updated,) = store.conn.execute(
        f'UPDATE {store.table(task.namespace)} SET {assignments},'
        f' updated = CASE WHEN :described OR ({old}) IS NOT ({new})'
        f' THEN {NOW} ELSE updated END WHERE id = :id RETURNING updated',
        _to_row(task)
        | {'described': _read_description(task.ref) != task.description},
    ).fetchone()
    _write_description(task)


def move(store: Store, task: schema.Task, source: schema.Ref) -> None:
    """Store a task, from `source`, under a new id in its namespace."""
    assert task.namespace != source.namespace, 'task has not moved'
    task.ident = None
    insert(store, task)
    (task.created,) = store.conn.execute(
        f'UPDATE {store.table(task.namespace)} SET created = ('
        f'  SELECT created FROM {store.table(source.namespace)}'
        '   WHERE id = :source'
        ') WHERE id = :id RETURNING created',
        {'source': source.ident, 'id': task.ident},
    ).fetchone()
    delete(store, source)


def delete(store: Store, ref: schema.Ref) -> None:
    store.conn.execute(
        f'DELETE FROM {store.table(ref.namespace)} WHERE id = :id',
        {'id': ref.ident},
    )
    _description_path(ref).unlink(missing_ok=True)


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
    }


def _to_task(row: tuple[object, ...]) -> schema.Task:
    fields = dict(zip(VIEW_COLUMNS, row, strict=True))
    namespace = fields['namespace']
    ident = fields.pop('id')
    assert isinstance(namespace, str)
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
            'description': _read_description(schema.Ref(namespace, ident)),
        }
    )


def _description_path(ref: schema.Ref) -> pathlib.Path:
    return _directory(ref.namespace) / f'{ref.ident}.txt'


def _read_description(ref: schema.Ref) -> str | None:
    try:
        text = _description_path(ref).read_text(encoding='utf-8')
    except FileNotFoundError:
        return None
    return text.strip() or None


def _write_description(task: schema.Task) -> None:
    if _read_description(task.ref) == task.description:
        return

    path = _description_path(task.ref)
    if task.description is None:
        path.unlink(missing_ok=True)
        return

    tmp = path.with_name(f'.{path.name}.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        f.write(task.description)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def _remove_orphans(store: Store, namespace: str) -> None:
    idents = {
        row[0]
        for row in store.conn.execute(
            f'SELECT id FROM {store.table(namespace)}'
        )
    }
    for path in _directory(namespace).iterdir():
        match = DESCRIPTION_RE.fullmatch(path.name)
        if match and int(match.group(1)) not in idents:
            path.unlink(missing_ok=True)
