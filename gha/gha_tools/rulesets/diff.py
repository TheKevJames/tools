import dataclasses
import difflib
import json

from gha_tools.rulesets import desired


@dataclasses.dataclass(frozen=True)
class Create:
    name: str
    body: desired.Ruleset


@dataclasses.dataclass(frozen=True)
class Update:
    name: str
    ruleset_id: int
    body: desired.Ruleset
    detail: str


@dataclasses.dataclass(frozen=True)
class Delete:
    name: str
    ruleset_id: int


Change = Create | Update | Delete


def matches(want: object, have: object) -> bool:
    """
    Whether `have` satisfies everything `want` specifies.

    Dicts match on the keys `want` sets: the API fills in defaults for
    unspecified parameters, so extra keys in `have` are not drift. This does
    mean a non-default remote value for a key omitted from `want` goes
    unnoticed; definitions should spell out every parameter they care about.
    Lists match as unordered collections, since nothing in a ruleset is
    order-sensitive and the API does not preserve order.
    """
    if isinstance(want, dict):
        return isinstance(have, dict) and all(
            key in have and matches(value, have[key])
            for key, value in want.items()
        )
    if isinstance(want, list):
        return (
            isinstance(have, list)
            and len(want) == len(have)
            and _pairs_up(want, have)
        )
    # bool is an int subclass: True == 1 must not count as a match.
    return type(want) is type(have) and want == have


def _pairs_up(want: list[object], have: list[object]) -> bool:
    if not want:
        return True
    head, rest = want[0], want[1:]
    return any(
        matches(head, candidate) and _pairs_up(rest, have[:i] + have[i + 1 :])
        for i, candidate in enumerate(have)
    )


def comparable(
    ruleset: desired.Ruleset, bypass_visible: bool
) -> desired.Ruleset:
    if bypass_visible:
        return ruleset
    return {k: v for k, v in ruleset.items() if k != 'bypass_actors'}


def plan(
    want: dict[str, desired.Ruleset],
    have: dict[str, desired.Ruleset],
    *,
    bypass_visible: bool,
) -> list[Change]:
    """
    Changes which make `have` match `want`, creates and updates first.

    Without admin access the API omits `bypass_actors`; `bypass_visible`
    False compares everything else.
    """
    changes: list[Change] = []
    for name, ruleset in sorted(want.items()):
        existing = have.get(name)
        if existing is None:
            changes.append(Create(name, ruleset))
            continue
        expected = comparable(ruleset, bypass_visible)
        if not matches(expected, existing):
            detail = render_diff(expected, existing)
            changes.append(Update(name, existing['id'], ruleset, detail))
    changes.extend(
        Delete(name, have[name]['id'])
        for name in sorted(set(have) - set(want))
    )
    return changes


def _project(want: object, have: object) -> object:
    """`have` restricted to the shape of `want`, for a readable diff."""
    if isinstance(want, dict) and isinstance(have, dict):
        return {k: _project(want[k], have[k]) for k in want if k in have}
    if isinstance(want, list) and isinstance(have, list):
        keys = {k for item in want if isinstance(item, dict) for k in item}
        if not keys:
            return have
        return [
            {k: v for k, v in item.items() if k in keys}
            if isinstance(item, dict)
            else item
            for item in have
        ]
    return have


def canonical(value: object) -> object:
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        items = [canonical(v) for v in value]
        return sorted(items, key=lambda v: json.dumps(v, sort_keys=True))
    return value


def render_diff(want: object, have: object) -> str:
    def dump(value: object) -> list[str]:
        return json.dumps(canonical(value), indent=2).splitlines()

    return '\n'.join(
        difflib.unified_diff(
            dump(_project(want, have)),
            dump(want),
            fromfile='github',
            tofile='repo',
            lineterm='',
        )
    )
