"""
Reconcile a repository's settings with their definitions in its `.github/`.

Each setting has its own module: `rulesets` (`.github/rulesets/*.json`),
`actions_permissions` (`.github/actions-permissions.json`), `environments`
(`.github/environments/*.json`), `immutable_releases`
(`.github/immutable-releases.json`), and `deploy_keys` (report-only, no
definition).

Modes:
  plan   report what apply would change; never fails on differences
  apply  make the changes
  check  fail if anything would change (drift detection)
"""

import argparse
import dataclasses
import os
import pathlib
from collections.abc import Sequence

from gha_tools.repo_settings import actions_permissions
from gha_tools.repo_settings import deploy_keys
from gha_tools.repo_settings import environments
from gha_tools.repo_settings import github
from gha_tools.repo_settings import immutable_releases
from gha_tools.repo_settings import report
from gha_tools.repo_settings import rulesets
from gha_tools.repo_settings.rulesets import desired


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--mode', required=True, choices=report.MODES)
    parser.add_argument('--repository', required=True, help='owner/name')
    parser.add_argument(
        '--directory',
        required=True,
        type=pathlib.Path,
        help='checkout of the repository',
    )
    return parser.parse_args(argv)


@dataclasses.dataclass(frozen=True)
class _Settings:
    rulesets: dict[str, desired.Ruleset]
    permissions: actions_permissions.Permissions
    environments: dict[str, frozenset[environments.Policy]]
    immutable_releases: bool


def _validate(root: pathlib.Path, out: report.Report) -> _Settings | None:
    """Every definition, reporting all invalid ones before giving up."""
    desired_rulesets = rulesets.validate(root, out)
    permissions = actions_permissions.validate(root, out)
    envs = environments.validate(root, out)
    immutable = immutable_releases.validate(root, out)
    if (
        desired_rulesets is None
        or permissions is None
        or envs is None
        or immutable is None
    ):
        return None
    return _Settings(desired_rulesets, permissions, envs, immutable)


def _reconcile(
    client: github.Client, settings: _Settings, mode: str, out: report.Report
) -> int:
    repo = client.repository()
    status = rulesets.reconcile(client, repo, settings.rulesets, mode, out)
    status |= actions_permissions.reconcile(
        client, settings.permissions, mode, out
    )
    status |= environments.reconcile(
        client, repo, settings.environments, mode, out
    )
    status |= immutable_releases.reconcile(
        client, settings.immutable_releases, mode, out
    )
    status |= deploy_keys.reconcile(client, mode, out)
    out.finish()
    return status


def _run(args: argparse.Namespace, out: report.Report) -> int:
    settings = _validate(args.directory, out)
    if settings is None:
        return 1

    token = os.environ.get('GH_TOKEN')
    if not token:
        out.error(
            'no token: set the REPO_SETTINGS_TOKEN secret on this repository '
            '(see `repo-template set-secret`)'
        )
        return 1

    api = os.environ.get('GITHUB_API_URL', 'https://api.github.com')
    client = github.Client(api, args.repository, token)
    try:
        return _reconcile(client, settings, args.mode, out)
    except github.ApiError as exc:
        out.error(str(exc))
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    out = report.Report(args.repository, args.mode)
    try:
        return _run(args, out)
    finally:
        out.write_summary(os.environ.get('GITHUB_STEP_SUMMARY'))
