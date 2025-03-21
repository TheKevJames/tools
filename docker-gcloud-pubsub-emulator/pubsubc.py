#!/usr/bin/env python3
"""
pubsubc.

Usage:

    export PUBSUBC_CONFIG=/my/config.json  # default: /etc/pubsubc/config.json
    ./pubsubc.py

If a configuration file is not found, you may alternatively configure pubsubc
via environment variables:

    export PUBSUB_PROJECT1=project,topic1,topic2:subscription1,...
    export PUBSUB_PROJECT2=...
    ./pubsubc.py

At least $PUBSUB_PROJECT1 must be set, and it must have at least the project
and one topic listed. Topics may have any number of subscriptions, each
separated by a colon.

To run against an emulator, use:

    export PUBSUB_EMULATOR_HOST=localhost:8681

Credit:

    This script was based on: https://github.com/prep/pubsubc
"""
import dataclasses
import json
import os
import sys
import traceback
from collections.abc import Iterator
from typing import Any
from typing import Optional

from google.cloud import pubsub_v1  # type: ignore[import-untyped]
# TODO: https://github.com/googleapis/python-pubsub/issues/536


@dataclasses.dataclass
class SubscriptionConfig:
    # pylint: disable=too-many-instance-attributes
    name: str

    # https://cloud.google.com/pubsub/docs/reference/rest/v1/projects.subscriptions/create?rep_location=global#request-body
    push_config: Optional[pubsub_v1.types.PushConfig] = None
    bigquery_config: Optional[pubsub_v1.types.BigQueryConfig] = None
    cloud_storage_config: Optional[pubsub_v1.types.CloudStorageConfig] = None
    ack_deadline_seconds: Optional[int] = None
    retain_acked_messages: Optional[bool] = None
    message_retention_duration: Optional[str] = None
    labels: Optional[dict[str, str]] = None
    enable_message_ordering: Optional[bool] = None
    expiration_policy: Optional[pubsub_v1.types.ExpirationPolicy] = None
    filter_: Optional[str] = None
    dead_letter_policy: Optional[pubsub_v1.types.DeadLetterPolicy] = None
    retry_policy: Optional[pubsub_v1.types.RetryPolicy] = None
    detached: Optional[bool] = None
    enable_exactly_once_delivery: Optional[bool] = None

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> 'SubscriptionConfig':
        push_config = (
            pubsub_v1.types.PushConfig(data.get('push_config', {}))
            if data.get('push_config') else None
        )
        if data.get('push_endpoint'):
            pprint('WARN: `$.push_endpoint` is deprecated, please nest ')
            pprint('      settings under the `push_config` block.')
            push_config = (
                pubsub_v1.types.PushConfig(push_endpoint=data['push_endpoint'])
            )
        bigquery_config = (
            pubsub_v1.types.BigQueryConfig(data.get('bigquery_config', {}))
            if data.get('bigquery_config') else None
        )
        cloud_storage_config = (
            pubsub_v1.types.CloudStorageConfig(
                data.get('cloud_storage_config', {}),
            )
            if data.get('cloud_storage_config') else None
        )
        expiration_policy = (
            pubsub_v1.types.ExpirationPolicy(data.get('expiration_policy', {}))
            if data.get('expiration_policy') else None
        )
        dead_letter_policy = (
            pubsub_v1.types.DeadLetterPolicy(
                data.get('dead_letter_policy', {}),
            )
            if data.get('dead_letter_policy') else None
        )
        retry_policy = (
            pubsub_v1.types.RetryPolicy(data.get('retry_policy', {}))
            if data.get('retry_policy') else None
        )

        return cls(
            data['name'],
            push_config=push_config,
            bigquery_config=bigquery_config,
            cloud_storage_config=cloud_storage_config,
            ack_deadline_seconds=data.get('ack_deadline_seconds'),
            retain_acked_messages=data.get('retain_acked_messages'),
            message_retention_duration=data.get('message_retention_duration'),
            labels=data.get('labels'),
            enable_message_ordering=data.get('enable_message_ordering'),
            expiration_policy=expiration_policy,
            filter_=data.get('filter'),
            dead_letter_policy=dead_letter_policy,
            retry_policy=retry_policy,
            detached=data.get('detached'),
            enable_exactly_once_delivery=data.get(
                'enable_exactly_once_delivery',
            ),
        )

    def to_args(self) -> dict[str, Any]:
        # pylint: disable=too-complex,too-many-branches
        pprint(f'  - creating subscription: {self.name}')

        data: dict[str, Any] = {}
        if self.push_config is not None:
            pprint(f'    using endpoint: {self.push_config.push_endpoint}')
            data['push_config'] = self.push_config
        if self.bigquery_config is not None:
            data['bigquery_config'] = self.bigquery_config
        if self.cloud_storage_config is not None:
            data['cloud_storage_config'] = self.cloud_storage_config
        if self.ack_deadline_seconds is not None:
            data['ack_deadline_seconds'] = self.ack_deadline_seconds
        if self.retain_acked_messages is not None:
            data['retain_acked_messages'] = self.retain_acked_messages
        if self.message_retention_duration is not None:
            data['message_retention_duration'] = (
                self.message_retention_duration
            )
        if self.labels is not None:
            data['labels'] = self.labels
        if self.enable_message_ordering is not None:
            data['enable_message_ordering'] = self.enable_message_ordering
        if self.expiration_policy is not None:
            data['expiration_policy'] = self.expiration_policy
        if self.filter_ is not None:
            data['filter'] = self.filter_
        if self.dead_letter_policy is not None:
            data['dead_letter_policy'] = self.dead_letter_policy
        if self.retry_policy is not None:
            data['retry_policy'] = self.retry_policy
        if self.detached is not None:
            data['detached'] = self.detached
        if self.enable_exactly_once_delivery is not None:
            data['enable_exactly_once_delivery'] = (
                self.enable_exactly_once_delivery
            )

        return data


@dataclasses.dataclass
class TopicConfig:
    name: str
    project: str
    subscriptions: list[SubscriptionConfig] = dataclasses.field(
        default_factory=list,
    )


def pprint(x: str, levels: int = 0) -> None:
    indent = ' ' * ((levels * 2) + 1)
    print(f'[pubsubc]{indent}{x}')


def build_config() -> Iterator[TopicConfig]:
    fname = os.environ.get('PUBSUBC_CONFIG', '/etc/pubsubc/config.json')
    try:
        with open(fname, encoding='utf-8') as f:
            config = json.load(f)

        pprint(f'loading config from file ({fname})...')
        for spec in config:
            subscriptions = [
                SubscriptionConfig.from_json(sub)
                for sub in spec.get('subscriptions') or []
            ]
            yield TopicConfig(spec['topic'], spec['project'], subscriptions)
    except FileNotFoundError:
        pprint('loading config from env...')
    except Exception:
        pprint(__doc__)
        print()
        pprint('ERROR: invalid configuration file')
        traceback.print_exc()
        sys.exit(1)
    else:
        if os.environ.get('PUBSUB_PROJECT1'):
            pprint('WARN: $PUBSUB_PROJECT1 is set but loaded config from file')
            pprint('      environment variables should be unset')

        return

    i = 0
    while True:
        i += 1
        env = os.environ.get(f'PUBSUB_PROJECT{i}')
        if not env:
            return

        project, *topics = env.split(',')
        if not topics:
            return

        for spec in topics:
            topic_name, *subscription_names = spec.split(':')
            subscriptions = [
                SubscriptionConfig(name)
                for name in subscription_names or []
            ]
            yield TopicConfig(topic_name, project, subscriptions)


def print_config(config: list[TopicConfig]) -> None:
    pprint('built pubsubc config:')
    for topic in config:
        pprint(f'topic: {topic.name} (project: {topic.project})', 1)
        for subscription in topic.subscriptions:
            pprint(f'subscription: {subscription.name}', 2)
            if subscription.push_config:
                pprint(
                    f'push endpoint: {subscription.push_config.push_endpoint}',
                    3,
                )


def create(topic: TopicConfig) -> None:
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()
    pprint(f'configuring topic: {topic.name} in project: {topic.project}')

    pprint(f'- creating topic: {topic.name}')
    topic_name = publisher.topic_path(topic.project, topic.name)
    publisher.create_topic(name=topic_name)

    for subscription in topic.subscriptions:
        args = subscription.to_args()

        subscription_name = subscriber.subscription_path(
            topic.project,
            subscription.name,
        )
        subscriber.create_subscription(
            request={
                'name': subscription_name,
                'topic': topic_name,
            } | args,
        )


def main() -> None:
    config = list(build_config())
    if not config:
        pprint(__doc__)
        print()
        pprint('ERROR: at least one topic must be provided')
        sys.exit(1)

    print_config(config)
    for topic in config:
        create(topic)


if __name__ == '__main__':
    main()
