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

from google.cloud import pubsub_v1  # type: ignore[attr-defined]


def create(project: str, topics: list[str]) -> None:
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()
    print(f'configuring project: {project}')

    for spec in topics:
        topic, *subscriptions = spec.split(':')

        print(f'- creating topic: {topic}')
        topic_name = publisher.topic_path(project, topic)
        publisher.create_topic(name=topic_name)

        for subscription in subscriptions:
            print(f'  - creating subscription: {subscription}')
            subscription_name = subscriber.subscription_path(
                project,
                subscription,
            )

            url = os.environ.get(f'PUBSUB_PUSHENDPOINT_{subscription_name}')
            if url:
                print(f'    setting push endpoint: {url}')
                config = pubsub_v1.types.PushConfig(push_endpoint=url)
            else:
                config = None

            subscriber.create_subscription(
                name=subscription_name,
                topic=topic_name,
                push_config=config,
            )


def main() -> None:
    i = 0
    while True:
        i += 1
        env = os.environ.get(f'PUBSUB_PROJECT{i}')
        if not env:
            if i == 1:
                print(__doc__)
                print()
                print('ERROR: $PUBSUB_PROJECT1 was not set')
                sys.exit(1)
            return

        project, *topics = env.split(',')
        if not topics:
            print(__doc__)
            print()
            print(f'ERROR: $PUBSUB_PROJECT{i} had no defined topic')
            sys.exit(1)

        create(project, topics)


if __name__ == '__main__':
    main()
