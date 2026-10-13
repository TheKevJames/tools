import pathlib
import sqlite3

import pytest

from task import db
from task import migrations
from task import schema

# The last schema version with a `done` column.
DONE_VERSION = 7
DONE = '2000-01-01T00:00:00Z'


def database(folder: pathlib.Path) -> sqlite3.Connection:
    """The default namespace's database, created unmigrated."""
    (folder / schema.DEFAULT).mkdir()
    return sqlite3.connect(
        folder / schema.DEFAULT / db.DATABASE, isolation_level=None
    )


@pytest.mark.parametrize('deleted', [[3], [1, 2, 3]])
def test_migration_keeps_tasks_and_never_reuses_ids(
    folder: pathlib.Path, deleted: list[int]
) -> None:
    conn = database(folder)
    conn.execute(migrations.MIGRATIONS[0])
    conn.execute('PRAGMA user_version = 1')
    conn.executemany(
        "INSERT INTO task (summary, tag, owner) VALUES (?, 'a', ?)",
        [('x', 'bot'), ('y', None), ('z', None)],
    )
    conn.executemany('DELETE FROM task WHERE id = ?', [(i,) for i in deleted])
    conn.close()

    added = schema.Task(summary='new', details=None, tag='a')
    with db.write(schema.DEFAULT) as conn:
        kept = db.select(conn, ' ORDER BY id')
        db.insert(conn, added)

    assert [(t.ident, t.summary, t.owner) for t in kept] == [
        (i, s, o)
        for i, s, o in ((1, 'x', 'bot'), (2, 'y', None))
        if i not in deleted
    ]
    assert all(t.created == t.updated for t in kept)
    # Ids stay unique across every later rebuild of the table.
    assert added.ident == 4


def test_migration_deletes_done_tasks(folder: pathlib.Path) -> None:
    conn = database(folder)
    for migration in migrations.MIGRATIONS[:DONE_VERSION]:
        conn.execute(migration)
    conn.execute(f'PRAGMA user_version = {DONE_VERSION}')
    conn.executemany(
        "INSERT INTO task (summary, tag, done) VALUES (?, 'a', ?)",
        [('x', None), ('y', DONE), ('z', DONE)],
    )
    conn.close()
    for ident in (1, 2):
        (folder / schema.DEFAULT / f'{ident}.txt').write_text('notes')

    with db.write(schema.DEFAULT) as conn:
        kept = db.select(conn, ' ORDER BY id')

    assert [(t.ident, t.description) for t in kept] == [(1, 'notes')]
    assert not (folder / schema.DEFAULT / '2.txt').exists()


def test_newer_database_is_refused(folder: pathlib.Path) -> None:
    version = len(migrations.MIGRATIONS) + 1
    conn = database(folder)
    conn.execute(f'PRAGMA user_version = {version}')
    conn.close()

    message = (
        f'^namespace default: database is at version {version},'
        ' newer than this task CLI$'
    )
    with pytest.raises(schema.TaskError, match=message), db.connect():
        pass
