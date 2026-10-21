import json
import pathlib

import pytest

from gha_tools.repo_settings import immutable_releases
from tests import fake_github


def _write(checkout: pathlib.Path, text: str) -> None:
    (checkout / immutable_releases.PATH).write_text(text)


@pytest.mark.parametrize('enabled', [True, False])
def test_definitions_parse(enabled: bool) -> None:
    text = json.dumps({'enabled': enabled})
    assert immutable_releases.parse('i.json', text) == {'enabled': enabled}


@pytest.mark.parametrize(
    'text', ['{', '[]', '{}', '{"enabled": 1}', '{"enabled": true, "x": 1}']
)
def test_invalid_definitions_are_rejected(text: str) -> None:
    with pytest.raises(immutable_releases.InvalidImmutableReleasesError):
        immutable_releases.parse('i.json', text)


def test_immutable_releases_converge_and_drift_is_detected(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(checkout, '{"enabled": true}')
    assert (
        fake_github.run(monkeypatch, checkout, 'plan', fake_github.READER) == 0
    )
    assert (
        'immutable releases were not compared'
        in (checkout / 'summary.md').read_text()
    )

    assert (
        fake_github.run(monkeypatch, checkout, 'check', fake_github.ADMIN) == 1
    )
    summary = (checkout / 'summary.md').read_text()
    print(summary)
    assert 'enable immutable releases' in summary
    assert not github.immutable

    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 0
    )
    assert github.immutable
    assert (
        fake_github.run(monkeypatch, checkout, 'check', fake_github.ADMIN) == 0
    )

    _write(checkout, '{"enabled": false}')
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 0
    )
    assert not github.immutable


def test_disabled_is_also_reported_as_not_found(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(checkout, '{"enabled": false}')
    github.errors[f'GET /repos/{fake_github.REPO}/immutable-releases'] = 404
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 0
    )
    assert not [
        c
        for c in github.calls
        if c.endswith('immutable-releases') and not c.startswith('GET')
    ]


def test_missing_definition_leaves_the_setting_alone(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 0
    )
    assert (
        'immutable releases skipped' in (checkout / 'summary.md').read_text()
    )
    assert not [c for c in github.calls if 'immutable' in c]


def test_invalid_definition_fails_before_touching_github(
    github: fake_github.FakeGitHub,
    checkout: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write(checkout, '{"enabled": "yes"}')
    assert (
        fake_github.run(monkeypatch, checkout, 'apply', fake_github.ADMIN) == 1
    )
    assert not github.calls
