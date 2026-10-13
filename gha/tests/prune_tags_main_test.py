import datetime
import email.utils
import itertools
import pathlib
import urllib.parse
from collections.abc import Callable
from collections.abc import Mapping
from typing import Any
from typing import ClassVar

import hypothesis
import hypothesis.strategies as st
import pytest

from gha_tools.prune_tags import main

NOW = datetime.datetime.now(datetime.UTC)
OLD = NOW - datetime.timedelta(days=30)
NEW = NOW - datetime.timedelta(days=1)
REPO = 'thekevjames/image'
CREDENTIALS = ('DOCKER_USER', 'DOCKER_PASS', 'QUAY_APIKEY')
# tag -> last pushed; old commit tags, a recent one, and protected releases.
MIXED = {
    'sha-0a1d': OLD,
    'latest': OLD,
    'sha-1e3': NEW,
    'v1.2.3': OLD,
    'deadbeef00': OLD,
}


class FakeRegistry:
    """Tag storage and paging shared by the per-registry API models."""

    name: ClassVar[str]
    api_root: ClassVar[str]
    url_env: ClassVar[str]
    env: ClassVar[dict[str, str]]

    def __init__(self) -> None:
        self.url = ''
        self.tags: dict[str, datetime.datetime] = {}
        # Server-side cap so tests can force paging below the requested size.
        self.page_size = 100
        self.failing: set[str] = set()
        self.deleted: list[str] = []

    def _page(
        self, number: int, size: int
    ) -> tuple[list[tuple[str, datetime.datetime]], bool]:
        size = min(size, self.page_size)
        start = (number - 1) * size
        items = list(self.tags.items())
        return items[start : start + size], start + size < len(items)

    def _delete(self, quoted: str) -> tuple[int, Any]:
        name = urllib.parse.unquote(quoted)
        if '/' in quoted or name not in self.tags:
            return 404, {'message': 'not found'}
        if name in self.failing:
            return 500, {'message': 'internal server error'}
        del self.tags[name]
        self.deleted.append(name)
        return 204, None


class FakeDockerHub(FakeRegistry):
    """The (deprecated) v2 Hub endpoints: JWT login, paged tag listing."""

    name = 'dockerhub'
    api_root = '/v2'
    url_env = 'DOCKERHUB_API_URL'
    env: ClassVar[dict[str, str]] = {'DOCKER_USER': 'me', 'DOCKER_PASS': 'pw'}

    def __init__(self) -> None:
        super().__init__()
        # Tags whose tag_last_pushed is null, as on very old Hub tags.
        self.unpushed: set[str] = set()

    def handle(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str],
        body: Any,  # noqa: ANN401
    ) -> tuple[int, Any]:
        url = urllib.parse.urlsplit(path)
        route = url.path.rstrip('/')
        if route == '/v2/users/login' and method == 'POST':
            if body == {'username': 'me', 'password': 'pw'}:
                return 200, {'token': 'jwt'}
            return 401, {'detail': 'Incorrect authentication credentials'}
        if headers.get('Authorization') != 'JWT jwt':
            return 401, {'detail': 'Authentication credentials missing'}
        tags = f'/v2/repositories/{REPO}/tags'
        if route == tags and method == 'GET':
            query = urllib.parse.parse_qs(url.query)
            number = int(query.get('page', ['1'])[0])
            size = int(query.get('page_size', ['10'])[0])
            items, more = self._page(number, size)
            following = f'{self.url}{tags}/?page={number + 1}&page_size={size}'
            return 200, {
                'count': len(self.tags),
                'next': following if more else None,
                'previous': None,
                'results': list(itertools.starmap(self._result, items)),
            }
        if route.startswith(f'{tags}/') and method == 'DELETE':
            return self._delete(route.removeprefix(f'{tags}/'))
        return 404, {'message': 'object not found'}

    def _result(self, name: str, pushed: datetime.datetime) -> dict[str, Any]:
        def iso(stamp: datetime.datetime) -> str:
            return stamp.isoformat(timespec='microseconds').replace(
                '+00:00', 'Z'
            )

        unpushed = name in self.unpushed
        return {
            'name': name,
            'full_size': 1234,
            'last_updated': iso(pushed if unpushed else NOW),
            'tag_last_pushed': None if unpushed else iso(pushed),
            'tag_status': 'active',
        }


class FakeQuay(FakeRegistry):
    """Quay's v1 tag API: page/has_additional paging, epoch start_ts."""

    name = 'quay'
    api_root = '/api/v1'
    url_env = 'QUAY_API_URL'
    env: ClassVar[dict[str, str]] = {'QUAY_APIKEY': 'quay-token'}

    def __init__(self) -> None:
        super().__init__()
        # Tag history Quay only returns without onlyActiveTags=true.
        self.expired: dict[str, datetime.datetime] = {}

    def handle(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str],
        _body: Any,  # noqa: ANN401
    ) -> tuple[int, Any]:
        if headers.get('Authorization') != 'Bearer quay-token':
            return 401, {'error': 'Unauthorized'}
        url = urllib.parse.urlsplit(path)
        tags = f'/api/v1/repository/{REPO}/tag/'
        if url.path == tags and method == 'GET':
            query = urllib.parse.parse_qs(url.query)
            number = int(query.get('page', ['1'])[0])
            size = int(query.get('limit', ['50'])[0])
            items, more = self._page(number, size)
            listed = list(itertools.starmap(self._tag, items))
            if query.get('onlyActiveTags') != ['true'] and number == 1:
                listed += [
                    self._tag(n, t) | {'end_ts': int(NOW.timestamp())}
                    for n, t in self.expired.items()
                ]
            return 200, {
                'tags': listed,
                'page': number,
                'has_additional': more,
            }
        if url.path.startswith(tags) and method == 'DELETE':
            return self._delete(url.path.removeprefix(tags))
        return 404, {'error_message': 'Not Found'}

    @staticmethod
    def _tag(name: str, pushed: datetime.datetime) -> dict[str, Any]:
        return {
            'name': name,
            'reversion': False,
            'start_ts': int(pushed.timestamp()),
            'manifest_digest': 'sha256:' + '0' * 64,
            'is_manifest_list': False,
            'size': 1234,
            'last_modified': email.utils.format_datetime(pushed),
        }


@pytest.fixture(name='output', scope='function')
def output_fixture(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> pathlib.Path:
    path = tmp_path / 'github_output'
    path.touch()
    monkeypatch.setenv('GITHUB_OUTPUT', str(path))
    return path


@pytest.fixture(
    name='registry', scope='function', params=['dockerhub', 'quay']
)
def registry_fixture(
    request: pytest.FixtureRequest,
    serve: Callable[..., str],
    monkeypatch: pytest.MonkeyPatch,
) -> FakeRegistry:
    fake: FakeDockerHub | FakeQuay = (
        FakeDockerHub() if request.param == 'dockerhub' else FakeQuay()
    )
    fake.url = serve(fake.handle)
    monkeypatch.setenv(fake.url_env, fake.url + fake.api_root)
    for name in CREDENTIALS:
        monkeypatch.delenv(name, raising=False)
    for name, value in fake.env.items():
        monkeypatch.setenv(name, value)
    return fake


def _run(registry: FakeRegistry, *args: str) -> int:
    return main.main(
        ['--registry', registry.name, '--repository', REPO, *args]
    )


@pytest.mark.parametrize('execute', [True, False])
def test_prunes_old_commit_tags_across_pages(
    registry: FakeRegistry,
    output: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    execute: bool,
) -> None:
    registry.tags = MIXED.copy()
    registry.page_size = 2
    output.write_text('earlier-step=1\n')

    code = _run(registry, *(['--execute'] if execute else []))

    assert code == 0
    doomed = ['sha-0a1d', 'deadbeef00']
    assert (
        '\n'.join(f'  - {name}' for name in doomed) in capsys.readouterr().out
    )
    deleted = doomed if execute else []
    assert registry.deleted == deleted
    assert output.read_text() == (
        'earlier-step=1\n'
        f'deleted-count={len(deleted)}\n'
        f'deleted-tags={" ".join(deleted)}\n'
    )


@hypothesis.settings(
    # The server outlives examples; each one resets the fake's state.
    suppress_health_check=[hypothesis.HealthCheck.function_scoped_fixture]
)
@hypothesis.given(
    count=st.integers(min_value=0, max_value=12),
    page_size=st.integers(min_value=1, max_value=5),
)
def test_any_page_split_yields_every_tag(
    registry: FakeRegistry, output: pathlib.Path, count: int, page_size: int
) -> None:
    names = [f'sha-{i:04x}' for i in range(count)]
    registry.tags = dict.fromkeys(names, NEW)
    registry.page_size = page_size
    registry.deleted = []
    output.write_text('')

    args = ['--max-age-days', '0', '--delete-pattern', '.', '--execute']
    assert _run(registry, *args) == 0
    assert registry.deleted == names
    assert f'deleted-count={count}\n' in output.read_text()


def test_tag_names_are_url_quoted(
    registry: FakeRegistry, output: pathlib.Path
) -> None:
    registry.tags = {'odd/name': OLD, 'odd': OLD}
    args = ['--delete-pattern', '^odd/', '--execute']
    assert _run(registry, *args) == 0
    assert registry.deleted == ['odd/name']
    assert 'deleted-tags=odd/name\n' in output.read_text()


@pytest.mark.usefixtures('output')
@pytest.mark.parametrize('registry', ['dockerhub'], indirect=True)
def test_dockerhub_falls_back_to_last_updated(registry: FakeDockerHub) -> None:
    registry.tags = {'sha-0a': OLD, 'sha-0b': NEW}
    registry.unpushed = {'sha-0a', 'sha-0b'}
    assert _run(registry, '--execute') == 0
    assert registry.deleted == ['sha-0a']


@pytest.mark.usefixtures('output')
@pytest.mark.parametrize('registry', ['quay'], indirect=True)
def test_quay_ignores_expired_tags(registry: FakeQuay) -> None:
    registry.tags = {'sha-0a': OLD}
    registry.expired = {'sha-0e': OLD}
    assert _run(registry, '--execute') == 0
    assert registry.deleted == ['sha-0a']


@pytest.mark.parametrize(
    ('registry_name', 'variable', 'value'),
    [
        ('dockerhub', 'DOCKER_USER', None),
        ('dockerhub', 'DOCKER_PASS', None),
        # Unset workflow secrets arrive as empty strings.
        ('dockerhub', 'DOCKER_PASS', ''),
        ('quay', 'QUAY_APIKEY', ''),
    ],
)
def test_missing_credentials_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    registry_name: str,
    variable: str,
    value: str | None,
) -> None:
    for name in CREDENTIALS:
        monkeypatch.setenv(name, 'set')
    # Fail fast rather than reach the real registries if validation regresses.
    for name in ('DOCKERHUB_API_URL', 'QUAY_API_URL'):
        monkeypatch.setenv(name, 'http://127.0.0.1:9')
    if value is None:
        monkeypatch.delenv(variable)
    else:
        monkeypatch.setenv(variable, value)
    with pytest.raises(ValueError, match=variable):
        main.main(['--registry', registry_name, '--repository', REPO])


def test_partial_failure_reports_what_was_deleted(
    registry: FakeRegistry, output: pathlib.Path
) -> None:
    registry.tags = {'sha-0a': OLD, 'sha-0b': OLD, 'sha-0c': OLD}
    registry.failing = {'sha-0b'}
    assert _run(registry, '--execute') == 1
    assert registry.deleted == ['sha-0a', 'sha-0c']
    assert output.read_text() == (
        'deleted-count=2\ndeleted-tags=sha-0a sha-0c\n'
    )
