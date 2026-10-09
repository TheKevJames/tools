import pathlib

from gha_tools.rulesets import checks
from gha_tools.rulesets import desired

CI = """
name: ci
on: [pull_request, push]
jobs:
  lint:
    runs-on: ubuntu-latest
  test:
    strategy:
      matrix:
        python: ['3.13', '3.14']
  docker:
    name: docker-${{ matrix.image }}
    strategy:
      matrix:
        image: [fava, mysqltuner]
    uses: ./.github/workflows/_docker-image.yml
"""

DOCS = """
name: docs
on:
  pull_request:
    paths: [docs/**]
jobs:
  readme:
    name: build readme
"""


def _warnings(tmp_path: pathlib.Path, contexts: list[str]) -> list[str]:
    workflows = tmp_path / '.github' / 'workflows'
    workflows.mkdir(parents=True)
    (workflows / 'ci.yml').write_text(CI)
    (workflows / 'docs.yaml').write_text(DOCS)
    jobs, problems = checks.load_jobs(workflows)
    assert not problems
    found = checks.warnings(contexts, jobs)
    print(found)
    return found


def test_names_reported_by_workflow_jobs_are_accepted(
    tmp_path: pathlib.Path,
) -> None:
    contexts = [
        'lint',
        'test (3.14)',
        'docker-fava / build',
        'ci/circleci: pre-commit',
    ]
    assert not _warnings(tmp_path, contexts)


def test_unknown_and_path_filtered_checks_warn(tmp_path: pathlib.Path) -> None:
    found = _warnings(tmp_path, ['lnt', 'build readme'])
    assert len(found) == 2
    assert '"lnt" matches no workflow job' in found[0]
    assert 'path-filtered workflow(s) docs.yaml' in found[1]


def test_required_contexts_collects_across_rulesets() -> None:
    def ruleset(*names: str) -> desired.Ruleset:
        checks_param = [{'context': name} for name in names]
        return {
            'rules': [
                {'type': 'deletion'},
                {
                    'type': 'required_status_checks',
                    'parameters': {'required_status_checks': checks_param},
                },
            ]
        }

    rulesets = [ruleset('wip', 'lint'), ruleset('lint'), {'rules': []}]
    assert checks.required_contexts(rulesets) == ['lint', 'wip']
