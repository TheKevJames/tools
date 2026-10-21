"""
The environments, deploy keys, Actions policy and immutable releases slice
of the fake GitHub, modelled on observed API responses.
"""

import copy
import itertools
import urllib.parse
from typing import Any

CUSTOM = {'protected_branches': False, 'custom_branch_policies': True}
PROTECTED = {'protected_branches': True, 'custom_branch_policies': False}

Response = tuple[int, Any]

_ids = itertools.count(1000)
_FORBIDDEN = 403, {'message': 'Resource not accessible'}
_NOT_FOUND = 404, {'message': 'Not Found'}


def environment(
    policy: dict[str, bool] | None = None,
    policies: list[tuple[str, str]] | None = None,
    reviewers: bool = False,
    wait_timer: int = 0,
) -> dict[str, Any]:
    """A stored environment, as GitHub would hold it."""
    return {
        'policy': policy,
        'reviewers': reviewers,
        'wait_timer': wait_timer,
        'policies': {next(_ids): p for p in policies or []},
    }


def _render(name: str, env: dict[str, Any]) -> dict[str, Any]:
    rules: list[dict[str, Any]] = []
    if env['wait_timer']:
        rules.append({'type': 'wait_timer', 'wait_timer': env['wait_timer']})
    if env['reviewers']:
        rules.append({'type': 'required_reviewers', 'reviewers': []})
    if env['policy'] is not None:
        rules.append({'type': 'branch_policy'})
    for rule in rules:
        rule |= {'id': next(_ids), 'node_id': 'GA_x'}
    return {
        'id': 1,
        'name': name,
        'can_admins_bypass': True,
        'protection_rules': rules,
        'deployment_branch_policy': env['policy'],
    }


def _put(env: dict[str, Any], body: dict[str, Any]) -> None:
    policy = body.get('deployment_branch_policy', env['policy'])
    if policy != env['policy']:
        env['policies'] = {}
    env['policy'] = policy
    if 'reviewers' in body:
        env['reviewers'] = bool(body['reviewers'])
    env['wait_timer'] = body.get('wait_timer', env['wait_timer'])


def _policies(
    env: dict[str, Any],
    method: str,
    rest: str,
    body: Any,  # noqa: ANN401
) -> Response:
    # GitHub only keeps name patterns for custom policies.
    if env['policy'] != CUSTOM:
        return _NOT_FOUND
    if method == 'GET':
        return 200, {
            'total_count': len(env['policies']),
            'branch_policies': [
                {'id': i, 'node_id': 'x', 'name': n, 'type': t}
                for i, (t, n) in env['policies'].items()
            ],
        }
    if method == 'POST':
        policy = (body.get('type', 'branch'), body['name'])
        if policy in env['policies'].values():
            return 303, None
        env['policies'][next(_ids)] = policy
        return 200, {'name': policy[1], 'type': policy[0]}
    if env['policies'].pop(int(rest.removeprefix('/')), None) is None:
        return _NOT_FOUND
    return 204, None


class Settings:
    def __init__(self) -> None:
        # name -> see environment()
        self.environments: dict[str, dict[str, Any]] = {}
        self.keys: list[dict[str, Any]] = []
        self.immutable = False
        self.policy = {
            'enabled': True,
            'allowed_actions': 'all',
            'sha_pinning_required': False,
        }

    def route(
        self,
        method: str,
        path: str,
        admin: bool,
        body: Any,  # noqa: ANN401
    ) -> Response:
        """Handle a path relative to the repo; 404 if it isn't ours."""
        if path.partition('?')[0] == '/environments':
            return 200, {
                'total_count': len(self.environments),
                'environments': list(
                    itertools.starmap(_render, self.environments.items())
                ),
            }
        if path.startswith('/environments/'):
            return self._environment(method, path, admin, body)
        if not admin:
            return _FORBIDDEN
        if path == '/keys?per_page=100':
            return 200, copy.deepcopy(self.keys)
        if path == '/actions/permissions':
            return self._policy(method, body)
        return self._immutable(method, path)

    def _policy(self, method: str, body: Any) -> Response:  # noqa: ANN401
        if method == 'GET':
            return 200, self.policy.copy()
        if 'enabled' not in body or set(body) - set(self.policy):
            return 422, {'message': 'Invalid request'}
        self.policy |= body
        return 204, None

    def _immutable(self, method: str, path: str) -> Response:
        if path != '/immutable-releases':
            return _NOT_FOUND
        if method == 'GET':
            return 200, {'enabled': self.immutable, 'enforced_by_owner': False}
        self.immutable = method == 'PUT'
        return 204, None

    def _environment(
        self,
        method: str,
        path: str,
        admin: bool,
        body: Any,  # noqa: ANN401
    ) -> Response:
        route = path.partition('?')[0]
        if method != 'GET' and not admin:
            return _FORBIDDEN
        quoted, policies, rest = route.removeprefix(
            '/environments/'
        ).partition('/deployment-branch-policies')
        name = urllib.parse.unquote(quoted)
        if method == 'PUT' and not policies:
            _put(self.environments.setdefault(name, environment()), body)
            return 200, _render(name, self.environments[name])
        if name not in self.environments:
            return _NOT_FOUND
        if policies:
            return _policies(self.environments[name], method, rest, body)
        if method == 'DELETE':
            del self.environments[name]
            return 204, None
        return 200, _render(name, self.environments[name])
