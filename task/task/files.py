import itertools
import os
import pathlib
import re
from collections.abc import Iterable

from . import schema

TASK_FOLDER = pathlib.Path(os.environ['TASK_FOLDER'])
INDEX_FILE = TASK_FOLDER / 'index.md'

IDENT_FILE_RE = re.compile(r'^(\d+)\.md$')


def task_sort_key(task: schema.Task) -> str:
    key = ' > '.join(x.split(maxsplit=1)[1] for x in task.tag)
    if key == 'Triage':
        key = '0'
    return key


def _ident_files() -> list[tuple[int, pathlib.Path]]:
    result = []
    for path in TASK_FOLDER.glob('*.md'):
        match = IDENT_FILE_RE.match(path.name)
        if match:
            result.append((int(match.group(1)), path))
    return sorted(result)


def _load_index() -> list[schema.Task]:
    if not INDEX_FILE.exists():
        return []

    tasks = []
    tag: list[str] = []
    for line in INDEX_FILE.read_text(encoding='utf-8').split('\n'):
        if line.startswith('##'):
            level = len(line.split(maxsplit=1)[0]) - 2
            tag = tag[:level]
            assert len(tag) >= level, 'error parsing tags'
            tag.append(line)
        elif line.startswith('* '):
            tasks.append(schema.Task.parse(line[2:], tag))
    return tasks


def _load_ident_file(ident: int, path: pathlib.Path) -> schema.Task:
    tag: list[str] = []
    lines = path.read_text(encoding='utf-8').split('\n')
    for lineno, line in enumerate(lines):
        if line.startswith('##'):
            level = len(line.split(maxsplit=1)[0]) - 2
            tag = tag[:level]
            assert len(tag) >= level, 'error parsing tags'
            tag.append(line)
        elif line.startswith('* '):
            rest = lines[lineno + 1 :]
            while rest and not rest[0].strip():
                rest = rest[1:]
            description = '\n'.join(rest).strip() or None
            task = schema.Task.parse(line[2:], tag, description=description)
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


def _write_index(tasks: Iterable[schema.Task]) -> None:
    xs = sorted(tasks, key=task_sort_key)
    with INDEX_FILE.open('w', encoding='utf-8') as f:
        f.write('# TODOs\n')
        lasttag: list[str] = []
        for task in xs:
            if lasttag != task.tag:
                # always keep a triage section at the top
                if not lasttag:
                    if task.tag[-1] != '## Triage':
                        f.write('\n## Triage\n')

                f.write(f'\n{task.tag[-1]}\n')
                lasttag = task.tag

            f.write(f'* {task.raw}\n')


def _write_ident_file(task: schema.Task) -> None:
    path = TASK_FOLDER / f'{task.ident}.md'
    lines = [f'{t}\n' for t in task.tag]
    lines.extend((f'* {task.raw}\n', '\n', f'{task.description}\n'))
    path.write_text(''.join(lines), encoding='utf-8')


def load() -> list[schema.Task]:
    index_tasks = _load_index()
    ident_tasks = list(itertools.starmap(_load_ident_file, _ident_files()))
    tasks = index_tasks + ident_tasks
    _check_duplicates(tasks)

    # Normalization persists on any command: hand-added lines lack an id, and a
    # description-less ident file (only possible via hand-edit) must move home.
    dirty = any(t.ident is None for t in index_tasks)
    dirty = dirty or any(not t.description for t in ident_tasks)
    if dirty:
        save(tasks)

    return tasks


def save(tasks: Iterable[schema.Task]) -> None:
    tasks = list(tasks)
    _assign_idents(tasks)
    _check_duplicates(tasks)

    print(f'Writing to {INDEX_FILE}')
    _write_index(t for t in tasks if not t.description)

    keep = set()
    for task in (t for t in tasks if t.description):
        _write_ident_file(task)
        keep.add(task.ident)

    for ident, path in _ident_files():
        if ident not in keep:
            path.unlink()
