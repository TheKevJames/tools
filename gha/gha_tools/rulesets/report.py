import pathlib
from collections.abc import Sequence

from gha_tools.rulesets import diff

MODES = ('plan', 'apply', 'check')


def _annotate(level: str, message: str) -> None:
    # Workflow commands are line-oriented; encode so multi-line messages (eg.
    # API error bodies) stay in one annotation.
    encoded = message.replace('%', '%25').replace('\n', '%0A')
    print(f'::{level}::{encoded}', flush=True)


def describe(change: diff.Change) -> str:
    match change:
        case diff.Create():
            return f'create ruleset "{change.name}"'
        case diff.Update():
            return f'update ruleset "{change.name}"'
        case diff.Delete():
            return f'delete ruleset "{change.name}"'


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

    def changes(
        self, changes: Sequence[diff.Change], *, delete_classic: bool
    ) -> None:
        self._changes = [describe(c) for c in changes]
        if delete_classic:
            self._changes.append('delete classic branch protection')
        for line in self._changes:
            print(f'{self.mode}: {line}', flush=True)
        for change in changes:
            if isinstance(change, diff.Update):
                print(change.detail, flush=True)
                self._diffs.append((change.name, change.detail))
        if not self._changes:
            print(f'{self.mode}: no changes', flush=True)

    def summary(self) -> str:
        lines = [f'## Rulesets ({self.mode}): {self.repository}', '']
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
