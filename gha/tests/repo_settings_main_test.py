import json
import pathlib
import shutil

import pytest

from gha_tools.repo_settings.rulesets import desired
from tests import fake_github


def test_apply_converges_and_check_detects_drift(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    github.classic = True
    github.store(fake_github.BASE | {'name': 'stray'})
    github.store(fake_github.CHECKS | {'enforcement': 'disabled'})

    assert (
        fake_github.run(monkeypatch, checkout, 'plan', fake_github.READER) == 0
    )
    summary = (checkout / 'summary.md').read_text()
    assert 'create ruleset "base"' in summary
    assert 'update ruleset "required-checks"' in summary
    assert 'delete ruleset "stray"' in summary
    assert 'classic branch protection was not checked' in summary
    assert not [c for c in github.calls if not c.startswith('GET')]

    assert (
        fake_github.run(monkeypatch, checkout, 'check', fake_github.ADMIN) == 1
    )
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 0
    )
    assert not github.classic
    assert sorted(r['name'] for r in github.rulesets.values()) == [
        'base',
        'required-checks',
    ]
    assert (
        fake_github.run(monkeypatch, checkout, 'check', fake_github.ADMIN) == 0
    )
    assert (
        fake_github.run(monkeypatch, checkout, 'plan', fake_github.READER) == 0
    )
    assert '- none' in (checkout / 'summary.md').read_text()

    # A UI edit to the bypass list is invisible to a non-admin plan but is
    # caught by the admin drift check.
    [base_id] = [i for i, r in github.rulesets.items() if r['name'] == 'base']
    github.rulesets[base_id]['bypass_actors'] = []
    assert (
        fake_github.run(monkeypatch, checkout, 'plan', fake_github.READER) == 0
    )
    assert '- none' in (checkout / 'summary.md').read_text()
    assert (
        fake_github.run(monkeypatch, checkout, 'check', fake_github.ADMIN) == 1
    )
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 0
    )

    github.classic = True
    assert (
        fake_github.run(monkeypatch, checkout, 'check', fake_github.ADMIN) == 1
    )
    summary = (checkout / 'summary.md').read_text()
    assert 'delete classic branch protection' in summary


def test_api_rejections_are_reported(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad = fake_github.CHECKS | {'name': 'broken', 'enforcement': 'evaluate'}
    (checkout / '.github' / 'rulesets' / 'broken.json').write_text(
        json.dumps(bad)
    )
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 1
    )
    summary = (checkout / 'summary.md').read_text()
    assert 'create ruleset "broken": POST' in summary
    assert 'HTTP 422' in summary
    assert len(github.rulesets) == 2


def test_rulesets_inherited_from_the_org_are_left_alone(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    github.inherit(fake_github.BASE | {'name': 'org-wide'})
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 0
    )
    assert 'org-wide' not in (checkout / 'summary.md').read_text()
    assert (
        fake_github.run(monkeypatch, checkout, 'check', fake_github.ADMIN) == 0
    )


def test_private_repositories_skip_only_rulesets(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    github.private = True
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 0
    )
    assert not [
        c for c in github.calls if '/rulesets' in c or '/protection' in c
    ]
    assert 'require GitHub Pro' in (checkout / 'summary.md').read_text()
    assert github.actions == fake_github.PERMISSIONS


def test_misconfiguration_fails_before_touching_github(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert fake_github.run(monkeypatch, checkout, 'apply', None) == 1
    assert 'REPO_SETTINGS_TOKEN' in (checkout / 'summary.md').read_text()

    (checkout / '.github' / 'rulesets' / 'copy.json').write_text(
        json.dumps(fake_github.CHECKS)
    )
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 1
    )
    assert 'duplicate ruleset name' in (checkout / 'summary.md').read_text()

    for path in (checkout / '.github' / 'rulesets').iterdir():
        path.unlink()
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 1
    )
    assert 'no ruleset definitions' in (checkout / 'summary.md').read_text()
    assert not github.calls


def _requiring(name: str, *contexts: str) -> desired.Ruleset:
    checks = [{'context': context} for context in contexts]
    rule = {
        'type': 'required_status_checks',
        'parameters': {'required_status_checks': checks},
    }
    return fake_github.CHECKS | {'name': name, 'rules': [rule]}


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

    assert (
        fake_github.run(monkeypatch, checkout, 'plan', fake_github.READER) == 0
    )
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
    assert (
        fake_github.run(monkeypatch, checkout, 'plan', fake_github.READER) == 0
    )
    summary = (checkout / 'summary.md').read_text()
    assert '"lint" matches no workflow job' in summary


@pytest.mark.parametrize(
    ('content', 'message'),
    [
        ('{"name": ', 'base.json: invalid JSON'),
        ('[]', 'base.json: expected a JSON object'),
        (
            json.dumps(fake_github.BASE | {'target': None}),
            'missing string "target"',
        ),
        (
            json.dumps(fake_github.BASE | {'enforcement': 1}),
            'missing string "enforcement"',
        ),
        (
            json.dumps(fake_github.BASE | {'rules': {}}),
            '"rules" must be a list',
        ),
    ],
)
def test_invalid_definitions_fail_before_touching_github(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    content: str,
    message: str,
) -> None:
    (checkout / '.github' / 'rulesets' / 'base.json').write_text(content)
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 1
    )
    assert message in (checkout / 'summary.md').read_text()
    assert not github.calls


@pytest.mark.parametrize(
    ('token', 'failing', 'status'),
    [
        ('bogus', None, 401),
        (fake_github.ADMIN, f'GET /repos/{fake_github.REPO}', 500),
    ],
)
def test_api_errors_fail_the_run(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    token: str,
    failing: str | None,
    status: int,
) -> None:
    if failing is not None:
        github.errors[failing] = status
    assert fake_github.run(monkeypatch, checkout, 'check', token) == 1
    assert f'HTTP {status}' in (checkout / 'summary.md').read_text()


def test_failed_classic_protection_delete_fails_apply(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    github.classic = True
    github.errors[
        f'DELETE /repos/{fake_github.REPO}/branches/master/protection'
    ] = 500
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 1
    )
    summary = (checkout / 'summary.md').read_text()
    assert 'delete classic branch protection: DELETE' in summary
    assert 'HTTP 500' in summary
    assert github.classic
    # Rulesets are still created, so the branch is not left unprotected.
    assert len(github.rulesets) == 2
