import copy
import json
import pathlib
import shutil
import urllib.parse
from collections.abc import Callable
from collections.abc import Mapping
from typing import Any

import pytest

from gha_tools.rulesets import desired
from gha_tools.rulesets import main

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

    def __init__(self) -> None:
        self.private = False
        self.classic = False
        self.rulesets: dict[int, dict[str, Any]] = {}
        # Defined on the owning organization and inherited by the repo; the
        # repo endpoints list and read these but cannot change them.
        self.inherited: dict[int, dict[str, Any]] = {}
        self.calls: list[str] = []
        # 'METHOD /path' -> status to fail that request with.
        self.errors: dict[str, int] = {}
        self._next_id = 100

    def store(
        self, body: dict[str, Any], ruleset_id: int | None = None
    ) -> int:
        if ruleset_id is None:
            ruleset_id = self._next_id
            self._next_id += 1
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
        base = f'/repos/{REPO}'
        if path == base:
            return 200, {'private': self.private, 'default_branch': 'master'}
        if path.startswith(f'{base}/rulesets'):
            return self._rulesets(method, path[len(base) :], admin, body)
        if path == f'{base}/branches/master/protection':
            return self._protection(method, admin)
        return 404, {'message': 'Not Found'}

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


@pytest.fixture(name='github', scope='function')
def github_fixture(
    serve: Callable[..., str], monkeypatch: pytest.MonkeyPatch
) -> FakeGitHub:
    fake = FakeGitHub()

    def handle(
        method: str,
        path: str,
        headers: Mapping[str, str],
        body: Any,  # noqa: ANN401
    ) -> tuple[int, Any]:
        token = headers['Authorization'].removeprefix('Bearer ')
        return fake.handle(method, path, token, body)

    monkeypatch.setenv('GITHUB_API_URL', serve(handle))
    return fake


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


@pytest.fixture(name='checkout', scope='function')
def checkout_fixture(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> pathlib.Path:
    rulesets = tmp_path / '.github' / 'rulesets'
    rulesets.mkdir(parents=True)
    # Committed straight from a UI export, server fields and all.
    exported = {'id': 42, 'source_type': 'Repository'} | BASE
    (rulesets / 'base.json').write_text(json.dumps(exported))
    (rulesets / 'required-checks.json').write_text(json.dumps(CHECKS))
    workflows = tmp_path / '.github' / 'workflows'
    workflows.mkdir()
    (workflows / 'ci.yml').write_text('on: push\njobs:\n  lint: {}\n')
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(tmp_path / 'summary.md'))
    return tmp_path


def _run(
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


def test_apply_converges_and_check_detects_drift(
    github: FakeGitHub, checkout: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    github.classic = True
    github.store(BASE | {'name': 'stray'})
    github.store(CHECKS | {'enforcement': 'disabled'})

    assert _run(monkeypatch, checkout, 'plan', READER) == 0
    summary = (checkout / 'summary.md').read_text()
    assert 'create ruleset "base"' in summary
    assert 'update ruleset "required-checks"' in summary
    assert 'delete ruleset "stray"' in summary
    assert 'classic branch protection was not checked' in summary
    assert not [c for c in github.calls if not c.startswith('GET')]

    assert _run(monkeypatch, checkout, 'check', ADMIN) == 1
    assert _run(monkeypatch, checkout, 'apply', ADMIN) == 0
    assert not github.classic
    assert sorted(r['name'] for r in github.rulesets.values()) == [
        'base',
        'required-checks',
    ]
    assert _run(monkeypatch, checkout, 'check', ADMIN) == 0
    assert _run(monkeypatch, checkout, 'plan', READER) == 0
    assert '- none' in (checkout / 'summary.md').read_text()

    # A UI edit to the bypass list is invisible to a non-admin plan but is
    # caught by the admin drift check.
    [base_id] = [i for i, r in github.rulesets.items() if r['name'] == 'base']
    github.rulesets[base_id]['bypass_actors'] = []
    assert _run(monkeypatch, checkout, 'plan', READER) == 0
    assert '- none' in (checkout / 'summary.md').read_text()
    assert _run(monkeypatch, checkout, 'check', ADMIN) == 1
    assert _run(monkeypatch, checkout, 'apply', ADMIN) == 0

    github.classic = True
    assert _run(monkeypatch, checkout, 'check', ADMIN) == 1
    summary = (checkout / 'summary.md').read_text()
    assert 'delete classic branch protection' in summary


def test_api_rejections_are_reported(
    github: FakeGitHub, checkout: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = CHECKS | {'name': 'broken', 'enforcement': 'evaluate'}
    (checkout / '.github' / 'rulesets' / 'broken.json').write_text(
        json.dumps(bad)
    )
    assert _run(monkeypatch, checkout, 'apply', ADMIN) == 1
    summary = (checkout / 'summary.md').read_text()
    assert 'create ruleset "broken": POST' in summary
    assert 'HTTP 422' in summary
    assert len(github.rulesets) == 2


def test_rulesets_inherited_from_the_org_are_left_alone(
    github: FakeGitHub, checkout: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    github.inherit(BASE | {'name': 'org-wide'})
    assert _run(monkeypatch, checkout, 'apply', ADMIN) == 0
    assert 'org-wide' not in (checkout / 'summary.md').read_text()
    assert _run(monkeypatch, checkout, 'check', ADMIN) == 0


def test_private_repositories_are_skipped(
    github: FakeGitHub, checkout: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    github.private = True
    assert _run(monkeypatch, checkout, 'apply', ADMIN) == 0
    assert not [
        c for c in github.calls if '/rulesets' in c or '/protection' in c
    ]
    assert 'require GitHub Pro' in (checkout / 'summary.md').read_text()


def test_misconfiguration_fails_before_touching_github(
    github: FakeGitHub, checkout: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _run(monkeypatch, checkout, 'apply', None) == 1
    assert 'RULESETS_TOKEN' in (checkout / 'summary.md').read_text()

    (checkout / '.github' / 'rulesets' / 'copy.json').write_text(
        json.dumps(CHECKS)
    )
    assert _run(monkeypatch, checkout, 'apply', ADMIN) == 1
    assert 'duplicate ruleset name' in (checkout / 'summary.md').read_text()

    for path in (checkout / '.github' / 'rulesets').iterdir():
        path.unlink()
    assert _run(monkeypatch, checkout, 'apply', ADMIN) == 1
    assert 'no ruleset definitions' in (checkout / 'summary.md').read_text()
    assert not github.calls


def _requiring(name: str, *contexts: str) -> desired.Ruleset:
    checks = [{'context': context} for context in contexts]
    rule = {
        'type': 'required_status_checks',
        'parameters': {'required_status_checks': checks},
    }
    return CHECKS | {'name': name, 'rules': [rule]}


@pytest.mark.usefixtures('github')
def test_required_check_warnings_reach_the_summary(
    checkout: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rulesets = checkout / '.github' / 'rulesets'
    for ruleset in (
        _requiring('more', 'lnt', 'build readme'),
        _requiring('dup', 'lnt'),
    ):
        (rulesets / f'{ruleset["name"]}.json').write_text(json.dumps(ruleset))
    workflows = checkout / '.github' / 'workflows'
    (workflows / 'docs.yaml').write_text(
        'on:\n'
        '  pull_request:\n'
        '    paths: [docs/**]\n'
        'jobs:\n'
        '  readme:\n'
        '    name: build readme\n'
    )
    (workflows / 'broken.yml').write_text('jobs: [unclosed\n')
    # Valid YAML that isn't a workflow is not worth a warning.
    (workflows / 'empty.yml').write_text('')
    (workflows / 'list.yml').write_text('- not a mapping\n')

    assert _run(monkeypatch, checkout, 'plan', READER) == 0
    summary = (checkout / 'summary.md').read_text()
    warnings = [
        line for line in summary.splitlines() if line.startswith('- **warning')
    ]
    # "lnt" is required twice but warned about once.
    assert len(warnings) == 3
    for expected in (
        'broken.yml: could not parse workflow',
        '"lnt" matches no workflow job',
        '"build readme" only comes from path-filtered workflow(s) docs.yaml',
    ):
        assert any(expected in warning for warning in warnings)

    shutil.rmtree(workflows)
    assert _run(monkeypatch, checkout, 'plan', READER) == 0
    summary = (checkout / 'summary.md').read_text()
    assert '"lint" matches no workflow job' in summary


@pytest.mark.parametrize(
    ('content', 'message'),
    [
        ('{"name": ', 'base.json: invalid JSON'),
        ('[]', 'base.json: expected a JSON object'),
        (json.dumps(BASE | {'target': None}), 'missing string "target"'),
        (
            json.dumps(BASE | {'enforcement': 1}),
            'missing string "enforcement"',
        ),
        (json.dumps(BASE | {'rules': {}}), '"rules" must be a list'),
    ],
)
def test_invalid_definitions_fail_before_touching_github(
    github: FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    content: str,
    message: str,
) -> None:
    (checkout / '.github' / 'rulesets' / 'base.json').write_text(content)
    assert _run(monkeypatch, checkout, 'apply', ADMIN) == 1
    assert message in (checkout / 'summary.md').read_text()
    assert not github.calls


@pytest.mark.parametrize(
    ('token', 'failing', 'status'),
    [('bogus', None, 401), (ADMIN, f'GET /repos/{REPO}', 500)],
)
def test_api_errors_fail_the_run(
    github: FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    token: str,
    failing: str | None,
    status: int,
) -> None:
    if failing is not None:
        github.errors[failing] = status
    assert _run(monkeypatch, checkout, 'check', token) == 1
    assert f'HTTP {status}' in (checkout / 'summary.md').read_text()


def test_failed_classic_protection_delete_fails_apply(
    github: FakeGitHub, checkout: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    github.classic = True
    github.errors[f'DELETE /repos/{REPO}/branches/master/protection'] = 500
    assert _run(monkeypatch, checkout, 'apply', ADMIN) == 1
    summary = (checkout / 'summary.md').read_text()
    assert 'delete classic branch protection: DELETE' in summary
    assert 'HTTP 500' in summary
    assert github.classic
    # Rulesets are still created, so the branch is not left unprotected.
    assert len(github.rulesets) == 2
