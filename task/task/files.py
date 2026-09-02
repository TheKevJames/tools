import os
import pathlib
from collections.abc import Iterable
from collections.abc import Iterator

from .schema import Task


TASK_FILE = pathlib.Path(os.environ['TASK_FILE'])


def task_sort_key(task: Task) -> str:
    key = ' > '.join(x.split(maxsplit=1)[1] for x in task.tag)
    if key == 'Triage':
        key = '0'
    return key


def save(tasks: Iterable[Task]) -> None:
    print(f'Writing to {TASK_FILE}')
    xs = sorted(tasks, key=task_sort_key)

    with TASK_FILE.open('w', encoding='utf-8') as f:
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


def load() -> Iterator[Task]:
    tag: list[str] = []
    text = TASK_FILE.read_text(encoding='utf-8')
    for lineno, line in enumerate(text.split('\n')):
        if line.startswith('##'):
            level = len(line.split(maxsplit=1)[0]) - 2
            tag = tag[:level]
            assert len(tag) >= level, 'error parsing tags'
            tag.append(line)
        elif line.startswith('* '):
            yield Task.parse(line[2:], tag, lineno)
