"""
Reconcile a repository's rulesets with its `.github/rulesets/*.json` files.

The definitions are authoritative: rulesets missing from them are deleted, as
is classic branch protection on the default branch, which would otherwise
keep enforcing alongside the rulesets.

Modes:
  plan   report what apply would change; never fails on differences
  apply  make the changes
  check  fail if anything would change (drift detection)
"""

import argparse
import os
import pathlib
from collections.abc import Sequence

from gha_tools.rulesets import checks
from gha_tools.rulesets import desired
from gha_tools.rulesets import diff
from gha_tools.rulesets import github
from gha_tools.rulesets import report


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


def _validate(
    root: pathlib.Path, out: report.Report
) -> dict[str, desired.Ruleset] | None:
    try:
        rulesets = desired.load(root / '.github' / 'rulesets')
    except desired.InvalidRulesetError as exc:
        out.error(str(exc))
        return None

    jobs, problems = checks.load_jobs(root / '.github' / 'workflows')
    contexts = checks.required_contexts(rulesets.values())
    for message in (*problems, *checks.warnings(contexts, jobs)):
        out.warning(message)
    return rulesets


def _apply_change(client: github.Client, change: diff.Change) -> None:
    match change:
        case diff.Create(body=body):
            client.create_ruleset(body)
        case diff.Update(ruleset_id=ruleset_id, body=body):
            client.update_ruleset(ruleset_id, body)
        case diff.Delete(ruleset_id=ruleset_id):
            client.delete_ruleset(ruleset_id)


def _apply(
    client: github.Client,
    changes: Sequence[diff.Change],
    delete_classic: str | None,
    out: report.Report,
) -> int:
    """
    Apply every change, reporting each failure rather than stopping.

    Changes arrive creates and updates first, so the branch is never left
    less protected than either the old or the new configuration.
    """
    failures = 0
    for change in changes:
        try:
            _apply_change(client, change)
        except github.ApiError as exc:
            failures += 1
            out.error(f'{report.describe(change)}: {exc}')
    if delete_classic is not None:
        try:
            client.delete_classic_protection(delete_classic)
        except github.ApiError as exc:
            failures += 1
            out.error(f'delete classic branch protection: {exc}')
    return 1 if failures else 0


def _reconcile(
    client: github.Client,
    rulesets: dict[str, desired.Ruleset],
    mode: str,
    out: report.Report,
) -> int:
    repo = client.repository()
    if repo['private']:
        out.notice(
            'skipped: rulesets on private repositories require GitHub Pro'
        )
        return 0

    bypass_visible = mode != 'plan'
    changes = diff.plan(
        rulesets, client.rulesets(), bypass_visible=bypass_visible
    )
    branch = repo['default_branch']
    classic = client.classic_protection(branch)
    if not bypass_visible:
        out.notice('bypass actors were not compared (needs an admin token)')
    if classic is None:
        out.notice('classic branch protection was not checked (needs admin)')

    out.changes(changes, delete_classic=bool(classic))
    if mode == 'check' and (changes or classic):
        out.error('rulesets have drifted; run the workflow manually to apply')
        return 1
    if mode != 'apply':
        return 0
    return _apply(client, changes, branch if classic else None, out)


def _run(args: argparse.Namespace, out: report.Report) -> int:
    rulesets = _validate(args.directory, out)
    if rulesets is None:
        return 1

    token = os.environ.get('GH_TOKEN')
    if not token:
        out.error(
            'no token: set the RULESETS_TOKEN secret on this repository '
            '(see `repo-template set-secret`)'
        )
        return 1

    api = os.environ.get('GITHUB_API_URL', 'https://api.github.com')
    client = github.Client(api, args.repository, token)
    try:
        return _reconcile(client, rulesets, args.mode, out)
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
