# syntax=docker/dockerfile:1

# renovate: datasource=repology depName=alpine_3_19/mysql-client versioning=loose
ARG MYSQLCLIENT_VERSION=10.11.6-r0
# renovate: datasource=repology depName=alpine_3_19/perl versioning=loose
ARG PERL_VERSION=5.38.2-r0
# renovate: datasource=repology depName=alpine_3_19/perl-doc versioning=loose
ARG PERLDOC_VERSION=5.38.2-r0


FROM alpine:3.19.1

ARG MYSQLCLIENT_VERSION
RUN --mount=type=cache,target=/var/cache/apk \
    apk --update add \
        "mysql-client=${MYSQLCLIENT_VERSION}" \
        "perl=${PERL_VERSION}" \
        "perl-doc=${PERLDOC_VERSION}"

COPY root /

ENTRYPOINT [ "/usr/bin/perl", "/mysqltuner.pl" ]
