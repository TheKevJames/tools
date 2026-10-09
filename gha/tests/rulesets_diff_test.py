import json
import random
from typing import Any

import hypothesis
import hypothesis.strategies as st

from gha_tools.rulesets import desired
from gha_tools.rulesets import diff

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
    view = _server_view(value, rng)
    print(json.dumps(view))
    assert diff.matches(value, view)


@hypothesis.given(json_values, json_values)
@hypothesis.example(True, 1)
@hypothesis.example([0, False], [False, 0])
def test_matches_is_equality_without_dicts(want: object, have: object) -> None:
    # With no dicts to carry extra keys, matching reduces to equality up to
    # list order (and without bool/int conflation).
    hypothesis.assume('{' not in json.dumps([want, have]))
    expected = json.dumps(diff.canonical(want)) == json.dumps(
        diff.canonical(have)
    )
    assert diff.matches(want, have) is expected


@hypothesis.given(json_objects.filter(bool), json_values, st.data())
def test_changed_value_does_not_match(
    want: dict[str, object], replacement: object, data: st.DataObject
) -> None:
    key = data.draw(st.sampled_from(sorted(want)))
    hypothesis.assume(not diff.matches(want[key], replacement))
    assert not diff.matches(want, want | {key: replacement})


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
    print(changes)

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
