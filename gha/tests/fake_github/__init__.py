"""An in-memory GitHub, and a repository checkout, for repo_settings tests."""

import copy
import itertools
import json
import pathlib
import urllib.parse
from typing import Any

import pytest

from gha_tools.repo_settings import main
from gha_tools.repo_settings.rulesets import desired

ADMIN = 'admin-token'
READER = 'read-token'
REPO = 'owner/repo'
API = f'https://api.github.com/repos/{REPO}'

# Defaults the real API fills into rule parameters (observed on public repos).
_PARAM_DEFAULTS = {
    'pull_request': {
        'required_reviewers': [],
        'dismissal_restriction': {'enabled': False, 'allowed_actors': []},
        'require_extra_approval_for_unattributed_changes': True,
    },
    'required_status_checks': {'do_not_enforce_on_create': False},
}


class FakeGitHub:
    """In-memory model of the slice of the repos API the reconciler uses."""

    # Shared by every instance: ids only need to be unique, as GitHub's are.
    _ids = itertools.count(100)

    def __init__(self) -> None:
        self.private = False
        self.classic = False
        self.actions = {
            'default_workflow_permissions': 'write',
            'can_approve_pull_request_reviews': False,
        }
        self.rulesets: dict[int, dict[str, Any]] = {}
        # Defined on the owning organization and inherited by the repo; the
        # repo endpoints list and read these but cannot change them.
        self.inherited: dict[int, dict[str, Any]] = {}
        self.calls: list[str] = []
        # 'METHOD /path' -> status to fail that request with.
        self.errors: dict[str, int] = {}

    def store(
        self, body: dict[str, Any], ruleset_id: int | None = None
    ) -> int:
        if ruleset_id is None:
            ruleset_id = next(self._ids)
        stored = copy.deepcopy(body)
        stored.setdefault('bypass_actors', [])
        for rule in stored.get('rules', []):
            defaults = _PARAM_DEFAULTS.get(rule['type'], {})
            rule['parameters'] = {**defaults, **rule.get('parameters', {})}
        stored['rules'] = list(reversed(stored.get('rules', [])))
        self.rulesets[ruleset_id] = stored
        return ruleset_id

    def inherit(self, body: dict[str, Any]) -> None:
        ruleset_id = self.store(body)
        self.inherited[ruleset_id] = self.rulesets.pop(ruleset_id)

    def detail(self, ruleset_id: int, admin: bool) -> dict[str, Any]:
        org = ruleset_id in self.inherited
        stored = self.inherited if org else self.rulesets
        body = copy.deepcopy(stored[ruleset_id])
        if not admin:
            del body['bypass_actors']
        owner = REPO.split('/', maxsplit=1)[0]
        server_fields = {
            'id': ruleset_id,
            'source_type': 'Organization' if org else 'Repository',
            'source': owner if org else REPO,
            'node_id': f'RRS_{ruleset_id}',
            '_links': {'self': {'href': f'{API}/rulesets/{ruleset_id}'}},
            'created_at': '2026-01-01T00:00:00Z',
            'updated_at': '2026-01-01T00:00:00Z',
        }
        return server_fields | body

    def _list(self, query: str) -> list[dict[str, Any]]:
        params = urllib.parse.parse_qs(query)
        ids = list(self.rulesets)
        if params.get('includes_parents', ['true']) == ['true']:
            ids = [*self.inherited, *ids]
        per_page = min(int(params.get('per_page', ['30'])[0]), 100)
        summary = (
            'id',
            'name',
            'target',
            'source_type',
            'source',
            'enforcement',
            'node_id',
            '_links',
            'created_at',
            'updated_at',
        )
        return [
            {k: v for k, v in self.detail(i, False).items() if k in summary}
            for i in ids[:per_page]
        ]

    def handle(
        self,
        method: str,
        path: str,
        token: str,
        body: Any,  # noqa: ANN401
    ) -> tuple[int, Any]:
        call = f'{method} {path}'
        self.calls.append(call)
        admin = token == ADMIN
        if token not in {ADMIN, READER}:
            return 401, {'message': 'Bad credentials'}
        if call in self.errors:
            return self.errors[call], {'message': 'Server Error'}
        return self._route(method, path, admin, body)

    def _route(
        self,
        method: str,
        path: str,
        admin: bool,
        body: Any,  # noqa: ANN401
    ) -> tuple[int, Any]:
        base = f'/repos/{REPO}'
        if path == base:
            return 200, {'private': self.private, 'default_branch': 'master'}
        if path.startswith(f'{base}/rulesets'):
            return self._rulesets(method, path[len(base) :], admin, body)
        if path == f'{base}/branches/master/protection':
            return self._protection(method, admin)
        if path == f'{base}/actions/permissions/workflow':
            return self._actions(method, admin, body)
        return 404, {'message': 'Not Found'}

    def _actions(
        self,
        method: str,
        admin: bool,
        body: Any,  # noqa: ANN401
    ) -> tuple[int, Any]:
        if not admin:
            return 403, {'message': 'Resource not accessible'}
        if method == 'GET':
            return 200, self.actions.copy()
        if set(body) - set(self.actions):
            return 422, {'message': 'Invalid request'}
        self.actions |= body
        return 204, None

    def _rulesets(
        self,
        method: str,
        path: str,
        admin: bool,
        body: Any,  # noqa: ANN401
    ) -> tuple[int, Any]:
        route, _, query = path.partition('?')
        if route == '/rulesets' and method == 'GET':
            return 200, self._list(query)
        if route == '/rulesets' and method == 'POST':
            return self._write(admin, body, None)
        ruleset_id = int(route.removeprefix('/rulesets/'))
        return self._ruleset(method, ruleset_id, admin, body)

    def _ruleset(
        self,
        method: str,
        ruleset_id: int,
        admin: bool,
        body: Any,  # noqa: ANN401
    ) -> tuple[int, Any]:
        known = ruleset_id in self.rulesets
        if method == 'GET' and (known or ruleset_id in self.inherited):
            return 200, self.detail(ruleset_id, admin)
        if not known:
            return 404, {'message': 'Not Found'}
        if method == 'PUT':
            return self._write(admin, body, ruleset_id)
        if not admin:
            return 403, {'message': 'Resource not accessible'}
        del self.rulesets[ruleset_id]
        return 204, None

    def _protection(self, method: str, admin: bool) -> tuple[int, Any]:
        if not admin:
            return 403, {'message': 'Resource not accessible'}
        if not self.classic:
            return 404, {'message': 'Branch not protected'}
        if method == 'DELETE':
            self.classic = False
            return 204, None
        return 200, {}

    def _write(
        self, admin: bool, body: dict[str, Any], ruleset_id: int | None
    ) -> tuple[int, Any]:
        if not admin:
            return 403, {'message': 'Resource not accessible'}
        unknown = set(body) & desired.SERVER_FIELDS
        if unknown or body.get('enforcement') not in {'active', 'disabled'}:
            return 422, {
                'message': 'Invalid request',
                'fields': sorted(unknown),
            }
        others = {
            r['name'] for i, r in self.rulesets.items() if i != ruleset_id
        }
        if body['name'] in others:
            return 422, {'message': 'Name must be unique'}
        status = 201 if ruleset_id is None else 200
        ruleset_id = self.store(body, ruleset_id)
        return status, self.detail(ruleset_id, admin)


BASE = {
    'name': 'base',
    'target': 'branch',
    'enforcement': 'active',
    'conditions': {
        'ref_name': {'include': ['~DEFAULT_BRANCH'], 'exclude': []}
    },
    'bypass_actors': [
        {
            'actor_id': 5,
            'actor_type': 'RepositoryRole',
            'bypass_mode': 'always',
        }
    ],
    'rules': [
        {'type': 'deletion'},
        {'type': 'non_fast_forward'},
        {
            'type': 'pull_request',
            'parameters': {
                'required_approving_review_count': 1,
                'allowed_merge_methods': ['squash', 'rebase'],
            },
        },
    ],
}
CHECKS = {
    'name': 'required-checks',
    'target': 'branch',
    'enforcement': 'active',
    'conditions': {
        'ref_name': {'include': ['~DEFAULT_BRANCH'], 'exclude': []}
    },
    'rules': [
        {
            'type': 'required_status_checks',
            'parameters': {
                'strict_required_status_checks_policy': False,
                'required_status_checks': [{'context': 'lint'}],
            },
        }
    ],
}


PERMISSIONS = {
    'default_workflow_permissions': 'read',
    'can_approve_pull_request_reviews': True,
}


def write_checkout(root: pathlib.Path) -> None:
    rulesets = root / '.github' / 'rulesets'
    rulesets.mkdir(parents=True)
    # Committed straight from a UI export, server fields and all.
    exported = {'id': 42, 'source_type': 'Repository'} | BASE
    (rulesets / 'base.json').write_text(json.dumps(exported))
    (rulesets / 'required-checks.json').write_text(json.dumps(CHECKS))
    workflows = root / '.github' / 'workflows'
    workflows.mkdir()
    (workflows / 'ci.yml').write_text('on: push\njobs:\n  lint: {}\n')
    (root / '.github' / 'actions-permissions.json').write_text(
        json.dumps(PERMISSIONS)
    )


def run(
    monkeypatch: pytest.MonkeyPatch,
    checkout: pathlib.Path,
    mode: str,
    token: str | None,
) -> int:
    if token is None:
        monkeypatch.delenv('GH_TOKEN', raising=False)
    else:
        monkeypatch.setenv('GH_TOKEN', token)
    (checkout / 'summary.md').unlink(missing_ok=True)
    args = ['--mode', mode, '--repository', REPO, '--directory', checkout]
    return main.main([str(arg) for arg in args])
