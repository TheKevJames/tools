import json
import pathlib
from typing import Any

import hypothesis
import hypothesis.strategies as st
import pytest

from gha_tools.repo_settings import actions_policy
from tests import fake_github

_FIELDS = ('enabled', 'allowed_actions', 'sha_pinning_required')
_valid = st.fixed_dictionaries(
    {
        'enabled': st.booleans(),
        'allowed_actions': st.sampled_from(['all', 'local_only']),
        'sha_pinning_required': st.booleans(),
    }
)
_scalars = (
    st.none()
    | st.booleans()
    | st.integers()
    | st.sampled_from(['all', 'local_only', 'selected'])
    | st.text(max_size=8)
)
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
PINNED = {
    'enabled': True,
    'allowed_actions': 'all',
    'sha_pinning_required': True,
}


def _mutated(body: actions_policy.Policy) -> st.SearchStrategy[dict[str, Any]]:
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


def _write(checkout: pathlib.Path, body: object) -> None:
    (checkout / actions_policy.PATH).write_text(json.dumps(body))


@hypothesis.given(_valid)
def test_valid_definitions_parse_verbatim(body: actions_policy.Policy) -> None:
    assert actions_policy.parse('p.json', json.dumps(body)) == body


@hypothesis.given(_json | _valid.flatmap(lambda v: st.just(v) | _mutated(v)))
def test_only_complete_valid_definitions_are_accepted(value: object) -> None:
    try:
        parsed = actions_policy.parse('p.json', json.dumps(value))
    except actions_policy.InvalidPolicyError:
        return
    print(value)
    assert parsed == value
    assert set(parsed) == set(_FIELDS)
    assert parsed['allowed_actions'] in {'all', 'local_only'}
    assert isinstance(parsed['enabled'], bool)
    assert isinstance(parsed['sha_pinning_required'], bool)


def test_actions_policy_converges_and_drift_is_detected(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(checkout, PINNED)
    # The Actions GITHUB_TOKEN plan runs with cannot read the setting.
    assert (
        fake_github.run(monkeypatch, checkout, 'plan', fake_github.READER) == 0
    )
    summary = (checkout / 'summary.md').read_text()
    print(summary)
    assert 'Actions policy was not compared' in summary

    assert (
        fake_github.run(monkeypatch, checkout, 'check', fake_github.ADMIN) == 1
    )
    summary = (checkout / 'summary.md').read_text()
    print(summary)
    assert 'the Actions policy has drifted' in summary
    assert '+sha_pinning_required: true' in summary
    assert not github.policy['sha_pinning_required']

    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 0
    )
    assert github.policy == PINNED
    assert (
        fake_github.run(monkeypatch, checkout, 'check', fake_github.ADMIN) == 0
    )

    github.policy['allowed_actions'] = 'local_only'
    assert (
        fake_github.run(monkeypatch, checkout, 'check', fake_github.ADMIN) == 1
    )


@pytest.mark.parametrize('mode', ['apply', 'check'])
def test_unreadable_actions_policy_fails_admin_modes(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    _write(checkout, PINNED)
    github.errors[f'GET /repos/{fake_github.REPO}/actions/permissions'] = 403
    assert fake_github.run(monkeypatch, checkout, mode, fake_github.ADMIN) == 1
    summary = (checkout / 'summary.md').read_text()
    print(summary)
    assert 'could not read the Actions policy' in summary


def test_missing_definition_leaves_the_setting_alone(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 0
    )
    assert 'Actions policy skipped' in (checkout / 'summary.md').read_text()
    assert not [c for c in github.calls if c.endswith('/actions/permissions')]


def test_selected_actions_fail_before_touching_github(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(checkout, PINNED | {'allowed_actions': 'selected'})
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 1
    )
    summary = (checkout / 'summary.md').read_text()
    print(summary)
    assert '"allowed_actions" must be one of' in summary
    assert not github.calls
