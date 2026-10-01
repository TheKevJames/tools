import datetime

import hypothesis
import hypothesis.strategies

from gha_tools.prune_tags import selection

NOW = datetime.datetime(2026, 10, 1, tzinfo=datetime.UTC)
WEEK = datetime.timedelta(days=7)

DELETE = selection.compile_patterns(selection.DEFAULT_DELETE_PATTERNS)
PROTECT = selection.compile_patterns(selection.DEFAULT_PROTECT_PATTERNS)

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
    hypothesis.strategies.integers(min_value=-30, max_value=30),
)


@hypothesis.strategies.composite
def tags(draw: hypothesis.strategies.DrawFn) -> selection.TagInfo:
    name = draw(_names)
    offset = draw(_ages)
    pushed = None if offset is None else NOW - datetime.timedelta(days=offset)
    return selection.TagInfo(name, pushed)


tag_lists = hypothesis.strategies.lists(tags(), unique_by=lambda t: t.name)


def _select(
    items: list[selection.TagInfo], *, max_age: datetime.timedelta = WEEK
) -> list[str]:
    return selection.select_tags_for_deletion(
        items,
        now=NOW,
        max_age=max_age,
        delete_patterns=DELETE,
        protect_patterns=PROTECT,
    )


@hypothesis.given(tag_lists)
def test_protected_tags_are_never_selected(
    items: list[selection.TagInfo],
) -> None:
    selected = set(_select(items))
    assert not any(p.search(name) for name in selected for p in PROTECT)


@hypothesis.given(tag_lists)
def test_nothing_within_the_window_is_selected(
    items: list[selection.TagInfo],
) -> None:
    doomed = set(_select(items))
    for tag in items:
        if tag.name in doomed:
            assert tag.last_pushed is not None
            assert NOW - tag.last_pushed >= WEEK


@hypothesis.given(tag_lists)
def test_selected_tags_match_delete_and_not_protect(
    items: list[selection.TagInfo],
) -> None:
    for name in _select(items):
        assert any(p.search(name) for p in DELETE)
        assert not any(p.search(name) for p in PROTECT)


@hypothesis.given(tag_lists)
def test_zero_max_age_selects_every_candidate(
    items: list[selection.TagInfo],
) -> None:
    doomed = set(_select(items, max_age=datetime.timedelta(0)))
    for tag in items:
        candidate = any(p.search(tag.name) for p in DELETE) and not any(
            p.search(tag.name) for p in PROTECT
        )
        assert (tag.name in doomed) == candidate


def test_missing_timestamp_is_kept_within_window() -> None:
    items = [selection.TagInfo('sha-abc123', None)]
    assert not _select(items)
