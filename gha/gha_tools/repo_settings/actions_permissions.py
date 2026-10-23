"""
The default permissions of the repository's GITHUB_TOKEN, and whether
Actions may approve pull requests, from `.github/actions-permissions.json`:
the body of `PUT /repos/{owner}/{repo}/actions/permissions/workflow`, with
both fields required so the file is the whole policy.
"""

import json
import pathlib
from typing import Any

from gha_tools.repo_settings import github
from gha_tools.repo_settings import report

Permissions = dict[str, Any]

PATH = pathlib.Path('.github', 'actions-permissions.json')
_DEFAULTS = ('read', 'write')
_CHANGE = 'update Actions workflow permissions'


class InvalidPermissionsError(ValueError):
    pass


def parse(label: str, text: str) -> Permissions:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidPermissionsError(f'{label}: invalid JSON: {exc}') from exc

    if not isinstance(data, dict):
        raise InvalidPermissionsError(f'{label}: expected a JSON object')
    fields = {
        'default_workflow_permissions',
        'can_approve_pull_request_reviews',
    }
    if set(data) != fields:
        raise InvalidPermissionsError(
            f'{label}: expected exactly the fields {sorted(fields)}'
        )
    if data['default_workflow_permissions'] not in _DEFAULTS:
        raise InvalidPermissionsError(
            f'{label}: "default_workflow_permissions" must be one of '
            f'{list(_DEFAULTS)}'
        )
    if not isinstance(data['can_approve_pull_request_reviews'], bool):
        raise InvalidPermissionsError(
            f'{label}: "can_approve_pull_request_reviews" must be a boolean'
        )
    return data


def validate(root: pathlib.Path, out: report.Report) -> Permissions | None:
    path = root / PATH
    if not path.is_file():
        out.error(f'{PATH}: missing')
        return None
    try:
        return parse(str(PATH), path.read_text(encoding='utf-8'))
    except InvalidPermissionsError as exc:
        out.error(str(exc))
        return None


def _unreadable(mode: str, out: report.Report) -> int:
    # The Actions GITHUB_TOKEN cannot be granted administration, so only plan,
    # which never gets the admin token, may proceed without it.
    if mode == 'plan':
        out.notice(
            'Actions workflow permissions were not compared (needs an admin '
            'token)'
        )
        return 0
    out.error(
        'could not read Actions workflow permissions: the token needs '
        'Administration: read'
    )
    return 1


def _apply(
    client: github.Client, permissions: Permissions, out: report.Report
) -> int:
    try:
        client.set_actions_permissions(permissions)
    except github.ApiError as exc:
        out.error(f'{_CHANGE}: {exc}')
        return 1
    return 0


def reconcile(
    client: github.Client,
    permissions: Permissions,
    mode: str,
    out: report.Report,
) -> int:
    have = client.actions_permissions()
    if have is None:
        return _unreadable(mode, out)
    if all(have.get(key) == value for key, value in permissions.items()):
        return 0
    out.change(_CHANGE, report.field_diff(permissions, have))
    if mode == 'check':
        out.error(
            'Actions workflow permissions have drifted; run the workflow '
            'manually to apply'
        )
        return 1
    if mode != 'apply':
        return 0
    return _apply(client, permissions, out)
