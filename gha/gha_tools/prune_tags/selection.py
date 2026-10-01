import dataclasses
import datetime
import re
from collections.abc import Iterable
from collections.abc import Sequence

# Commit-hash tags: the docker/metadata-action `type=sha` form (`sha-<hex>`)
# and the legacy CircleCI form (a bare `${CIRCLE_SHA1:0:10}` hex string). The
# bare-hex pattern also sweeps any stray short/full SHAs.
DEFAULT_DELETE_PATTERNS = (r'^sha-[0-9a-f]+$', r'^[0-9a-f]{7,40}$')
# Protect wins over delete, so an unrecognised tag is always kept. `latest` and
# semver releases must survive even if a future scheme makes them look hex-ish.
DEFAULT_PROTECT_PATTERNS = (r'^latest$', r'^v?\d+\.\d+\.\d+')


@dataclasses.dataclass(frozen=True)
class TagInfo:
    name: str
    last_pushed: datetime.datetime | None


def compile_patterns(patterns: Iterable[str]) -> list[re.Pattern[str]]:
    return [re.compile(p) for p in patterns]


def _matches_any(name: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    return any(p.search(name) for p in patterns)


def _old_enough(
    last_pushed: datetime.datetime | None,
    *,
    now: datetime.datetime,
    max_age: datetime.timedelta,
) -> bool:
    if max_age <= datetime.timedelta(0):
        return True
    if last_pushed is None:
        return False
    return now - last_pushed >= max_age


def select_tags_for_deletion(
    tags: Iterable[TagInfo],
    *,
    now: datetime.datetime,
    max_age: datetime.timedelta,
    delete_patterns: Sequence[re.Pattern[str]],
    protect_patterns: Sequence[re.Pattern[str]],
) -> list[str]:
    selected: list[str] = []
    for tag in tags:
        if _matches_any(tag.name, protect_patterns):
            continue
        if not _matches_any(tag.name, delete_patterns):
            continue
        if not _old_enough(tag.last_pushed, now=now, max_age=max_age):
            continue
        selected.append(tag.name)
    return selected
