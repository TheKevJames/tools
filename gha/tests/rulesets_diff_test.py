import collections
import random
from typing import Any

import hypothesis
import hypothesis.strategies as st

from gha_tools.repo_settings.rulesets import desired
from gha_tools.repo_settings.rulesets import diff

_scalars = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-5, max_value=5),
    st.text(max_size=4),
)
_keys = st.text(alphabet='abcdef', min_size=1, max_size=3)
json_values = st.recursive(
    _scalars,
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(_keys, children, max_size=4),
    ),
    max_leaves=12,
)
json_objects = st.dictionaries(_keys, json_values, max_size=4)
_values_by_type = {
    type(None): st.none(),
    bool: st.booleans(),
    int: st.integers(min_value=-5, max_value=5),
    str: st.text(max_size=4),
    list: st.lists(json_values, max_size=4),
    dict: json_objects,
}
dictless_values = st.recursive(
    _scalars, lambda children: st.lists(children, max_size=4), max_leaves=12
)


def _multiset(value: object) -> object:
    """Hashable form equal for values which differ only in list order."""
    if isinstance(value, list):
        counts = collections.Counter(_multiset(item) for item in value)
        return list, frozenset(counts.items())
    return type(value), value


def _server_view(value: object, rng: random.Random) -> Any:  # noqa: ANN401
    """What the API hands back: defaults filled in, lists reordered."""
    if isinstance(value, dict):
        view = {k: _server_view(v, rng) for k, v in value.items()}
        view['zz_server_default'] = rng.random()
        return view
    if isinstance(value, list):
        items = [_server_view(v, rng) for v in value]
        rng.shuffle(items)
        return items
    return value


@hypothesis.given(json_values, st.randoms(use_true_random=False))
def test_server_view_of_a_value_matches_it(
    value: object, rng: random.Random
) -> None:
    assert diff.matches(value, _server_view(value, rng))


@st.composite
def _dictless_pairs(draw: st.DrawFn) -> tuple[object, object]:
    want = draw(dictless_values)
    reordered = st.randoms(use_true_random=False).map(
        lambda rng: _server_view(want, rng)
    )
    return want, draw(st.one_of(dictless_values, reordered))


@hypothesis.given(_dictless_pairs())
@hypothesis.example((True, 1))
@hypothesis.example(([0, False], [False, 0]))
@hypothesis.example(([[1, 2], [3]], [[3], [2, 1]]))
def test_matches_is_equality_without_dicts(
    pair: tuple[object, object],
) -> None:
    # With no dicts to carry extra keys, matching reduces to equality up to
    # list order (and without bool/int conflation).
    want, have = pair
    expected = _multiset(want) == _multiset(have)
    assert diff.matches(want, have) is expected


@hypothesis.given(
    st.dictionaries(_keys, json_values, min_size=1, max_size=4), st.data()
)
def test_changed_or_missing_value_does_not_match(
    want: dict[str, object], data: st.DataObject
) -> None:
    key = data.draw(st.sampled_from(sorted(want)))
    # A value of another type can never match, whatever its contents.
    replacement = data.draw(
        st.one_of(
            *(
                values
                for kind, values in _values_by_type.items()
                if not isinstance(want[key], kind)
            )
        )
    )
    assert not diff.matches(want, want | {key: replacement})
    assert not diff.matches(want, {k: v for k, v in want.items() if k != key})


def test_list_pairing_backtracks() -> None:
    # Greedily pairing {a} with the first candidate would strand {a, b}.
    want = [{'a': 1}, {'a': 1, 'b': 2}]
    have = [{'a': 1, 'b': 2}, {'a': 1, 'c': 3}]
    assert diff.matches(want, have)


_names = st.text(alphabet='xyz', min_size=1, max_size=3)
_rulesets = st.dictionaries(_names, json_objects, max_size=4)


@hypothesis.given(_rulesets, _rulesets, st.randoms(use_true_random=False))
def test_plan_converges(
    want: dict[str, desired.Ruleset],
    have: dict[str, desired.Ruleset],
    rng: random.Random,
) -> None:
    remote = {
        name: {**body, 'id': i} for i, (name, body) in enumerate(have.items())
    }
    changes = diff.plan(want, remote, bypass_visible=True)

    for change in changes:
        match change:
            case (
                diff.Create(name=name, body=body)
                | diff.Update(name=name, body=body)
            ):
                remote[name] = {**_server_view(body, rng), 'id': -1}
            case diff.Delete(name=name):
                del remote[name]

    assert set(remote) == set(want)
    assert not diff.plan(want, remote, bypass_visible=True)


_bypass = st.none() | st.lists(json_objects, max_size=2)
# Few names, so want and have mostly share them and plans include updates.
_with_bypass = st.dictionaries(
    st.sampled_from('xyz'),
    st.builds(
        lambda body, bypass: (
            body if bypass is None else body | {'bypass_actors': bypass}
        ),
        json_objects,
        _bypass,
    ),
    max_size=4,
)


def _hidden(ruleset: desired.Ruleset) -> desired.Ruleset:
    """What a non-admin token sees."""
    return {k: v for k, v in ruleset.items() if k != 'bypass_actors'}


@hypothesis.given(_with_bypass, st.randoms(use_true_random=False))
def test_bypass_actors_are_ignored_without_admin(
    want: dict[str, desired.Ruleset], rng: random.Random
) -> None:
    hidden = {
        name: _server_view(_hidden(body), rng) | {'id': i}
        for i, (name, body) in enumerate(want.items())
    }
    assert not diff.plan(want, hidden, bypass_visible=False)


@hypothesis.given(_with_bypass, _with_bypass)
def test_hiding_bypass_actors_only_hides_changes(
    want: dict[str, desired.Ruleset], have: dict[str, desired.Ruleset]
) -> None:
    remote = {
        name: {**body, 'id': i} for i, (name, body) in enumerate(have.items())
    }
    hidden = {name: _hidden(body) for name, body in remote.items()}

    def summary(changes: list[diff.Change]) -> set[tuple[type, str]]:
        return {(type(change), change.name) for change in changes}

    seen = diff.plan(want, hidden, bypass_visible=False)
    assert summary(seen) <= summary(
        diff.plan(want, remote, bypass_visible=True)
    )
    for change in seen:
        if isinstance(change, diff.Create | diff.Update):
            assert change.body == want[change.name]


def test_hidden_bypass_actors_are_not_drift() -> None:
    bypass = [{'actor_id': 5, 'actor_type': 'RepositoryRole'}]
    want = {'base': {'enforcement': 'active', 'bypass_actors': bypass}}
    have = {'base': {'enforcement': 'active', 'id': 1}}

    assert not diff.plan(want, have, bypass_visible=False)
    changes = diff.plan(want, have, bypass_visible=True)
    assert len(changes) == 1
    change = changes[0]
    assert isinstance(change, diff.Update)
    assert change.body == want['base']
    assert '+  "bypass_actors"' in change.detail
