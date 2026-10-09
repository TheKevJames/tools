import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from gha_tools.rulesets import desired

_TIMEOUT = 30


class ApiError(RuntimeError):
    def __init__(self, method: str, path: str, status: int, body: str) -> None:
        super().__init__(f'{method} {path}: HTTP {status}: {body}')
        self.status = status


class Client:
    def __init__(self, api: str, repository: str, token: str) -> None:
        self.api = api
        self.base = f'/repos/{repository}'
        self._headers = {
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {token}',
            'X-GitHub-Api-Version': '2022-11-28',
        }

    def _request(
        self, method: str, path: str, body: desired.Ruleset | None = None
    ) -> Any:  # noqa: ANN401
        headers = self._headers.copy()
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(
            f'{self.api}{path}', data=data, method=method, headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                text = resp.read().decode()
        except urllib.error.HTTPError as exc:
            raise ApiError(
                method, path, exc.code, exc.read().decode()
            ) from exc
        return json.loads(text) if text else None

    def repository(self) -> dict[str, Any]:
        result: dict[str, Any] = self._request('GET', self.base)
        return result

    def rulesets(self) -> dict[str, desired.Ruleset]:
        """Rulesets defined on this repo itself, keyed by name."""
        summaries = self._request(
            'GET', f'{self.base}/rulesets?includes_parents=false&per_page=100'
        )
        return {
            summary['name']: self._request(
                'GET', f'{self.base}/rulesets/{summary["id"]}'
            )
            for summary in summaries
            if summary['source_type'] == 'Repository'
        }

    def create_ruleset(self, body: desired.Ruleset) -> None:
        self._request('POST', f'{self.base}/rulesets', body)

    def update_ruleset(self, ruleset_id: int, body: desired.Ruleset) -> None:
        self._request('PUT', f'{self.base}/rulesets/{ruleset_id}', body)

    def delete_ruleset(self, ruleset_id: int) -> None:
        self._request('DELETE', f'{self.base}/rulesets/{ruleset_id}')

    def _protection_path(self, branch: str) -> str:
        quoted = urllib.parse.quote(branch, safe='')
        return f'{self.base}/branches/{quoted}/protection'

    def classic_protection(self, branch: str) -> bool | None:
        """Whether classic protection exists; None if the token can't tell."""
        try:
            self._request('GET', self._protection_path(branch))
        except ApiError as exc:
            if exc.status == 404:
                return False
            if exc.status in {401, 403}:
                return None
            raise
        return True

    def delete_classic_protection(self, branch: str) -> None:
        self._request('DELETE', self._protection_path(branch))
