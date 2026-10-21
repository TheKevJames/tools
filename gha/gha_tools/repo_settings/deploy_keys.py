"""
Deploy keys: report, never change.

The `tags` ruleset's DeployKey bypass trusts every deploy key on the
repository, so the only write key allowed is the one release tags are pushed
with (`repo-template set-deploy-key`). Read-only keys can't push, so they are
ignored.

Nothing is deleted or added: a key added through the API is deleted along
with the token that added it, so keys are added in the web UI, and an
unexpected one is for the owner to look at.
"""

from typing import Any

from gha_tools.repo_settings import github
from gha_tools.repo_settings import report

TAG_KEY_TITLE = 'tag'


def problems(keys: list[dict[str, Any]]) -> list[str]:
    writers = [key for key in keys if not key['read_only']]
    found = [
        f'unexpected write deploy key "{key["title"]}" (id {key["id"]}): '
        f'only "{TAG_KEY_TITLE}" may push'
        for key in writers
        if key['title'] != TAG_KEY_TITLE
    ]
    tag_keys = [key for key in writers if key['title'] == TAG_KEY_TITLE]
    if len(tag_keys) > 1:
        ids = ', '.join(str(key['id']) for key in tag_keys)
        found.append(
            f'{len(tag_keys)} write deploy keys titled "{TAG_KEY_TITLE}" '
            f'(ids {ids}): delete all but the one in use'
        )
    return found


def reconcile(client: github.Client, mode: str, out: report.Report) -> int:
    keys = client.deploy_keys()
    if keys is None:
        if mode == 'plan':
            out.notice('deploy keys were not checked (needs an admin token)')
            return 0
        out.error(
            'could not read deploy keys: the token needs Administration: read'
        )
        return 1
    found = problems(keys)
    for message in found:
        out.error(message)
    return 1 if found else 0
