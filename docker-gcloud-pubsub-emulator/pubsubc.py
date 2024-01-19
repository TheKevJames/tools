#!/usr/bin/env python3
"""
pubsubc.

Usage:

    export PUBSUB_PROJECT1=project,topic1,topic2:subscription1,...
    export PUBSUB_PROJECT2=...
    ./pubsubc.py

At least $PUBSUB_PROJECT1 must be set, and it must have at least the project
and one topic listed. Topics may have any number of subscription, each
separated by a colon.

To run against an emulator, use:

    export PUBSUB_EMULATOR_HOST=localhost:8681

Credit:

    This script was originally ported from: https://github.com/prep/pubsubc
"""
import os
import sys
from collections.abc import Iterator

from google.cloud import pubsub_v1


def pprint(x: str, levels: int = 0) -> None:
    indent = ' ' * ((levels * 2) + 1)
    print(f'[pubsubc]{indent}{x}')


def build_config() -> Iterator[tuple[str, list[str]]]:
    i = 0
    while True:
        i += 1
        env = os.environ.get(f'PUBSUB_PROJECT{i}')
        if not env:
            if i == 1:
                pprint(__doc__)
                print()
                pprint('ERROR: $PUBSUB_PROJECT1 was not set')
                sys.exit(1)
            return

        project, *topics = env.split(',')
        if not topics:
            pprint(__doc__)
            print()
            pprint(f'ERROR: $PUBSUB_PROJECT{i} had no defined topic')
            sys.exit(1)

        yield (project, topics)


def print_config(config: list[tuple[str, list[str]]]) -> None:
    pprint('Built pubsubc config:')
    for project, topics in config:
        pprint(f'Project: {project}', 1)
        for spec in topics:
            topic, *subscriptions = spec.split(':')
            pprint(f'Topic: {topic}', 2)
            for subscription in subscriptions:
                pprint(f'Subscription: {subscription}', 3)


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
    print_config(config)
    for project, topics in config:
        create(project, topics)


if __name__ == '__main__':
    main()
