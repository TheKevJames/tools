"""
Deployment environments, from `.github/environments/<name>.json`.

Each definition is the environment's deployment policies, the only refs that
may run a job in it (and so read its secrets):

    {"deployment_policies": [{"type": "branch", "name": "~DEFAULT_BRANCH"}]}

`~DEFAULT_BRANCH` stands for the repository's default branch, as in rulesets.
An environment cannot be unrestricted: GitHub creates one like that whenever a
workflow names an environment that doesn't exist, which is what these
definitions replace.

The definitions are authoritative: environments missing from them are
deleted, as are protection rules they don't express (required reviewers, wait
timers). A repository without `.github/environments/` doesn't manage them.
"""

import dataclasses
import json
import pathlib
from typing import Any

from gha_tools.repo_settings import github
from gha_tools.repo_settings import report

Policy = tuple[str, str]

DIRECTORY = pathlib.Path('.github', 'environments')
DEFAULT_BRANCH = '~DEFAULT_BRANCH'
_TYPES = ('branch', 'tag')
_CUSTOM = {'protected_branches': False, 'custom_branch_policies': True}
# Sent on every update so protection rules made in the UI are removed.
_SETTINGS = {
    'wait_timer': 0,
    'prevent_self_review': False,
    'reviewers': None,
    'deployment_branch_policy': _CUSTOM,
}


class InvalidEnvironmentError(ValueError):
    pass


@dataclasses.dataclass(frozen=True)
class Change:
    name: str
    create: bool = False
    # Create or update the environment's settings.
    put: bool = False
    add: frozenset[Policy] = frozenset()
    # Policy ids to remove, with the policy each one is.
    remove: tuple[tuple[int, Policy], ...] = ()
    delete: bool = False

    def describe(self) -> str:
        if self.delete:
            return f'delete environment "{self.name}"'
        if self.create:
            return f'create environment "{self.name}"'
        if self.put and not self.remove and not self.add:
            return f'update environment "{self.name}" protection rules'
        return f'update environment "{self.name}"'

    def detail(self) -> str | None:
        if self.delete:
            return None
        lines = ['--- github', '+++ repo']
        lines.extend(f'-{t}: {n}' for _, (t, n) in sorted(self.remove))
        lines.extend(f'+{t}: {n}' for t, n in sorted(self.add))
        return '\n'.join(lines)


def _policy(label: str, value: object) -> Policy:
    if (
        not isinstance(value, dict)
        or set(value) != {'type', 'name'}
        or value['type'] not in _TYPES
        or not isinstance(value['name'], str)
        or not value['name']
    ):
        raise InvalidEnvironmentError(
            f'{label}: each deployment policy must be exactly '
            f'{{"type": {" | ".join(_TYPES)}, "name": <pattern>}}'
        )
    kind: str = value['type']
    pattern: str = value['name']
    return kind, pattern


def parse(label: str, text: str) -> frozenset[Policy]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidEnvironmentError(f'{label}: invalid JSON: {exc}') from exc

    if not isinstance(data, dict) or set(data) != {'deployment_policies'}:
        raise InvalidEnvironmentError(
            f'{label}: expected exactly the field "deployment_policies"'
        )
    raw = data['deployment_policies']
    if not isinstance(raw, list) or not raw:
        raise InvalidEnvironmentError(
            f'{label}: "deployment_policies" must be a non-empty list'
        )
    policies = [_policy(label, value) for value in raw]
    if len(set(policies)) != len(policies):
        raise InvalidEnvironmentError(f'{label}: duplicate deployment policy')
    return frozenset(policies)


def validate(
    root: pathlib.Path, out: report.Report
) -> dict[str, frozenset[Policy]] | None:
    """
    Definitions keyed by environment name; {} if unmanaged.

    A missing or empty directory means unmanaged rather than "no
    environments", which would delete every one.
    """
    directory = root / DIRECTORY
    paths = sorted(directory.glob('*.json')) if directory.is_dir() else []
    if not paths:
        out.notice(f'environments skipped: no definitions in {DIRECTORY}/')
        return {}
    try:
        return {
            path.stem: parse(
                f'{DIRECTORY}/{path.name}', path.read_text(encoding='utf-8')
            )
            for path in paths
        }
    except InvalidEnvironmentError as exc:
        out.error(str(exc))
        return None


def _resolve(
    policies: frozenset[Policy], default_branch: str
) -> frozenset[Policy]:
    return frozenset(
        (kind, default_branch if name == DEFAULT_BRANCH else name)
        for kind, name in policies
    )


def _diff(
    client: github.Client,
    name: str,
    want: frozenset[Policy],
    have: dict[str, Any] | None,
) -> Change | None:
    if have is None:
        return Change(name, create=True, put=True, add=want)
    rules = {rule['type'] for rule in have['protection_rules']}
    custom = have['deployment_branch_policy'] == _CUSTOM
    put = not custom or bool(rules - {'branch_policy'})
    existing = client.deployment_policies(name) if custom else {}
    remove = tuple(
        (policy_id, policy)
        for policy_id, policy in existing.items()
        if policy not in want
    )
    add = want - set(existing.values())
    if not (put or remove or add):
        return None
    return Change(name, put=put, add=add, remove=remove)


def plan(
    client: github.Client,
    definitions: dict[str, frozenset[Policy]],
    default_branch: str,
) -> list[Change]:
    """Creates and updates first, then deletes."""
    have = client.environments()
    changes = [
        change
        for name, policies in definitions.items()
        if (
            change := _diff(
                client,
                name,
                _resolve(policies, default_branch),
                have.get(name),
            )
        )
    ]
    changes.extend(
        Change(name, delete=True)
        for name in sorted(set(have) - set(definitions))
    )
    return changes


def _apply_change(client: github.Client, change: Change) -> None:
    if change.delete:
        client.delete_environment(change.name)
        return
    if change.put:
        client.put_environment(change.name, _SETTINGS)
    # Remove before adding, so the environment never admits more refs than
    # either the old or the new policies: admitting none for a moment is safe.
    for policy_id, _ in change.remove:
        client.delete_deployment_policy(change.name, policy_id)
    for kind, pattern in sorted(change.add):
        client.create_deployment_policy(change.name, kind, pattern)


def _apply(
    client: github.Client, changes: list[Change], out: report.Report
) -> int:
    failures = 0
    for change in changes:
        try:
            _apply_change(client, change)
        except github.ApiError as exc:
            failures += 1
            out.error(f'{change.describe()}: {exc}')
    return 1 if failures else 0


def reconcile(
    client: github.Client,
    repo: dict[str, Any],
    definitions: dict[str, frozenset[Policy]],
    mode: str,
    out: report.Report,
) -> int:
    if not definitions:
        return 0
    if repo['private']:
        out.notice(
            'environments skipped: environments on private repositories '
            'require GitHub Pro'
        )
        return 0
    changes = plan(client, definitions, repo['default_branch'])
    for change in changes:
        out.change(change.describe(), change.detail())
    if mode == 'check' and changes:
        out.error(
            'environments have drifted; run the workflow manually to apply'
        )
        return 1
    if mode != 'apply':
        return 0
    return _apply(client, changes, out)
