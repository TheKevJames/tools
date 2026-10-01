import argparse
import datetime
import os
import sys
from collections.abc import Sequence

from gha_tools.prune_tags import registries
from gha_tools.prune_tags import selection


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--registry', required=True, choices=['dockerhub', 'quay']
    )
    parser.add_argument('--repository', required=True)
    parser.add_argument('--max-age-days', type=int, default=7)
    parser.add_argument('--delete-pattern', action='append', dest='delete')
    parser.add_argument('--protect-pattern', action='append', dest='protect')
    parser.add_argument(
        '--execute',
        action='store_true',
        help='actually delete; omit for a dry run',
    )
    return parser.parse_args(argv)


def _emit_output(deleted: Sequence[str]) -> None:
    path = os.environ.get('GITHUB_OUTPUT')
    if not path:
        return
    with open(path, 'a', encoding='utf-8') as handle:
        handle.write(f'deleted-count={len(deleted)}\n')
        handle.write(f'deleted-tags={" ".join(deleted)}\n')


def _delete_all(
    client: registries.DockerHubClient | registries.QuayClient,
    tags: Sequence[str],
) -> int:
    failures = 0
    for name in tags:
        try:
            client.delete_tag(name)
        except Exception as exc:
            failures += 1
            print(f'  FAILED {name}: {exc}', file=sys.stderr)
        else:
            print(f'  deleted {name}')
    return failures


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    delete_patterns = selection.compile_patterns(
        args.delete or selection.DEFAULT_DELETE_PATTERNS
    )
    protect_patterns = selection.compile_patterns(
        args.protect or selection.DEFAULT_PROTECT_PATTERNS
    )

    client = registries.make_client(args.registry, args.repository)
    doomed = selection.select_tags_for_deletion(
        client.list_tags(),
        now=datetime.datetime.now(datetime.UTC),
        max_age=datetime.timedelta(days=args.max_age_days),
        delete_patterns=delete_patterns,
        protect_patterns=protect_patterns,
    )

    print(
        f'{args.registry}:{args.repository}: '
        f'{len(doomed)} tag(s) match the prune policy'
    )
    for name in doomed:
        print(f'  - {name}')

    if not args.execute:
        print('dry run: no tags deleted (pass --execute to delete)')
        _emit_output([])
        return 0

    failures = _delete_all(client, doomed)
    _emit_output([] if failures else doomed)
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
