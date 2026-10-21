import json
import pathlib
import shutil
from typing import Any

import hypothesis
import hypothesis.strategies as st
import pytest

from gha_tools.repo_settings import environments
from tests import fake_github
from tests.fake_github import settings

_NAMES = ('pypi', 'repo-settings', 'tag')
_policy = st.tuples(
    st.sampled_from(['branch', 'tag']),
    st.sampled_from(['~DEFAULT_BRANCH', 'master', '*.*.*', 'release/*']),
)
_definitions = st.dictionaries(
    st.sampled_from(_NAMES),
    st.frozensets(_policy, min_size=1, max_size=3),
    min_size=1,
)
_stored = st.builds(
    settings.environment,
    policy=st.sampled_from([None, settings.PROTECTED, settings.CUSTOM]),
    policies=st.lists(_policy, max_size=3, unique=True),
    reviewers=st.booleans(),
    wait_timer=st.sampled_from([0, 5]),
)


def _write(checkout: pathlib.Path, name: str, policies: object) -> None:
    directory = checkout / environments.DIRECTORY
    directory.mkdir(exist_ok=True)
    (directory / f'{name}.json').write_text(
        json.dumps({'deployment_policies': policies})
    )


def _as_json(policies: frozenset[environments.Policy]) -> list[object]:
    return [{'type': t, 'name': n} for t, n in sorted(policies)]


@hypothesis.given(_definitions)
def test_valid_definitions_parse(
    definitions: dict[str, frozenset[environments.Policy]],
) -> None:
    for policies in definitions.values():
        text = json.dumps({'deployment_policies': _as_json(policies)})
        assert environments.parse('e.json', text) == policies


@pytest.mark.parametrize(
    'value',
    [
        [],
        {},
        {'deployment_policies': []},
        {'deployment_policies': None},
        {'deployment_policies': [{'type': 'branch'}]},
        {'deployment_policies': [{'type': 'ref', 'name': 'x'}]},
        {'deployment_policies': [{'type': 'tag', 'name': ''}]},
        {'deployment_policies': [{'type': 'tag', 'name': 'x', 'id': 1}]},
        {'deployment_policies': [{'type': 'tag', 'name': 'x'}] * 2},
        {
            'deployment_policies': [{'type': 'tag', 'name': 'x'}],
            'reviewers': [],
        },
    ],
)
def test_invalid_definitions_are_rejected(value: object) -> None:
    with pytest.raises(environments.InvalidEnvironmentError):
        environments.parse('e.json', json.dumps(value))


@hypothesis.settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[hypothesis.HealthCheck.function_scoped_fixture],
)
@hypothesis.given(
    _definitions, st.dictionaries(st.sampled_from([*_NAMES, 'x']), _stored)
)
def test_apply_converges_from_any_state(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    definitions: dict[str, frozenset[environments.Policy]],
    stored: dict[str, dict[str, Any]],
) -> None:
    shutil.rmtree(checkout / environments.DIRECTORY, ignore_errors=True)
    for name, policies in definitions.items():
        _write(checkout, name, _as_json(policies))
    github.environments = stored

    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 0
    ), (checkout / 'summary.md').read_text()
    assert (
        fake_github.run(monkeypatch, checkout, 'check', fake_github.ADMIN) == 0
    ), (checkout / 'summary.md').read_text()
    assert set(github.environments) == set(definitions)
    for name, policies in definitions.items():
        env = github.environments[name]
        print(name, env)
        assert env['policy'] == settings.CUSTOM
        assert not env['reviewers']
        assert not env['wait_timer']
        want = {
            (t, 'master' if n == '~DEFAULT_BRANCH' else n) for t, n in policies
        }
        assert set(env['policies'].values()) == want


def test_plan_reports_without_writing_and_check_detects_drift(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(checkout, 'tag', [{'type': 'branch', 'name': '~DEFAULT_BRANCH'}])
    _write(checkout, 'pypi', [{'type': 'tag', 'name': '*.*.*'}])
    github.environments = {
        'copilot': settings.environment(),
        'pypi': settings.environment(
            settings.CUSTOM, [('branch', 'master')], reviewers=True
        ),
    }

    # Environments are readable with the read-only Actions token.
    assert (
        fake_github.run(monkeypatch, checkout, 'plan', fake_github.READER) == 0
    )
    summary = (checkout / 'summary.md').read_text()
    print(summary)
    assert 'create environment "tag"' in summary
    assert 'update environment "pypi"' in summary
    assert '-branch: master' in summary
    assert '+tag: *.*.*' in summary
    assert 'delete environment "copilot"' in summary
    assert not [c for c in github.calls if not c.startswith('GET')]

    assert (
        fake_github.run(monkeypatch, checkout, 'check', fake_github.ADMIN) == 1
    )
    assert 'environments have drifted' in (checkout / 'summary.md').read_text()
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 0
    )

    github.environments['tag']['reviewers'] = True
    assert (
        fake_github.run(monkeypatch, checkout, 'check', fake_github.ADMIN) == 1
    )
    summary = (checkout / 'summary.md').read_text()
    assert 'update environment "tag" protection rules' in summary


@pytest.mark.parametrize('remove_directory', [False, True])
def test_no_definitions_fail_before_touching_github(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    remove_directory: bool,
) -> None:
    directory = checkout / environments.DIRECTORY
    for path in directory.iterdir():
        path.unlink()
    if remove_directory:
        directory.rmdir()
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 1
    )
    summary = (checkout / 'summary.md').read_text()
    print(summary)
    assert 'no environment definitions' in summary
    assert not github.calls


def test_private_repositories_skip_environments(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    github.private = True
    _write(checkout, 'tag', [{'type': 'branch', 'name': '~DEFAULT_BRANCH'}])
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 0
    )
    assert 'require GitHub Pro' in (checkout / 'summary.md').read_text()
    assert not [c for c in github.calls if '/environments' in c]


def test_invalid_definitions_fail_before_touching_github(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(checkout, 'tag', [])
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 1
    )
    summary = (checkout / 'summary.md').read_text()
    print(summary)
    assert 'environments/tag.json' in summary
    assert not github.calls


def test_api_rejections_are_reported(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(checkout, 'tag', [{'type': 'branch', 'name': '~DEFAULT_BRANCH'}])
    github.environments = {'copilot': settings.environment()}
    github.errors[f'PUT /repos/{fake_github.REPO}/environments/tag'] = 422
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 1
    )
    summary = (checkout / 'summary.md').read_text()
    assert 'create environment "tag": PUT' in summary
    # The other changes still go ahead.
    assert 'copilot' not in github.environments
