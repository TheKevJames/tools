import json
import pathlib
from typing import Any

import hypothesis
import hypothesis.strategies as st
import pytest

from gha_tools.repo_settings import actions_permissions
from tests import fake_github

_FIELDS = ('default_workflow_permissions', 'can_approve_pull_request_reviews')
_valid = st.fixed_dictionaries(
    {
        'default_workflow_permissions': st.sampled_from(['read', 'write']),
        'can_approve_pull_request_reviews': st.booleans(),
    }
)
_scalars = st.none() | st.booleans() | st.integers() | st.text(max_size=8)
_json = st.recursive(
    _scalars,
    lambda children: (
        st.lists(children, max_size=3)
        | st.dictionaries(
            st.sampled_from(_FIELDS) | st.text(max_size=8),
            children,
            max_size=3,
        )
    ),
    max_leaves=8,
)


def _mutated(
    body: actions_permissions.Permissions,
) -> st.SearchStrategy[dict[str, Any]]:
    """`body` with one field replaced, dropped, or an extra one added."""
    return (
        st.sampled_from(_FIELDS).flatmap(
            lambda key: st.builds(lambda v: body | {key: v}, _scalars)
        )
        | st.sampled_from(_FIELDS).map(
            lambda key: {k: v for k, v in body.items() if k != key}
        )
        | st.builds(lambda v: body | {'extra': v}, _scalars)
    )


@hypothesis.given(_valid)
def test_valid_definitions_parse_verbatim(
    body: actions_permissions.Permissions,
) -> None:
    assert actions_permissions.parse('p.json', json.dumps(body)) == body


@hypothesis.given(_json | _valid.flatmap(lambda v: st.just(v) | _mutated(v)))
def test_only_complete_valid_definitions_are_accepted(value: object) -> None:
    try:
        parsed = actions_permissions.parse('p.json', json.dumps(value))
    except actions_permissions.InvalidPermissionsError:
        return
    print(value)
    assert parsed == value
    assert set(parsed) == set(_FIELDS)
    assert parsed['default_workflow_permissions'] in {'read', 'write'}
    assert isinstance(parsed['can_approve_pull_request_reviews'], bool)


@pytest.mark.parametrize('text', ['{', '[]', '"read"'])
def test_non_objects_are_rejected(text: str) -> None:
    with pytest.raises(actions_permissions.InvalidPermissionsError):
        actions_permissions.parse('p.json', text)


def test_actions_permissions_converge_and_drift_is_detected(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The Actions GITHUB_TOKEN plan runs with cannot read the setting.
    assert (
        fake_github.run(monkeypatch, checkout, 'plan', fake_github.READER) == 0
    )
    summary = (checkout / 'summary.md').read_text()
    print(summary)
    assert 'Actions workflow permissions were not compared' in summary
    assert not [c for c in github.calls if not c.startswith('GET')]

    assert (
        fake_github.run(monkeypatch, checkout, 'check', fake_github.ADMIN) == 1
    )
    summary = (checkout / 'summary.md').read_text()
    print(summary)
    assert 'Actions workflow permissions have drifted' in summary
    assert '+default_workflow_permissions: "read"' in summary
    assert github.actions['default_workflow_permissions'] == 'write'

    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 0
    )
    assert github.actions == fake_github.PERMISSIONS
    assert (
        fake_github.run(monkeypatch, checkout, 'check', fake_github.ADMIN) == 0
    )

    github.actions['can_approve_pull_request_reviews'] = False
    assert (
        fake_github.run(monkeypatch, checkout, 'check', fake_github.ADMIN) == 1
    )


@pytest.mark.parametrize('mode', ['apply', 'check'])
def test_unreadable_actions_permissions_fail_admin_modes(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    github.errors[
        f'GET /repos/{fake_github.REPO}/actions/permissions/workflow'
    ] = 403
    assert fake_github.run(monkeypatch, checkout, mode, fake_github.ADMIN) == 1
    summary = (checkout / 'summary.md').read_text()
    print(summary)
    assert 'could not read Actions workflow permissions' in summary


def test_missing_actions_permissions_fail_before_touching_github(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (checkout / '.github' / 'actions-permissions.json').unlink()
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 1
    )
    assert (
        'actions-permissions.json: missing'
        in (checkout / 'summary.md').read_text()
    )
    assert not github.calls


def test_invalid_actions_permissions_fail_before_touching_github(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = checkout / '.github' / 'actions-permissions.json'
    path.write_text(json.dumps(fake_github.PERMISSIONS | {'enabled': True}))
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 1
    )
    summary = (checkout / 'summary.md').read_text()
    print(summary)
    assert 'expected exactly the fields' in summary
    assert not github.calls
