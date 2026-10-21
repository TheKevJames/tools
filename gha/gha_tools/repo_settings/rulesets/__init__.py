"""
Branch rulesets, from `.github/rulesets/*.json`.

The definitions are authoritative: rulesets missing from them are deleted, as
is classic branch protection on the default branch, which would otherwise
keep enforcing alongside the rulesets.
"""

import pathlib
from collections.abc import Sequence
from typing import Any

from gha_tools.repo_settings import github
from gha_tools.repo_settings import report
from gha_tools.repo_settings.rulesets import checks
from gha_tools.repo_settings.rulesets import desired
from gha_tools.repo_settings.rulesets import diff


def describe(change: diff.Change) -> str:
    match change:
        case diff.Create():
            return f'create ruleset "{change.name}"'
        case diff.Update():
            return f'update ruleset "{change.name}"'
        case diff.Delete():
            return f'delete ruleset "{change.name}"'


def validate(
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
            out.error(f'{describe(change)}: {exc}')
    if delete_classic is not None:
        try:
            client.delete_classic_protection(delete_classic)
        except github.ApiError as exc:
            failures += 1
            out.error(f'delete classic branch protection: {exc}')
    return 1 if failures else 0


def reconcile(
    client: github.Client,
    repo: dict[str, Any],
    rulesets: dict[str, desired.Ruleset],
    mode: str,
    out: report.Report,
) -> int:
    if repo['private']:
        out.notice(
            'rulesets skipped: rulesets on private repositories require '
            'GitHub Pro'
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

    for change in changes:
        detail = change.detail if isinstance(change, diff.Update) else None
        out.change(describe(change), detail)
    if classic:
        out.change('delete classic branch protection')
    if mode == 'check' and (changes or classic):
        out.error('rulesets have drifted; run the workflow manually to apply')
        return 1
    if mode != 'apply':
        return 0
    return _apply(client, changes, branch if classic else None, out)
