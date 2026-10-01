import datetime
import json
import os
import urllib.parse
import urllib.request
from collections.abc import Iterator
from typing import Any

from gha_tools.prune_tags import selection

_TIMEOUT = 30


def _http(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    data: dict[str, str] | None = None,
) -> Any:  # noqa: ANN401
    body = None
    hdrs = dict(headers or {})
    if data is not None:
        body = json.dumps(data).encode()
        hdrs['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=body, method=method, headers=hdrs)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        text = resp.read().decode()
    return json.loads(text) if text else None


class DockerHubClient:
    base = 'https://hub.docker.com/v2'

    def __init__(self, repository: str, username: str, password: str) -> None:
        self.repository = repository
        token = _http(
            'POST',
            f'{self.base}/users/login/',
            data={'username': username, 'password': password},
        )['token']
        self._headers = {'Authorization': f'JWT {token}'}

    def list_tags(self) -> Iterator[selection.TagInfo]:
        url: str | None = (
            f'{self.base}/repositories/{self.repository}/tags/?page_size=100'
        )
        while url:
            page = _http('GET', url, headers=self._headers)
            for result in page['results']:
                stamp = result.get('tag_last_pushed') or result.get(
                    'last_updated'
                )
                yield selection.TagInfo(result['name'], _parse_iso(stamp))
            url = page.get('next')

    def delete_tag(self, name: str) -> None:
        tag = urllib.parse.quote(name, safe='')
        _http(
            'DELETE',
            f'{self.base}/repositories/{self.repository}/tags/{tag}/',
            headers=self._headers,
        )


class QuayClient:
    base = 'https://quay.io/api/v1'

    def __init__(self, repository: str, token: str) -> None:
        self.repository = repository
        self._headers = {'Authorization': f'Bearer {token}'}

    def list_tags(self) -> Iterator[selection.TagInfo]:
        page = 1
        while True:
            url = (
                f'{self.base}/repository/{self.repository}/tag/'
                f'?limit=100&page={page}&onlyActiveTags=true'
            )
            body = _http('GET', url, headers=self._headers)
            for tag in body['tags']:
                yield selection.TagInfo(
                    tag['name'], _parse_epoch(tag.get('start_ts'))
                )
            if not body.get('has_additional'):
                return
            page += 1

    def delete_tag(self, name: str) -> None:
        tag = urllib.parse.quote(name, safe='')
        _http(
            'DELETE',
            f'{self.base}/repository/{self.repository}/tag/{tag}',
            headers=self._headers,
        )


def _parse_iso(stamp: str | None) -> datetime.datetime | None:
    if not stamp:
        return None
    return datetime.datetime.fromisoformat(stamp.replace('Z', '+00:00'))


def _parse_epoch(stamp: int | None) -> datetime.datetime | None:
    if stamp is None:
        return None
    return datetime.datetime.fromtimestamp(stamp, datetime.UTC)


def make_client(
    registry: str, repository: str
) -> DockerHubClient | QuayClient:
    if registry == 'dockerhub':
        return DockerHubClient(
            repository,
            _require_env('DOCKER_USER'),
            _require_env('DOCKER_PASS'),
        )
    if registry == 'quay':
        return QuayClient(repository, _require_env('QUAY_APIKEY'))
    raise ValueError(f'unknown registry: {registry}')


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f'missing required environment variable: {name}')
    return value
