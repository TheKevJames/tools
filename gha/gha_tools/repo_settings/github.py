import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

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
        self, method: str, path: str, body: dict[str, Any] | None = None
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

    def rulesets(self) -> dict[str, dict[str, Any]]:
        """
        Rulesets defined on this repo itself, keyed by name.

        Only a single page of up to 100 rulesets is fetched.
        """
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

    def create_ruleset(self, body: dict[str, Any]) -> None:
        self._request('POST', f'{self.base}/rulesets', body)

    def update_ruleset(self, ruleset_id: int, body: dict[str, Any]) -> None:
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

    def actions_permissions(self) -> dict[str, Any] | None:
        """The GITHUB_TOKEN's default permissions; None if the token can't."""
        try:
            result: dict[str, Any] = self._request(
                'GET', f'{self.base}/actions/permissions/workflow'
            )
        except ApiError as exc:
            if exc.status in {401, 403}:
                return None
            raise
        return result

    def set_actions_permissions(self, body: dict[str, Any]) -> None:
        self._request('PUT', f'{self.base}/actions/permissions/workflow', body)

    def _environment_path(self, name: str) -> str:
        return f'{self.base}/environments/{urllib.parse.quote(name, safe="")}'

    def environments(self) -> dict[str, dict[str, Any]]:
        """
        Environments keyed by name.

        Only a single page of up to 100 environments is fetched.
        """
        result = self._request('GET', f'{self.base}/environments?per_page=100')
        return {env['name']: env for env in result['environments']}

    def put_environment(self, name: str, body: dict[str, Any]) -> None:
        self._request('PUT', self._environment_path(name), body)

    def delete_environment(self, name: str) -> None:
        self._request('DELETE', self._environment_path(name))

    def deployment_policies(self, name: str) -> dict[int, tuple[str, str]]:
        """
        An environment's (type, pattern) deployment policies, keyed by id.

        Only a single page of up to 100 policies is fetched.
        """
        result = self._request(
            'GET',
            f'{self._environment_path(name)}/deployment-branch-policies'
            '?per_page=100',
        )
        return {
            policy['id']: (policy.get('type', 'branch'), policy['name'])
            for policy in result['branch_policies']
        }

    def create_deployment_policy(
        self, name: str, kind: str, pattern: str
    ) -> None:
        self._request(
            'POST',
            f'{self._environment_path(name)}/deployment-branch-policies',
            {'name': pattern, 'type': kind},
        )

    def delete_deployment_policy(self, name: str, policy_id: int) -> None:
        self._request(
            'DELETE',
            f'{self._environment_path(name)}/deployment-branch-policies/'
            f'{policy_id}',
        )

    def deploy_keys(self) -> list[dict[str, Any]] | None:
        """
        Every deploy key; None if the token can't read them.

        Only a single page of up to 100 keys is fetched.
        """
        try:
            result: list[dict[str, Any]] = self._request(
                'GET', f'{self.base}/keys?per_page=100'
            )
        except ApiError as exc:
            if exc.status in {401, 403}:
                return None
            raise
        return result

    def immutable_releases(self) -> bool | None:
        """Whether releases are immutable; None if the token can't tell."""
        try:
            result = self._request('GET', f'{self.base}/immutable-releases')
        except ApiError as exc:
            # Documented as the response when disabled, though GitHub also
            # answers 200 with "enabled": false.
            if exc.status == 404:
                return False
            if exc.status in {401, 403}:
                return None
            raise
        return bool(result['enabled'])

    def set_immutable_releases(self, enabled: bool) -> None:
        method = 'PUT' if enabled else 'DELETE'
        self._request(method, f'{self.base}/immutable-releases')
