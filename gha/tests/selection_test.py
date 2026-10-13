import datetime
import re

import hypothesis
import hypothesis.strategies
import pytest

from gha_tools.prune_tags import selection

NOW = datetime.datetime(2026, 10, 1, tzinfo=datetime.UTC)
DAY = datetime.timedelta(days=1)

# Overlapping delete/protect choices so protect-wins-over-delete is exercised.
_PATTERN_POOL = (
    *selection.DEFAULT_DELETE_PATTERNS,
    *selection.DEFAULT_PROTECT_PATTERNS,
    r'^sha-0',
    r'rc',
    r'a',
)

_hex = hypothesis.strategies.text('0123456789abcdef', min_size=1, max_size=40)
_names = hypothesis.strategies.one_of(
    _hex.map(lambda h: f'sha-{h}'),
    _hex,
    hypothesis.strategies.sampled_from(
        ['latest', 'v1.2.3', '1.2.3', '2.0.0-rc1']
    ),
    hypothesis.strategies.text(min_size=1, max_size=12),
)
_ages = hypothesis.strategies.one_of(
    hypothesis.strategies.none(),
    hypothesis.strategies.integers(min_value=-1, max_value=10),
)
_max_age_days = hypothesis.strategies.integers(min_value=-1, max_value=10)
_patterns = hypothesis.strategies.lists(
    hypothesis.strategies.sampled_from(_PATTERN_POOL), max_size=3
).map(selection.compile_patterns)


@hypothesis.strategies.composite
def tags(draw: hypothesis.strategies.DrawFn) -> selection.TagInfo:
    name = draw(_names)
    offset = draw(_ages)
    pushed = None if offset is None else NOW - offset * DAY
    return selection.TagInfo(name, pushed)


tag_lists = hypothesis.strategies.lists(tags())


def _select(
    items: list[selection.TagInfo],
    *,
    max_age: datetime.timedelta,
    delete: list[re.Pattern[str]],
    protect: list[re.Pattern[str]],
) -> list[str]:
    return selection.select_tags_for_deletion(
        items,
        now=NOW,
        max_age=max_age,
        delete_patterns=delete,
        protect_patterns=protect,
    )


@hypothesis.given(tag_lists, _max_age_days, _patterns, _patterns)
@hypothesis.example(
    [selection.TagInfo('sha-0', NOW - 7 * DAY)],
    7,
    selection.compile_patterns(['sha']),
    [],
)
@hypothesis.example(
    [selection.TagInfo('sha-0', None)],
    0,
    selection.compile_patterns(['sha']),
    [],
)
@hypothesis.example(
    [selection.TagInfo('sha-0', NOW - 30 * DAY)],
    7,
    selection.compile_patterns(['sha']),
    selection.compile_patterns(['0$']),
)
def test_selects_exactly_old_candidates_in_order(
    items: list[selection.TagInfo],
    max_age_days: int,
    delete: list[re.Pattern[str]],
    protect: list[re.Pattern[str]],
) -> None:
    max_age = max_age_days * DAY

    def doomed(tag: selection.TagInfo) -> bool:
        candidate = any(p.search(tag.name) for p in delete) and not any(
            p.search(tag.name) for p in protect
        )
        # A non-positive window disables the age check entirely, even for
        # tags without a timestamp.
        old = max_age <= datetime.timedelta(0) or (
            tag.last_pushed is not None and NOW - tag.last_pushed >= max_age
        )
        return candidate and old

    selected = _select(items, max_age=max_age, delete=delete, protect=protect)
    assert selected == [tag.name for tag in items if doomed(tag)]


@hypothesis.given(
    tag_lists, _max_age_days, _max_age_days, _patterns, _patterns
)
def test_widening_the_window_never_selects_more(
    items: list[selection.TagInfo],
    days_a: int,
    days_b: int,
    delete: list[re.Pattern[str]],
    protect: list[re.Pattern[str]],
) -> None:
    shorter, longer = sorted([days_a, days_b])
    kwargs = {'delete': delete, 'protect': protect}
    assert set(_select(items, max_age=longer * DAY, **kwargs)) <= set(
        _select(items, max_age=shorter * DAY, **kwargs)
    )


@pytest.mark.parametrize(
    ('name', 'deleted'),
    [
        ('sha-0123abc', True),
        ('0123abc', True),
        ('0123abc0123abc0123abc0123abc0123abc0123a', True),
        ('0123ab', False),
        ('latest', False),
        ('v1.2.3', False),
        ('1.2.3', False),
        ('2.0.0-rc1', False),
        ('main', False),
    ],
)
def test_default_policy(name: str, deleted: bool) -> None:
    items = [selection.TagInfo(name, NOW - 30 * DAY)]
    selected = _select(
        items,
        max_age=7 * DAY,
        delete=selection.compile_patterns(selection.DEFAULT_DELETE_PATTERNS),
        protect=selection.compile_patterns(selection.DEFAULT_PROTECT_PATTERNS),
    )
    assert selected == ([name] if deleted else [])
