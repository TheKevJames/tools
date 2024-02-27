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
from collections.abc import Iterator
from typing import Optional

from google.cloud import pubsub_v1  # type: ignore[import-untyped]
# TODO: https://github.com/googleapis/python-pubsub/issues/536


@dataclasses.dataclass
class SubscriptionConfig:
    name: str
    endpoint: Optional[str] = None


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
                SubscriptionConfig(sub['name'], sub.get('push_endpoint'))
                for sub in spec.get('subscriptions') or []
            ]
            yield TopicConfig(spec['topic'], spec['project'], subscriptions)
    except FileNotFoundError:
        pprint('loading config from env...')
    except Exception:
        pprint(__doc__)
        print()
        pprint('ERROR: invalid configuration file')
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
            if subscription.endpoint:
                pprint(f'push endpoint: {subscription.endpoint}', 3)


def create(topic: TopicConfig) -> None:
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()
    pprint(f'configuring topic: {topic.name} in project: {topic.project}')

    pprint(f'- creating topic: {topic.name}')
    topic_name = publisher.topic_path(topic.project, topic.name)
    publisher.create_topic(name=topic_name)

    for subscription in topic.subscriptions:
        pprint(f'  - creating subscription: {subscription.name}')

        c: Optional[pubsub_v1.types.PushConfig]
        if subscription.endpoint:
            pprint(f'    using push endpoint: {subscription.endpoint}')
            c = pubsub_v1.types.PushConfig(push_endpoint=subscription.endpoint)
        else:
            c = None

        subscription_name = subscriber.subscription_path(
            topic.project,
            subscription.name,
        )
        subscriber.create_subscription(
            name=subscription_name,
            topic=topic_name,
            push_config=c,
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
