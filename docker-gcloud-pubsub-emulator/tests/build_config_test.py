import json
import os
import pathlib

import hypothesis
import pytest
from hypothesis import strategies as st

import pubsubc

Topic = tuple[str, str, list[str]]

NAME = st.text(
    st.characters(exclude_categories=['Cs'], exclude_characters=',:\x00'),
    min_size=1,
    max_size=8,
)
PROJECTS = st.lists(
    st.tuples(
        NAME,
        st.lists(
            st.tuples(NAME, st.lists(NAME, max_size=3)), min_size=1, max_size=3
        ),
    ),
    max_size=3,
)


@pytest.fixture(name='missing_config', scope='module')
def missing_config_fixture(
    tmp_path_factory: pytest.TempPathFactory,
) -> pathlib.Path:
    return tmp_path_factory.mktemp('pubsubc') / 'missing.json'


def _build(
    monkeypatch: pytest.MonkeyPatch,
    config: pathlib.Path,
    env: dict[str, str] | None = None,
) -> list[Topic]:
    for key in list(os.environ):
        if key.startswith('PUBSUB_PROJECT'):
            monkeypatch.delenv(key)
    monkeypatch.setenv('PUBSUBC_CONFIG', str(config))
    for key, value in (env or {}).items():
        monkeypatch.setenv(key, value)
    return [
        (topic.project, topic.name, [sub.name for sub in topic.subscriptions])
        for topic in pubsubc.build_config()
    ]


def _write(path: pathlib.Path, config: object) -> pathlib.Path:
    path.write_text(json.dumps(config), encoding='utf-8')
    return path


@hypothesis.given(PROJECTS)
@hypothesis.example(
    [
        (
            'company-dev',
            [
                ('invoices', ['invoice-calculator']),
                ('chats', ['slack-out', 'irc-out']),
                ('notifications', []),
            ],
        )
    ]
)
def test_env_config_round_trips(
    missing_config: pathlib.Path,
    projects: list[tuple[str, list[tuple[str, list[str]]]]],
) -> None:
    env = {
        f'PUBSUB_PROJECT{i}': ','.join(
            [project, *(':'.join([topic, *subs]) for topic, subs in topics)]
        )
        for i, (project, topics) in enumerate(projects, start=1)
    }
    print(env)
    expected = [
        (project, topic, subs)
        for project, topics in projects
        for topic, subs in topics
    ]
    with pytest.MonkeyPatch.context() as monkeypatch:
        assert _build(monkeypatch, missing_config, env) == expected


@pytest.mark.parametrize(
    ('env', 'expected'),
    [
        ({}, []),
        ({'PUBSUB_PROJECT1': 'p1', 'PUBSUB_PROJECT2': 'p2,t'}, []),
        ({'PUBSUB_PROJECT1': 'p1,', 'PUBSUB_PROJECT2': 'p2,t'}, []),
        (
            {'PUBSUB_PROJECT1': 'p1,,t1,t2::s1:,', 'PUBSUB_PROJECT2': 'p2'},
            [('p1', 't1', []), ('p1', 't2', ['s1'])],
        ),
        (
            {
                'PUBSUB_PROJECT1': 'p1,t1',
                'PUBSUB_PROJECT2': 'p2',
                'PUBSUB_PROJECT3': 'p3,t3',
            },
            [('p1', 't1', [])],
        ),
        (
            {'PUBSUB_PROJECT1': 'p1,t1', 'PUBSUB_PROJECT3': 'p3,t3'},
            [('p1', 't1', [])],
        ),
    ],
)
def test_env_scan_stops_at_first_project_without_topics(
    monkeypatch: pytest.MonkeyPatch,
    missing_config: pathlib.Path,
    env: dict[str, str],
    expected: list[Topic],
) -> None:
    assert _build(monkeypatch, missing_config, env) == expected


def test_file_config_takes_precedence_over_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = _write(
        tmp_path / 'config.json',
        [
            {'project': 'p1', 'topic': 't1'},
            {'project': 'p1', 'topic': 't2', 'subscriptions': None},
            {
                'project': 'p2',
                'topic': 't3',
                'subscriptions': [{'name': 's1'}, {'name': 's2'}],
            },
        ],
    )
    env = {'PUBSUB_PROJECT1': 'p9,t9:s9'}
    assert _build(monkeypatch, config, env) == [
        ('p1', 't1', []),
        ('p1', 't2', []),
        ('p2', 't3', ['s1', 's2']),
    ]
    assert '$PUBSUB_PROJECT1 is set' in capsys.readouterr().out


@pytest.mark.parametrize(
    'content',
    [
        '',
        '[{"project": "p", "topic": "t"}',
        json.dumps({'project': 'p', 'topic': 't'}),
        json.dumps([{'topic': 't'}]),
        json.dumps([{'project': 'p'}]),
        json.dumps([{'project': 'p', 'topic': 't', 'subscriptions': [{}]}]),
        json.dumps(
            [
                {
                    'project': 'p',
                    'topic': 't',
                    'subscriptions': [
                        {'name': 's', 'push_config': {'bad': 1}}
                    ],
                }
            ]
        ),
    ],
)
def test_invalid_file_config_exits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    content: str,
) -> None:
    config = tmp_path / 'config.json'
    config.write_text(content, encoding='utf-8')
    with pytest.raises(SystemExit) as exc:
        _build(monkeypatch, config, {'PUBSUB_PROJECT1': 'p,t'})
    assert exc.value.code == 1
    assert 'ERROR: invalid configuration file' in capsys.readouterr().out
