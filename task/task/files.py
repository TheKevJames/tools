import pathlib
from collections.abc import Iterable
from collections.abc import Iterator

from .schema import Link
from .schema import Task


# TODO(feat): pydantic_settings? load from vim config?
class Settings:
    fnames: list[pathlib.Path]

    def __init__(self) -> None:
        self.fnames = [
            pathlib.Path.home() / 'sync' / 'work' / 'vimwiki' / 'todos.md',
            pathlib.Path.home() / 'sync' / 'vimwiki' / 'todos.md',
        ]


def task_sort_key(task: Task) -> str:
    key = ' > '.join(x.split(maxsplit=1)[1] for x in task.tag)
    if key == 'Triage':
        key = '0'
    return key


def save(tasks: Iterable[Task]) -> None:
    settings = Settings()

    tasks = list(tasks)
    for fname in settings.fnames:
        print(f'Writing to {fname}')
        xs = sorted(
            (x for x in tasks if x.link.fname == fname),
            key=task_sort_key,
        )

        with fname.open('w', encoding='utf-8') as f:
            f.write(f'# TODOs: {xs[-1].link.ftitle}\n')
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
    settings = Settings()

    title: str
    tag: list[str] = []
    for fname in settings.fnames:
        for lineno, line in enumerate(fname.read_text().split('\n')):
            if line.startswith('# TODOs'):
                title = line.split()[2]
            elif line.startswith('##'):
                level = len(line.split(maxsplit=1)[0]) - 2
                tag = tag[:level]
                assert len(tag) >= level, 'error parsing tags'
                tag.append(line)
            elif line.startswith('* '):
                link = Link(fname=fname, ftitle=title, lineno=lineno)
                yield Task.parse(line[2:], tag, link)
