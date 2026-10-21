import json
import pathlib
from typing import Any

Ruleset = dict[str, Any]

# Present in UI exports and API responses but not part of a create/update
# body; dropping them lets UI exports be committed verbatim.
SERVER_FIELDS = frozenset(
    {
        '_links',
        'created_at',
        'current_user_can_bypass',
        'id',
        'node_id',
        'source',
        'source_type',
        'updated_at',
    }
)
REQUIRED_FIELDS = ('name', 'target', 'enforcement')


class InvalidRulesetError(ValueError):
    pass


def parse(label: str, text: str) -> Ruleset:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidRulesetError(f'{label}: invalid JSON: {exc}') from exc

    if not isinstance(data, dict):
        raise InvalidRulesetError(f'{label}: expected a JSON object')
    for field in REQUIRED_FIELDS:
        if not isinstance(data.get(field), str):
            raise InvalidRulesetError(f'{label}: missing string "{field}"')
    if not isinstance(data.get('rules', []), list):
        raise InvalidRulesetError(f'{label}: "rules" must be a list')

    return {k: v for k, v in data.items() if k not in SERVER_FIELDS}


def load(directory: pathlib.Path) -> dict[str, Ruleset]:
    """
    Every ruleset defined in `directory`, keyed by ruleset name.

    A missing or empty directory is an error rather than "no rulesets": the
    reconciler is authoritative, so treating it as empty would delete every
    ruleset and the classic branch protection.
    """
    paths = sorted(directory.glob('*.json')) if directory.is_dir() else []
    if not paths:
        raise InvalidRulesetError(f'{directory}: no ruleset definitions')

    rulesets: dict[str, Ruleset] = {}
    for path in paths:
        ruleset = parse(path.name, path.read_text(encoding='utf-8'))
        name = ruleset['name']
        if name in rulesets:
            raise InvalidRulesetError(
                f'{path.name}: duplicate ruleset name "{name}"'
            )
        rulesets[name] = ruleset
    return rulesets
