import contextlib
import fcntl
import functools
import itertools
import os
import pathlib
import re
import sys
import time
from collections.abc import Generator
from collections.abc import Iterable

from . import schema

IDENT_FILE_RE = re.compile(r'^(\d+)\.md$')
# Dropbox and Syncthing conflict copies. Writing while one exists would bake
# in whichever side the sync tool happened to pick, so refuse until resolved.
CONFLICT_GLOBS = ('* (*conflicted copy*', '*.sync-conflict-*')
LOCK_TIMEOUT = 30.0
LOCK_POLL_INTERVAL = 0.05
FRONTMATTER_FENCE = '---'
FRONTMATTER_KEYS = ('owner', 'link')


@functools.cache
def task_folder() -> pathlib.Path:
    return pathlib.Path(os.environ['TASK_FOLDER'])


@functools.cache
def index_file() -> pathlib.Path:
    return task_folder() / 'index.md'


@contextlib.contextmanager
def locked() -> Generator[None]:
    """
    Hold an exclusive lock on the task folder for a whole command.

    Reads need it too: load() normalizes and may write. The lock is taken on
    the folder itself rather than a lockfile so nothing extra gets synced.
    """
    fd = os.open(task_folder(), os.O_RDONLY)
    try:
        deadline = time.monotonic() + LOCK_TIMEOUT
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise schema.TaskError(
                        f'timed out waiting for the lock on {task_folder()}'
                    ) from None
                time.sleep(LOCK_POLL_INTERVAL)
        _check_conflicts()
        yield
    finally:
        os.close(fd)


def _check_conflicts() -> None:
    conflicts = sorted(
        path.name
        for pattern in CONFLICT_GLOBS
        for path in task_folder().glob(pattern)
    )
    if conflicts:
        raise schema.TaskError(
            f'resolve sync conflicts first: {", ".join(conflicts)}'
        )


def _atomic_write(path: pathlib.Path, text: str) -> None:
    tmp = path.with_name(f'.{path.name}.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def task_sort_key(task: schema.Task) -> tuple[bool, list[str]]:
    # always keep triage at the top
    return (task.tag_names != ['Triage'], task.tag_names)


def _ident_files() -> list[tuple[int, pathlib.Path]]:
    result = []
    for path in task_folder().glob('*.md'):
        match = IDENT_FILE_RE.match(path.name)
        if match:
            result.append((int(match.group(1)), path))
    return sorted(result)


def _push_heading(tag: list[str], line: str) -> list[str]:
    level = len(line.split(maxsplit=1)[0]) - 2
    assert len(tag) >= level, 'error parsing tags'
    return [*tag[:level], line]


def _load_index() -> list[schema.Task]:
    if not index_file().exists():
        return []

    tasks = []
    tag: list[str] = []
    for line in index_file().read_text(encoding='utf-8').split('\n'):
        if line.startswith('##'):
            tag = _push_heading(tag, line)
        elif line.startswith('* '):
            tasks.append(schema.Task.parse(line[2:], tag))
    return tasks


def _split_frontmatter(
    path: pathlib.Path, lines: list[str]
) -> tuple[dict[str, str], list[str]]:
    if not lines or lines[0] != FRONTMATTER_FENCE:
        return {}, lines
    assert FRONTMATTER_FENCE in lines[1:], f'{path}: unterminated frontmatter'
    end = lines.index(FRONTMATTER_FENCE, 1)

    meta: dict[str, str] = {}
    for line in lines[1:end]:
        key, sep, value = line.partition(': ')
        assert sep and key in FRONTMATTER_KEYS, f'{path}: bad line {line!r}'
        meta[key] = value
    return meta, lines[end + 1 :]


def _load_ident_file(ident: int, path: pathlib.Path) -> schema.Task:
    lines = path.read_text(encoding='utf-8').split('\n')
    meta, lines = _split_frontmatter(path, lines)

    tag: list[str] = []
    for lineno, line in enumerate(lines):
        if line.startswith('##'):
            tag = _push_heading(tag, line)
        elif line.startswith('* '):
            rest = lines[lineno + 1 :]
            while rest and not rest[0].strip():
                rest = rest[1:]
            task = schema.Task.parse(
                line[2:],
                tag,
                description='\n'.join(rest).strip() or None,
                owner=meta.get('owner'),
                link=meta.get('link'),
            )
            assert task.ident in (None, ident), f'{path}: id mismatch'
            task.ident = ident
            return task

    raise AssertionError(f'{path}: no task found')


def _assign_idents(tasks: list[schema.Task]) -> None:
    taken = {t.ident for t in tasks if t.ident is not None}
    taken |= {ident for ident, _ in _ident_files()}
    counter = max(taken, default=0)
    for task in tasks:
        if task.ident is None:
            counter += 1
            task.ident = counter


def _check_duplicates(tasks: Iterable[schema.Task]) -> None:
    seen: set[int] = set()
    for task in tasks:
        if task.ident is None:
            continue
        assert task.ident not in seen, f'task {task.ident} lives in two homes'
        seen.add(task.ident)


def _shared_prefix(lhs: list[str], rhs: list[str]) -> int:
    for i, (left, right) in enumerate(zip(lhs, rhs, strict=False)):
        if left != right:
            return i
    return min(len(lhs), len(rhs))


def _render_index(tasks: Iterable[schema.Task]) -> str:
    lines = ['# TODOs']
    previous: list[str] | None = None
    for task in sorted(tasks, key=task_sort_key):
        if task.tag != previous:
            if previous is None and task.tag != ['## Triage']:
                lines.extend(('', '## Triage'))
            # Emit every heading that changed, not just the leaf, so nested
            # sections keep their parents even when a parent has no tasks.
            for heading in task.tag[
                _shared_prefix(previous or [], task.tag) :
            ]:
                lines.extend(('', heading))
            previous = task.tag
        lines.append(f'* {task.raw}')
    return '\n'.join(lines) + '\n'


def _render_ident_file(task: schema.Task) -> str:
    lines: list[str] = []
    meta = [(k, getattr(task, k)) for k in FRONTMATTER_KEYS]
    meta = [(k, v) for k, v in meta if v]
    if meta:
        lines.append(FRONTMATTER_FENCE)
        lines.extend(f'{k}: {v}' for k, v in meta)
        lines.append(FRONTMATTER_FENCE)
    lines.extend(task.tag)
    lines.append(f'* {task.raw}')
    if task.description:
        lines.extend(('', task.description))
    return '\n'.join(lines) + '\n'


def load() -> list[schema.Task]:
    index_tasks = _load_index()
    ident_tasks = list(itertools.starmap(_load_ident_file, _ident_files()))
    tasks = index_tasks + ident_tasks
    _check_duplicates(tasks)

    # Normalization persists on any command: hand-added lines lack an id, and a
    # bare ident file (only possible via hand-edit) must move home.
    dirty = any(t.ident is None for t in index_tasks)
    dirty = dirty or any(not t.needs_own_file for t in ident_tasks)
    if dirty:
        save(tasks)

    return tasks


def save(tasks: Iterable[schema.Task]) -> None:
    tasks = list(tasks)
    _assign_idents(tasks)
    _check_duplicates(tasks)

    print(f'Writing to {index_file()}', file=sys.stderr)
    # Ident files are written before the index: a crash in between leaves a
    # task in two homes (caught by _check_duplicates) rather than in none.
    keep = set()
    for task in (t for t in tasks if t.needs_own_file):
        _atomic_write(
            task_folder() / f'{task.ident}.md', _render_ident_file(task)
        )
        keep.add(task.ident)

    _atomic_write(
        index_file(), _render_index(t for t in tasks if not t.needs_own_file)
    )

    for ident, path in _ident_files():
        if ident not in keep:
            path.unlink()
