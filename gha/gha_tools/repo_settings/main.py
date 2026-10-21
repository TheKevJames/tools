"""
Reconcile a repository's settings with their definitions in its `.github/`.

Each setting has its own module: `rulesets` (`.github/rulesets/*.json`) and
`actions_permissions` (`.github/actions-permissions.json`).

Modes:
  plan   report what apply would change; never fails on differences
  apply  make the changes
  check  fail if anything would change (drift detection)
"""

import argparse
import os
import pathlib
from collections.abc import Sequence

from gha_tools.repo_settings import actions_permissions
from gha_tools.repo_settings import github
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
    # TODO: remove once no caller uses _rulesets.yml, which predates
    # .github/actions-permissions.json.
    parser.add_argument(
        '--rulesets-only', action='store_true', help='reconcile only rulesets'
    )
    return parser.parse_args(argv)


def _reconcile(
    client: github.Client,
    desired_rulesets: dict[str, desired.Ruleset],
    permissions: actions_permissions.Permissions | None,
    mode: str,
    out: report.Report,
) -> int:
    status = rulesets.reconcile(
        client, client.repository(), desired_rulesets, mode, out
    )
    if permissions is not None:
        status |= actions_permissions.reconcile(client, permissions, mode, out)
    out.finish()
    return status


def _run(args: argparse.Namespace, out: report.Report) -> int:
    desired_rulesets = rulesets.validate(args.directory, out)
    permissions = None
    if not args.rulesets_only:
        permissions = actions_permissions.validate(args.directory, out)
    if desired_rulesets is None or (
        permissions is None and not args.rulesets_only
    ):
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
        return _reconcile(
            client, desired_rulesets, permissions, args.mode, out
        )
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
