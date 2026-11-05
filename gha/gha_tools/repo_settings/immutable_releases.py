"""
Whether published releases are immutable, from
`.github/immutable-releases.json`: `{"enabled": true}`.

Once a release is published, its tag can't be moved or deleted, and its tag
name can never be reused.
"""

import json
import pathlib

from gha_tools.repo_settings import github
from gha_tools.repo_settings import report

PATH = pathlib.Path('.github', 'immutable-releases.json')


class InvalidImmutableReleasesError(ValueError):
    pass


def parse(label: str, text: str) -> bool:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidImmutableReleasesError(
            f'{label}: invalid JSON: {exc}'
        ) from exc
    if (
        not isinstance(data, dict)
        or set(data) != {'enabled'}
        or not isinstance(data['enabled'], bool)
    ):
        raise InvalidImmutableReleasesError(
            f'{label}: expected exactly {{"enabled": <boolean>}}'
        )
    enabled: bool = data['enabled']
    return enabled


def validate(root: pathlib.Path, out: report.Report) -> bool | None:
    path = root / PATH
    if not path.is_file():
        out.error(f'{PATH}: missing')
        return None
    try:
        return parse(str(PATH), path.read_text(encoding='utf-8'))
    except InvalidImmutableReleasesError as exc:
        out.error(str(exc))
        return None


def _unreadable(mode: str, out: report.Report) -> int:
    if mode == 'plan':
        out.notice(
            'immutable releases were not compared (needs an admin token)'
        )
        return 0
    out.error(
        'could not read immutable releases: the token needs '
        'Administration: read'
    )
    return 1


def _apply(
    client: github.Client, enabled: bool, change: str, out: report.Report
) -> int:
    try:
        client.set_immutable_releases(enabled)
    except github.ApiError as exc:
        out.error(f'{change}: {exc}')
        return 1
    return 0


def reconcile(
    client: github.Client, enabled: bool, mode: str, out: report.Report
) -> int:
    have = client.immutable_releases()
    if have is None:
        return _unreadable(mode, out)
    if have == enabled:
        return 0
    change = f'{"enable" if enabled else "disable"} immutable releases'
    out.change(change)
    if mode == 'check':
        out.error(
            'immutable releases have drifted; run the workflow manually to '
            'apply'
        )
        return 1
    if mode != 'apply':
        return 0
    return _apply(client, enabled, change, out)
