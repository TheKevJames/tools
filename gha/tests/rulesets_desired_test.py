import json

import hypothesis
import hypothesis.strategies as st

from gha_tools.rulesets import desired

_json = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(max_size=8),
    lambda children: (
        st.lists(children, max_size=3)
        | st.dictionaries(st.text(max_size=8), children, max_size=3)
    ),
    max_leaves=8,
)
_bodies = st.fixed_dictionaries(
    {
        'name': st.text(max_size=8),
        'target': st.sampled_from(['branch', 'tag', 'push']),
        'enforcement': st.sampled_from(['active', 'disabled', 'evaluate']),
    },
    optional={
        'rules': st.lists(_json, max_size=3),
        'conditions': _json,
        'bypass_actors': st.lists(_json, max_size=3),
    },
)
# Read-only fields of GitHub's ruleset responses, which UI exports include.
_server_fields = st.dictionaries(
    st.sampled_from(
        [
            '_links',
            'created_at',
            'current_user_can_bypass',
            'id',
            'node_id',
            'source',
            'source_type',
            'updated_at',
        ]
    ),
    _json,
)


@hypothesis.given(_bodies, _server_fields)
def test_server_fields_are_dropped_from_exports(
    body: desired.Ruleset, server_fields: dict[str, object]
) -> None:
    exported = json.dumps(server_fields | body)
    assert desired.parse('ruleset.json', exported) == body
