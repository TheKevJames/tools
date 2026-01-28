# syntax=docker/dockerfile:1
FROM alpine:3.23.3

# TODO: figure out how to properly pin these versions and have renovate update them
RUN --mount=type=cache,target=/var/cache/apk \
    apk add --no-progress \
        "bc" \
        "mariadb" \
        "mariadb-client" \
        "ncurses" \
        "socat"

COPY root /

ENV TERM=rxvt

ENTRYPOINT [ "/tuning-primer-wrapper.sh" ]
