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
import json
import os
import sys
from collections.abc import Iterator

from google.cloud import pubsub_v1


def pprint(x: str, levels: int = 0) -> None:
    indent = ' ' * ((levels * 2) + 1)
    print(f'[pubsubc]{indent}{x}')


def build_config() -> Iterator[tuple[str, list[str]]]:
    fname = os.environ.get('PUBSUBC_CONFIG', '/etc/pubsubc/config.json')
    try:
        with open(fname, encoding='utf-8') as f:
            config = json.load(f)

        pprint(f'loading config from file ({fname})...')
        for spec in config:
            subscriptions = spec.get('subscriptions')
            topic = spec['topic']
            if subscriptions:
                topic += f':{":".join(s["name"] for s in subscriptions)}'

            yield (spec['project'], [topic])

        if os.environ.get('PUBSUB_PROJECT1'):
            pprint('WARN: $PUBSUB_PROJECT1 is set but loaded config from file')
            pprint('      environment variables should be unset')

        return
    except FileNotFoundError:
        pprint('loading config from env...')
    except Exception:
        pprint(__doc__)
        print()
        pprint('ERROR: invalid configuration file')
        sys.exit(1)

    i = 0
    while True:
        i += 1
        env = os.environ.get(f'PUBSUB_PROJECT{i}')
        if not env:
            return

        project, *topics = env.split(',')
        if not topics:
            return

        yield (project, topics)


def print_config(config: list[tuple[str, list[str]]]) -> None:
    pprint('built pubsubc config:')
    for project, topics in config:
        pprint(f'project: {project}', 1)
        for spec in topics:
            topic, *subscriptions = spec.split(':')
            pprint(f'topic: {topic}', 2)
            for subscription in subscriptions:
                pprint(f'subscription: {subscription}', 3)


def create(project: str, topics: list[str]) -> None:
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()
    pprint(f'configuring project: {project}')

    for spec in topics:
        topic, *subscriptions = spec.split(':')

        pprint(f'- creating topic: {topic}')
        topic_name = publisher.topic_path(project, topic)
        publisher.create_topic(name=topic_name)

        for subscription in subscriptions:
            pprint(f'  - creating subscription: {subscription}')
            subscription_name = subscriber.subscription_path(
                project,
                subscription,
            )
            subscriber.create_subscription(
                name=subscription_name,
                topic=topic_name,
            )


def main() -> None:
    config = list(build_config())
    if not config:
        pprint(__doc__)
        print()
        pprint('ERROR: at least one topic must be provided')
        sys.exit(1)

    print_config(config)
    for project, topics in config:
        create(project, topics)


if __name__ == '__main__':
    main()
