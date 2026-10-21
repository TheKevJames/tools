import pathlib
from typing import Any

import hypothesis
import hypothesis.strategies as st
import pytest

from gha_tools.repo_settings import deploy_keys
from tests import fake_github

_keys = st.lists(
    st.fixed_dictionaries(
        {
            'id': st.integers(1, 99),
            'title': st.sampled_from(['tag', 'CircleCI', 'other']),
            'read_only': st.booleans(),
        }
    ),
    max_size=4,
)


@hypothesis.given(_keys)
def test_only_a_single_write_key_titled_tag_is_accepted(
    keys: list[dict[str, Any]],
) -> None:
    writers = [key['title'] for key in keys if not key['read_only']]
    print(keys)
    assert (not deploy_keys.problems(keys)) == (writers in ([], ['tag']))


def _key(title: str, read_only: bool) -> dict[str, Any]:
    return {'id': 7, 'title': title, 'read_only': read_only, 'key': 'ssh-x'}


def test_unexpected_write_keys_fail_admin_modes_without_changes(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    github.keys = [_key('CircleCI', True), _key('tag', False)]
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 0
    ), (checkout / 'summary.md').read_text()

    github.keys.append(_key('laptop', False))
    for mode in ('apply', 'check'):
        assert (
            fake_github.run(monkeypatch, checkout, mode, fake_github.ADMIN)
            == 1
        )
        summary = (checkout / 'summary.md').read_text()
        print(summary)
        assert 'unexpected write deploy key "laptop"' in summary
    assert len(github.keys) == 3
    assert all(c.startswith('GET') for c in github.calls if '/keys' in c)


def test_plan_cannot_read_deploy_keys(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    github.keys = [_key('laptop', False)]
    assert (
        fake_github.run(monkeypatch, checkout, 'plan', fake_github.READER) == 0
    )
    summary = (checkout / 'summary.md').read_text()
    assert 'deploy keys were not checked' in summary
