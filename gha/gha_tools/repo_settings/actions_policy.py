"""
Whether Actions is enabled, which actions it may run, and whether they must be
pinned to a full commit SHA, from `.github/actions-policy.json`: the body of
`PUT /repos/{owner}/{repo}/actions/permissions`, with every field required so
the file is the whole policy.

`allowed_actions: selected` is rejected: its allow-list lives behind another
endpoint, which this does not manage.
"""

import json
import pathlib
from typing import Any

from gha_tools.repo_settings import github
from gha_tools.repo_settings import report

Policy = dict[str, Any]

PATH = pathlib.Path('.github', 'actions-policy.json')
_FIELDS = frozenset({'enabled', 'allowed_actions', 'sha_pinning_required'})
_ALLOWED = ('all', 'local_only')
_CHANGE = 'update Actions policy'


class InvalidPolicyError(ValueError):
    pass


def parse(label: str, text: str) -> Policy:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidPolicyError(f'{label}: invalid JSON: {exc}') from exc

    if not isinstance(data, dict):
        raise InvalidPolicyError(f'{label}: expected a JSON object')
    if set(data) != _FIELDS:
        raise InvalidPolicyError(
            f'{label}: expected exactly the fields {sorted(_FIELDS)}'
        )
    for key in ('enabled', 'sha_pinning_required'):
        if not isinstance(data[key], bool):
            raise InvalidPolicyError(f'{label}: "{key}" must be a boolean')
    if data['allowed_actions'] not in _ALLOWED:
        raise InvalidPolicyError(
            f'{label}: "allowed_actions" must be one of {list(_ALLOWED)}'
        )
    return data


def validate(root: pathlib.Path, out: report.Report) -> Policy | None:
    """The definition; {} if unmanaged (no file), None if invalid."""
    path = root / PATH
    if not path.is_file():
        out.notice(f'Actions policy skipped: no {PATH}')
        return {}
    try:
        return parse(str(PATH), path.read_text(encoding='utf-8'))
    except InvalidPolicyError as exc:
        out.error(str(exc))
        return None


def _unreadable(mode: str, out: report.Report) -> int:
    if mode == 'plan':
        out.notice('Actions policy was not compared (needs an admin token)')
        return 0
    out.error(
        'could not read the Actions policy: the token needs '
        'Administration: read'
    )
    return 1


def _apply(client: github.Client, policy: Policy, out: report.Report) -> int:
    try:
        client.set_actions_policy(policy)
    except github.ApiError as exc:
        out.error(f'{_CHANGE}: {exc}')
        return 1
    return 0


def reconcile(
    client: github.Client, policy: Policy, mode: str, out: report.Report
) -> int:
    if not policy:
        return 0
    have = client.actions_policy()
    if have is None:
        return _unreadable(mode, out)
    if all(have.get(key) == value for key, value in policy.items()):
        return 0
    out.change(_CHANGE, report.field_diff(policy, have))
    if mode == 'check':
        out.error(
            'the Actions policy has drifted; run the workflow manually to '
            'apply'
        )
        return 1
    if mode != 'apply':
        return 0
    return _apply(client, policy, out)
