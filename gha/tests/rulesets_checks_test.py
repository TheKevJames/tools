import pathlib

from gha_tools.repo_settings.rulesets import checks

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
    return checks.warnings(contexts, jobs)


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
