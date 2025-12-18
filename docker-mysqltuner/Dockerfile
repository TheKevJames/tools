# syntax=docker/dockerfile:1
FROM alpine:3.23.2

# TODO: figure out how to properly pin these versions and have renovate update them
RUN --mount=type=cache,target=/var/cache/apk \
    apk --update add \
        "mariadb-client" \
        "perl" \
        "perl-doc"

COPY root /

ENTRYPOINT [ "/usr/bin/perl", "/mysqltuner.pl" ]
