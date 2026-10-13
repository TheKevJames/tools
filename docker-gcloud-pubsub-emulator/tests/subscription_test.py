import json
import pathlib
from typing import Any

import hypothesis
import pytest
from google.pubsub_v1 import types
from hypothesis import strategies as st

import pubsubc

SAMPLE_CONFIG = pathlib.Path(__file__).parent.parent / 'config.json'

TEXT = st.text(
    st.characters(exclude_categories=['Cs'], exclude_characters='\x00'),
    max_size=12,
)
NAME = TEXT.filter(bool)
DURATION = st.builds(
    lambda seconds, nanos: f'{seconds}.{nanos:09d}s',
    st.integers(min_value=0, max_value=10**8),
    st.integers(min_value=0, max_value=10**9 - 1),
)
INT32 = st.integers(min_value=0, max_value=2**31 - 1)
LABELS = st.dictionaries(NAME, TEXT, max_size=3)

# Nested configs are generated non-empty: an empty block is treated as unset,
# which the API considers equivalent but proto equality does not.
SUBSCRIPTION = st.fixed_dictionaries(
    {'name': NAME},
    optional={
        'push_config': st.fixed_dictionaries(
            {'push_endpoint': NAME}, optional={'attributes': LABELS}
        ),
        'bigquery_config': st.fixed_dictionaries(
            {'table': NAME},
            optional={
                'use_table_schema': st.booleans(),
                'write_metadata': st.booleans(),
                'drop_unknown_fields': st.booleans(),
                'service_account_email': TEXT,
            },
        ),
        'cloud_storage_config': st.fixed_dictionaries(
            {'bucket': NAME},
            optional={'filename_prefix': TEXT, 'filename_suffix': TEXT},
        ),
        'ack_deadline_seconds': INT32,
        'retain_acked_messages': st.booleans(),
        'message_retention_duration': DURATION,
        'labels': LABELS,
        'enable_message_ordering': st.booleans(),
        'expiration_policy': st.fixed_dictionaries({'ttl': DURATION}),
        'filter': TEXT,
        'dead_letter_policy': st.fixed_dictionaries(
            {'dead_letter_topic': NAME},
            optional={'max_delivery_attempts': INT32},
        ),
        'retry_policy': st.fixed_dictionaries(
            {'minimum_backoff': DURATION},
            optional={'maximum_backoff': DURATION},
        ),
        'detached': st.booleans(),
        'enable_exactly_once_delivery': st.booleans(),
    },
)


def _request(topic: str, data: dict[str, Any]) -> types.Subscription:
    """The request ``create()`` would send for this subscription config."""
    args = pubsubc.SubscriptionConfig.from_json(data).to_args()
    return types.Subscription({'name': data['name'], 'topic': topic} | args)


@hypothesis.given(SUBSCRIPTION)
def test_config_is_passed_through_as_subscription_resource(
    data: dict[str, Any],
) -> None:
    # The README promises the JSON block mirrors the API's Subscription
    # resource, so building that resource directly from the JSON is the oracle.
    print(json.dumps(data))
    expected = types.Subscription({'topic': 'projects/p/topics/t'} | data)
    assert _request('projects/p/topics/t', data) == expected


def test_sample_config_is_passed_through() -> None:
    specs = json.loads(SAMPLE_CONFIG.read_text(encoding='utf-8'))
    subscriptions = [sub for spec in specs for sub in spec['subscriptions']]
    assert subscriptions
    for data in subscriptions:
        expected = types.Subscription({'topic': 't'} | data)
        assert _request('t', data) == expected


def test_deprecated_push_endpoint_configures_push(
    capsys: pytest.CaptureFixture[str],
) -> None:
    endpoint = 'http://localhost:3001/messages'
    expected = types.Subscription(
        name='s', topic='t', push_config={'push_endpoint': endpoint}
    )
    assert _request('t', {'name': 's', 'push_endpoint': endpoint}) == expected
    assert 'deprecated' in capsys.readouterr().out
