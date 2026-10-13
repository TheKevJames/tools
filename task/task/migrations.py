"""The schema of a namespace's database, as the migrations building it."""

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
    # Done tasks are deleted from now on, so the `done` column goes along with
    # every task stamped with it; the next write removes their descriptions.
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
        created TEXT NOT NULL
            DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', created) IS created),
        updated TEXT NOT NULL
            DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', updated) IS updated),
        CHECK (next IS NOT NULL OR (interval IS NULL AND shift = 0)),
        CHECK (updated >= created)
    ) STRICT
    """,
    """
    INSERT INTO task_new (
        id, summary, tag, next, interval, shift, owner, link, priority, size,
        created, updated
    )
    SELECT
        id, summary, tag, next, interval, shift, owner, link, priority, size,
        created, updated
    FROM task
    WHERE done IS NULL
    """,
    "DELETE FROM sqlite_sequence WHERE name = 'task_new'",
    "UPDATE sqlite_sequence SET name = 'task_new' WHERE name = 'task'",
    'DROP TABLE task',
    'ALTER TABLE task_new RENAME TO task',
    # Tags are flat names: namespaces, one database each, replace paths.
    """
    CREATE TABLE task_new (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        summary TEXT NOT NULL
            CHECK (trim(summary) != '' AND instr(summary, char(10)) = 0),
        tag TEXT NOT NULL
            CHECK (tag GLOB '[a-z0-9]*' AND tag NOT GLOB '*[^a-z0-9_.-]*'),
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
        created TEXT NOT NULL
            DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', created) IS created),
        updated TEXT NOT NULL
            DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            CHECK (strftime('%Y-%m-%dT%H:%M:%SZ', updated) IS updated),
        CHECK (next IS NOT NULL OR (interval IS NULL AND shift = 0)),
        CHECK (updated >= created)
    ) STRICT
    """,
    """
    INSERT INTO task_new (
        id, summary, tag, next, interval, shift, owner, link, priority, size,
        created, updated
    )
    SELECT
        id, summary, tag, next, interval, shift, owner, link, priority, size,
        created, updated
    FROM task
    """,
    "DELETE FROM sqlite_sequence WHERE name = 'task_new'",
    "UPDATE sqlite_sequence SET name = 'task_new' WHERE name = 'task'",
    'DROP TABLE task',
    'ALTER TABLE task_new RENAME TO task',
)
