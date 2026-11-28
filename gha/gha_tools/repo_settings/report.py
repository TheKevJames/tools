import json
import pathlib
from collections.abc import Mapping
from typing import Any

MODES = ('plan', 'apply', 'check')


def field_diff(want: Mapping[str, Any], have: Mapping[str, Any]) -> str:
    """A diff of the fields of `want` that `have` does not match."""
    lines = ['--- github', '+++ repo']
    for key, value in want.items():
        if have.get(key) != value:
            lines.extend(
                (
                    f'-{key}: {json.dumps(have.get(key))}',
                    f'+{key}: {json.dumps(value)}',
                )
            )
    return '\n'.join(lines)


def _annotate(level: str, message: str) -> None:
    # Workflow commands are line-oriented; encode so multi-line messages (eg.
    # API error bodies) stay in one annotation.
    encoded = message.replace('%', '%25').replace('\n', '%0A')
    print(f'::{level}::{encoded}', flush=True)


class Report:
    """Annotations as they happen, plus a markdown job summary at the end."""

    def __init__(self, repository: str, mode: str) -> None:
        self.repository = repository
        self.mode = mode
        self._messages: list[tuple[str, str]] = []
        self._changes: list[str] = []
        self._diffs: list[tuple[str, str]] = []

    def _record(self, level: str, message: str) -> None:
        _annotate(level, message)
        self._messages.append((level, message))

    def error(self, message: str) -> None:
        self._record('error', message)

    def warning(self, message: str) -> None:
        self._record('warning', message)

    def notice(self, message: str) -> None:
        self._record('notice', message)

    def change(self, line: str, detail: str | None = None) -> None:
        """A change apply makes (or made), with an optional diff of it."""
        self._changes.append(line)
        print(f'{self.mode}: {line}', flush=True)
        if detail is not None:
            print(detail, flush=True)
            self._diffs.append((line, detail))

    def finish(self) -> None:
        if not self._changes:
            print(f'{self.mode}: no changes', flush=True)

    def summary(self) -> str:
        lines = [
            f'## Repository settings ({self.mode}): {self.repository}',
            '',
        ]
        lines.extend(f'- **{lvl}**: {msg}' for lvl, msg in self._messages)
        if self._messages:
            lines.append('')
        lines.append('### Changes')
        lines.extend(f'- {line}' for line in self._changes or ['none'])
        for name, detail in self._diffs:
            lines.extend(
                [
                    '',
                    f'<details><summary>{name}</summary>',
                    '',
                    '```diff',
                    detail,
                    '```',
                    '</details>',
                ]
            )
        return '\n'.join(lines) + '\n'

    def write_summary(self, path: str | None) -> None:
        if not path:
            return
        with pathlib.Path(path).open('a', encoding='utf-8') as handle:
            handle.write(self.summary())
