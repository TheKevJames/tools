import copy
import http.server
import json
import pathlib
import threading
from collections.abc import Iterator
from typing import Any

import pytest

from gha_tools.rulesets import desired
from gha_tools.rulesets import main

ADMIN = 'admin-token'
READER = 'read-token'
REPO = 'owner/repo'

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
        self.calls: list[str] = []
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

    def detail(self, ruleset_id: int, admin: bool) -> dict[str, Any]:
        body = copy.deepcopy(self.rulesets[ruleset_id])
        if not admin:
            del body['bypass_actors']
        server_fields = {
            'id': ruleset_id,
            'source_type': 'Repository',
            'source': REPO,
            'node_id': f'RRS_{ruleset_id}',
        }
        return server_fields | body

    def handle(
        self,
        method: str,
        path: str,
        token: str,
        body: Any,  # noqa: ANN401
    ) -> tuple[int, Any]:
        self.calls.append(f'{method} {path}')
        admin = token == ADMIN
        if token not in {ADMIN, READER}:
            return 401, {'message': 'Bad credentials'}
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
        if path.startswith('/rulesets?') and method == 'GET':
            return 200, [
                {'id': i, 'name': r['name'], 'source_type': 'Repository'}
                for i, r in self.rulesets.items()
            ]
        if path == '/rulesets' and method == 'POST':
            return self._write(admin, body, None)
        ruleset_id = int(path.removeprefix('/rulesets/'))
        if method == 'GET':
            return 200, self.detail(ruleset_id, admin)
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
        ruleset_id = self.store(body, ruleset_id)
        return 200, self.detail(ruleset_id, admin)


@pytest.fixture(name='github', scope='function')
def github_fixture(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeGitHub]:
    fake = FakeGitHub()

    class Handler(http.server.BaseHTTPRequestHandler):
        def _serve(self) -> None:
            length = int(self.headers.get('Content-Length') or 0)
            body = json.loads(self.rfile.read(length)) if length else None
            token = self.headers['Authorization'].removeprefix('Bearer ')
            status, payload = fake.handle(self.command, self.path, token, body)
            self.send_response(status)
            self.end_headers()
            if payload is not None:
                self.wfile.write(json.dumps(payload).encode())

        do_GET = do_POST = do_PUT = do_DELETE = _serve

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv(
        'GITHUB_API_URL', f'http://127.0.0.1:{server.server_address[1]}'
    )
    yield fake
    server.shutdown()


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
    code = main.main([str(arg) for arg in args])
    print((checkout / 'summary.md').read_text())
    return code


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


def test_private_repositories_are_skipped(
    github: FakeGitHub, checkout: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    github.private = True
    assert _run(monkeypatch, checkout, 'apply', ADMIN) == 0
    assert github.calls == [f'GET /repos/{REPO}']
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
