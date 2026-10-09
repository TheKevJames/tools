"""
Heuristic validation of required status checks against workflow jobs.

A required check that never reports blocks every merge, and the two usual
causes are a typo'd name and a workflow skipped by `paths` filtering (a
job-level `if:` reports "skipped", which satisfies the requirement; a
filtered-out workflow reports nothing). This only warns: names derived from
workflow files are approximate, and external CI cannot be checked at all.
"""

import dataclasses
import pathlib
import re
from collections.abc import Iterable
from collections.abc import Iterator
from typing import Any

import yaml

from gha_tools.rulesets import desired

# Commit statuses posted by CircleCI; nothing in the repo predicts them.
EXTERNAL_PREFIXES = ('ci/circleci:',)
_EXPRESSION = re.compile(r'\$\{\{.*?\}\}')
_FILTERED_EVENTS = ('pull_request', 'pull_request_target', 'push')


@dataclasses.dataclass(frozen=True)
class Job:
    workflow: str
    patterns: tuple[re.Pattern[str], ...]
    path_filtered: bool


def required_contexts(rulesets: Iterable[desired.Ruleset]) -> list[str]:
    return sorted(
        {
            check['context']
            for ruleset in rulesets
            for rule in ruleset.get('rules', [])
            if rule.get('type') == 'required_status_checks'
            for check in rule['parameters']['required_status_checks']
        }
    )


def _pattern(template: str) -> re.Pattern[str]:
    parts = _EXPRESSION.split(template)
    return re.compile('.*'.join(re.escape(p) for p in parts))


def check_names(job_id: str, job: dict[str, Any]) -> list[str]:
    """Templates for the check names a job reports, `${{ }}` as wildcards."""
    base = job.get('name') or job_id
    if 'uses' in job:
        return [f'{base} / ${{{{ callee }}}}']
    if 'matrix' in job.get('strategy', {}):
        # Without a matrix expression in the name, GitHub appends the matrix
        # values in parentheses.
        return [base, f'{base} (${{{{ matrix }}}})']
    return [base]


def _is_path_filtered(triggers: object) -> bool:
    if not isinstance(triggers, dict):
        return False
    return any(
        isinstance(triggers.get(event), dict)
        and ('paths' in triggers[event] or 'paths-ignore' in triggers[event])
        for event in _FILTERED_EVENTS
    )


def parse_workflow(name: str, text: str) -> Iterator[Job]:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return
    # YAML 1.1 parses the bare key `on` as boolean True.
    triggers = data.get('on', data.get(True))
    filtered = _is_path_filtered(triggers)
    for job_id, job in (data.get('jobs') or {}).items():
        patterns = tuple(_pattern(n) for n in check_names(job_id, job))
        yield Job(name, patterns, filtered)


def load_jobs(workflows: pathlib.Path) -> tuple[list[Job], list[str]]:
    jobs: list[Job] = []
    problems: list[str] = []
    if not workflows.is_dir():
        return jobs, problems
    paths = sorted([*workflows.glob('*.yml'), *workflows.glob('*.yaml')])
    for path in paths:
        try:
            jobs.extend(parse_workflow(path.name, path.read_text()))
        except yaml.YAMLError as exc:
            problems.append(f'{path.name}: could not parse workflow: {exc}')
    return jobs, problems


def warnings(contexts: Iterable[str], jobs: Iterable[Job]) -> list[str]:
    jobs = list(jobs)
    found: list[str] = []
    for context in contexts:
        if context.startswith(EXTERNAL_PREFIXES):
            continue
        sources = [
            job
            for job in jobs
            if any(p.fullmatch(context) for p in job.patterns)
        ]
        if not sources:
            found.append(
                f'required check "{context}" matches no workflow job; '
                'merges will block until something reports it'
            )
        elif all(job.path_filtered for job in sources):
            names = ', '.join(sorted({job.workflow for job in sources}))
            found.append(
                f'required check "{context}" only comes from path-filtered '
                f'workflow(s) {names}; PRs outside those paths will block'
            )
    return found
