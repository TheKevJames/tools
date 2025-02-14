# syntax=docker/dockerfile:1

# https://pkgs.alpinelinux.org/packages?name=&branch=v3.21&repo=&arch=&maintainer=
# renovate: datasource=repology depName=alpine_3_21/mysql-client versioning=loose
ARG MYSQLCLIENT_VERSION=11.4.4-r1
# renovate: datasource=repology depName=alpine_3_21/perl versioning=loose
ARG PERL_VERSION=5.40.1-r0
# renovate: datasource=repology depName=alpine_3_21/perl-doc versioning=loose
ARG PERLDOC_VERSION=5.40.1-r0


FROM alpine:3.21.3

ARG MYSQLCLIENT_VERSION
ARG PERL_VERSION
ARG PERLDOC_VERSION
RUN --mount=type=cache,target=/var/cache/apk \
    apk --update add \
        "mysql-client=${MYSQLCLIENT_VERSION}" \
        "perl=${PERL_VERSION}" \
        "perl-doc=${PERLDOC_VERSION}"

COPY root /

ENTRYPOINT [ "/usr/bin/perl", "/mysqltuner.pl" ]
