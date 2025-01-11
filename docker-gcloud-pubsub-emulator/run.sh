#!/bin/sh
# Start the PubSub client in the background. It will poll for an open PubSub
# emulator port and create its topics and subscriptions when it's up.
#
# After it's done, port 8682 will be open to facilitate the wait-for and
# wait-for-it scripts.
(
    echo "Waiting for emulator..."
    TIMEOUT_OPTION=""
    if [ ! -z "$PUBSUB_EMULATOR_WAIT_TIMEOUT" ]; then
        TIMEOUT_OPTION="-t $PUBSUB_EMULATOR_WAIT_TIMEOUT"
    fi
    /usr/bin/wait-for localhost:8681 $TIMEOUT_OPTION -- env PUBSUB_EMULATOR_HOST=localhost:8681 /usr/bin/pubsubc
    echo "[run.sh] Done building projects/topics/subscriptions! Opening readiness port..."
    nc -lkp 8682
) &

# Start the PubSub emulator in the foreground.
gcloud beta emulators pubsub start --host-port=0.0.0.0:8681 "$@"
